import { NextResponse } from "next/server";

import { clientKey, rateLimit } from "@/lib/ratelimit";
import { cardSpecSchema, canonicalSpec, type CardSpec } from "@/lib/spec";
import { WorkerError, callWorker } from "@/lib/worker";

export const runtime = "nodejs";

const MAX_BODY = 8 * 1024;
// Renders per IP per minute. A person typing hits maybe twenty; the number is
// configurable because it exists to protect one worker machine, and how much
// that machine can take is a deployment fact, not a source code fact.
const RATE = Number(process.env.RATE_RENDER ?? 60);

/**
 * In process memo, keyed by the canonical spec.
 *
 * The editor renders on every keystroke, and users type the same thing twice
 * constantly: undo, retype, flip a switch and flip it back. Holding the last
 * few hundred answers turns those into a free round trip and keeps the single
 * worker machine from doing the same job twice.
 */
const MEMO = new Map<string, unknown>();
const MEMO_MAX = 400;

function remember(key: string, value: unknown) {
  if (MEMO.size >= MEMO_MAX) MEMO.delete(MEMO.keys().next().value as string);
  MEMO.set(key, value);
}

export async function POST(request: Request) {
  const limit = rateLimit(`render:${clientKey(request)}`, RATE);
  if (!limit.ok) {
    return NextResponse.json(
      { detail: "Zu viele Anfragen. Warte einen Moment." },
      { status: 429, headers: { "Retry-After": String(limit.retryAfter) } },
    );
  }

  const raw = await request.text();
  if (raw.length > MAX_BODY) {
    return NextResponse.json({ detail: "Spec zu gross" }, { status: 413 });
  }

  let spec: CardSpec;
  try {
    spec = cardSpecSchema.parse(JSON.parse(raw));
  } catch (error) {
    return NextResponse.json(
      { detail: "Ungueltige Spec", error: String(error) },
      { status: 422 },
    );
  }

  const key = canonicalSpec(spec);
  const hit = MEMO.get(key);
  if (hit) {
    return NextResponse.json(hit, { headers: { "x-cache": "hit" } });
  }

  try {
    const response = await callWorker("/render", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: key,
    });
    const payload = await response.json();
    remember(key, payload);
    return NextResponse.json(payload, {
      headers: {
        "x-cache": "miss",
        // the spec fully determines the answer, so it never goes stale
        "Cache-Control": "private, max-age=31536000, immutable",
      },
    });
  } catch (error) {
    if (error instanceof WorkerError) {
      return NextResponse.json(error.payload, { status: error.status });
    }
    return NextResponse.json(
      { detail: "Der Worker antwortet nicht." },
      { status: 502 },
    );
  }
}

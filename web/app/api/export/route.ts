import { NextResponse } from "next/server";

import { clientKey, rateLimit } from "@/lib/ratelimit";
import { cardSpecSchema, canonicalSpec } from "@/lib/spec";
import { WorkerError, callWorker } from "@/lib/worker";

export const runtime = "nodejs";

const MAX_BODY = 8 * 1024;
// Exports per IP per minute. A mesh costs several times a render, so this one
// is tighter. Same reasoning as RATE_RENDER: a deployment fact.
const RATE = Number(process.env.RATE_EXPORT ?? 10);
const FORMATS = new Set(["3mf", "stl-base", "stl-top", "svg"]);

export async function POST(request: Request) {
  const limit = rateLimit(`export:${clientKey(request)}`, RATE);
  if (!limit.ok) {
    return NextResponse.json(
      { detail: "Zu viele Downloads. Warte einen Moment." },
      { status: 429, headers: { "Retry-After": String(limit.retryAfter) } },
    );
  }

  const raw = await request.text();
  if (raw.length > MAX_BODY) {
    return NextResponse.json({ detail: "Spec zu gross" }, { status: 413 });
  }

  let body: { spec: unknown; format?: string };
  try {
    body = JSON.parse(raw);
  } catch {
    return NextResponse.json({ detail: "Kein gueltiges JSON" }, { status: 400 });
  }

  const format = body.format ?? "3mf";
  if (!FORMATS.has(format)) {
    return NextResponse.json({ detail: `Unbekanntes Format: ${format}` }, { status: 422 });
  }

  const parsed = cardSpecSchema.safeParse(body.spec);
  if (!parsed.success) {
    return NextResponse.json(
      { detail: "Ungueltige Spec", error: parsed.error.message },
      { status: 422 },
    );
  }

  try {
    const response = await callWorker("/export", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: `{"spec":${canonicalSpec(parsed.data)},"format":"${format}"}`,
      timeoutMs: 40_000,
    });

    // stream it straight through: a 3MF is a hundred kilobytes and there is
    // nothing for this hop to add
    return new NextResponse(response.body, {
      headers: {
        "content-type":
          response.headers.get("content-type") ?? "application/octet-stream",
        "content-disposition":
          response.headers.get("content-disposition") ?? "attachment",
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

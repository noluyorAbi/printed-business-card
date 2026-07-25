import "server-only";

/**
 * A per instance sliding window.
 *
 * Deliberately not a shared store. The thing worth protecting is the single
 * worker machine, and a per instance cap already bounds the damage while
 * costing nothing to run and nothing to operate. If this ever needs to be
 * exact, it moves to Vercel KV, and the call sites do not change.
 */

type Window = { count: number; resetAt: number };

const buckets = new Map<string, Window>();

export type Limit = { ok: boolean; retryAfter: number };

export function rateLimit(key: string, max: number, windowMs = 60_000): Limit {
  const now = Date.now();
  const found = buckets.get(key);

  if (!found || now >= found.resetAt) {
    buckets.set(key, { count: 1, resetAt: now + windowMs });
    // opportunistic sweep, so an instance that lives for days does not grow
    if (buckets.size > 5000) {
      for (const [k, v] of buckets) if (now >= v.resetAt) buckets.delete(k);
    }
    return { ok: true, retryAfter: 0 };
  }

  found.count += 1;
  if (found.count > max) {
    return { ok: false, retryAfter: Math.ceil((found.resetAt - now) / 1000) };
  }
  return { ok: true, retryAfter: 0 };
}

export function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  return forwarded?.split(",")[0].trim() || "unknown";
}

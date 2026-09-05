/** In-memory fixed-window rate limiter for server actions.

Keyed by IP or username.  Per-process only (acceptable for a single
Next.js server instance; multiple processes would each keep their own
counters — same trade-off documented in backend/app/core/ratelimit.py).
*/

interface RateBucket {
  windowStart: number
  count: number
}

const buckets = new Map<string, RateBucket>()

const WINDOW_MS = 60_000 // 1 minute
const MAX_ATTEMPTS = 10 // per window

/** Evict stale windows periodically to prevent unbounded memory growth. */
setInterval(() => {
  const now = Date.now()
  for (const [key, bucket] of buckets) {
    if (now - bucket.windowStart >= WINDOW_MS * 2) {
      buckets.delete(key)
    }
  }
}, WINDOW_MS * 5)

/**
 * Returns true if the request is allowed, false if rate-limited.
 * `retryAfterMs` is set when denied.
 */
export function checkRateLimit(
  key: string,
  limit: number = MAX_ATTEMPTS,
  windowMs: number = WINDOW_MS,
): { allowed: boolean; retryAfterMs: number } {
  const now = Date.now()
  const bucket = buckets.get(key)

  if (!bucket || now - bucket.windowStart >= windowMs) {
    buckets.set(key, { windowStart: now, count: 1 })
    return { allowed: true, retryAfterMs: 0 }
  }

  if (bucket.count >= limit) {
    const retryAfterMs = windowMs - (now - bucket.windowStart)
    return { allowed: false, retryAfterMs }
  }

  bucket.count++
  return { allowed: true, retryAfterMs: 0 }
}

/** Reset a key (e.g. after a successful login). */
export function resetRateLimit(key: string): void {
  buckets.delete(key)
}

/**
 * In-memory rate limiter: max N operations per time window.
 */

export interface RateLimiterOptions {
  max: number;
  windowMs: number;
}

export interface RateLimiter {
  tryAcquire(): boolean;
}

export function createRateLimiter(opts: RateLimiterOptions): RateLimiter {
  const { max, windowMs } = opts;
  let timestamps: number[] = [];

  function prune(): void {
    const now = Date.now();
    timestamps = timestamps.filter((t) => now - t < windowMs);
  }

  return {
    tryAcquire(): boolean {
      prune();
      if (timestamps.length >= max) return false;
      timestamps.push(Date.now());
      return true;
    },
  };
}

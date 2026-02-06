/**
 * WhatsApp send throttling: token bucket (per minute + per hour), jitter delay, circuit breaker.
 */

import { env } from "./env.js";
import { logger } from "./logger.js";

// --- Token bucket (two buckets: per minute, per hour) ---
const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;

interface Bucket {
  tokens: number;
  capacity: number;
  refillRate: number; // tokens per ms
  lastRefillAt: number;
}

function refill(b: Bucket, now: number): void {
  const elapsed = now - b.lastRefillAt;
  b.tokens = Math.min(b.capacity, b.tokens + elapsed * b.refillRate);
  b.lastRefillAt = now;
}

const bucketMinute: Bucket = {
  tokens: env.WA_RATE_PER_MINUTE,
  capacity: env.WA_RATE_PER_MINUTE,
  refillRate: env.WA_RATE_PER_MINUTE / MINUTE_MS,
  lastRefillAt: Date.now(),
};

const bucketHour: Bucket = {
  tokens: env.WA_RATE_PER_HOUR,
  capacity: env.WA_RATE_PER_HOUR,
  refillRate: env.WA_RATE_PER_HOUR / HOUR_MS,
  lastRefillAt: Date.now(),
};

/** Consume one token from both buckets. Returns true if both had capacity. */
export function tryConsumeSendToken(): boolean {
  const now = Date.now();
  refill(bucketMinute, now);
  refill(bucketHour, now);
  if (bucketMinute.tokens >= 1 && bucketHour.tokens >= 1) {
    bucketMinute.tokens -= 1;
    bucketHour.tokens -= 1;
    return true;
  }
  return false;
}

/** Random delay between WA_MIN_DELAY_MS and WA_MAX_DELAY_MS (inclusive). */
export function getJitterDelayMs(): number {
  const min = Math.max(0, env.WA_MIN_DELAY_MS);
  const max = Math.max(min, env.WA_MAX_DELAY_MS);
  return min + Math.floor(Math.random() * (max - min + 1));
}

/** Delay helper. */
export function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// --- Circuit breaker ---
type CircuitState = "closed" | "open" | "half_open";

let circuitState: CircuitState = "closed";
let failureCount = 0;
let openUntil = 0;

export function circuitCanSend(): boolean {
  const now = Date.now();
  if (circuitState === "closed") return true;
  if (circuitState === "open") {
    if (now < openUntil) return false;
    circuitState = "half_open";
    logger.info("Circuit breaker: half-open (allowing one trial send)");
    return true;
  }
  // half_open: allow the one trial
  return true;
}

export function circuitRecordSuccess(): void {
  if (circuitState === "half_open") {
    circuitState = "closed";
    failureCount = 0;
    logger.info("Circuit breaker: closed (trial send succeeded)");
  } else if (circuitState === "closed") {
    failureCount = 0;
  }
}

export function circuitRecordFailure(): void {
  if (circuitState === "half_open") {
    circuitState = "open";
    openUntil = Date.now() + env.WA_CIRCUIT_OPEN_MS;
    logger.warn("Circuit breaker: open (trial send failed). Sends paused.", {
      openMinutes: env.WA_CIRCUIT_OPEN_MS / 60_000,
    });
    return;
  }
  if (circuitState === "closed") {
    failureCount += 1;
    if (failureCount >= env.WA_CIRCUIT_FAILURE_THRESHOLD) {
      circuitState = "open";
      openUntil = Date.now() + env.WA_CIRCUIT_OPEN_MS;
      logger.warn("Circuit breaker: open after repeated failures. Sends paused.", {
        failureCount,
        openMinutes: env.WA_CIRCUIT_OPEN_MS / 60_000,
      });
    }
  }
}

export function getCircuitState(): { state: CircuitState; failureCount: number; openUntil: number } {
  return { state: circuitState, failureCount, openUntil };
}

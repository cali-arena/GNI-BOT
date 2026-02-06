/**
 * Redis-backed rate limit counters (per-channel and per-group). Survives restarts.
 * Keys: wa_rate:channel:{channel}:min|hr:{ts}, wa_rate:group:{groupJid}:min|hr:{ts}
 * When REDIS_URL is empty, falls back to in-memory (no persistence).
 */

import Redis from "ioredis";
import { env } from "./env.js";
import { logger } from "./logger.js";

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;

let redis: Redis | null = null;

function getRedis(): Redis | null {
  if (redis) return redis;
  const url = env.REDIS_URL?.trim();
  if (!url) return null;
  try {
    redis = new Redis(url, { maxRetriesPerRequest: 2 });
    redis.on("error", (e) => logger.warn("Redis error", { err: String(e) }));
    return redis;
  } catch (e) {
    logger.warn("Redis connect failed, using in-memory rate limit", { err: String(e) });
    return null;
  }
}

function minuteKey(prefix: string, id: string): string {
  const now = new Date();
  const ts = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}-${String(now.getUTCHours()).padStart(2, "0")}-${String(now.getUTCMinutes()).padStart(2, "0")}`;
  return `wa_rate:${prefix}:${id}:min:${ts}`;
}

function hourKey(prefix: string, id: string): string {
  const now = new Date();
  const ts = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}-${String(now.getUTCHours()).padStart(2, "0")}`;
  return `wa_rate:${prefix}:${id}:hr:${ts}`;
}

/** Normalize group JID for Redis key (safe string). */
function safeKeyId(jid: string): string {
  return jid.replace(/[^a-z0-9._-]/gi, "_");
}

/**
 * Try to consume `count` send tokens for both channel and group. Returns true if both
 * channel and group would stay under per-minute and per-hour limits (and increments).
 * When Redis is unavailable, returns { allowed: true, redisUsed: false } (caller uses in-memory).
 */
export async function tryConsumeSendTokenRedis(
  channel: string,
  groupJid: string,
  count: number,
): Promise<{ allowed: boolean; redisUsed: boolean }> {
  const r = getRedis();
  if (!r) return { allowed: true, redisUsed: false };
  if (count <= 0) return { allowed: true, redisUsed: true };

  const ch = safeKeyId(channel);
  const gr = safeKeyId(groupJid);
  const keys = [
    minuteKey("channel", ch),
    hourKey("channel", ch),
    minuteKey("group", gr),
    hourKey("group", gr),
  ];
  const perMin = env.WA_RATE_PER_MINUTE;
  const perHour = env.WA_RATE_PER_HOUR;

  try {
    const pipe = r.pipeline();
    keys.forEach((k) => pipe.get(k));
    const results = await pipe.exec();
    if (!results) return { allowed: true, redisUsed: true };

    const counts = results.map(([err, val]) => (err ? 0 : parseInt(String(val || "0"), 10)));
    const [chMin, chHr, grMin, grHr] = counts;
    if (chMin + count > perMin || chHr + count > perHour || grMin + count > perMin || grHr + count > perHour) {
      return { allowed: false, redisUsed: true };
    }

    const incrPipe = r.pipeline();
    incrPipe.incrby(keys[0]!, count);
    incrPipe.expire(keys[0]!, 120);
    incrPipe.incrby(keys[1]!, count);
    incrPipe.expire(keys[1]!, 7200);
    incrPipe.incrby(keys[2]!, count);
    incrPipe.expire(keys[2]!, 120);
    incrPipe.incrby(keys[3]!, count);
    incrPipe.expire(keys[3]!, 7200);
    await incrPipe.exec();
    return { allowed: true, redisUsed: true };
  } catch (e) {
    logger.warn("Redis rate limit check failed, allowing send", { err: String(e) });
    return { allowed: true, redisUsed: true };
  }
}

export async function closeRedis(): Promise<void> {
  if (redis) {
    await redis.quit();
    redis = null;
  }
}

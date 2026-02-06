/**
 * Environment configuration. All config via env vars (no hardcoded numbers/groups).
 */

function getEnv(key: string): string {
  const v = process.env[key];
  if (v === undefined || v === "") {
    throw new Error(`Missing required env: ${key}`);
  }
  return v;
}

function getEnvOptional(key: string, defaultValue: string): string {
  return process.env[key] ?? defaultValue;
}

export const env = {
  /** Port for internal HTTP server (receive send requests from API worker) */
  PORT: parseInt(getEnvOptional("PORT", "3000"), 10),

  /** Auth/session folder for Baileys (persist across restarts). Default /data/wa-auth in container. */
  AUTH_FOLDER: getEnvOptional("AUTH_FOLDER", "/data/wa-auth"),

  /** Target group: JID override (if set, used directly). Otherwise resolved by name. */
  WA_TARGET_GROUP_JID: process.env.WA_TARGET_GROUP_JID?.trim() ?? process.env.WHATSAPP_GROUP_JID?.trim() ?? "",
  /** Target group name for resolution when WA_TARGET_GROUP_JID is empty (exact match). */
  WA_TARGET_GROUP_NAME: process.env.WA_TARGET_GROUP_NAME?.trim() ?? process.env.WHATSAPP_GROUP_NAME?.trim() ?? "",
  /** Optional: only allow send if this number is a participant admin in the target group. */
  WA_ADMIN_NUMBER: process.env.WA_ADMIN_NUMBER?.trim() ?? "",

  /** Rate limit: max messages per window (default 30 per minute) */
  RATE_LIMIT_MAX: parseInt(getEnvOptional("RATE_LIMIT_MAX", "30"), 10),
  RATE_LIMIT_WINDOW_MS: parseInt(getEnvOptional("RATE_LIMIT_WINDOW_MS", "60000"), 10),

  /** Retries for send failures */
  SEND_MAX_RETRIES: parseInt(getEnvOptional("SEND_MAX_RETRIES", "3"), 10),

  /** Max characters per WhatsApp message; longer messages are split (header line preserved). */
  WA_MAX_CHARS: parseInt(getEnvOptional("WA_MAX_CHARS", "3500"), 10),

  /** WhatsApp send rate: token bucket limits (enforced inside bot). */
  WA_RATE_PER_MINUTE: parseInt(getEnvOptional("WA_RATE_PER_MINUTE", "3"), 10),
  WA_RATE_PER_HOUR: parseInt(getEnvOptional("WA_RATE_PER_HOUR", "20"), 10),
  /** Jitter delay between consecutive sends (ms). */
  WA_MIN_DELAY_MS: parseInt(getEnvOptional("WA_MIN_DELAY_MS", "800"), 10),
  WA_MAX_DELAY_MS: parseInt(getEnvOptional("WA_MAX_DELAY_MS", "2500"), 10),

  /** Circuit breaker: open after this many consecutive send failures. */
  WA_CIRCUIT_FAILURE_THRESHOLD: parseInt(getEnvOptional("WA_CIRCUIT_FAILURE_THRESHOLD", "5"), 10),
  /** Circuit breaker: keep open for this many ms (e.g. 5 min = 300000). */
  WA_CIRCUIT_OPEN_MS: parseInt(getEnvOptional("WA_CIRCUIT_OPEN_MS", "300000"), 10),

  /** Redis URL for rate limit counters (persisted). Empty = fallback to in-memory. */
  REDIS_URL: getEnvOptional("REDIS_URL", ""),

  /** Reconnect backoff: base ms, cap ms. */
  WA_RECONNECT_BACKOFF_BASE_MS: parseInt(getEnvOptional("WA_RECONNECT_BACKOFF_BASE_MS", "2000"), 10),
  WA_RECONNECT_BACKOFF_CAP_MS: parseInt(getEnvOptional("WA_RECONNECT_BACKOFF_CAP_MS", "60000"), 10),
} as const;

/** Target group config: optional JID override, optional name for resolve. */
export function getTargetGroupConfig(): { jid?: string; name?: string } {
  const jid = env.WA_TARGET_GROUP_JID || undefined;
  const name = env.WA_TARGET_GROUP_NAME || undefined;
  return { jid: jid || undefined, name: name || undefined };
}

/** Normalize phone to WhatsApp JID (e.g. +1XXXXXXXXXX -> 1XXXXXXXXXX@s.whatsapp.net). */
export function phoneToJid(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  return `${digits}@s.whatsapp.net`;
}

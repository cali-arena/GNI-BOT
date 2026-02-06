/**
 * WhatsApp Web connection via Baileys: QR-based session, persistent auth, send to target group with retries.
 */

import { Boom } from "@hapi/boom";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
  type WASocket,
} from "baileys";
import type { GroupMetadata } from "baileys";
import pino from "pino";
import { createRequire } from "module";
import { env, getTargetGroupConfig, phoneToJid } from "./env.js";
import { logger } from "./logger.js";
import { incDisconnects } from "./metrics.js";
import { tryConsumeSendTokenRedis } from "./rateLimitRedis.js";
import {
  circuitCanSend,
  circuitRecordFailure,
  circuitRecordSuccess,
  delay,
  getJitterDelayMs,
  tryConsumeSendToken,
} from "./sendThrottle.js";
import { getAuthFolder } from "./store.js";

const require = createRequire(import.meta.url);
const qrcodeTerminal = require("qrcode-terminal") as { generate: (value: string, opts?: { small?: boolean }) => void };

const baileysLogger = pino({ level: "silent" });

let sock: WASocket | null = null;
let resolveReady: (() => void) | null = null;
export const readyPromise = new Promise<void>((resolve) => {
  resolveReady = resolve;
});

// Current QR payload (when waiting for scan). Cleared when connection opens or TTL expired.
const WA_QR_TTL_MS = parseInt(process.env.WA_QR_TTL_MS ?? "60000", 10); // 60s default
let currentQr: string | null = null;
let qrExpiresAt: number = 0; // Unix ms; QR is invalid after this

// Connection state for /health
let connectionStatus: "connecting" | "connected" | "disconnected" = "connecting";
let lastDisconnectReason: string | null = null;
let lastDisconnectCode: number | null = null;
let disconnectCount = 0;
let reconnectAttempt = 0;

// Manual intervention: when true, session invalid (e.g. logged out), stop sending until QR re-scan
let needsRescan = false;

// Session state for /session (persists until process exit)
let loggedIn = false;
let meId: string | null = null;
let lastSeen: string | null = null;

// Resolved target group JID (set on startup when resolving by name)
let cachedTargetGroupJid: string | null = null;

// Last N error messages for /health (no secrets, no QR)
const MAX_LAST_ERRORS = 5;
const lastErrors: string[] = [];

function pushLastError(message: string): void {
  const safe = message.slice(0, 200).replace(/\s+/g, " ").trim();
  if (!safe) return;
  lastErrors.push(safe);
  if (lastErrors.length > MAX_LAST_ERRORS) lastErrors.shift();
}

/** Whether the socket is connected and ready to send. */
export function isReady(): boolean {
  return sock !== null;
}

/** Get the current socket (null if not connected). */
export function getSocket(): WASocket | null {
  return sock;
}

/** Current QR string if waiting for scan and not expired; null otherwise. Never log return value. */
export function getCurrentQr(): string | null {
  if (!currentQr) return null;
  if (Date.now() > qrExpiresAt) {
    currentQr = null;
    qrExpiresAt = 0;
    return null;
  }
  return currentQr;
}

/** Get QR expiry timestamp (ms) for API response. */
export function getQrExpiresAt(): number {
  return qrExpiresAt;
}

/** Health: status, connected, lastDisconnectReason, disconnectCount, needsRescan. */
export function getConnectionState(): {
  status: "ok" | "degraded" | "error";
  connected: boolean;
  lastDisconnectReason: string | null;
  lastDisconnectCode: number | null;
  disconnectCount: number;
  needsRescan: boolean;
} {
  const connected = connectionStatus === "connected";
  return {
    status: connected ? "ok" : connectionStatus === "connecting" ? "degraded" : "error",
    connected,
    lastDisconnectReason,
    lastDisconnectCode,
    disconnectCount,
    needsRescan,
  };
}

/** Health summary for /health: activeSessions (1 for single-session), lastErrors (no secrets). */
export function getHealthSummary(): { activeSessions: number; lastErrors: string[] } {
  const active = connectionStatus === "connected" ? 1 : 0;
  return { activeSessions: active, lastErrors: [...lastErrors] };
}

/** Session: loggedIn, meId, lastSeen, needsRescan. */
export function getSessionState(): {
  loggedIn: boolean;
  meId: string | null;
  lastSeen: string | null;
  needsRescan: boolean;
} {
  return { loggedIn, meId, lastSeen, needsRescan };
}

/** On startup: resolve target group by name and cache JID (when JID not set). */
export async function resolveAndCacheTargetGroup(wa: WASocket): Promise<void> {
  const { jid: envJid, name } = getTargetGroupConfig();
  if (envJid) {
    cachedTargetGroupJid = envJid.includes("@") ? envJid : `${envJid}@g.us`;
    logger.info("Target group from env JID", { jid: cachedTargetGroupJid });
    return;
  }
  if (!name) {
    logger.warn("No WA_TARGET_GROUP_JID or WA_TARGET_GROUP_NAME set; sending will fail until configured");
    return;
  }
  try {
    const groups = await wa.groupFetchAllParticipating();
    const list = Object.entries(groups).map(([, meta]) => meta as GroupMetadata);
    const found = list.find((g) => g.subject === name);
    if (found) {
      cachedTargetGroupJid = found.id;
      logger.info("Target group resolved by name", { name, jid: cachedTargetGroupJid });
    } else {
      const available = list.map((g) => g.subject ?? "(no name)").join(", ");
      logger.error(
        `Target group not found by name: "${name}". Available groups: ${available || "(none)"}`,
      );
    }
  } catch (e) {
    logger.error("Failed to resolve target group on startup", { name, err: String(e) });
  }
}

/** Fetch all groups for listing (--print-groups). */
export async function fetchAllGroupsList(wa: WASocket): Promise<{ name: string; jid: string }[]> {
  const groups = await wa.groupFetchAllParticipating();
  return Object.entries(groups).map(([, meta]) => {
    const g = meta as GroupMetadata;
    return { name: g.subject ?? "(no name)", jid: g.id };
  });
}

/** Resolve target group JID: use env JID, else cached, else fetch and find by exact name. */
async function resolveGroupJid(wa: WASocket): Promise<string> {
  const { jid: envJid, name } = getTargetGroupConfig();
  if (envJid) {
    return envJid.includes("@") ? envJid : `${envJid}@g.us`;
  }
  if (cachedTargetGroupJid) {
    return cachedTargetGroupJid;
  }
  if (name) {
    const groups = await wa.groupFetchAllParticipating();
    const list = Object.entries(groups).map(([, meta]) => meta as GroupMetadata);
    const found = list.find((g) => g.subject === name);
    if (found) {
      return found.id;
    }
    const available = list.map((g) => g.subject ?? "(no name)").join(", ");
    throw new Error(
      `Group not found by name: "${name}". Available groups: ${available || "(none)"}`,
    );
  }
  throw new Error("Set WA_TARGET_GROUP_JID or WA_TARGET_GROUP_NAME");
}

/** Best-effort: ensure bot is in group and WA_ADMIN_NUMBER is a participant admin. */
async function checkAdminGuard(wa: WASocket, groupJid: string): Promise<{ ok: boolean; error?: string }> {
  const adminNum = env.WA_ADMIN_NUMBER;
  if (!adminNum) return { ok: true };

  const me = meId ?? wa.user?.id;
  if (!me) return { ok: false, error: "Bot user id unknown" };

  let meta: GroupMetadata;
  try {
    meta = await wa.groupMetadata(groupJid);
  } catch (e) {
    return { ok: false, error: `Failed to fetch group metadata: ${(e as Error).message}` };
  }

  const participants = meta.participants ?? [];
  const botInGroup = participants.some((p) => p.id === me);
  if (!botInGroup) {
    return { ok: false, error: "Bot is not in the target group" };
  }

  const adminJid = phoneToJid(adminNum);
  const adminParticipant = participants.find((p) => p.id === adminJid);
  if (!adminParticipant) {
    return { ok: false, error: `WA_ADMIN_NUMBER (${adminNum}) is not a participant in the group` };
  }
  const isAdmin =
    adminParticipant.isAdmin === true ||
    adminParticipant.isSuperAdmin === true ||
    (adminParticipant as { admin?: string }).admin === "admin" ||
    (adminParticipant as { admin?: string }).admin === "superadmin";
  if (!isAdmin) {
    return { ok: false, error: `WA_ADMIN_NUMBER (${adminNum}) is not an admin in the group` };
  }
  return { ok: true };
}

/** Whether the error is transient (worth retrying). */
function isTransientError(e: unknown): boolean {
  const msg = e instanceof Error ? e.message : String(e);
  const code = (e as { code?: string })?.code;
  const statusCode = (e as { output?: { statusCode?: number } })?.output?.statusCode;
  if (statusCode != null) {
    if (statusCode === 408 || statusCode === 500 || statusCode === 502 || statusCode === 503) return true;
    if (statusCode >= 400 && statusCode < 500 && statusCode !== 408) return false;
  }
  if (code === "ECONNRESET" || code === "ETIMEDOUT" || code === "ECONNREFUSED" || code === "ENOTFOUND") return true;
  if (/timeout|network|temporarily|unavailable/i.test(msg)) return true;
  return false;
}

/** Exponential backoff delay with jitter (ms). */
function backoffDelayMs(attempt: number): number {
  const base = 1000;
  const cap = 30_000;
  const exponential = Math.min(cap, base * Math.pow(2, attempt - 1));
  const jitter = Math.floor(Math.random() * 501); // 0..500
  return exponential + jitter;
}

const DEFAULT_CHANNEL = "whatsapp_web";

/** Send one or more texts to the target group; returns message_ids and group_jid. */
export async function sendMessagesToGroup(
  texts: string[],
  channel: string = DEFAULT_CHANNEL,
): Promise<{
  ok: boolean;
  error?: string;
  message_ids?: string[];
  group_jid?: string;
}> {
  const wa = getSocket();
  if (!wa) {
    return { ok: false, error: "WhatsApp not connected" };
  }

  if (needsRescan) {
    return {
      ok: false,
      error: "Session invalid; manual intervention required. Scan QR (GET /qr) to re-link. See README.",
    };
  }

  if (!circuitCanSend()) {
    return { ok: false, error: "Circuit breaker open; send paused after repeated failures" };
  }

  // Resolve group first for Redis rate limit (per-channel + per-group)
  let groupJid: string;
  try {
    groupJid = await resolveGroupJid(wa);
  } catch (e) {
    return { ok: false, error: (e as Error).message };
  }

  const redisResult = await tryConsumeSendTokenRedis(channel, groupJid, texts.length);
  if (!redisResult.allowed) {
    return { ok: false, error: "Rate limit exceeded" };
  }
  if (!redisResult.redisUsed) {
    for (let i = 0; i < texts.length; i++) {
      if (!tryConsumeSendToken()) {
        return { ok: false, error: "Rate limit exceeded" };
      }
    }
  }

  const maxRetries = env.SEND_MAX_RETRIES;
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const guard = await checkAdminGuard(wa, groupJid);
      if (!guard.ok) {
        logger.warn("Admin guard rejected send", { error: guard.error });
        return { ok: false, error: guard.error };
      }
      const messageIds: string[] = [];
      for (let i = 0; i < texts.length; i++) {
        if (i > 0) await delay(getJitterDelayMs());
        const sent = await wa.sendMessage(groupJid, { text: texts[i]! });
        const id = sent?.key?.id;
        if (id) messageIds.push(id);
      }
      circuitRecordSuccess();
      logger.info("Messages sent to group", { groupJid, count: texts.length, messageIds });
      return { ok: true, message_ids: messageIds, group_jid: groupJid };
    } catch (e) {
      lastError = e instanceof Error ? e : new Error(String(e));
      const transient = isTransientError(e);
      logger.warn("Send attempt failed", {
        attempt,
        maxRetries,
        error: lastError.message,
        transient,
      });
      if (!transient) {
        circuitRecordFailure();
        return { ok: false, error: lastError.message };
      }
      if (attempt < maxRetries) {
        const waitMs = backoffDelayMs(attempt);
        logger.debug("Retrying after backoff", { waitMs });
        await delay(waitMs);
      }
    }
  }

  circuitRecordFailure();
  const errMsg = lastError?.message ?? "Unknown error";
  pushLastError(`send_failed: ${errMsg}`);
  logger.error("Send failed after retries", { maxRetries, error: errMsg });
  return { ok: false, error: errMsg };
}

/** Start WhatsApp connection (QR-based session). */
export async function startWa(): Promise<void> {
  const authFolder = getAuthFolder();
  const { state, saveCreds } = await useMultiFileAuthState(authFolder);

  const { version } = await fetchLatestBaileysVersion();
  logger.info("Connecting to WhatsApp", { version: version.join(".") });

  const socket = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: state.keys,
    },
    logger: baileysLogger,
  });

  sock = socket;

  socket.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      currentQr = qr;
      qrExpiresAt = Date.now() + WA_QR_TTL_MS;
      logger.info("Waiting for QR…");
      try {
        qrcodeTerminal.generate(qr, { small: true });
      } catch (e) {
        logger.warn("Could not print QR to terminal", { err: String(e) });
      }
    } else {
      currentQr = null;
      qrExpiresAt = 0;
    }

    if (connection === "open") {
      connectionStatus = "connected";
      currentQr = null;
      needsRescan = false;
      reconnectAttempt = 0;
      loggedIn = true;
      meId = socket.user?.id ?? null;
      lastSeen = new Date().toISOString();
      logger.info("WhatsApp connected", { meId });
      resolveAndCacheTargetGroup(socket).finally(() => {
        if (resolveReady) {
          resolveReady();
          resolveReady = null;
        }
      });
    }

    if (connection === "close") {
      sock = null;
      connectionStatus = "disconnected";
      const err = lastDisconnect?.error as Boom | undefined;
      const statusCode = err?.output?.statusCode ?? null;
      lastDisconnectCode = statusCode;
      lastDisconnectReason = err?.message ?? (statusCode != null ? String(statusCode) : "unknown");
      disconnectCount += 1;
      incDisconnects();
      pushLastError(`disconnect: ${lastDisconnectReason}`);
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      if (statusCode === DisconnectReason.loggedOut) {
        loggedIn = false;
        meId = null;
        needsRescan = true;
        logger.error(
          "Session invalid (logged out). MANUAL INTERVENTION: Scan QR (GET /qr) to re-link. Sends disabled until re-scan.",
        );
      } else {
        logger.warn("Connection closed", {
          statusCode,
          lastDisconnectReason,
          shouldReconnect,
          disconnectCount,
        });
      }
      if (shouldReconnect) {
        connectionStatus = "connecting";
        const base = env.WA_RECONNECT_BACKOFF_BASE_MS;
        const cap = env.WA_RECONNECT_BACKOFF_CAP_MS;
        const backoffMs = Math.min(cap, base * Math.pow(2, reconnectAttempt));
        reconnectAttempt += 1;
        logger.info("Reconnecting with backoff", { backoffMs, attempt: reconnectAttempt });
        setTimeout(() => startWa(), backoffMs);
      }
    }
  });

  socket.ev.on("creds.update", saveCreds);
}

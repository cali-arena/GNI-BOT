/**
 * Internal HTTP server: receive POST /send with validation, idempotency, chunking.
 * Structured logs with correlation_id, item_id, template, channel, attempt, error_code.
 *
 * POST /send body: { text, idempotency_key?, meta? }
 * Response: { ok: true, message_ids, group_jid } or { ok: false, error }
 */

import { createServer, type IncomingMessage, type ServerResponse } from "http";
import { randomUUID } from "crypto";
import { env } from "./env.js";
import { logger, withContext, type LogContext } from "./logger.js";
import { getMetrics, incRateLimited, incSendsFailed, incSendsSuccess } from "./metrics.js";
import { createRateLimiter } from "./rateLimit.js";
import { ensureUserSessionFolder } from "./store.js";
import {
  getConnectionState,
  getCurrentQr,
  getHealthSummary,
  getQrExpiresAt,
  getSessionState,
  sendMessagesToGroup,
} from "./wa.js";

const rateLimiter = createRateLimiter({
  max: env.RATE_LIMIT_MAX,
  windowMs: env.RATE_LIMIT_WINDOW_MS,
});

const IDEMPOTENCY_TTL_MS = 24 * 60 * 60 * 1000; // 24h
const idempotencyStore = new Map<
  string,
  { message_ids: string[]; group_jid: string; createdAt: number }
>();

function pruneIdempotencyStore(): void {
  const now = Date.now();
  for (const [key, entry] of idempotencyStore.entries()) {
    if (now - entry.createdAt > IDEMPOTENCY_TTL_MS) idempotencyStore.delete(key);
  }
}

/** Split text into chunks of at most maxChars, preserving first line as header on each chunk. */
function splitIntoChunks(text: string, maxChars: number): string[] {
  if (text.length <= maxChars) return [text];
  const newline = text.indexOf("\n");
  const hasHeader = newline >= 0;
  const header = hasHeader ? text.slice(0, newline + 1) : "";
  const rest = hasHeader ? text.slice(newline + 1) : text;
  const chunkSize = maxChars - header.length;
  if (chunkSize <= 0) {
    // header alone exceeds max; split by maxChars only
    const out: string[] = [];
    for (let i = 0; i < text.length; i += maxChars) {
      out.push(text.slice(i, i + maxChars));
    }
    return out;
  }
  const chunks: string[] = [];
  for (let i = 0; i < rest.length; i += chunkSize) {
    chunks.push(header + rest.slice(i, i + chunkSize));
  }
  return chunks;
}

interface SendBody {
  text?: string;
  idempotency_key?: string;
  meta?: {
    source?: string;
    url?: string;
    item_id?: number | string;
    template?: string;
    channel?: string;
  };
}

async function parseBody(req: IncomingMessage): Promise<SendBody> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw.trim()) return {};
  try {
    return JSON.parse(raw) as SendBody;
  } catch {
    return { text: raw };
  }
}

function getCorrelationId(req: IncomingMessage, meta?: SendBody["meta"]): string {
  const header = req.headers["x-correlation-id"];
  const id = Array.isArray(header) ? header[0] : header;
  if (id && typeof id === "string") return id.trim();
  return meta?.item_id != null ? `item-${meta.item_id}` : randomUUID();
}

async function handleSend(req: IncomingMessage, res: ServerResponse): Promise<void> {
  if (req.method !== "POST") {
    sendJson(res, 405, { ok: false, error: "Method not allowed" });
    return;
  }

  if (!rateLimiter.tryAcquire()) {
    incRateLimited();
    sendJson(res, 429, { ok: false, error: "Rate limit exceeded" });
    logger.warn("Rate limit exceeded");
    return;
  }

  let body: SendBody;
  try {
    body = await parseBody(req);
  } catch {
    sendJson(res, 400, { ok: false, error: "Invalid body" });
    return;
  }

  const meta = body?.meta;
  const correlationId = getCorrelationId(req, meta);
  const logCtx: LogContext = {
    correlation_id: correlationId,
    item_id: meta?.item_id,
    template: meta?.template,
    channel: meta?.channel ?? "whatsapp_web",
    attempt: 1,
  };
  const log = withContext(logCtx);

  const text = typeof body?.text === "string" ? body.text.trim() : "";
  if (!text) {
    log.warn("Missing or empty text", { error_code: "MISSING_TEXT" });
    sendJson(res, 400, { ok: false, error: "Missing or empty text" });
    return;
  }

  const idempotencyKey = typeof body?.idempotency_key === "string" ? body.idempotency_key.trim() : undefined;
  if (idempotencyKey) {
    pruneIdempotencyStore();
    const cached = idempotencyStore.get(idempotencyKey);
    if (cached && Date.now() - cached.createdAt < IDEMPOTENCY_TTL_MS) {
      log.info("Duplicate idempotency_key, skipping send");
      sendJson(res, 200, {
        ok: true,
        message_ids: cached.message_ids,
        group_jid: cached.group_jid,
      });
      return;
    }
  }

  const maxChars = Math.max(100, env.WA_MAX_CHARS);
  const textChunks = splitIntoChunks(text, maxChars);
  const channel = meta?.channel ?? "whatsapp_web";

  const result = await sendMessagesToGroup(textChunks, channel);
  if (!result.ok) {
    const status =
      result.error === "Rate limit exceeded"
        ? 429
        : result.error?.includes("Circuit breaker")
          ? 503
          : result.error?.includes("Session invalid")
            ? 503
            : 503;
    if (status === 429) incRateLimited();
    else incSendsFailed();
    log.warn("Send failed", { error_code: status === 429 ? "RATE_LIMITED" : "SEND_FAILED", error: result.error });
    sendJson(res, status, { ok: false, error: result.error });
    return;
  }

  incSendsSuccess();
  if (idempotencyKey && result.message_ids && result.group_jid) {
    idempotencyStore.set(idempotencyKey, {
      message_ids: result.message_ids,
      group_jid: result.group_jid,
      createdAt: Date.now(),
    });
  }

  log.info("Send success", { message_count: result.message_ids?.length ?? 0 });
  sendJson(res, 200, {
    ok: true,
    message_ids: result.message_ids ?? [],
    group_jid: result.group_jid ?? "",
  });
}

function sendJson(res: ServerResponse, status: number, data: object): void {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

/** Parse query string from request url. */
function getQuery(req: IncomingMessage): Record<string, string> {
  const url = req.url ?? "/";
  const q = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
  const out: Record<string, string> = {};
  for (const part of q.split("&")) {
    const [k, v] = part.split("=");
    if (k && v !== undefined) out[decodeURIComponent(k)] = decodeURIComponent(v.replace(/\+/g, " "));
  }
  return out;
}

/** Parse JSON body (for POST /session/start). */
async function parseJsonBody<T = unknown>(req: IncomingMessage): Promise<T> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw.trim()) return {} as T;
  return JSON.parse(raw) as T;
}

export function startWebhookServer(): void {
  const server = createServer(async (req, res) => {
    const url = req.url ?? "/";
    const path = url.split("?")[0];

    if (path === "/" || path === "/health") {
      const state = getConnectionState();
      const summary = getHealthSummary();
      sendJson(res, 200, {
        status: state.status,
        connected: state.connected,
        lastDisconnectReason: state.lastDisconnectReason,
        lastDisconnectCode: state.lastDisconnectCode,
        disconnectCount: state.disconnectCount,
        needsRescan: state.needsRescan,
        activeSessions: summary.activeSessions,
        lastErrors: summary.lastErrors,
      });
      return;
    }
    if (path === "/session") {
      const session = getSessionState();
      sendJson(res, 200, {
        loggedIn: session.loggedIn,
        meId: session.meId,
        lastSeen: session.lastSeen,
        needsRescan: session.needsRescan,
      });
      return;
    }
    if (path === "/metrics") {
      res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(getMetrics());
      return;
    }
    if (path === "/qr") {
      const qr = getCurrentQr();
      sendJson(res, 200, qr !== null ? { qr } : { qr: null });
      return;
    }
    if (path === "/send") {
      await handleSend(req, res);
      return;
    }
    if (path === "/session/start" && req.method === "POST") {
      try {
        const body = await parseJsonBody<{ user_id?: number }>(req);
        const userId = body?.user_id;
        if (userId == null || typeof userId !== "number") {
          sendJson(res, 400, { ok: false, error: "user_id required" });
          return;
        }
        const sessionPath = await ensureUserSessionFolder(userId);
        sendJson(res, 200, { status: "qr_ready", session_path: sessionPath });
      } catch (e) {
        logger.warn("session/start error", { err: String(e) });
        sendJson(res, 500, { ok: false, error: "Internal error" });
      }
      return;
    }
    if (path === "/session/qr" && req.method === "GET") {
      const query = getQuery(req);
      const _userId = query.user_id; // per-user isolation placeholder; single-session returns global QR
      const qr = getCurrentQr();
      const expiresAt = getQrExpiresAt();
      const expiresIn = expiresAt > 0 ? Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)) : 0;
      const state = getConnectionState();
      sendJson(res, 200, { qr: qr ?? null, expires_in: expiresIn, status: state.status });
      return;
    }
    if (path === "/session/status" && req.method === "GET") {
      const query = getQuery(req);
      const _userId = query.user_id; // per-user isolation placeholder; single-session returns global status
      const state = getConnectionState();
      const session = getSessionState();
      const phone = session.meId ? session.meId.replace(/@.*$/, "") : null;
      sendJson(res, 200, {
        status: state.status,
        connected: state.connected,
        phone: phone ?? null,
        phone_e164: phone ? `+${phone}` : null,
        lastDisconnectReason: state.lastDisconnectReason ?? null,
      });
      return;
    }
    sendJson(res, 404, { ok: false, error: "Not found" });
  });

  server.listen(env.PORT, () => {
    logger.info("Webhook server listening", { port: env.PORT });
  });
}

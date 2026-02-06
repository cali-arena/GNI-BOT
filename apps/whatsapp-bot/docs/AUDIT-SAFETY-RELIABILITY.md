# WhatsApp Web Bot — Safety, Ban Risk & Reliability Audit

**Scope:** `apps/whatsapp-bot` and its use in the GNI pipeline (docker-compose, worker integration).  
**Date:** 2025-02-04  
**No code changes in this step; report only.**

---

## 1) High-risk issues (must fix)

### 1.1 Admin phone number in logs (ban risk / privacy)

- **Where:** `wa.ts` — `checkAdminGuard()` returns error strings that include the raw `WA_ADMIN_NUMBER` (e.g. `"WA_ADMIN_NUMBER (+1XXXXXXXXXX) is not a participant in the group"`). These are passed to `logger.warn("Admin guard rejected send", { error: guard.error })`.
- **Risk:** Log aggregation or support access could expose the admin’s phone number; logging full phone numbers is also a common ToS/safety concern for messaging platforms.
- **Recommendation:** Redact or hash the number in guard error messages and in any log that includes `guard.error` (e.g. last 4 digits only, or “REDACTED”).

### 1.2 No maximum request body size (DoS / OOM)

- **Where:** `webhook.ts` — `parseBody()` reads the full request body with `for await (const chunk of req)` and no limit.
- **Risk:** A client can send an unbounded body; the process buffers it all in memory, leading to OOM and service failure.
- **Recommendation:** Enforce a max body size (e.g. 512 KB or 1 MB) and reject (413) or close the request when exceeded (e.g. via a capped stream or byte counter).

### 1.3 Idempotency lost on restart (duplicate sends)

- **Where:** `webhook.ts` — idempotency store is an in-memory `Map` with 24h TTL. Process restart clears all keys.
- **Risk:** After a deploy or crash, the same `idempotency_key` can be sent again and the message will be sent twice. For critical “send once” semantics this is a correctness and user-trust issue.
- **Recommendation:** Persist idempotency (e.g. Redis or DB) with the same 24h semantics, or document that idempotency is best-effort and only within a single process lifetime.

---

## 2) Medium-risk issues

### 2.1 HTTP rate limit looser than WhatsApp rate limit

- **Where:** `env.ts` — `RATE_LIMIT_MAX` default 30 per minute (HTTP); `WA_RATE_PER_MINUTE` default 3 (token bucket).
- **Risk:** Up to 30 HTTP requests/min can hit the bot; only 3 sends/min are allowed by the token bucket. Many callers get 429 and may retry, increasing load and complexity. Not a safety bug but can cause confusion and extra load.
- **Recommendation:** Align HTTP limit with WA capacity (e.g. same or slightly higher than `WA_RATE_PER_MINUTE`) or document that 429 is expected when WA limit is reached.

### 2.2 Reconnect loop has no backoff

- **Where:** `wa.ts` — on `connection === "close"` with `shouldReconnect === true`, `startWa()` is called immediately with no delay.
- **Risk:** If WhatsApp is throttling or the network is flapping, repeated instant reconnects could look abusive and risk temporary blocks; also CPU churn.
- **Recommendation:** Add a short (e.g. 2–5 s) delay before calling `startWa()`, or exponential backoff with a cap (e.g. up to 60 s).

### 2.3 QR and session endpoints reachable on internal network

- **Where:** `webhook.ts` — `GET /qr` and `GET /session` are available to any service on the same Docker network (e.g. worker, api).
- **Risk:** QR payload is a one-time pairing secret; `/session` exposes `meId` (JID). If another container is compromised or misconfigured, it could read QR or session info. Lower than public exposure but still an internal exposure.
- **Recommendation:** Restrict access (e.g. internal auth header or allowlist by caller) or document that only trusted services should be on the same network and that QR/session are sensitive.

### 2.4 Group name and JID in logs

- **Where:** `wa.ts` — e.g. `logger.info("Target group resolved by name", { name, jid: cachedTargetGroupJid })`, `logger.info("Messages sent to group", { groupJid, count, messageIds })`.
- **Risk:** Group name and group JID are logged; in some environments this is considered PII or sensitive. Also `meId` on “WhatsApp connected”.
- **Recommendation:** Consider redacting or shortening JIDs/names in logs (e.g. last 4 chars of JID), or gate detailed logs behind a debug flag.

### 2.5 Idempotency key logged

- **Where:** `webhook.ts` — `logger.info("Duplicate idempotency_key, skipping send", { idempotency_key: idempotencyKey })`.
- **Risk:** Keys often include `item_id` and template; usually not secret but can be business-sensitive. Low severity.
- **Recommendation:** Log that a duplicate was skipped without the full key, or hash the key for logs.

### 2.6 No cap on number of chunks per request

- **Where:** `webhook.ts` — `splitIntoChunks(text, maxChars)` can produce many chunks for a very long `text`; `sendMessagesToGroup(textChunks)` pre-consumes one token per chunk.
- **Risk:** A single request with a huge body could consume many tokens (up to hour bucket) and/or cause many sends in one go, increasing ban risk and skewing rate limits.
- **Recommendation:** Enforce a maximum number of chunks per request (e.g. 5–10) and reject (400) if exceeded.

---

## 3) Suggested safe defaults

### 3.1 Rate limiting (already in place; verify env)

- **Per-minute / per-hour:** Token bucket with `WA_RATE_PER_MINUTE=3`, `WA_RATE_PER_HOUR=20` — keep these or lower for initial rollout.
- **Jitter:** `WA_MIN_DELAY_MS=800`, `WA_MAX_DELAY_MS=2500` between chunk sends — good; keeps sends from being perfectly periodic.
- **Backoff:** Exponential backoff with jitter (base 1s, cap 30s) for transient errors — good.
- **Suggestion:** Document that these defaults are conservative and that increasing them increases ban risk; avoid raising per-minute above ~5 without testing.

### 3.2 Idempotency

- **Current:** 24h TTL, in-memory; duplicate keys within same process return cached response and do not send.
- **Suggestion:** Require `idempotency_key` for all non–dry-run sends in the worker so that retries and duplicate webhooks do not double-send; document that after a bot restart, idempotency is reset.

### 3.3 Failure modes

- **Disconnects:** On non–logged-out close, code calls `startWa()` again (reconnect). No backoff (see 2.2).
- **Session drop / logout:** On `DisconnectReason.loggedOut`, `loggedIn` and `meId` are cleared; reconnect is not attempted. User must scan QR again; auth files remain on disk but are invalid. Acceptable.
- **QR re-scan flow:** When there is no valid session, Baileys emits `qr`; bot prints it (terminal) and exposes it via `GET /qr`. After scan, `creds.update` persists; next run uses saved creds. Flow is correct; ensure QR is only available on internal network (see 3.4).

### 3.4 Network exposure

- **Confirmed:** In `docker-compose.yml`, `whatsapp-bot` has **no `ports:`** mapping. The service listens on `env.PORT` (3100) inside the container; Node’s `server.listen(port)` binds to all interfaces inside the container, but the host does not publish port 3100. Only services on the `internal` network (e.g. worker, api) can reach `http://whatsapp-bot:3100`. **whatsapp-bot is not publicly exposed.**

### 3.5 Logs and secrets

- **Confirmed:** No auth tokens, session keys, or QR payload are passed to the app logger. Baileys logger is set to `pino({ level: "silent" })`, so Baileys does not log to the app.
- **Caveats:**  
  - Admin phone number can appear in guard error messages and thus in logs (see 1.1).  
  - Group name, group JID, and `meId` appear in info logs (see 2.4).  
  - QR is printed to stdout and returned by `GET /qr`; ensure stdout and that endpoint are not in public or overly broad log sinks.

### 3.6 Safe defaults checklist

| Item                         | Current default              | Suggestion                          |
|-----------------------------|------------------------------|-------------------------------------|
| WA_RATE_PER_MINUTE          | 3                            | Keep; do not raise above 5 initially |
| WA_RATE_PER_HOUR            | 20                           | Keep                                |
| WA_MIN_DELAY_MS / MAX       | 800 / 2500                   | Keep                                |
| RATE_LIMIT_MAX (HTTP)       | 30 per minute                | Consider lowering to ~5–10         |
| Idempotency TTL             | 24h                          | Keep                                |
| Max body size               | None                         | Add 512 KB–1 MB                     |
| Max chunks per request      | Unbounded                    | Add cap (e.g. 10)                   |
| Reconnect delay             | None                         | Add 2–5 s or backoff                |

---

## Summary

- **High:** Fix admin number in logs, add max body size, and either persist idempotency or clearly document its process-local, best-effort nature.
- **Medium:** Tighten or document HTTP vs WA rate limits, add reconnect backoff, restrict or document QR/session access, and consider redacting or limiting sensitive data and chunk count in logs/requests.
- **Exposure:** whatsapp-bot port is **not** publicly exposed; only internal Docker network can reach it.
- **Logs:** No direct logging of auth or QR in app code; reduce exposure of phone numbers, JIDs, and group names in logs as above.

# WhatsApp Web Bot

Internal service: maintains a WhatsApp Web session (Baileys) and exposes an HTTP API for the GNI pipeline to send messages to a target group. Rate limiting, idempotency, and circuit breaker are built in.

## Endpoints

- `GET /health` — status, connected, lastDisconnectReason, lastDisconnectCode, disconnectCount, needsRescan
- `GET /session` — loggedIn, meId, lastSeen, needsRescan
- `GET /qr` — current QR payload (when waiting for scan)
- `POST /send` — send message (body: `{ text, idempotency_key?, meta? }`)
- `GET /metrics` — Prometheus-format counters (sends_success_total, sends_failed_total, rate_limited_total, disconnects_total)

## Manual intervention (session invalid / needs re-scan)

When the WhatsApp session is invalid (e.g. logged out from the phone, or session expired), the bot sets **needsRescan = true** and **stops accepting sends** until the session is re-linked.

### What you’ll see

- **Logs:**  
  `Session invalid (logged out). MANUAL INTERVENTION: Scan QR (GET /qr) to re-link. Sends disabled until re-scan.`
- **Health:** `GET /health` returns `needsRescan: true`, `connected: false`.
- **Session:** `GET /session` returns `needsRescan: true`, `loggedIn: false`.
- **Send:** `POST /send` returns **503** with body:  
  `Session invalid; manual intervention required. Scan QR (GET /qr) to re-link. See README.`

### Operator steps

1. **Confirm** — Call `GET /health` or `GET /session` and check `needsRescan === true`.
2. **Get QR** — Call `GET /qr` from a trusted service on the same network (or open the bot’s logs if QR is printed to stdout). If `GET /qr` returns `{ "qr": null }`, wait a few seconds and retry; the QR may not be ready yet.
3. **Scan** — On the phone that owns the WhatsApp account: WhatsApp → Linked devices → Link a device → Scan the QR from step 2.
4. **Verify** — After a few seconds, `GET /health` should show `connected: true`, `needsRescan: false`. Sends will work again.

### Important

- Do **not** rely on the bot to “reconnect” after a full logout. Once logged out, a **new QR scan is required**.
- The auth files in `AUTH_FOLDER` (e.g. `/data/wa-auth`) are invalid after logout; the next successful scan will replace them.
- Keep `GET /qr` and the bot’s logs only on trusted networks; the QR is a one-time secret.

## Env (summary)

- `PORT`, `AUTH_FOLDER`, `REDIS_URL` (optional; rate limits persist when set)
- `WA_TARGET_GROUP_JID` / `WA_TARGET_GROUP_NAME`, `WA_ADMIN_NUMBER`
- `WA_RATE_PER_MINUTE`, `WA_RATE_PER_HOUR`, `WA_MIN_DELAY_MS`, `WA_MAX_DELAY_MS`
- `WA_RECONNECT_BACKOFF_BASE_MS`, `WA_RECONNECT_BACKOFF_CAP_MS`
- `WA_CIRCUIT_FAILURE_THRESHOLD`, `WA_CIRCUIT_OPEN_MS`
- `LOG_LEVEL` (debug | info | warn | error)

## Rate limiting

- **Redis (when `REDIS_URL` is set):** Counters are stored in Redis with per-channel and per-group keys, so limits survive restarts and are shared across instances.
- **In-memory fallback:** If Redis is not set or fails, the in-memory token bucket is used (resets on restart).

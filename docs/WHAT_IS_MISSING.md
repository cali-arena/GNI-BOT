# What’s Missing in This Project (vs Full Spec)

Single reference for gaps between the current repo and the full 24/7 autopilot spec. **Do not implement from this file alone** — use the full spec for behavior and formats.

---

## 1. Architecture & API

| Area | Current | Missing |
|------|---------|--------|
| **API** | `/health` only (DB check) | `/control/pause`, `/control/resume`, `/control/status`; admin endpoints |
| **API layout** | `main.py` only | `routes/health.py`, `routes/control.py`; `settings.py` (load settings from DB) |
| **Pause safety** | Settings table has `pause_all_publish` | Pipeline does **not** read `pause_all_publish` before publishing; no “kill switch” in worker |
| **Control** | — | API must read/write Settings (pause flags) and expose them as control endpoints |

---

## 2. Ingest & Normalize

| Area | Current | Missing |
|------|---------|--------|
| **RSS** | ✅ `rss.py`, `normalize.py`, `config.py` | — |
| **Telegram ingest** | — | **`telegram_ingest.py`**: Telethon client, read groups/channels, normalize to Raw Item; persisted session file (volume); env: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` |
| **Normalized schema** | title, url, published_at, summary, source_name | **`source_type`**: `rss` / `telegram` / `api` (not in Item/source model) |
| **Sources table** | name, url | **`type`** (rss/telegram/api), **`tier`**, Telegram **chat_id** for Telegram sources |

---

## 3. Dedupe

| Area | Current | Missing |
|------|---------|--------|
| **Fingerprint** | ✅ sha256(canonical_url + title + published_at); stored on Item | Fingerprint formula does **not** include **source_type** (spec: `sha256(source_type + canonical_url + normalized_title)`) |
| **Window** | Dedupe by fingerprint forever (no time window) | Spec: “drop duplicates **within a time window (e.g. last 7 days)**” — no 7-day (or configurable) window implemented |
| **Module** | Dedupe logic lives in collector/normalize + rss | Spec calls for **`worker/dedupe.py`** (separate module; can wrap same logic) |

---

## 4. Scoring (Heuristic)

| Area | Current | Missing |
|------|---------|--------|
| **Rules** | ✅ rumor/unconfirmed/allegedly → ANALISE_INTEL, risk high, needs_review; announcement/launch/etc. → FLASH_SETORIAL | — |
| **Outputs** | priority (P0/P1/P2 as int), risk, template, needs_review | **sector** (Defense/Macro/Crypto), **flag_emoji** (🇺🇸 🇨🇳 etc.) not produced by scoring; LLM has sector/flag but scoring heuristics don’t set them |

---

## 5. LLM (Ollama)

| Area | Current | Missing |
|------|---------|--------|
| **Classifier** | ✅ template, risk, priority, sector, flag, requires_review | **`reason`** field (spec) not in schema |
| **Generator** | ✅ strict JSON payload (headline, body, etc.) | Spec expects **fields to render Template A or B** (tema, status_confirmacao, leitura rápida, por que isso importa, como validar, insight, etc.); current payload is generic headline/body/bullets |
| **Prompts** | Generic English | Spec: exact Portuguese prompts and field names for Template A/B |

---

## 6. Render (Exact GNI Format)

| Area | Current | Missing |
|------|---------|--------|
| **Template A** | “🚨 GNI — Intelligence Analysis” + bullets + separator | Spec: **“GNI — Análise de Inteligência”** with fixed structure: **Tema**, **Leitura rápida**, **Por que isso importa**, **Como validar (checklist OSINT)**, **Insight central** (exact Portuguese labels and layout) |
| **Template B** | “🚨 GNI \| {Sector} {Flag}” + bullets + separator | Spec: **“GNI \| {Setor} {flag}”** + **Em destaque** + **Insight** (exact Portuguese) |
| **Payload shape** | headline, body, bullets | Spec: **tema**, **status_confirmacao**, **a/b/c** bullets, **insight**, etc. — render must consume LLM output shaped for these sections |

---

## 7. Publish

| Area | Current | Missing |
|------|---------|--------|
| **Telegram** | Stub only (prints + DB log) | **Real Bot API**: send to `TELEGRAM_TARGET_CHAT_ID` using `TELEGRAM_BOT_TOKEN` |
| **Make webhook** | POST with `text`, `template`, `priority`, `source`, `url`, `item_id` | Spec payload: **`channel: "whatsapp"`**, **`meta`** object with `source`, `url`, `item_id` (and optionally `uuid`) |
| **Rate limiting** | — | **`publisher/rate_limit.py`**: use Redis counters; enforce per-channel/per-minute (and optional per-hour) limits from Settings |
| **Logging** | Publications table + events_log (Make dead-letter) | **`attempts`** column on publications (spec) not in model |

---

## 8. Reliability & Safety

| Area | Current | Missing |
|------|---------|--------|
| **Pause** | Settings.pause_all_publish exists | **Worker** never checks it before publish; no `safety.py` or equivalent that reads Settings and blocks publish |
| **Retries** | Make webhook has retries + backoff | **`worker/retry.py`**: shared retry/backoff helper used across pipeline (and optionally by publishers) |
| **Dead-letter** | Make: events_log + publication status | No dedicated “dead-letter queue” table or RQ queue; no **review gate** queue for high-risk items |
| **Queue** | Worker runs pipeline on timer (no RQ jobs) | Spec assumes “queue + retries + rate limit counters” in Redis; current design is scheduler loop, not job queue |

---

## 9. Repo Structure (Spec vs Current)

| Spec path | Exists? |
|-----------|--------|
| `apps/api/routes/health.py` | ❌ |
| `apps/api/routes/control.py` | ❌ |
| `apps/api/db/session.py` | ❌ (logic in `db/__init__.py`) |
| `apps/api/settings.py` | ❌ |
| `apps/collector/telegram_ingest.py` | ❌ |
| `apps/worker/dedupe.py` | ❌ |
| `apps/worker/retry.py` | ❌ |
| `apps/worker/safety.py` | ❌ |
| `apps/publisher/rate_limit.py` | ❌ |
| `apps/api/main.py` | ✅ |
| `apps/api/db/models.py` | ✅ |
| `apps/collector/rss.py`, `normalize.py` | ✅ |
| `apps/worker/tasks.py`, `scoring.py`, `render.py`, `llm/*` | ✅ |
| `apps/publisher/telegram.py`, `whatsapp_make.py` | ✅ |

---

## 10. Storage (Postgres)

| Table / field | Current | Missing |
|---------------|---------|--------|
| **sources** | name, url | **type** (rss/telegram/api), **tier**, **chat_id** (for Telegram) |
| **items** | fingerprint, normalized fields, status, etc. | **source_type** |
| **publications** | channel, status, external_id, created_at, published_at | **attempts** |
| **settings** | autopilot_enabled, pause_all_publish, rate_limits (JSON) | — (limits exist as JSON; rate_limit module missing) |

---

## 11. Telegram (E2E)

| Area | Missing |
|------|--------|
| **Ingest** | Telethon session (one-time login), `telegram_ingest.py`, env vars, volume for session file |
| **Publish** | Real Bot API send; `TELEGRAM_BOT_TOKEN` + `TELEGRAM_TARGET_CHAT_ID` |
| **Docs** | One-time Telethon login steps and where to store session file |

---

## 12. Deployment & Verification

| Area | Current | Missing |
|------|---------|--------|
| **Provision** | ✅ `provision_ubuntu.sh` (Docker, UFW, optional swap) | — |
| **systemd** | ✅ `install_systemd.sh` (gni-bot.service) | — |
| **Verification** | README run steps | Explicit **verification checklist**: /health OK, one test RSS ingested, one test published to Telegram + Make (and what “success” looks like for each) |
| **Telethon** | — | Document one-time login and how to run it (e.g. script or command). |

---

## 13. Summary Checklist (for implementation)

- [ ] API: `/control/pause`, `/control/resume`, `/control/status`; read/write Settings.
- [ ] API: split into `routes/health.py`, `routes/control.py`; add `settings.py`.
- [ ] Worker: before publish, read `Settings.pause_all_publish` and skip publish if set (e.g. `safety.py`).
- [ ] Collector: add `telegram_ingest.py` (Telethon), session volume, env vars.
- [ ] Models: add `source_type` (items/sources), `type`/`tier`/`chat_id` (sources), `attempts` (publications).
- [ ] Fingerprint: include `source_type`; optional 7-day (or configurable) dedupe window.
- [ ] Worker: add `dedupe.py`, `retry.py`, `safety.py`.
- [ ] Publisher: add `rate_limit.py` (Redis); Telegram real Bot API; Make payload to spec (`channel`, `meta`).
- [ ] Render: replace with exact Portuguese Template A/B (Análise de Inteligência, Setor, Leitura rápida, etc.).
- [ ] LLM: classifier add `reason`; generator output fields for Template A/B sections; prompts in Portuguese.
- [ ] Scoring: optional sector/flag_emoji from heuristics (or leave to LLM).
- [ ] Docs: Telethon one-time login; verification steps (health, one RSS, one publish to Telegram + Make).

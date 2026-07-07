# SalesMoy — Infrastructure Recovery Report

**Situation:** The DigitalOcean account was suspended for non-payment, then terminated, and the Droplet was **permanently destroyed**. Assume the original server and everything on it (including Docker volumes) is **gone**. The only surviving assets are:

- ✅ This GitHub repository (source code)
- ✅ The domain
- ✅ External service accounts (MoySklad, Sales Doctor)
- ✅ API accounts

This document lets an engineer with **no prior knowledge** rebuild the whole system from scratch.

> **⚠️ The single most important fact in this report:**
> This application stores **all real business credentials and business data _inside PostgreSQL_**, not in the codebase or env files. MoySklad tokens, Sales Doctor logins/passwords, users, orders, clients, and debts all lived in the database's Docker volume on the destroyed server. **If there is no PostgreSQL backup, that data is permanently lost** and must be re-entered by each company. See [Risk Register](#13-risk-register).

---

## 1. What this project is

A multi-tenant SaaS that keeps **MoySklad** (inventory/ERP) and **Sales Doctor** (Uzbekistan field-sales/distribution platform) in sync. Sales agents create orders in MoySklad; the backend syncs orders, clients, stock, and debts into Sales Doctor and back, converting USD→UZS along the way.

**Stack**

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind, built to a **single static file**, served by nginx |
| Backend | Python 3.11, FastAPI, async SQLAlchemy 2.0, uvicorn |
| Database | PostgreSQL 15 (prod) / SQLite (dev) |
| Cache/Queue | Redis 7 (**provisioned but not used by any code**) |
| Reverse proxy | nginx (HTTP) behind Dokploy/Traefik (HTTPS + Let's Encrypt) |
| Orchestration | docker-compose (three variants — see §9) |

---

## 2. Complete environment variable inventory

Backend settings are loaded by `pydantic-settings` (`backend/config.py`); field names map to UPPER_SNAKE env vars. A few are read directly via `os.getenv`. The full annotated template is in **`.env.example`** (repo root, generated as part of this recovery).

| Variable | Required | Where used | Purpose / notes |
|---|---|---|---|
| `APP_SECRET_KEY` | ✅ **Critical** | `config.py`, `security/jwt_tokens.py`, `security/secret_box.py` | Signs JWTs **and** derives the Fernet key that encrypts SD passwords in the DB. **If it changes, stored SD passwords become undecryptable.** Min 32 chars. |
| `DB_PASSWORD` | ✅ | `docker-compose*.yml` | Postgres password; also composed into `DATABASE_URL`. |
| `DATABASE_URL` | ✅ | `database.py` | Async DB URL (`postgresql+asyncpg://…`). SQLite auto-rewritten to aiosqlite. |
| `CORS_ORIGINS` | ✅ | `config.py`, `main.py` | Comma-separated allowed frontend origins. No trailing slash. |
| `PUBLIC_BASE_URL` | ✅ (for webhooks) | `config.py`, `webhooks.py`, `register_webhooks.py` | HTTPS base; MoySklad webhooks post to `{PUBLIC_BASE_URL}/webhook/moysklad`. Must be `https://`. |
| `DEBUG` | ⬜ | `config.py`, `main.py`, `database.py` | `false` in prod. |
| `TEST_MODE` | ⬜ | `config.py`, `main.py` | `false` in prod. |
| `REDIS_URL` | ⬜ | `config.py` only | **Defined but unused** — no module imports Redis. |
| `MOYSKLAD_BASE_URL` | ⬜ | `moysklad.py` | Default `https://api.moysklad.ru/api/remap/1.2`. |
| `MOYSKLAD_TOKEN` | ⬜ | `moysklad.py` | Global fallback for dev only; real tokens are per-tenant in DB. |
| `MOYSKLAD_ACCOUNT` | ⬜ | `config.py` | Optional. |
| `MOYSKLAD_ACCOUNT_UTC_OFFSET_HOURS` | ⬜ | `config.py`, `moysklad.py` | Default `3` (Moscow). Converts MS local `moment` → UTC. |
| `INITIAL_ORDER_LOOKBACK_DAYS` | ⬜ | `config.py` | Default `3`. Webhook-gap safety net window. |
| `SALESDOCTOR_BASE_URL` | ⬜ | `config.py` | Default SD API base; per-tenant override in DB. |
| `SD_VERIFY_SSL` | ⬜ | `services/salesdoctor.py` | `false` (default) / `true` / CA-bundle path. SD cert often mismatches. |
| `SALESDOCTOR_ORDER_DATE_OFFSET_HOURS` | ⬜ | `config.py` | Default `5`. |
| `STOCK_SYNC_INTERVAL` | ⬜ | `config.py` | Default `60`s. |
| `DEBT_SYNC_INTERVAL` | ⬜ | `config.py` | Default `600`s. |
| `CLIENT_SYNC_INTERVAL` | ⬜ | `config.py` | Default `300`s. |
| `ORDER_SYNC_INTERVAL` | ⬜ | `config.py` | Default `60`s. |
| `SYNC_STALE_AFTER_MINUTES` | ⬜ | `main.py` | Default `10`. Health threshold. |
| `USD_TO_UZS_RATE` | ⬜ | `config.py`, `utils/currency.py` | Fallback rate `12695`. |
| `FORCE_PRICE_CURRENCY` | ⬜ | `orders.py`, `sync.py` | Default `USD`. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | ⬜ | `config.py` | Default `10080` (7 days). |
| `WEBHOOK_SECRET` / `WEBHOOK_URL` | ⬜ | `config.py` | Optional server-wide; per-tenant values live in DB. |
| `VITE_API_URL` | ⬜ | `src/services/api.ts` (build-time) | API base baked into frontend. Empty = same-origin. |

**Payment vars in the old `backend/.env.example` (`PAYME_*`, `CLICK_*`, `YOOKASSA_*`) are obsolete** — `routers/billing.py` is an empty stub ("Billing module — disabled"). They are not required and are omitted from the new template.

---

## 3. `.env.example` (generated)

A complete, commented `.env.example` has been written to the **repo root**. It documents every variable above, marks the required ones, and explains the `APP_SECRET_KEY` stability constraint. The older `backend/.env.example` remains for backend-only local dev but contains stale payment vars.

---

## 4. Does PostgreSQL hold critical business data?

**Yes — it is the crown jewels.** The schema (`backend/models.py`) stores:

| Table | Contents | Recreatable without a backup? |
|---|---|---|
| `tenants` | Company config, **MoySklad access token**, **Sales Doctor login/password/token**, filial id, webhook secret | ❌ Must be re-entered per company |
| `users` | Login emails + **bcrypt password hashes**, roles | ❌ Must be recreated / users re-invited |
| `orders` | Synced customer orders + raw MS payload | ⚠️ Re-syncs from MoySklad within the lookback window; older history is lost |
| `clients` | Counterparties, phones, debt, debt limits | ⚠️ Re-syncs from MoySklad |
| `stock_items` | Product stock snapshot | ✅ Rebuilt on next sync |
| `debt_records` | Per-client debt | ⚠️ Re-syncs from MoySklad reports |
| `deliveries` | Delivery/courier state | ⚠️ Partly reconstructable |
| `sync_logs`, `webhook_events` | Operational logs | ✅ Disposable |

**Verdict:**
- **Config & auth data (`tenants`, `users`) is NOT safely recreatable** — it only existed in the destroyed volume. Without a dump, each company must re-enter MoySklad/SD credentials and users must be recreated.
- **Transactional data (orders/clients/stock/debts) is largely re-derivable** from MoySklad on the next sync cycle, but **historical orders older than `INITIAL_ORDER_LOOKBACK_DAYS` (3 days) will not backfill automatically.** MoySklad remains the system of record for that history.

If **any** PostgreSQL dump exists (DigitalOcean managed-DB backup, manual `pg_dump`, off-box snapshot), restoring it is dramatically faster and preserves everything — locate it before rebuilding.

---

## 5. Are Alembic / migrations sufficient to recreate the schema?

**There is no Alembic in this project.** Schema is created at boot by:

1. `Base.metadata.create_all` (in `database.py::init_db`) — creates all tables from `models.py`.
2. `_patch_schema()` — a hand-written idempotent migration that `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for columns added after first deploy, dedups orders, and adds a unique index.

**Implications:**
- ✅ For a **fresh** database the schema is recreated **fully and automatically** on first backend start — no migration tool needed. The startup command in compose runs `init_db()` before uvicorn.
- ⚠️ There is **no migration history and no downgrade path.** Schema evolution relies on `create_all` (which never alters existing tables) plus the manual `_patch_schema`. This is fine for recovery-from-empty but is a maintainability risk going forward (see §13).
- ✅ `create_all` is safe/idempotent against an existing DB, so restoring a `pg_dump` and then booting the app also works.

**Conclusion:** For rebuilding from empty, the code is self-sufficient — no separate migration step is required. Migrations are **sufficient to recreate the schema, but not the data.**

---

## 6. External dependencies

| Dependency | Type | How it's used | Recovery action |
|---|---|---|---|
| **MoySklad** | External SaaS API (`api.moysklad.ru`) | Source of orders/clients/stock; webhooks push events. Auth = permanent bearer token, entered per tenant in Settings. | Account survives. **Re-issue a fresh permanent access token** per company and paste in Settings; **re-register webhooks** (see §12). |
| **Sales Doctor** | External API (`api.salesdoctor.uz` or per-tenant URL) | Destination for orders/stock/clients/debts; JSON-RPC login→token. Login+password stored (encrypted) per tenant. | Account survives. Re-enter login/password in Settings; token auto-refreshes on login. Note `SD_VERIFY_SSL=false` default. |
| **Telegram** | ❌ **Not an integration.** | Only appears as a code comment in `utils/phone.py` and as a support contact in docs. No bot, no token, no API calls. | **Nothing to recover.** |
| **Redis** | Containerized service | **Provisioned in compose but never imported by any code.** No queues/cache in use. | No data to restore. Optional to keep the container. |
| **PostgreSQL** | Containerized service (or managed) | Primary datastore (see §4). | Restore from dump if available, else rebuild empty. |
| **Payme / Click / YooKassa** | Payment APIs | Referenced only in obsolete env vars; `billing.py` is a disabled stub. | **Not required.** |
| **Let's Encrypt** | TLS issuance via Traefik/Dokploy | Auto-issues the HTTPS cert for the domain. | Automatic on redeploy once DNS points at the new server. |

---

## 7. Credentials: regenerate vs. keep

### Must be REGENERATED (were on the destroyed server / best practice after a breach)
- 🔁 **`APP_SECRET_KEY`** — generate a **new** strong value. (You have no choice — the old one is gone. Note: a new key means any legacy encrypted SD passwords from a restored dump can't be decrypted; users re-enter SD passwords.)
- 🔁 **`DB_PASSWORD`** / PostgreSQL password — set a new one on the rebuilt DB.
- 🔁 **MoySklad permanent access token(s)** — the old token's confidentiality can't be assured; issue a fresh token in MoySklad → Settings → Access tokens and paste per tenant.
- 🔁 **User passwords** — recreate users (or reset), since hashes lived only in the lost DB.
- 🔁 **Webhook secrets** — regenerate per tenant when re-registering webhooks.

### Can STAY UNCHANGED (live in external systems, not on the server)
- ✅ **MoySklad account** itself (login/subscription) — unchanged.
- ✅ **Sales Doctor account, login, and password** — unchanged; simply re-enter them. (Rotate only if you suspect exposure.)
- ✅ **Domain registrar / DNS account** — unchanged.
- ✅ **GitHub credentials** — unchanged.

> Rule of thumb: anything **generated on or stored only on the server** must be regenerated; anything **owned in an external service** can be reused by re-entering it.

---

## 8. Recovery checklist — from an empty Ubuntu server

> Estimated total: **2–4 hours** (empty DB) — see §14 for the breakdown. Add ~30 min per tenant for credential re-entry.

- [ ] **0. Locate any PostgreSQL backup first** (DO managed-DB backup, off-box `pg_dump`, snapshot). If found, recovery is a restore, not a rebuild.
- [ ] **1. Provision** a fresh Ubuntu 22.04+ server (≥2 vCPU / 4 GB RAM / 40 GB disk).
- [ ] **2. Harden**: create a sudo user, SSH keys only, enable `ufw` (allow 22, 80, 443), `unattended-upgrades`.
- [ ] **3. Install Docker Engine + Compose plugin.**
- [ ] **4. Point DNS**: `A` record for your app host (e.g. `app.your-domain.com`) → new server IP. Wait for propagation.
- [ ] **5. Clone the repo**: `git clone <repo-url> && cd salesmoy`.
- [ ] **6. Create `.env`** from `.env.example`; set **new** `APP_SECRET_KEY`, `DB_PASSWORD`, `CORS_ORIGINS`, `PUBLIC_BASE_URL`.
- [ ] **7. Choose a deploy path**:
  - **Dokploy** (matches production): install Dokploy, create a Compose app from `docker-compose.dokploy.yml`, set env vars in the Dokploy UI, set the domain → Traefik auto-issues Let's Encrypt.
  - **Plain compose + Traefik**: use `docker-compose.yml` (already has Traefik labels for `app.pipely.uz` — **edit the Host rule to your domain**), ensure the external `dokploy-network` exists or remove those labels and terminate TLS yourself.
- [ ] **8. Deploy**: `docker compose up -d --build`. Backend auto-runs `init_db()` (creates schema) and (base compose) `seed.py`.
- [ ] **9. Restore data** *(if a dump exists)*: `docker exec -i <db> psql -U integration_user integration < dump.sql`. Otherwise continue empty.
- [ ] **10. Verify HTTPS**: `https://your-domain.com` loads; `GET /health` returns OK; `/docs` reachable.
- [ ] **11. Create the first admin/tenant** (via `seed.py` demo or the app's registration).
- [ ] **12. Per tenant — re-enter credentials** in Settings: MoySklad token, Sales Doctor base URL/login/password/filial.
- [ ] **13. Re-register MoySklad webhooks**: `docker exec <backend> python register_webhooks.py` (needs `PUBLIC_BASE_URL` https).
- [ ] **14. Watch sync**: confirm stock/orders/clients populate and `last_successful_sync_at` advances; check Logs panel.
- [ ] **15. Set up backups** (see §13): daily `pg_dump` off-box + volume snapshots.

---

## 9. docker-compose — every service explained

Three compose files exist:

| File | Purpose |
|---|---|
| `docker-compose.yml` | Full local/standalone stack **with Traefik labels** hardcoded for `app.pipely.uz`. Seeds demo data. Binds DB/Redis/backend to `127.0.0.1`. |
| `docker-compose.dokploy.yml` | **Production** on Dokploy. No host port binds, no Traefik labels in-file (Dokploy/Traefik handle routing + HTTPS). No seed step. 1 uvicorn worker. |
| *(implicit)* | `.env.dokploy` supplies the Dokploy UI env values. |

**Services (from `docker-compose.yml`):**

1. **`db` — PostgreSQL 15-alpine.** DB `integration`, user `integration_user`, password from `DB_PASSWORD`. Volume `postgres_data`. Healthcheck via `pg_isready`. **This holds all business data.**
2. **`redis` — Redis 7-alpine.** `--appendonly yes`, volume `redis_data`. Healthcheck `redis-cli ping`. **Not referenced by application code** — effectively inert.
3. **`backend` — FastAPI (built from `backend/Dockerfile`).** On start runs `init_db()` → `seed.py` → `uvicorn … --workers 4`. Reads `DATABASE_URL`, `REDIS_URL`, `APP_SECRET_KEY`, etc. Depends on healthy `db` + `redis`. In base file it also bind-mounts `./backend:/app` (dev-style hot code) — **remove that bind mount for a clean prod image**.
4. **`frontend` — static build (`Dockerfile.frontend`).** Multi-stage: `npm run build` → nginx serving `/usr/share/nginx/html`. Vite `viteSingleFile` produces one self-contained HTML asset.
5. **`nginx` — reverse proxy.** Serves frontend at `/`, proxies `/api/`, `/webhook/`, `/health`, `/docs`, `/redoc` to backend. Rate-limits API (10 r/s) and webhooks (50 r/s). Exposes `8080:80`. In base file it carries **Traefik labels** (HTTP→HTTPS redirect + Let's Encrypt cert resolver) and joins the external `dokploy-network`.

**Networks:** `integration_network` (internal bridge) + `dokploy-network` (external, Traefik). **Volumes:** `postgres_data`, `redis_data`.

---

## 10. Persistent volumes & expected data loss

**Declared volumes:** `postgres_data` and `redis_data` (named Docker volumes).

- These volumes lived **on the destroyed Droplet's disk**. Named Docker volumes are **not** in the GitHub repo and are **not** backed up anywhere by default. **They are gone.**
- **`postgres_data` loss = the critical loss** (all tenant configs, credentials, users, historical orders/clients/debts). See §4.
- **`redis_data` loss = irrelevant** — Redis isn't used; nothing depended on its persistence.

**Expected data loss on rebuild (no external backup):**
- ❌ All tenant credentials & config → must be re-entered.
- ❌ All user accounts/passwords → must be recreated.
- ❌ Order/client/debt history older than the sync lookback window → not auto-restored (MoySklad still holds the source records).
- ✅ Current stock, and recent orders/clients within the lookback window → repopulate automatically on first sync.

---

## 11. Secrets that may exist ONLY on the destroyed server

These were **never in Git** (`.env`, `backend/.env` are git-ignored) and, unless separately backed up, existed only on the lost machine:

- 🔴 **`APP_SECRET_KEY`** — the production value. **Unrecoverable.** → generate new (accept SD-password re-entry).
- 🔴 **`DB_PASSWORD`** and the entire **PostgreSQL data** (all encrypted per-tenant MoySklad/SD credentials, user password hashes). **Unrecoverable without a dump.**
- 🔴 **Per-tenant secrets inside the DB**: MoySklad tokens, SD passwords/tokens, webhook secrets — encrypted with the old `APP_SECRET_KEY`, so even a restored dump needs the *old* key to decrypt SD passwords (JWTs don't matter, they expire).
- 🟠 **Let's Encrypt account/cert state** (Traefik `acme.json`) — regenerated automatically, no action needed.
- 🟠 Any **manual server tweaks** not captured in the repo (cron jobs, firewall rules, `acme.json`, monitoring agents). Rebuild from this checklist.

**Nothing that is required to _rebuild_ is trapped on the server** — all such secrets are either regenerated (`APP_SECRET_KEY`, `DB_PASSWORD`) or re-entered from external accounts (MoySklad/SD). The only true, irreversible loss is **historical DB data** without a dump.

---

## 12. Deployment guide — rebuild from GitHub only

> Assumes empty server, no dump. Domain = `app.your-domain.com`.

**A. Server prep**
```bash
# Docker + compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # re-login after this
```

**B. DNS**
- `A  app.your-domain.com  → <new server IP>`

**C. Get the code + config**
```bash
git clone <repo-url> salesmoy && cd salesmoy
cp .env.example .env
# Edit .env:
#   APP_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
#   DB_PASSWORD=<strong>
#   CORS_ORIGINS=https://app.your-domain.com
#   PUBLIC_BASE_URL=https://app.your-domain.com
```

**D. Pick ONE deployment path**

*Path 1 — Dokploy (production parity, recommended):*
1. Install Dokploy: `curl -sSL https://dokploy.com/install.sh | sh`.
2. In Dokploy UI → **Create → Compose**, point at `docker-compose.dokploy.yml`.
3. Paste env vars (from `.env.dokploy` template): `APP_SECRET_KEY`, `DB_PASSWORD`, `CORS_ORIGINS`, `PUBLIC_BASE_URL`.
4. Set the app **Domain** to `app.your-domain.com` → Traefik auto-issues Let's Encrypt.
5. Deploy.

*Path 2 — Plain docker compose:*
1. Edit `docker-compose.yml` Traefik labels: replace `app.pipely.uz` with your host (5 occurrences).
2. Ensure the external `dokploy-network` exists (`docker network create dokploy-network`) **or** strip the Traefik labels and put your own TLS in front.
3. `docker compose up -d --build`.

**E. First boot (automatic)**
- Backend runs `init_db()` → schema created; base compose also runs `seed.py` (demo tenant `demo` / `demo@example.com` / `demo123` — **change or remove for prod**).

**F. Verify**
```bash
curl -k https://app.your-domain.com/health
# open https://app.your-domain.com  and  /docs
```

**G. Per-tenant credential entry**
- Log in → **Settings** → paste MoySklad permanent token, Sales Doctor base URL + login + password + filial id. Save.

**H. Re-register MoySklad webhooks**
```bash
docker exec -it <backend-container> python register_webhooks.py
# Requires PUBLIC_BASE_URL to be https://
```

**I. Confirm sync**
- Watch the **Logs** panel; confirm stock/orders/clients populate and `last_successful_sync_at` advances.

---

## 13. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **No PostgreSQL backup exists** → all tenant configs, credentials, users, and order history permanently lost. | 🔴 Critical | Search for any DO managed-DB backup / `pg_dump` / snapshot **before** rebuilding. If none, accept re-entry; set up daily off-box `pg_dump` immediately after recovery. |
| R2 | **`APP_SECRET_KEY` was only on the server.** A new key can't decrypt SD passwords from a restored dump. | 🔴 Critical | Generate new key; have each tenant re-enter SD passwords. Store the new key in a secrets manager, not just `.env`. |
| R3 | **Historical orders older than lookback (3 days) don't backfill.** | 🟠 High | MoySklad is the system of record; widen `INITIAL_ORDER_LOOKBACK_DAYS` temporarily for a one-off deeper resync if needed. |
| R4 | **No Alembic / migration history** — schema managed by `create_all` + manual `_patch_schema`. | 🟠 Medium | Fine for rebuild; adopt Alembic going forward to make schema changes auditable and reversible. |
| R5 | **`SD_VERIFY_SSL=false` by default** — SD calls skip TLS verification (MITM-exposed). | 🟠 Medium | Obtain the correct SD cert/CA and set `SD_VERIFY_SSL=true` (or a bundle path) once available. |
| R6 | **Traefik host rule hardcoded to `app.pipely.uz`** in `docker-compose.yml`. | 🟡 Low | Edit to the real domain, or use the Dokploy path where routing is UI-driven. |
| R7 | **Base compose bind-mounts `./backend:/app` and runs `seed.py`** (demo creds `demo123`). | 🟡 Low | Use `docker-compose.dokploy.yml` for prod; remove the bind mount and demo seed. |
| R8 | **Redis provisioned but unused** — false sense of a dependency; wasted resources. | 🟡 Low | Safe to remove the service, or keep for future queue use. No data risk. |
| R9 | **Single-server, no HA** — one destroyed Droplet took everything down. | 🟠 Medium | Consider a managed Postgres (with automated backups) + separate app host; keep IaC in the repo. |
| R10 | **Secrets only in `.env` on-box.** | 🟠 Medium | Move to a secrets manager / Dokploy env store; never commit `.env`. |

---

## 14. Recovery Report (executive summary)

### Critical files (in this repo)
- `docker-compose.yml` / `docker-compose.dokploy.yml` — orchestration
- `.env.example` (generated) + `.env.dokploy` — config templates
- `backend/config.py`, `backend/database.py`, `backend/models.py` — settings, schema, ORM
- `backend/seed.py`, `backend/register_webhooks.py` — bootstrap & webhook registration
- `nginx.conf` / `nginx.dokploy.conf`, `Dockerfile.frontend`, `backend/Dockerfile`
- `backend/security/secret_box.py` — credential encryption (explains the `APP_SECRET_KEY` dependency)

### Critical secrets
- `APP_SECRET_KEY` (regenerate), `DB_PASSWORD` (regenerate), PostgreSQL data (restore or lose)

### Required API keys / credentials
- **MoySklad** permanent access token (per tenant) — re-issue
- **Sales Doctor** base URL + login + password + filial id (per tenant) — re-enter
- *(No Telegram, no payment gateways, no other third-party keys required.)*

### Required databases
- **PostgreSQL 15** — required (all business data). Redis — optional/unused.

### Required Docker volumes
- `postgres_data` — **must recreate** (lost); restore from dump if available.
- `redis_data` — recreated automatically; no data of value.

### Required DNS records
- `A` record: `app.your-domain.com` → new server IP. (No other records needed for the app; add `AAAA`/`CAA` per your policy.)

### SSL requirements
- HTTPS via **Let's Encrypt**, auto-issued by **Traefik/Dokploy** once DNS resolves. nginx serves HTTP internally only. No manual certs needed. Optionally fix `SD_VERIFY_SSL` for outbound SD calls.

### Recovery priority
1. 🔴 Find/restore PostgreSQL backup (if any)
2. 🔴 Provision server + DNS + Docker
3. 🔴 Deploy stack with **new** `APP_SECRET_KEY` + `DB_PASSWORD`
4. 🟠 Re-enter per-tenant MoySklad/SD credentials
5. 🟠 Re-register MoySklad webhooks
6. 🟡 Validate sync, set up backups & monitoring

### Estimated recovery time
| Phase | Time |
|---|---|
| Server provision + harden + Docker | 30–45 min |
| DNS propagation | 5–60 min (parallelizable) |
| Deploy stack + HTTPS | 20–30 min |
| Restore DB dump *(if available)* | 10–30 min |
| Per-tenant credential re-entry + webhooks | ~30 min per tenant |
| Validation | 15–30 min |
| **Total (single tenant, empty DB)** | **~2–4 hours** |

### Step-by-step deployment order
1. Locate any DB backup.
2. Provision + harden Ubuntu server; install Docker.
3. Point DNS at the new IP.
4. `git clone`; create `.env` with new secrets.
5. Deploy via Dokploy (`docker-compose.dokploy.yml`) or plain compose.
6. Backend auto-creates schema on boot.
7. Restore `pg_dump` if you have one.
8. Confirm HTTPS + `/health`.
9. Create admin/tenant; re-enter MoySklad + Sales Doctor credentials.
10. Run `register_webhooks.py`.
11. Validate sync; enable daily off-box backups + monitoring.

---
*Recovery report generated from source analysis of this repository. External accounts (MoySklad, Sales Doctor, domain, GitHub) are assumed intact; the destroyed server and its Docker volumes are assumed unrecoverable unless a database dump is found.*

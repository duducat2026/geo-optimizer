# GEO-Optimizer Deployment Guide

[English](DEPLOY.en.md) | [简体中文](DEPLOY.md)

This guide covers **bare-metal / cloud host** deployment (non-Docker), from building the
MySQL database through to MCP and Skill exports. All scripts live in `deployment/`.
For one-command Docker orchestration see the "Deployment Guide" section of
[`README.md`](../README.md) (English) or [`README.zh-CN.md`](../README.zh-CN.md) (Chinese).

---

## 0. Prerequisites

| Component | Version | Notes |
|---|---|---|
| Python | 3.11+ | Runtime for the platform and the MCP service |
| MySQL | 8.0+ | Web platform only; database name `geo-op` (contains a hyphen, so quote it with backticks in SQL) |
| Nginx | any stable release | Reverse proxy: `/` → 127.0.0.1:5000, `/mcp` → 127.0.0.1:8000 |
| systemd | — | Manages two services: `geotool` (platform) and `geo-mcp` (MCP) |

---

## 1. Build the MySQL database

Pick one of the two options:

**A. Install MySQL 8 with the helper script and create the schema**
```bash
bash deployment/setup_mysql.sh              # installs and starts MySQL 8, sets the root password
mysql -u root -p < deployment/init_db.sql   # creates geo-op (if setup did not do it)
```

**B. MySQL already exists — just create the database**
```bash
mysql -u root -p < deployment/init_db.sql
```
> You never write table DDL by hand: SQLAlchemy `create_all` builds the tables on application
> start, and `app.py::_ensure_schema_upgrades()` adds new columns to existing tables
> (for example the per-day quota column on API keys).

---

## 2. Configure runtime settings

```bash
cp deployment/settings.example.py deployment/settings.py
```

Edit `deployment/settings.py` (already in `.gitignore`, so it is never committed):

```python
SECRET_KEY = "<random secret>"
DB_HOST, DB_PORT = "localhost", 3306
DB_USER, DB_PASSWORD = "root", "<database password>"
DB_NAME = "geo-op"
ADMIN_USERNAME = "geoadmin"        # default administrator
ADMIN_PASSWORD = "geo-optimizer"
```

---

## 3. Initialize data (schema + seeds + demo account + shared key)

```bash
python deployment/init_platform.py
```

The script is idempotent and performs, in order:

1. creates the `geo-op` database if missing;
2. creates all tables and patches new columns;
3. writes the default system LLM configuration;
4. writes **demo data** (a regular user plus a shared API key):

| Type | Value | Notes |
|---|---|---|
| Regular user | `geo_tool` / password from `DEMO_USER_PASSWORD` in `deployment/init_platform.py` | evaluation quota 50, can log in immediately |
| Shared API key | plaintext constant `DEMO_API_KEY_PLAIN` in the same script | owned by `geo_tool`, **limited to 50 calls/day**, used for MCP / Skill exports |

> **The administrator account is not created by this script** — it only seeds the demo user and
> shared key. Admins come from `seed_defaults` in `settings.py` (only when absent) or are created
> in the backend; an existing cloud admin is untouched.
> **Every API key must carry a quota**; 0 / unlimited is not permitted.

> ⚠️ **Security note**: the demo password and shared key hard-coded in `init_platform.py` are for
> **quick starts and demos only**, and they are visible to anyone reading this public repository.
> Before serving traffic: change the `geo_tool` password after logging in, and rotate or delete the
> shared key in favour of private keys.

---

## 4. Deploy the application (platform + MCP)

`deploy.sh` is the main entry point. It runs seven steps — package → upload → install
dependencies → sync configuration → switch release → restart geotool + geo-mcp → sync Nginx —
with built-in rollback (an `nginx -t` failure restores the previous config automatically).

```bash
REMOTE_HOST=your-ssh-host-alias \
REMOTE_IP=203.0.113.10 \
DOMAIN=geo.tool.example.com \
bash deployment/deploy.sh
```

| Environment variable | Meaning | Default |
|---|---|---|
| `REMOTE_HOST` | SSH alias from `~/.ssh/config` | your-ssh-host-alias |
| `REMOTE_IP` | host IP | 203.0.113.10 |
| `DOMAIN` | public domain, used to render Nginx certificate paths and `server_name` | geo.tool.example.com |
| `DEPLOY_BASE` | deployment root on the cloud host | /opt/geotool |

Release directories are named `geotool-release-<yyyyMMddHHmmss>-v0.1.0`; the `current` symlink
points at the active release and the last 5 are kept.

> On a first deployment, run steps 1 and 3 (`setup_mysql.sh` and `init_platform.py`) so the
> database and seed data exist on the host; `deploy.sh` only publishes the application and does
> not create databases. The cloud-side `shared/settings.py` and `shared/mcp.env` are generated
> from the examples on the first run and reused afterwards — they are never overwritten.

---

## 5. MCP and Skill exports

1. Log in to the platform as `geo_tool` → **API keys** in the left menu;
2. the "shared key (demo)" row in the list is the one seeded in step 3 — click **Export Skill** or **Export MCP** and pick the target platform to download a ZIP;
3. inside the general (non-variant) package, `config.json` (Skill) / `mcp-config.json` (MCP) has this key's plaintext written in, so it works out of the box;
   - platform variant packages contain no plaintext key: the MCP config uses the `${GEO_API_KEY}` placeholder and you inject the environment variable yourself;
4. if a historical key has no stored plaintext, the export **regenerates a working key automatically** and persists it.

Live MCP endpoint: `https://<DOMAIN>/mcp` (streamable-HTTP, reverse-proxied to `127.0.0.1:8000`).

---

## 6. Post-deployment verification

```bash
# service state
ssh <REMOTE_HOST> 'systemctl is-active geotool geo-mcp'

# platform and MCP reachability
curl -I  https://<DOMAIN>/login                 # expect 200
curl -sI -X POST https://<DOMAIN>/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'   # expect 200
```

Troubleshooting with logs:
```bash
ssh <REMOTE_HOST> 'journalctl -u geotool -n 50 --no-pager'
ssh <REMOTE_HOST> 'journalctl -u geo-mcp -n 50 --no-pager'
```

---

## 7. Go-live security checklist

- [ ] Change the default `geoadmin` / `geo_tool` passwords
- [ ] Rotate or delete the hard-coded shared API key and switch to private keys
- [ ] `SECRET_KEY` and `DB_PASSWORD` in `settings.py` are real random values (never committed)
- [ ] `GEO_API_KEY` in `mcp.env` is valid (chmod 600)
- [ ] The domain's TLS certificate is in place and `nginx -t` passes
- [ ] Set sensible per-day quotas for each API key on the admin "key quota" page

# GEO-Optimizer

**English** | [简体中文](README.zh-CN.md)

<div align="center">

**Generative Engine Optimization (GEO) toolchain & multi-user platform** — get your content cited by AI search engines instead of buried by them.

[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](#-changelog)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![AI Engines](https://img.shields.io/badge/AI_Engines-11-orange.svg)](#-supported-ai-engines)
[![Platforms](https://img.shields.io/badge/Export-6_Platforms-brightgreen.svg)](#-multi-platform-export)
[![Docs](https://img.shields.io/badge/Docs-online-8ca2fd.svg)](https://duducat2026.github.io/geo-optimizer/)

[Features](#-features) • [Architecture](#-architecture-overview) • [Quick Start](#-quick-start) • [Configuration](#-configuration-reference) • [Deployment](#-deployment-guide) • [License](#-license)

**Crawl & analyze → dual-engine scoring → LLM content generation → multi-platform distribution → rank monitoring, covering 11 AI engines end to end**

</div>

---

## 📖 Overview

GEO-Optimizer is an open-source toolchain and multi-user platform built for *Generative Engine Optimization* — the practice of making content discoverable and citable by AI search engines. It crawls websites with Playwright, scores AI-engine readiness with a dual-engine model (5 dimensions for Chinese engines, 6 for global ones), uses LLMs to generate FAQs, structured data and platform-ready content, and can be used in four interchangeable forms: **CLI**, **Web platform**, **MCP server** and **Agent SKILL**.

### 🎯 Core Value

- **🔍 Real crawling** — Playwright-driven, JS-rendered pages supported, robust on heavily instrumented sites
- **🎯 Dual-engine scoring** — 5 Chinese + 6 global dimension GEO-readiness assessment across 11 AI engines
- **🤖 LLM content optimization** — OpenAI-compatible endpoints (Bailian / Token Plan / custom), auto-generates FAQ, Schema and rewritten body copy
- **📤 Multi-platform export** — WeChat, Zhihu, Toutiao, Medium, Quora and Reddit formats
- **👥 Multi-user platform** — Self-service signup with admin approval, quota governance, multi-source compute switching, audit log, task queue with retry
- **🔌 MCP server** — streamable-HTTP mode exposing platform capabilities to any MCP client
- **🧩 Agent SKILL** — ClawHub-format skill package, triggered by a natural-language prompt

### 🧭 Architecture Overview

The project consists of four independently usable pipelines:

```
src/geo_optimizer/            — Core library + CLI (analyze/optimize/export/eval/check/monitor/report)
├── crawler.py                — Playwright website crawling
├── analyzer.py               — Dual-engine GEO-readiness scoring
├── generators/               — LLM content / FAQ / Schema generation
├── evaluation/               — Multi-engine evaluation / index checks / rank monitoring
├── export.py · report.py     — Multi-platform export / report generation
└── web/portal/               — Flask multi-user platform (blueprints: main/auth/user/admin/api/planitems/audit/guide/packaging/tasks)

mcp_server/                   — MCP server (streamable-HTTP / stdio, 8 tools)
docs/geo-skill/               — ClawHub Agent SKILL package and client scripts
client/geo_api_client.py      — Open-API Python client
deployment/                   — systemd / Nginx one-shot deployment, init scripts, config templates
data/artifacts/               — Runtime artifacts (gitignored)
```

---

## ✨ Features

### Core Capabilities

- **Website crawl & analysis** — Playwright-driven, JS rendering, depth crawling, page snapshots
- **Dual-engine scoring** — 5 Chinese + 6 global dimension GEO-readiness assessment
- **LLM content optimization** — Generates improved copy via any OpenAI-compatible compute source
- **Automatic FAQ generation** — Structured Q&A pairs derived from keywords and user scenarios
- **Schema structured data** — JSON-LD output (`FAQPage`, `Article`, `Organization`)
- **Multi-platform export** — WeChat, Zhihu, Toutiao, Medium, Quora, Reddit
- **Rank monitoring** — Periodic tracking of target-keyword citations per engine
- **Multi-engine GEO evaluation** — Performance and index-status assessment across 11 AI engines

### Web Platform (Multi-user)

- **Users & approval** — Self-service registration, admin approval and activation, role isolation (user / admin)
- **Quota governance** — Daily-resetting evaluation quota, usage statistics
- **Compute plans** — System-level multi-source chain (`SystemLLMConfig`) with priorities, plus user-owned keys; the active source is always labelled
- **Task queue** — Async background execution, fine-grained processing logs, retry on failure, cancellation
- **Plan packaging** — Generates plan artifacts (body copy / FAQ / Schema / platform drafts), ZIP bundle download, PDF report

### 🌐 Supported AI Engines

| Chinese engines | Global engines |
|---------|---------|
| Doubao | Google AI Overviews |
| Tongyi Qianwen | ChatGPT Search |
| Hunyuan | Perplexity |
| ChatGLM | Claude |
| DeepSeek | Copilot |
| — | Gemini |

---

## 🚀 Quick Start

### 📋 Requirements

| Software | Version | Notes |
|---|---|---|
| **Python** | **3.10+** | Main runtime |
| **Playwright** | 1.40+ | Browser automation (requires `playwright install chromium`) |
| **MySQL** | 8.0+ | Web platform only; the CLI toolchain needs no database |

### 📥 Installation

```bash
# Clone the repository
git clone https://github.com/duducat2026/geo-optimizer.git
cd geo-optimizer

# Virtualenv + install (development mode, includes test deps)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Web platform: pip install -e ".[web]"
# MCP server:    pip install -e ".[mcp]"

# Install the Playwright browser (set a mirror if the download is slow)
playwright install chromium
# Mainland China mirror: export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
```

> `pyproject.toml` is the single source of truth for dependencies; the root `requirements.txt` only exists for `pip install -r` compatibility.

### 🔧 Configuration

1. Copy the config: `cp geo_config.yaml geo_config.local.yaml`, then edit `target.url` and `keywords`.
2. Set up LLM compute (either way works):
   - Environment variable: `export DASHSCOPE_API_KEY="sk-xxx"` (read automatically when `llm.api_key` in `geo_config.yaml` is left empty)
   - Or fill in `llm.api_key` / `base_url` / `model` directly in `geo_config.local.yaml`

### ▶️ Usage

```bash
# CLI — GEO-readiness analysis / full optimization / multi-platform export
geo-optimizer analyze https://example.com
geo-optimizer optimize https://example.com
geo-optimizer export  https://example.com
geo-optimizer eval    https://example.com -k "keyword1,keyword2"
geo-optimizer check   https://example.com
geo-optimizer report  https://example.com

# Web multi-user platform (port 5000 by default; use 5001 on macOS if 5000 is taken)
geo-web --host 127.0.0.1 --port 5001

# MCP server (streamable-HTTP, defaults to 127.0.0.1:8000/mcp)
python -m mcp_server
```

> Without the entry scripts, run modules directly: `python -m geo_optimizer analyze <url>`.

---

## 💻 Command Reference

| Command | Purpose | Common options |
|---|---|---|
| `analyze` | Crawl page + GEO-readiness analysis | `-o` output dir, `-f` markdown/html/json, `-v` verbose |
| `optimize` | Full optimization (crawl → analyze → LLM optimize → FAQ → Schema) | |
| `export` | Optimization + multi-platform export (6 platforms) | |
| `faq` / `schema` | Generate FAQ only / Schema only | |
| `eval` | Multi-engine GEO performance evaluation | `-k` keywords, `-e` engines, `--no-check` skips index detection |
| `check` | Index status check (HTTPS / robots / sitemap) | |
| `monitor` | Engine citation monitoring | `-i` interval in days, `--notify` |
| `report` | Comprehensive analysis report | `-f` markdown/html, `-o` output dir |
| `full` | Complete pipeline (optimize + export + monitor) | |

---

## 📊 Scoring Dimensions

### Chinese engines (5 dimensions)

| Dimension | What is assessed | Weight |
|------|---------|------|
| Content quality | E-E-A-T, originality, domain depth | 30% |
| Structured data | Schema markup, FAQ formatting, tables | 20% |
| Citation readiness | Data sourcing, authoritative references, verifiability | 20% |
| AI crawler compatibility | robots.txt rules, load speed, mobile adaptation | 15% |
| User experience | Page structure, readability, interaction design | 15% |

### Global engines (6 dimensions)

| Dimension | What is assessed | Weight |
|------|---------|------|
| Content Quality | Originality, depth, E-E-A-T | 25% |
| Citation Readiness | Citation formats, data sources, endorsements | 20% |
| Structured Data | JSON-LD, FAQ Schema, Article Schema | 15% |
| AI Crawler Compatibility | GPTBot/CCBot/Claude-Web rules | 15% |
| User Experience | Core Web Vitals, mobile friendliness | 15% |
| Platform Optimization | Content formats, multilingual support | 10% |

---

## 📤 Multi-Platform Export

One analysis run produces six platform-ready drafts in the artifact directory:

| Platform | File prefix |
|---|---|
| WeChat Official Account | `wechat_*` |
| Zhihu | `zhihu_*` |
| Toutiao | `toutiao_*` |
| Medium | `medium_*` |
| Quora | `quora_*` |
| Reddit | `reddit_*` |

---

## 🔧 Configuration Reference

### geo_config.yaml (CLI / core library)

```yaml
target:
  url: "https://example.com"
  crawl_depth: 3
  max_pages: 50
keywords:
  zh: { primary: [], longtail: [], scenarios: [] }
  en: { primary: [], longtail: [], scenarios: [] }
llm:
  api_key: ""            # Falls back to env DASHSCOPE_API_KEY
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen-plus"     # qwen-plus / qwen-max etc.
  temperature: 0.7
  max_tokens: 4096
playwright:
  headless: true
  timeout_ms: 30000
  wait_until: "domcontentloaded"   # Most robust option for instrumented sites
  settle_ms: 3000
```

### Environment variables

| Variable | Description |
|------|------|
| `GEO_CONFIG` | Config file path (defaults to `geo_config.yaml`) |
| `DASHSCOPE_API_KEY` | Bailian / OpenAI-compatible API key |
| `OPENAI_API_KEY` | OpenAI API key (optional, for global engines) |

### Web platform configuration

- Copy `deployment/settings.example.py` → `deployment/settings.py` (gitignored) and fill in the MySQL connection, `SECRET_KEY` and default admin account.
- Environment variables with the `GEO_` prefix override same-named settings (e.g. `GEO_DB_PASSWORD`, `GEO_GTM_CONTAINER`).
- AI compute (key / base URL / model) is maintained and persisted on the **admin configuration page**, supporting multiple sources with a priority chain — no environment changes needed.
- `GTM_CONTAINER` holds the Google Tag Manager container ID for site-wide traffic measurement; leaving the default placeholder `GTM-XXXXXXX` injects no real tracking, so replace it with your own container ID when you want measurement.

### MCP server environment variables

| Variable | CLI flag | Default | Description |
|---|---|---|---|
| `GEO_BASE_URL` | — | `http://localhost:5000` | Platform open-API address |
| `GEO_API_KEY` | — | none | Default server-side key (starts with `geo_`) |
| `GEO_MCP_HOST` | `--host` | `127.0.0.1` | Bind address |
| `GEO_MCP_PORT` | `--port` | `8000` | Bind port |
| `GEO_MCP_PATH` | `--path` | `/mcp` | Mount path |
| `GEO_MCP_ALLOWED_HOSTS` | — | loopback | Required behind a reverse proxy with a public domain (DNS-rebinding protection) |

---

## 🔌 MCP Server

`mcp_server/` exposes 8 tools over streamable-HTTP so any MCP client can drive the platform:

`geo_submit_task` · `geo_list_tasks` · `geo_get_task_status` · `geo_get_task_logs` · `geo_get_task_result` · `geo_cancel_task` · `geo_get_usage` · `geo_download_report`

```bash
python -m mcp_server                                  # Defaults to 127.0.0.1:8000/mcp
python -m mcp_server --host 0.0.0.0 --port 8000       # Externally reachable
python -m mcp_server --transport stdio                # Local stdio mode
```

> See [`mcp_server/README.md`](mcp_server/README.md) for details.

## 🧩 Agent SKILL

`docs/geo-skill/` is a ClawHub-format skill package: a natural-language prompt such as "please evaluate the site www.example.com" triggers it; the client scripts submit a task and then poll status and results on demand rather than on a timer.

- `SKILL.md` — Skill definition and interaction pattern
- `scripts/geo_skill_client.py` · `geo_skill_api.py` · `geo_skill_common.py` — Submit / query / download

---

## 📦 Deployment Guide

### 🐳 Docker (recommended, one command for the full stack)

The image bundles Python 3.12 + Chromium and orchestrates **Web platform + MySQL 8.4** (schema creation and admin bootstrap run on first start):

```bash
docker compose up -d
# Add the MCP server on the same host (optional profile):
docker compose --profile mcp up -d
```

Then open `http://localhost:5000`. Default ports: Web 5000, MCP 8000, MySQL 3307 on the host.
Before any production deployment, change the secrets in `docker-compose.yml`:

| Environment variable | Description |
|---|---|
| `GEO_SECRET_KEY` | Flask session secret (must change) |
| `GEO_ADMIN_PASSWORD` | Admin password created on first init (must change) |
| `GEO_DB_PASSWORD` / `MYSQL_PASSWORD` | Database password, must match in both places (must change) |
| `DASHSCOPE_API_KEY` | LLM API key (can also be configured in the admin UI after login) |
| `GEO_GTM_CONTAINER` | GTM container ID; keep the placeholder if you don't need tracking |

- Build args are tuned for mainland-China networks and can be overridden with `--build-arg`: `PIP_INDEX`, `APT_MIRROR`, `PLAYWRIGHT_DOWNLOAD_HOST`.
- Evaluation artifacts and logs bind-mount to host `./data` and `./logs`; MySQL data lives in the `mysql-data` volume.
- To just build the image without orchestration: `docker build -t geo-optimizer .`.

### 🚀 systemd + Nginx (production cloud deployment)

Both the Web platform and the MCP service run as **systemd units behind an Nginx reverse proxy**; scripts live in `deployment/`:

```bash
# 1. Initialize the database and platform accounts
cp deployment/settings.example.py deployment/settings.py   # Fill in real MySQL / SECRET_KEY
mysql < deployment/init_db.sql
python deployment/init_platform.py

# 2. Run the platform locally (gunicorn in production, run for development)
geo-web --host 127.0.0.1 --port 5000

# 3. One-shot cloud deployment (platform + MCP + Nginx sync, requires passwordless SSH in ~/.ssh/config)
bash deployment/deploy.sh
```

| Script / unit | Purpose |
|---|---|
| `deployment/deploy.sh` | One-shot platform + MCP release (package → upload → dependencies → systemd → Nginx validate & rollback) |
| `deployment/init_server.sh` | Cloud host bootstrap |
| `deployment/geotool.service` | Platform systemd unit |
| `deployment/geo-mcp.service` | MCP systemd unit |
| `deployment/nginx_geotool.conf` | Nginx reverse-proxy template (HTTPS, `/mcp` subpath, SSE buffering off) |
| `deployment/init_db.sql` | Schema creation SQL |
| `deployment/setup_mysql.sh` | MySQL 8 install + local data migration (override host/password via env) |

**First login**: the default admin is created at init time from `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `settings.py` — **change the default password immediately after logging in**.

---

## 🧪 Development Guide

```bash
pip install -e ".[dev]"
pytest tests/ -v                    # Network-dependent integration tests are skipped by default
pytest tests/ -v -m integration     # Run integration tests explicitly
```

- Tests run on an in-memory SQLite database (`tests/conftest.py`) and do not need MySQL.
- Adding an engine: extend `geo_config.yaml` → add evaluation logic in `evaluation/evaluator.py` → add scoring dimensions in `analyzer.py`.
- Code style: Python 3.10+, type annotations, docstrings, modular layout.

---

## ❓ FAQ

**Q: `Missing credentials` / API call failures?**
A: Check `llm.api_key` or the `DASHSCOPE_API_KEY` environment variable, and make sure the key matches `base_url` (Bailian general keys and Token Plan keys are not interchangeable).

**Q: Playwright reports `Executable doesn't exist`?**
A: Run `playwright install chromium`; if the download is slow, set the `PLAYWRIGHT_DOWNLOAD_HOST` mirror.

**Q: Crawling times out?**
A: For heavily instrumented sites use `wait_until: "domcontentloaded"` (the default) and raise `timeout_ms` if needed.

**Q: Unstyled pages / MCP returns 421 Invalid Host?**
A: Static asset paths are handled in `deployment/nginx_geotool.conf`; when the MCP server is exposed through a reverse proxy on a public domain, set `GEO_MCP_ALLOWED_HOSTS` / `GEO_MCP_ALLOWED_ORIGINS`.

**Q: The Web platform cannot connect to the database?**
A: Verify the MySQL settings in `deployment/settings.py` and that `init_db.sql` has been applied; hyphenated database names are escaped correctly in the connection string.

---

## 📋 Changelog

### v1.0.0 (2026-07-26)

- Initial release: evaluation across 11 AI engines, bilingual content generation, multi-platform export
- Web multi-user platform (registration approval / quotas / compute plans / task queue / audit)
- MCP server (streamable-HTTP) and Agent SKILL package

---

## 🤝 Contributing

Issues and pull requests are welcome!

1. Fork this repository and clone your fork
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`; `feat:` / `fix:` / `docs:` prefixes are preferred)
4. Push the branch (`git push origin feature/amazing-feature`)
5. Open a pull request describing the affected components and how it was verified

Please run `pytest tests/` before committing so the suite stays green.

---

## 📜 License

This project is open-sourced under the **GNU Affero General Public License v3.0 (AGPL-3.0)**; the full text is in [LICENSE](./LICENSE).

> ⚠️ **Commercial licensing**: AGPL-3.0 also requires source disclosure when you run a modified version as a network service. If you need to embed this project in a closed-source product, SaaS integration, or want the AGPL copyleft obligations waived, request a commercial license at **`52859273@qq.com`**.

---

## 📚 References

- Aggarwal, P. et al. "GEO: Generative Engine Optimization." arXiv:2311.09735 (2024)
- Google. "Search Quality Evaluator Guidelines." (2024)
- Schema.org. "Schema.org Official Documentation." https://schema.org

## 📎 Citation

If this project is useful to you, please cite it:

```bibtex
@software{geo_optimizer,
  title  = {GEO-Optimizer: Generative Engine Optimization Toolchain},
  author = {GEO-Optimizer},
  year   = {2026},
  url    = {https://github.com/duducat2026/geo-optimizer},
  license = {AGPL-3.0}
}
```

See [`CITATION.cff`](./CITATION.cff). Chinese documentation lives in [`README.zh-CN.md`](README.zh-CN.md) and [`docs/user-guide.md`](docs/user-guide.md).

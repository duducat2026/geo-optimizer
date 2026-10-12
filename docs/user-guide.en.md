# GEO-Optimizer User Guide

> This document is the English version. 简体中文版本：[docs/user-guide.md](user-guide.md) · [README.md](https://github.com/duducat2026/geo-optimizer/blob/main/README.md) (English) · [Landing page](https://duducat2026.github.io/geo-optimizer/index.en.html)
> This guide shows how to run GEO (Generative Engine Optimization) evaluations through the **web console** and the **open API**.

---

## Contents

1. [Platform overview](#1-platform-overview)
2. [Quick start](#2-quick-start)
3. [Console walkthrough](#3-console-walkthrough)
4. [Open API guide](#4-open-api-guide)
5. [CLI toolchain](#5-cli-toolchain)
6. [Skill client (AI agent integration)](#6-skill-client-ai-agent-integration)
7. [FAQ](#7-faq)

---

## 1. Platform overview

GEO-Optimizer is a Generative Engine Optimization platform for AI search engines. Core capabilities:

| Capability | Description |
|------|------|
| Website crawling & analysis | Playwright-driven, supports JS-rendered pages |
| Dual-engine GEO scoring | 5 dimensions for Chinese engines + 6 for global engines |
| 11 engines covered | Doubao, Tongyi Qianwen, Hunyuan, ChatGLM, DeepSeek + Google AI Overviews, ChatGPT Search, Perplexity, Claude, Copilot, Gemini |
| LLM content optimization | Generates FAQ, Schema and platform-adapted content automatically |
| Multi-platform export | WeChat, Zhihu, Toutiao, Medium, Quora, Reddit |
| Rank monitoring | Continuous tracking of AI engine citation ranks |

**User roles:**
- **Admin** — system configuration, user management, full data access, audit log, quota management
- **User** — evaluation tasks, history management, report download, API key management, compute configuration

---

## 2. Quick start

### 2.1 Open the platform

Point your browser at the platform address (`http://localhost:5001` by default) to reach the login page.

### 2.2 Sign in

- Default administrator account: `admin` / `admin123`
- Regular user accounts are created by an admin in the backend

### 2.3 Your first evaluation

1. After signing in, click **New evaluation** in the left menu
2. Enter the target website URL (e.g. `https://example.com`)
3. Choose the task type:
   - **eval** — GEO score report only
   - **plan** — score + improvement plan + multi-platform content + ZIP bundle download
4. Click **Submit**; you are redirected to the task detail page
5. Wait for completion (typically 30-120 seconds), then review the scores and report

---

## 3. Console walkthrough

### 3.1 Dashboard

**Admin view:**
- Overall totals: users, tasks, plans
- The 5 most recent evaluation tasks

**User view:**
- Personal summary: my task count, remaining quota
- The 10 most recent evaluation records

### 3.2 New evaluation (/eval/new)

| Field | Description |
|------|------|
| Target URL | Required — the site to evaluate |
| Task type | `eval` (score only) / `plan` (score + improvement plan) |

**Constraints:**
- Submission is blocked when the quota is exhausted (ask an admin to raise it)
- Up to 3 concurrent tasks per user
- Tasks queue automatically when the global concurrency limit is reached
- A usable compute configuration is required (user-side or platform-side)

### 3.3 Task detail (/eval/<task_id>)

After submission you land on the detail page, which shows:

- **Status bar** — queued → running → completed/failed
- **Live progress** — percentage plus the current step description
- **Processing log** — reverse chronological, refreshed every 3 seconds
- **Scores** — once finished: overall score, Chinese/global split, per-dimension breakdown
- **Actions**:
  - Queued/running → **Cancel task**
  - Failed/cancelled → **Retry**
  - Completed (`plan`) → **View improvement plan**, **Download report ZIP**

### 3.4 Evaluation history (/history)

- Paginated list of all tasks (10/20/50 per page)
- Each row shows URL, type, status, score, creation time
- Actions: view details, delete (cascades to plans, artifacts and logs)

### 3.5 Improvement plan (/plan/<task_id>)

Generated when a `plan` task completes:

- **Plan item list** — grouped by priority (high/mid/low)
- **Item tags** — the target AI engines for each item (e.g. "fits: Doubao, ChatGPT")
- **Inline editing** — click an item to edit its content
- **Artifact management** (/plan/<task_id>/artifacts):
  - Browse generated artifacts (FAQ, Schema, platform articles)
  - Edit artifact content online
  - Generate artifacts that have not been created yet
  - Download individually or as a bundle

### 3.6 API key management (/api-keys)

Keys used for open API calls:

1. **Generate** — provide a name + validity period (1-3650 days) to receive a key starting with `geo_`
   > ⚠️ The plaintext key is displayed only once, at generation time. Store it safely.
2. **List** — shows prefix, name, call count and status for every key
3. **Regenerate / delete** — *regenerate* replaces the key content and invalidates the old one immediately; *delete* removes the key and its call log
4. **Call details** — click a key to see its paginated call log

### 3.7 Compute configuration (/llm-config)

Users may configure their own LLM compute:

| Plan | Base URL | API key format |
|---------|----------|-------------|
| Bailian pay-as-you-go | `https://dashscope.aliyuncs.com/compatible-mode/v1` | starts with `sk-` |
| Token Plan (team) | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` | starts with `sk-sp-` |
| Custom MaaS | enter your own | depends on the endpoint |

**Steps:**
1. Click **Add configuration** → pick a plan → enter the API key → save
2. Click **Activate** to make it the current compute source
3. Click **Test** to verify connectivity
4. Multiple configurations are allowed, but only one is active at a time

**Compute priority:** user-side compute > platform-side compute

### 3.8 Administrator features

#### System configuration (/admin/config)
- Configure platform-side LLM parameters (provider/api_key/base_url/model/temperature/max_tokens)
- Presets for Bailian, Token Plan and custom endpoints

#### User management (/admin/users)
- Create users (username/password/role/quota)
- Adjust user quotas
- Enable or disable accounts
- Toggle whether a user may use platform compute

#### Site overview (/admin/sites)
- Paginated list of every evaluated site across users
- Pagination with 10/20/50 rows per page

#### Audit log (/admin/audit)
- All operation records (login, evaluation, download, deletion, configuration changes)

#### User compute management (/admin/user-llm)
- Paginated view of each user's compute configurations
- Fuzzy search by account name
- Filter by date range

### 3.9 Optimization guide (/guide)

Built-in AI engine onboarding guide:
- Webmaster submission entry points per engine (Google/Bing/Perplexity/Baidu/Shenma)
- How Chinese AI models index content (Qianwen/Doubao/Hunyuan/Wenxin)
- robots.txt configuration examples
- A prioritized action checklist

### 3.10 Language switching

The UI is available in Chinese and English: use the language button in the top navigation bar (`/lang/zh` or `/lang/en`).

---

## 4. Open API guide

### 4.1 Authentication

Every API request must carry a Bearer token:

```
Authorization: Bearer geo_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Generate keys on the console's **API key management** page.

### 4.2 Endpoint reference

| Method | Path | Description |
|------|------|------|
| POST | `/api/v1/tasks` | Submit an evaluation task |
| GET | `/api/v1/tasks/{task_id}` | Query task status |
| GET | `/api/v1/tasks/{task_id}/result` | Fetch task result |
| GET | `/api/v1/tasks/{task_id}/download` | Download the report ZIP |
| POST | `/api/v1/tasks/{task_id}/cancel` | Cancel a task |
| GET | `/api/v1/usage` | API usage statistics |

### 4.3 End-to-end flow

#### Step 1: submit a task

```bash
curl -X POST http://localhost:5001/api/v1/tasks \
  -H "Authorization: Bearer geo_your_key" \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "task_type": "plan"}'
```

Response (201):
```json
{
  "task_id": "67dcbe3c-6bfb-47fa-8856-de467a39cefc",
  "status": "pending",
  "target_url": "https://example.com",
  "task_type": "plan",
  "queued": false,
  "message": "Task submitted successfully"
}
```

#### Step 2: poll the status

```bash
curl http://localhost:5001/api/v1/tasks/67dcbe3c-... \
  -H "Authorization: Bearer geo_your_key"
```

Response (200):
```json
{
  "task_id": "67dcbe3c-...",
  "status": "running",
  "progress": 60,
  "message": "generating_plan",
  "overall_score": 0.0
}
```

Status transitions: `queued` → `pending` → `running` → `completed` / `failed` / `cancelled`

#### Step 3: fetch the result

```bash
curl http://localhost:5001/api/v1/tasks/67dcbe3c-.../result \
  -H "Authorization: Bearer geo_your_key"
```

Response (200, only when completed):
```json
{
  "task_id": "67dcbe3c-...",
  "status": "completed",
  "overall_score": 72.5,
  "result": {
    "url": "https://example.com",
    "title": "Example Domain",
    "overall_score": 72.5,
    "engine_scores": [...],
    "strengths": [...],
    "weaknesses": [...]
  },
  "download_url": "/api/v1/tasks/67dcbe3c-.../download"
}
```

#### Step 4: download the report

```bash
curl -o report.zip http://localhost:5001/api/v1/tasks/67dcbe3c-.../download \
  -H "Authorization: Bearer geo_your_key"
```

ZIP contents (`plan` tasks):
- `geo_analysis_report.md` — full analysis report
- `schema.jsonld.html` — Schema.org structured data
- `wechat_*.md` / `zhihu_*.md` / `toutiao_*.md` — Chinese platform articles
- `medium_*.md` / `quora_*.md` / `reddit_*.md` — international platform articles
- `plan_items/` — improvement items grouped by priority

### 4.4 Cancelling a task

```bash
curl -X POST http://localhost:5001/api/v1/tasks/67dcbe3c-.../cancel \
  -H "Authorization: Bearer geo_your_key"
```

### 4.5 Error codes

| HTTP status | error field | Meaning |
|-----------|-----------|------|
| 400 | invalid_params | `target_url` missing |
| 401 | missing_token / invalid_token | Key absent or invalid |
| 403 | quota_exceeded | Quota exhausted |
| 403 | forbidden | No access to another user's task |
| 404 | not_found | Task does not exist |
| 409 | invalid_state | A completed task cannot be cancelled |
| 429 | concurrent_limit | Concurrent task limit reached |

### 4.6 Python client

```python
from client.geo_api_client import GeoApiClient

with GeoApiClient("http://localhost:5001", "geo_your_key") as client:
    # submit a task
    task_id = client.submit_task("https://example.com", task_type="plan")

    # wait for completion (polls automatically)
    result = client.wait_for_completion(task_id, timeout=600)
    print(f"GEO Score: {result['overall_score']}")

    # download the report
    client.download(task_id, "./output/report.zip")

    # check usage
    usage = client.get_usage()
    print(f"Total calls: {usage['total_calls']}")
```

---

## 5. CLI toolchain

Best for local development and debugging — no web service required.

### 5.1 Installation

```bash
pip install -e .
# or, without installing: python -m geo_optimizer <subcommand>
```

### 5.2 Command reference

| Command | Description |
|------|------|
| `geo-optimizer analyze <URL>` | Crawl + GEO analysis |
| `geo-optimizer optimize <URL>` | Full optimization pipeline |
| `geo-optimizer export <URL>` | Optimization + multi-platform export |
| `geo-optimizer report <URL>` | Generate the analysis report |
| `geo-optimizer faq <URL>` | Generate FAQ only |
| `geo-optimizer schema <URL>` | Generate Schema only |
| `geo-optimizer monitor <URL>` | Engine citation monitoring |

### 5.3 Environment variables

| Variable | Description |
|------|------|
| `DASHSCOPE_API_KEY` | Bailian API key |
| `GEO_CONFIG` | Config file path (defaults to `geo_config.yaml`) |

### 5.4 Examples

```bash
# full analysis and export
export DASHSCOPE_API_KEY=sk-xxxxx
geo-optimizer export https://example.com

# scoring only
geo-optimizer analyze https://example.com
```

---

## 6. Skill client (AI agent integration)

A thin client for AI agents that completes submit → wait → result → download in one go.

### 6.1 Getting the skill files

Publicly available (no login required):
- SKILL.md: `http://<host>:5001/geo-skill`
- Client: `http://<host>:5001/geo-skill/geo_skill_client.py`

### 6.2 Usage

```python
import sys
sys.path.insert(0, "docs/geo-skill/scripts")
from geo_skill_client import GeoSkillClient

client = GeoSkillClient("http://localhost:5001", "geo_your_key")

# submit → wait for completion → download the report
task_id = client.submit("https://example.com", task_type="plan")
result = client.wait_and_get_result(task_id, timeout=600)
print(f"Score: {result['overall_score']}")
client.download(task_id, "./output/report.zip")
```

### 6.3 CLI mode

By default a submission returns immediately (non-blocking, no scheduled polling); progress checks are initiated by the operator. Use `--wait` in an interactive terminal to block:

```bash
# submit (returns at once, printing the evaluated site, task ID and expected duration)
python docs/geo-skill/scripts/geo_skill_client.py \
  --base-url http://localhost:5001 \
  --api-key geo_your_key \
  --url https://example.com

# list recently submitted tasks (ID / site / status) to decide which one to query
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key --recent

# query progress of a task (status + new log lines; results and a login-free download link once completed)
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --progress <task_id> --after-id 0

# download the bundle of a completed task
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --progress <task_id> --output ./report.zip

# blocking end-to-end flow in an interactive terminal
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --url https://example.com \
  --wait --output ./report.zip

# query an existing task's status
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --status <task_id>
```

---

## 7. FAQ

### Q: I was told the quota is insufficient when submitting a task.
A: Ask an administrator to raise your evaluation quota under user management.

### Q: My task stays in `queued`.
A: The global concurrency limit is reached, so the task waits. It starts automatically once capacity frees up.

### Q: How do I retry a failed task?
A: Click **Retry** on the task detail page, or cancel through the API and submit again.

### Q: I lost my API key.
A: The plaintext key is shown only once at generation time. Regenerate that key, or delete it and create a new one.

### Q: Which compute plan should I choose?
A: Priority is user-side > platform-side. If you configured your own compute under /llm-config, it is used first; otherwise the platform falls back to the admin-configured compute.

### Q: What is the difference between `eval` and `plan`?
A: `eval` produces only the score report. `plan` additionally generates the improvement plan, FAQ, Schema and six platform articles, bundled as a ZIP.

### Q: Which AI engines are evaluated?
A: Five Chinese engines (Doubao, Tongyi Qianwen, Hunyuan, ChatGLM, DeepSeek) plus six global ones (Google AI Overviews, ChatGPT Search, Perplexity, Claude, Copilot, Gemini) — 11 in total.

### Q: Which languages does the platform support?
A: Chinese and English. Switch from the top navigation bar; the preference is saved per user.

---

*Document version: 1.0.0 | Updated: 2026-10-12 | Applies to platform version: 1.0.0*

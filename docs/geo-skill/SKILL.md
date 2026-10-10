---
name: geo-optimizer
description: >-
  Submit GEO (Generative Engine Optimization) analysis tasks to the GEO-Optimizer
  platform, check progress on demand, and fetch optimization reports. Use this skill
  whenever users ask to evaluate, analyze or score a website in natural language
  — e.g. "请评估网站 www.aliyun.com", "分析一下 example.com 的 GEO 表现",
  "evaluate website example.com" — or want AI search engine visibility checks,
  GEO scores across 11 AI engines, optimization plans, or multi-platform content
  packages. Submitted tasks default to full analysis (evaluation + optimization
  plan). IMPORTANT agent workflow — (1) Submit: run the client with `--url <site>`;
  it submits and returns immediately, printing the site, task id and estimated
  wait minutes — relay those to the user and STOP; never poll on a timer.
  (2) When the user asks for progress: run `--recent` to list recent task ids and
  sites, ask the user to clarify which task id (skip asking if only one candidate),
  then run `--progress <task_id>` — it returns the current status plus all
  execution logs produced so far. (3) If the task is completed, `--progress`
  returns the final scores and the no-login download link for the optimization
  plan package (or pass `--output <file.zip>` to download the archive directly).
  All client output is in Chinese; surface it to the user as-is.
version: 1.8.4
metadata:
  openclaw:
    requires:
      bins:
        - python3
    primaryEnv: GEO_API_KEY
    envVars:
      - name: GEO_API_KEY
        required: false
        description: GEO-Optimizer API key (starts with "geo_"). Falls back to the bundled config.json when unset.
      - name: GEO_BASE_URL
        required: false
        description: GEO-Optimizer platform base URL. Falls back to config.json, then http://localhost:5001.
      - name: GEO_POLL_INTERVAL
        required: false
        description: Task status poll interval in seconds. Falls back to config.json poll_interval, then 6.
    install:
      - kind: uv
        package: httpx
    emoji: "📈"
---
# GEO-Optimizer Skill

Analyze websites for AI search engine (GEO) readiness via the GEO-Optimizer platform API. Covers 11 AI engines: Doubao, Qwen, Hunyuan, Zhipu, DeepSeek, Google AI, ChatGPT Search, Perplexity, Claude, Copilot, Gemini.

## Prompt Triggers

Invoke this skill directly from natural-language prompts. Extract the website from the
prompt and run the evaluation — no extra questions needed unless the URL is missing:


| User prompt (example)                       | Action                                   |
| ------------------------------------------- | ---------------------------------------- |
| 请评估网站 www.aliyun.com                    | `plan` task on `https://www.aliyun.com`  |
| 分析一下 example.com 的 GEO 表现            | `plan` task on `https://example.com`     |
| 评估 example.com 并生成优化方案             | `plan` task (score + plan + content)     |
| Evaluate website example.com                | `plan` task                              |
| 只要评分 / score only for example.com       | `eval` task (score only)                 |
| Analyze example.com and download the report | `plan` task with `--output`              |

Execution recipe — every command below returns immediately; there is NO timed
polling loop (progress checks are user-initiated; blocking requires an explicit
`--wait`, which must never be used inside an agent):

```bash
# 1. Submit — prints the site, task id and estimated wait minutes, then exits.
#    Relay those three facts to the user and STOP (do not poll on a timer).
python scripts/geo_skill_client.py --url www.aliyun.com

# 2. When the user asks "进展如何/查一下任务": list recent tasks (id + site + status).
#    Shows total count + one page (10 per page). Ask WHICH task id to check
#    (skip asking if only one candidate). Use --page/--limit to paginate and
#    --start/--end (YYYY-MM-DD, end inclusive) to filter by submit date.
python scripts/geo_skill_client.py --recent
python scripts/geo_skill_client.py --recent --page 2 --limit 10
python scripts/geo_skill_client.py --recent --start 2026-07-01 --end 2026-07-31

# 3. Check the chosen task — returns current status + all logs produced so far.
python scripts/geo_skill_client.py --progress <task_id> --after-id 0

# 4. If completed, --progress prints the final scores and the no-login download
#    link for the optimization plan package; add --output to save the ZIP locally.
python scripts/geo_skill_client.py --progress <task_id> --output report.zip

# 5. If the user wants to STOP a task (queued or still running), cancel it.
python scripts/geo_skill_client.py --cancel <task_id>
```

Notes:

- Bare domains are accepted — the client auto-prepends `https://` (e.g.
  `www.aliyun.com` → `https://www.aliyun.com`).
- Default task type is `plan` (evaluation + optimization plan + multi-platform
  content); only use `eval` when the user explicitly asks for a score-only check.
- Right after submission, the client prints the evaluated site, the task id and
  the estimated wait (about 5 minutes for `plan`, 2 minutes for `eval`) — relay
  all three to the user, then STOP. Do NOT run a timed polling loop.
- Progress checks are user-initiated: when the user asks, run `--recent` first.
  It lists the CURRENT API key account's recently submitted tasks with their
  FULL task ids (never truncated), evaluated sites, status and progress, plus
  the total task count. It returns 10 per page by default — use `--page <n>`
  and `--limit <1-50>` to paginate, and `--start`/`--end` (YYYY-MM-DD or ISO
  time; `end` bare date includes that whole day) to filter by submit date. Ask
  the user to clarify which task id to check (if only one task is plausible,
  proceed with it directly). Then run `--progress <task_id>` with the full id —
  it returns the task status AND every execution log line produced so far (use
  `--after-id <last_id>` to fetch only newer lines on repeated checks), then
  exits immediately.
- If the specified task is already completed, `--progress` returns the result
  info: overall/domestic/international scores plus the no-login share download
  link (`[下载链接] 生成与改进方案...`) for the optimization plan package — give
  that link to the user, or pass `--output <file.zip>` to download the archive.
- Besides cloud logs (`[云端日志 ...]`), the client prints its own execution log
  lines (`[客户端 HH:MM:SS] ...`) for every step — credential resolution, each
  HTTP request with status code and latency, and failures (e.g. TLS errors) —
  surface them to the user so the local call chain is fully visible.
- When the task reaches a final state, the `--progress` output shows the overall
  GEO score (0-100), domestic/international scores, the share download link, and
  downloads the report if `--output` was given — present this final summary to the user.
- All client output is already in Chinese; show it to the user as-is.
- To STOP a task the user no longer wants, run
  `python scripts/geo_skill_client.py --cancel <task_id>` (works while the task
  is queued or running; a queued task is cancelled immediately, a running task
  is cancelled cooperatively at its next checkpoint — crawling/LLM stages finish
  the current step first). Already-finished tasks (completed/failed/cancelled)
  cannot be cancelled and the client prints `[终止失败] ...`. Cancelling a task
  refunds its daily quota; the task can later be re-run by submitting again.

## Skill Layout

```
geo-optimizer/
├── SKILL.md                    # This file
├── .clawhubignore              # Excludes config.json from publishing
├── config.json                 # Personal credentials (exported packs only, never publish)
└── scripts/                    # Client modules (each file kept under 300 lines)
    ├── geo_skill_client.py     # CLI entry point (also re-exports the library API)
    ├── geo_skill_api.py        # GeoSkillClient class (platform API wrapper)
    └── geo_skill_common.py     # Config resolution, helpers, GeoSkillError
```

## Prerequisites

- Python 3.10+
- `httpx` package (`pip install httpx` or `uv pip install httpx`)
- A running GEO-Optimizer platform instance
- A valid API key (starts with `geo_`)

## Configuration

Credentials are resolved in this order (highest priority first):

1. Explicit arguments (`GeoSkillClient(base_url, api_key)` or CLI `--base-url` / `--api-key`)
2. Environment variables `GEO_API_KEY` and `GEO_BASE_URL`
3. `config.json` in the skill root (bundled automatically in packs exported from the platform)

`config.json` format:

```json
{
  "base_url": "https://your-geo-optimizer-host",
  "api_key": "geo_your_api_key_here",
  "key_name": "my-key",
  "key_prefix": "geo_xxxx",
  "poll_interval": 6
}
```

`poll_interval` sets the task status polling interval in seconds (default 6).
Priority: CLI `--poll-interval` > env `GEO_POLL_INTERVAL` > config.json > 6.

> **Security note:** `config.json` contains your plaintext API key. It is listed in
> `.clawhubignore` so it is never uploaded if you publish this skill to ClawHub.
> Do not remove that ignore entry or commit `config.json` to a public repository.

## Quick Start

```python
import sys
sys.path.insert(0, "<path-to-skill>/scripts")
from geo_skill_client import GeoSkillClient

# Auto-resolve credentials from env vars / config.json
client = GeoSkillClient.from_config()

# Or pass credentials explicitly
client = GeoSkillClient(
    base_url="http://localhost:5001",
    api_key="geo_your_api_key_here"
)

# Submit a full analysis task (default: evaluation + optimization plan).
# submit() returns immediately after the task is queued — it does NOT wait for
# the analysis to finish. It prints the site, task id and estimated minutes.
task_id = client.submit("https://www.aliyun.com")
print(f"Task submitted: {task_id}")

# Do NOT block waiting for completion inside an agent. Check progress on demand:
status = client.get_status(task_id)           # current status + progress
log_data = client.get_logs(task_id, after_id=0)  # execution logs produced so far

# Once status is "completed", fetch the result and download the package:
if status["status"] == "completed":
    result = client.get_result(task_id)
    print(f"GEO Score: {result['overall_score']}/100")
    client.download(task_id, "./output/report.zip")

# (Interactive terminals ONLY) block until done — never do this inside an agent:
# result = client.wait_and_get_result(task_id, timeout=600)
```

## Workflow

This skill operates in a 4-step workflow:

### Step 1: Submit Task

```python
task_id = client.submit(target_url)  # task_type defaults to "plan"
```

**Parameters:**

- `target_url` (required): The website URL to analyze; bare domains like
  `www.aliyun.com` are auto-normalized to `https://www.aliyun.com`
- `task_type`: `"plan"` (default — score + optimization plan + multi-platform content) or `"eval"` (score only)

**Returns:** `task_id` string. After submission the client prints the estimated
minutes until results are ready (about 5 min for `plan`, 2 min for `eval`).

### Step 2: Monitor Progress (on demand — never on a timer)

```python
status = client.get_status(task_id)
# status: {"status": "running", "progress": 45, "message": "..."}
```

**Status values:** `queued` → `running` → `completed` / `failed` / `cancelled`

Check progress only when the user asks. `get_status()` returns the current
status/progress and `get_logs(task_id, after_id=N)` incrementally fetches the
platform's task execution logs (translated, e.g. "页面爬取完成，耗时: 5321ms")
so the user can follow the cloud-side pipeline. Each call returns immediately:

```python
log_data = client.get_logs(task_id, after_id=0)
# {"logs": [{"id": 1, "level": "info", "message": "任务已创建", "detail": "...", "time": "07-30 09:00:01"}],
#  "last_id": 1, "status": "running", "progress": 10}
```

> `wait_and_get_result()` BLOCKS the process, polling every 6s until the task
> finishes (up to `timeout` seconds). Use it ONLY in interactive terminals —
> never inside an agent, or the command appears to hang until completion.

### Step 3: Get Results

```python
result = client.get_result(task_id)
# result: {"overall_score": 72, "result": {...}, "download_url": "..."}
```

**Result structure:**

- `overall_score`: 0-100 composite GEO score
- `result.domestic_score`: Domestic 5-dimension score
- `result.international_score`: International 6-dimension score
- `result.dimensions`: Per-dimension breakdown
- `result.engines`: Per-engine evaluation details
- `download_url`: ZIP package download path (plan tasks only, Bearer auth required)
- `share_download_url`: no-login share link for the optimization plan package
  (link itself is the credential; safe to hand to the user directly)

### Step 4: Download Report

```python
path = client.download(task_id, "./output/geo_report.zip")
```

**ZIP contents (plan task):**

- `geo_analysis_report.md` — Full analysis report
- `schema.jsonld.html` — Schema.org structured data
- `wechat_*.md` — WeChat article
- `zhihu_*.md` — Zhihu article
- `toutiao_*.md` — Toutiao article
- `medium_*.md` — Medium article
- `quora_*.md` — Quora answer
- `reddit_*.md` — Reddit post
- `plan_items/` — Prioritized action items

## CLI Usage

Credentials from env vars or `config.json` are picked up automatically:

```bash
# Agent step-wise mode (default): submit returns immediately; progress checks are user-initiated
python scripts/geo_skill_client.py --url www.aliyun.com
python scripts/geo_skill_client.py --recent
python scripts/geo_skill_client.py --progress <task_id> --after-id 0
python scripts/geo_skill_client.py --progress <task_id> --output ./report.zip

# Blocking full flow (interactive terminals ONLY — never inside an agent)
python scripts/geo_skill_client.py --url www.aliyun.com --wait --output ./report.zip

# Explicit credentials
python scripts/geo_skill_client.py \
  --base-url http://localhost:5001 \
  --api-key geo_your_key \
  --url https://www.aliyun.com

# Score-only evaluation
python scripts/geo_skill_client.py --url https://www.aliyun.com --type eval

# Query an existing task
python scripts/geo_skill_client.py --status <task_id>
```

## API Reference


| Method | Endpoint                      | Description          |
| ------ | ----------------------------- | -------------------- |
| POST   | `/api/v1/tasks`               | Submit analysis task |
| GET    | `/api/v1/tasks`               | List recent tasks (`?limit=N`, default 10) |
| GET    | `/api/v1/tasks/{id}`          | Query task status    |
| GET    | `/api/v1/tasks/{id}/logs`     | Task execution logs (incremental via `?after_id=N`) |
| GET    | `/api/v1/tasks/{id}/result`   | Get task result      |
| GET    | `/api/v1/tasks/{id}/download` | Download ZIP report  |
| POST   | `/api/v1/tasks/{id}/cancel`   | Cancel task          |
| GET    | `/api/v1/usage`               | API usage statistics |

**Authentication:** All endpoints require `Authorization: Bearer geo_<key>` header.

## Error Handling

```python
from geo_skill_client import GeoSkillError

try:
    task_id = client.submit(url, task_type="plan")
    # Check on demand (non-blocking). Do NOT call wait_and_get_result in an agent.
    status = client.get_status(task_id)
except GeoSkillError as e:
    print(f"API Error [{e.status_code}]: {e.error} - {e.message}")
except TimeoutError as e:
    print(f"Task timed out: {e}")
```

**Common errors:**

- `401 invalid_token` — API key expired or incorrect
- `403 quota_exceeded` — Evaluation quota exhausted
- `429 concurrent_limit` — Too many concurrent tasks
- `404 not_found` — Task ID does not exist
- `503 llm_unavailable` — Computing (LLM) service unavailable for this account, contact admin

## Scoring Dimensions

**Domestic (5D):** Content Quality, Structured Data, Citation Friendliness, AI Crawler Compatibility, User Experience

**International (6D):** Content Quality, Structured Data, Citation Friendliness, AI Crawler Compatibility, User Experience, E-E-A-T Signals

## Notes

- Submitted tasks default to `plan` (evaluation + optimization plan); estimated time
  to results is about 5 minutes for `plan` and 2 minutes for `eval` — tell the user
  right after submission
- In agent environments the default `--url` submission already returns
  immediately. Never pass `--wait` inside an agent — it blocks the process until
  the task finishes and looks like an endless wait
- There is no timed polling: after submitting, report the site/task id/estimated
  minutes and stop. Check progress only when the user asks, via `--recent` (to
  clarify the task id) and `--progress <task_id>` (status + logs so far, in
  Chinese) — relay the output to the user as-is
- `plan` tasks generate LLM-powered content using configured AI models
- Maximum concurrent tasks per user: 3
- Global concurrent limit: configurable by platform admin
- Queued tasks automatically start when slots become available
- The GEO-Optimizer platform is a paid/quota-managed external service; you need an
  account and API key issued by your platform administrator

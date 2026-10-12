# GEO-Optimizer MCP Server (streamable-HTTP)

[English](README.en.md) | [简体中文](README.md)

Wraps the GEO-Optimizer platform's open API (`/api/v1/*`) as a set of **MCP tools** so any
MCP client (Claude Desktop, Cursor, Qoder, your own agent, …) can submit website GEO
evaluations in natural language, query progress and logs, fetch scores and plan download
links, cancel tasks and check usage.

The transport is **streamable-HTTP** by default, which suits remote deployment and
concurrent clients; a stdio mode is kept for single-client local debugging. Built on MCP
Python SDK **v2** (`mcp.server.mcpserver.MCPServer`).

- **Source code**: <https://github.com/duducat2026/geo-optimizer> (AGPL-3.0; closed-source commercial use requires a commercial license)
- **Documentation site**: <https://duducat2026.github.io/geo-optimizer/index.en.html>
- **Official hosted endpoint**: <https://geo.tool.jiuchongju.com/mcp> (operated by the project; self-hosting follows below)

---

## Layout

```
mcp_server/
├── __init__.py       # package exports: mcp (MCPServer instance), main (entry point)
├── __main__.py       # enables python -m mcp_server
├── server.py         # MCPServer + 8 tools + streamable-HTTP/stdio entry point
├── api_client.py     # async httpx wrapper for the GEO open API + unified error mapping
├── config.py         # credentials (base_url/api_key) and transport (host/port/path) resolution
├── formatting.py     # markdown / json response rendering
└── README.md         # Chinese documentation (this file is the English version)
```

---

## Installation

```bash
pip install "mcp[cli]>=2.1,<3" httpx pydantic
# or install everything this repository needs
pip install -r requirements.txt
```

> Python 3.10+ required. The MCP SDK v2 entry point is `MCPServer` (v1's `FastMCP` was renamed).

---

## Configuration

### Platform credentials (access to the GEO open API)

| Variable | Description | Default |
| --- | --- | --- |
| `GEO_BASE_URL` | GEO platform address | `http://localhost:5000` |
| `GEO_API_KEY` | Server-side default API key (starts with `geo_`) | none |

Alternatively place a `config.json` in `mcp_server/`, the repository root, or
`docs/geo-skill/` (searched in that order):

```json
{ "base_url": "https://your-geo-host", "api_key": "geo_your_key" }
```

### MCP transport (streamable-HTTP)

| Variable | CLI flag | Description | Default |
| --- | --- | --- | --- |
| `GEO_MCP_HOST` | `--host` | Bind address | `127.0.0.1` |
| `GEO_MCP_PORT` | `--port` | Bind port | `8000` |
| `GEO_MCP_PATH` | `--path` | Mount path | `/mcp` |
| `GEO_MCP_TRANSPORT` | `--transport` | `streamable-http` / `stdio` | `streamable-http` |

Precedence: **CLI flags > environment variables > defaults**.

---

## Starting the server (streamable-HTTP)

```bash
# Option 1: run as a package (recommended)
python -m mcp_server
# → listens on http://127.0.0.1:8000/mcp

# Option 2: run the script directly
python mcp_server/server.py --host 127.0.0.1 --port 8000 --path /mcp

# Option 3: MCP CLI (v2) —— `:mcp` points at the MCPServer object (import style)
mcp run mcp_server/server.py:mcp --transport streamable-http
# interactive debugging with the official Inspector
mcp dev mcp_server/server.py:mcp

# Externally reachable deployment (careful: put it behind a reverse proxy + TLS)
python -m mcp_server --host 0.0.0.0 --port 8000

# Local debugging in stdio mode
python -m mcp_server --transport stdio
```

The full endpoint is `http://<host>:<port><path>`, i.e. `http://127.0.0.1:8000/mcp` by default.

---

## Client integration

### Generic MCP clients (streamable-HTTP)

Most clients only need the URL:

```
http://127.0.0.1:8000/mcp
```

### Claude Desktop / Cursor / Qoder (`mcpServers` config)

A streamable-HTTP service is reached through `url` (use whatever field your client supports):

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": { "Authorization": "Bearer geo_your_key" }
    }
  }
}
```

If your client only supports spawning a local stdio process:

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "command": "python",
      "args": ["-m", "mcp_server", "--transport", "stdio"],
      "cwd": "/path/to/geo-optimizer",
      "env": { "GEO_API_KEY": "geo_your_key", "GEO_BASE_URL": "http://localhost:5000" }
    }
  }
}
```

### Python client (shipped with this SDK)

```python
import asyncio
from mcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()
        print([t.name for t in tools.tools])
        r = await client.call_tool("geo_submit_task",
                                   {"target_url": "www.aliyun.com", "task_type": "plan"})
        print(r.content[0].text)

asyncio.run(main())
```

---

## Authentication model

Resolution order for the caller's API key:

1. **Per-request header** `Authorization: Bearer geo_xxx` — each client uses its own key, which fits streamable-HTTP best
2. **Server-side default key**: the `GEO_API_KEY` environment variable or `config.json`

With neither available, tools return an actionable `missing_token` error instead of crashing.

---

## Tool reference

| Tool | Purpose | Read-only |
| --- | --- | --- |
| `geo_submit_task` | Submit a website GEO evaluation task; returns `task_id` immediately (`plan`/`eval`) | no |
| `geo_list_tasks` | List the account's recent tasks (pagination + submission time range filter) | yes |
| `geo_get_task_status` | Query task status and progress | yes |
| `geo_get_task_logs` | Fetch cloud execution logs (supports incremental `after_id` pulls) | yes |
| `geo_get_task_result` | Fetch results: overall/per-engine scores, strengths, weaknesses, download links | yes |
| `geo_cancel_task` | Cancel a queued/running task (quota is refunded) | no (destructive) |
| `geo_get_usage` | Show API call statistics | yes |
| `geo_download_report` | Download the report and plan ZIP to a local path | no (writes local files) |

Every tool accepts `response_format` (`markdown` default / `json`).

### Recommended workflow

1. `geo_submit_task(target_url="www.aliyun.com")` → get a `task_id`, **returns immediately without blocking**.
2. When the user asks about progress: `geo_get_task_status(task_id)` or `geo_get_task_logs(task_id, after_id=0)`.
3. Once complete: `geo_get_task_result(task_id)` for scores and download links; use `geo_download_report` when local files are needed.

> Never poll on a timer and block — progress checks should be user-initiated.

---

## Security notes

- Binds to `127.0.0.1` (loopback) by default to reduce DNS-rebinding risk; to expose it, terminate TLS at a reverse proxy and validate the origin.
- API keys are passed only via environment variables, `config.json` or request headers — never hard-code them or commit them to a public repository.
- If you add a `config.json`, put it in `.gitignore` (it contains a plaintext key).
- Errors are actionable for clients but never leak server-side implementation details.

---

## Cloud deployment (production)

The MCP service is part of the `deployment/deploy.sh` automation: it runs on the same host as
the platform and is exposed through Nginx under the `/mcp` subpath, reusing the main domain
and TLS certificate.

**Architecture**:

```
MCP client ─HTTPS─> Nginx(443) ─/mcp─> geo-mcp(127.0.0.1:8000)
                                            │  streamable-HTTP
                                            └─HTTP─> platform gunicorn(127.0.0.1:5000)
```

**One-shot deployment** (run from the repository root):

```bash
bash deployment/deploy.sh
```

`deploy.sh` will: package and upload → install cloud dependencies (including `mcp[cli]`) →
generate `shared/mcp.env` on first run → install and start `geo-mcp.service` → sync the
Nginx configuration (with backup and `nginx -t` validation plus rollback).

**Set the server-side default API key afterwards** (so clients without a Bearer header work out of the box):

```bash
ssh your-ssh-host-alias
vim /opt/geotool/shared/mcp.env      # put a valid GEO_API_KEY=geo_xxx here
systemctl restart geo-mcp
```

**Endpoint**: `https://geo.tool.example.com/mcp`

**Operations**:

```bash
systemctl status geo-mcp             # service status
journalctl -u geo-mcp -f             # live logs
systemctl restart geo-mcp            # required after editing mcp.env
ss -ltnp | grep 8000                 # confirm the listener
```

Related files: `deployment/geo-mcp.service` (systemd unit), `deployment/mcp.env.example`
(environment template), and the `location /mcp` block in `deployment/nginx_geotool.conf`
(SSE-friendly reverse proxy).

---

## Local smoke test

```bash
# 1) syntax / imports
python -m py_compile mcp_server/*.py

# 2) start streamable-HTTP
python -m mcp_server --port 8765 &

# 3) from another process, connect with the bundled client, list tools, call one
python - <<'PY'
import asyncio
from mcp import Client
async def main():
    async with Client("http://127.0.0.1:8765/mcp") as c:
        print(len((await c.list_tools()).tools), "tools")
        r = await c.call_tool("geo_get_usage", {"response_format": "json"})
        print(r.content[0].text)
asyncio.run(main())
PY
```

You can also test interactively with the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
# choose Streamable HTTP transport, URL http://127.0.0.1:8000/mcp
```

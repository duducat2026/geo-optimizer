# GEO-Optimizer MCP 服务端（streamable-HTTP 模式）

把 GEO-Optimizer 平台的开放 API（`/api/v1/*`）封装为一组 **MCP 工具**，让任意 MCP
客户端（Claude Desktop、Cursor、Qoder、自研 Agent 等）用自然语言提交网站 GEO 评估、
查询进度与日志、获取评分与优化方案下载链接、终止任务、查看用量。

传输模式为 **streamable-HTTP**（默认），适合远程部署与多客户端并发；亦保留 stdio
模式用于本地单客户端调试。基于 MCP Python SDK **v2**（`mcp.server.mcpserver.MCPServer`）。

- **开源地址**：<https://github.com/duducat2026/geo-optimizer>（AGPL-3.0，闭源商用需商业授权）
- **文档首页**：<https://duducat2026.github.io/geo-optimizer/>
- **官方云端端点**：<https://geo.tool.jiuchongju.com/mcp>（平台方运营，也可按下文自建）

---

## 目录结构

```
mcp_server/
├── __init__.py       # 包导出：mcp（MCPServer 实例）、main（启动入口）
├── __main__.py       # 支持 python -m mcp_server
├── server.py         # MCPServer + 8 个工具 + streamable-HTTP/stdio 启动入口
├── api_client.py     # 异步 httpx 封装 GEO 开放 API + 统一错误映射
├── config.py         # 凭据(base_url/api_key) 与 传输(host/port/path) 配置解析
├── formatting.py     # markdown / json 双格式响应
└── README.md         # 本文件
```

---

## 安装

```bash
pip install "mcp[cli]>=2.1,<3" httpx pydantic
# 或安装本仓库全部依赖
pip install -r requirements.txt
```

> 需要 Python 3.10+。MCP SDK v2 的入口是 `MCPServer`（v1 的 `FastMCP` 已重命名）。

---

## 配置

### 平台凭据（访问 GEO 开放 API）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `GEO_BASE_URL` | GEO 平台地址 | `http://localhost:5000` |
| `GEO_API_KEY` | 服务端默认 API Key（`geo_` 开头） | 无 |

也可在 `mcp_server/config.json`、仓库根 `config.json` 或 `docs/geo-skill/config.json`
放置（按此顺序查找）：

```json
{ "base_url": "https://your-geo-host", "api_key": "geo_your_key" }
```

### MCP 传输（streamable-HTTP）

| 变量 | 命令行 | 说明 | 默认 |
| --- | --- | --- | --- |
| `GEO_MCP_HOST` | `--host` | 监听地址 | `127.0.0.1` |
| `GEO_MCP_PORT` | `--port` | 监听端口 | `8000` |
| `GEO_MCP_PATH` | `--path` | 挂载路径 | `/mcp` |
| `GEO_MCP_TRANSPORT` | `--transport` | `streamable-http` / `stdio` | `streamable-http` |

优先级：**命令行 > 环境变量 > 默认值**。

---

## 启动（streamable-HTTP）

```bash
# 方式一：包方式启动（推荐）
python -m mcp_server
# → 监听 http://127.0.0.1:8000/mcp

# 方式二：直接运行脚本
python mcp_server/server.py --host 127.0.0.1 --port 8000 --path /mcp

# 方式三：MCP CLI（v2）—— 用 `:mcp` 指向 MCPServer 对象（导入式）
mcp run mcp_server/server.py:mcp --transport streamable-http
# 配合官方 Inspector 交互式调试
mcp dev mcp_server/server.py:mcp

# 对外部署（谨慎：建议置于反向代理 + TLS 之后）
python -m mcp_server --host 0.0.0.0 --port 8000

# 本地调试：stdio 模式
python -m mcp_server --transport stdio
```

启动后完整访问端点为 `http://<host>:<port><path>`，默认 `http://127.0.0.1:8000/mcp`。

---

## 客户端接入

### 通用 MCP 客户端（streamable-HTTP）

大多数客户端只需填 URL：

```
http://127.0.0.1:8000/mcp
```

### Claude Desktop / Cursor / Qoder（`mcpServers` 配置）

streamable-HTTP 服务通过 `url` 接入（以客户端实际支持的字段为准）：

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

若客户端只支持 stdio 启动本地进程，可改为：

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

### Python 客户端（本 SDK 自带）

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

## 鉴权模型

调用方 API Key 的解析优先级：

1. **每个 MCP 请求头** `Authorization: Bearer geo_xxx`（多客户端各用自己的 key，最适配 streamable-HTTP）
2. **服务端默认 key**：`GEO_API_KEY` 环境变量 / `config.json`

两者都没有时，工具返回可执行错误提示（`missing_token`），不会崩溃。

---

## 工具一览

| 工具 | 作用 | 只读 |
| --- | --- | --- |
| `geo_submit_task` | 提交网站 GEO 评估任务，立即返回 task_id（`plan`/`eval`） | 否 |
| `geo_list_tasks` | 列出当前账号最近任务（分页 + 提交时间范围过滤） | 是 |
| `geo_get_task_status` | 查询任务状态与进度 | 是 |
| `geo_get_task_logs` | 获取云端执行日志（中文，支持 `after_id` 增量拉取） | 是 |
| `geo_get_task_result` | 获取评估结果：综合/各引擎评分、优势与待改进、下载链接 | 是 |
| `geo_cancel_task` | 终止排队中/运行中的任务（退回配额） | 否（destructive） |
| `geo_get_usage` | 查看 API 调用统计 | 是 |
| `geo_download_report` | 把报告与方案 ZIP 下载到本地路径 | 否（写本地文件） |

所有工具都支持 `response_format`（`markdown` 默认 / `json`）。

### 推荐工作流

1. `geo_submit_task(target_url="www.aliyun.com")` → 拿到 `task_id`，**立即返回，不阻塞**。
2. 用户问进度时：`geo_get_task_status(task_id)` 或 `geo_get_task_logs(task_id, after_id=0)`。
3. 完成后：`geo_get_task_result(task_id)` 取评分与下载链接；需要本地文件时 `geo_download_report`。

> 切勿定时轮询阻塞——进度查询应由用户发起。

---

## 安全说明

- 默认绑定 `127.0.0.1`（回环），降低 DNS rebinding 风险；对外暴露请置于反向代理 + TLS 之后，并做来源校验。
- API Key 只经环境变量 / `config.json` / 请求头传入，切勿硬编码进代码或提交到公共仓库。
- 若放置 `config.json`，请将其加入 `.gitignore`（明文含 key）。
- 错误信息对客户端友好、可执行，但不泄露服务端内部实现细节。

---

## 云端部署（生产）

MCP 服务已纳入 `deployment/deploy.sh` 自动化部署，与平台同机运行、经 Nginx 以子路径
`/mcp` 对外（复用主站域名与 SSL 证书）。

**架构**：

```
MCP 客户端 ─HTTPS─> Nginx(443) ─/mcp─> geo-mcp(127.0.0.1:8000)
                                            │  streamable-HTTP
                                            └─HTTP─> 平台 gunicorn(127.0.0.1:5000)
```

**一键部署**（在仓库根执行）：

```bash
bash deployment/deploy.sh
```

`deploy.sh` 会自动：打包上传 → 云端装依赖（含 `mcp[cli]`）→ 生成 `shared/mcp.env`
（首次）→ 安装并启动 `geo-mcp.service` → 同步 Nginx 配置（带备份与 `nginx -t` 校验回滚）。

**部署后配置服务端默认 API Key**（让不带 Bearer 的客户端开箱即用）：

```bash
ssh your-ssh-host-alias
vim /opt/geotool/shared/mcp.env      # 填入有效的 GEO_API_KEY=geo_xxx
systemctl restart geo-mcp
```

**访问端点**：`https://geo.tool.example.com/mcp`

**运维命令**：

```bash
systemctl status geo-mcp             # 服务状态
journalctl -u geo-mcp -f             # 实时日志
systemctl restart geo-mcp            # 改 mcp.env 后重启生效
ss -ltnp | grep 8000                 # 确认监听
```

相关文件：`deployment/geo-mcp.service`（systemd 单元）、`deployment/mcp.env.example`
（环境模板）、`deployment/nginx_geotool.conf` 的 `location /mcp`（SSE 友好反代）。

---

## 本地自测

```bash
# 1) 语法/导入
python -m py_compile mcp_server/*.py

# 2) 启动 streamable-HTTP
python -m mcp_server --port 8765 &

# 3) 另开一个进程，用自带客户端连接、列工具、调用
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

也可用官方 MCP Inspector 交互测试：

```bash
npx @modelcontextprotocol/inspector
# 传输选 Streamable HTTP，URL 填 http://127.0.0.1:8000/mcp
```

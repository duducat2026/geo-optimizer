# GEO-Optimizer MCP 服务

把 GEO-Optimizer 平台的开放 API 封装为一组 **MCP 工具**（streamable-HTTP 传输），
让任意 MCP 客户端用自然语言提交网站 GEO 评估、查询进度与日志、获取评分与优化方案下载链接、终止任务、查看用量。

**线上端点**：`https://geo.tool.jiuchongju.com/mcp`（streamable-HTTP）
**本地端点**：`http://127.0.0.1:8000/mcp`（自建调试）
**开源地址**：<https://github.com/duducat2026/geo-optimizer>（AGPL-3.0，平台/MCP/SKILL 同仓库）
**English**：see the [English overview](#english-overview) at the end of this document.

---

## 产品简介

GEO-Optimizer 是面向 AI 搜索引擎的生成式引擎优化（GEO, Generative Engine Optimization）
自动化工具链，帮助网站提升内容在 AI 搜索结果中的被引用率与排名：

- **11 个 AI 引擎评估**：豆包、通义千问、混元、智谱、DeepSeek、Google AI、ChatGPT Search、Perplexity、Claude、Copilot、Gemini
- **双评分体系**：国内 5 维度 + 国外 6 维度（含 E-E-A-T 信号）
- **LLM 优化方案**：自动生成改进项清单与多平台内容包（微信/知乎/头条/Medium/Quora/Reddit）
- **结构化数据**：Schema.org JSON-LD 与 FAQ 自动生成

MCP 服务端把以上能力以工具形式开放给 Agent：提交任务立即返回 `task_id`，
进度查询由用户按需发起，结果包含综合评分与免登录下载链接。

---

## 工具列表（8 个）

| 工具 | 作用 | 只读 |
| --- | --- | --- |
| `geo_submit_task` | 提交网站 GEO 评估任务，立即返回 task_id（`plan`/`eval`） | 否 |
| `geo_list_tasks` | 列出当前账号最近任务（分页 + 提交时间范围过滤） | 是 |
| `geo_get_task_status` | 查询任务状态与进度 | 是 |
| `geo_get_task_logs` | 获取云端执行日志（中文，支持 `after_id` 增量拉取） | 是 |
| `geo_get_task_result` | 获取评估结果：综合/各引擎评分、优势与待改进、下载链接 | 是 |
| `geo_cancel_task` | 终止排队中/运行中的任务（退回配额） | 否 |
| `geo_get_usage` | 查看 API 调用统计 | 是 |
| `geo_download_report` | 把报告与方案 ZIP 下载到本地路径 | 否 |

所有工具都支持 `response_format`（`markdown` 默认 / `json`）。

### 推荐工作流

1. `geo_submit_task(target_url="www.aliyun.com")` → 拿到 `task_id`，**立即返回，不阻塞**。
2. 用户问进度时：`geo_get_task_status(task_id)` 或 `geo_get_task_logs(task_id, after_id=0)`。
3. 完成后：`geo_get_task_result(task_id)` 取评分与下载链接；需要本地文件时 `geo_download_report`。

> 切勿定时轮询阻塞——进度查询应由用户发起。

---

## 快速接入

### 通用 MCP 客户端（streamable-HTTP）

大多数客户端只需填 URL 与请求头：

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "type": "streamableHttp",
      "url": "https://geo.tool.jiuchongju.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GEO_API_KEY}"
      }
    }
  }
}
```

`${GEO_API_KEY}` 替换为你的 API Key（`geo_` 开头），在
[geo.tool.jiuchongju.com](https://geo.tool.jiuchongju.com) 控制台的「API密钥」页面创建获取。

### 本地调试（自建服务）

先在仓库根启动服务：`python -m mcp_server`，然后：

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": { "Authorization": "Bearer geo_your_key" }
    }
  }
}
```

### 鉴权模型

调用方 API Key 的解析优先级：

1. **每个 MCP 请求头** `Authorization: Bearer geo_xxx`（多客户端各用自己的 key）
2. **服务端默认 key**：`GEO_API_KEY` 环境变量 / `config.json`

两者都没有时，工具返回可执行错误提示（`missing_token`），不会崩溃。

---

## 环境变量说明

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `GEO_API_KEY` | GEO 平台 API Key（`geo_` 开头），控制台「API密钥」页获取 | 无 |
| `GEO_BASE_URL` | GEO 平台地址 | `http://localhost:5000` |
| `GEO_MCP_HOST` | MCP 服务监听地址 | `127.0.0.1` |
| `GEO_MCP_PORT` | MCP 服务监听端口 | `8000` |
| `GEO_MCP_PATH` | MCP 挂载路径 | `/mcp` |
| `GEO_MCP_TRANSPORT` | 传输模式：`streamable-http` / `stdio` | `streamable-http` |

优先级：**命令行 > 环境变量 > 默认值**。

---

## 安全说明

- API Key 只经环境变量 / `config.json` / 请求头传入，切勿硬编码进代码或提交到公共仓库。
- 若放置 `config.json`，请将其加入 `.gitignore`（明文含 key）。
- 线上端点已置于反向代理 + TLS 之后；自建对外部署时建议同样处理。

---

## 开源与自建

本 MCP 服务、Web 平台、CLI 与 SKILL 客户端均来自同一个开源仓库：

- 源码：<https://github.com/duducat2026/geo-optimizer>
- 文档/首页：<https://duducat2026.github.io/geo-optimizer/>
- 许可证：AGPL-3.0（闭源商用 / SaaS 集成请联系 52859273@qq.com 获取商业授权）

自建部署（Docker 一键）：

```bash
git clone https://github.com/duducat2026/geo-optimizer.git
cd geo-optimizer
docker compose up -d geo-web geo-mcp
```

---

## English overview

GEO-Optimizer is an open-source **Generative Engine Optimization (GEO)** toolchain and
multi-user platform that helps websites get cited by AI search engines. This MCP server wraps
its open API (`/api/v1/*`) as 8 tools over **streamable-HTTP**, so any MCP client can submit
evaluations, follow progress and fetch optimization plans in natural language.

- **11 AI engines evaluated**: Doubao, Tongyi Qianwen, Hunyuan, ChatGLM, DeepSeek + Google AI Overviews, ChatGPT Search, Perplexity, Claude, Copilot, Gemini
- **Dual scoring model**: 5 dimensions for Chinese engines, 6 for global engines (incl. E-E-A-T signals)
- **LLM-generated plans**: improvement items plus content packs adapted to WeChat / Zhihu / Toutiao / Medium / Quora / Reddit
- **Structured data**: automatic Schema.org JSON-LD and FAQ generation

### Hosted endpoint

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "type": "streamableHttp",
      "url": "https://geo.tool.jiuchongju.com/mcp",
      "headers": { "Authorization": "Bearer ${GEO_API_KEY}" }
    }
  }
}
```

Replace `${GEO_API_KEY}` with your own key (starts with `geo_`), created on the
**API Keys** page of the [console](https://geo.tool.jiuchongju.com). Keys may be passed per
request via the `Authorization` header, or as the server-side default through `GEO_API_KEY`.

### Tools

| Tool | Purpose | Read-only |
| --- | --- | --- |
| `geo_submit_task` | Submit a GEO evaluation; returns `task_id` immediately (`plan`/`eval`) | no |
| `geo_list_tasks` | List recent tasks of the account (pagination + time-range filter) | yes |
| `geo_get_task_status` | Query task status and progress | yes |
| `geo_get_task_logs` | Fetch execution logs (incremental via `after_id`) | yes |
| `geo_get_task_result` | Fetch scores per engine, strengths, weaknesses and download links | yes |
| `geo_cancel_task` | Cancel a queued/running task (quota refunded) | no |
| `geo_get_usage` | Show API call statistics | yes |
| `geo_download_report` | Download the report and plan ZIP to a local path | no |

All tools accept `response_format` (`markdown` by default, or `json`).

**Recommended workflow**: submit the task (returns at once, never blocks) → check status or
logs only when the user asks → read results and download links once completed. Do not poll on a
timer.

### License & self-hosting

Platform, MCP server, CLI and SKILL package all come from the same repository:

- Source: <https://github.com/duducat2026/geo-optimizer>
- Docs: <https://duducat2026.github.io/geo-optimizer/index.en.html> · [MCP guide (English)](https://github.com/duducat2026/geo-optimizer/blob/main/mcp_server/README.en.md)
- License: AGPL-3.0 (for closed-source commercial or SaaS use, contact 52859273@qq.com for a commercial license)

```bash
git clone https://github.com/duducat2026/geo-optimizer.git
cd geo-optimizer
docker compose --profile mcp up -d   # web platform + MySQL + MCP server
```

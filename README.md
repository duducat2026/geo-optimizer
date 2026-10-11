# GEO-Optimizer

<div align="center">

**Generative Engine Optimization (GEO) 工具链与多用户平台** — 让你的内容在 AI 搜索引擎中获得更好的引用排名。

[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](#更新日志)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![AI Engines](https://img.shields.io/badge/AI_Engines-11-orange.svg)](#-支持的-ai-引擎)
[![Platforms](https://img.shields.io/badge/Export-6_Platforms-brightgreen.svg)](#多平台导出)

[功能特性](#-功能特性) • [架构总览](#-架构总览) • [快速开始](#-快速开始) • [配置说明](#%EF%B8%8F-配置说明) • [部署指南](#-部署指南) • [许可证](#-许可证)

**爬取分析 → 双引擎评分 → LLM 内容生成 → 多平台分发 → 排名监控，全流程覆盖 11 个 AI 引擎**

</div>

---

## 📖 项目简介

GEO-Optimizer 是一套面向「生成式引擎优化（GEO）」的开源工具链与多用户平台。它以 Playwright 驱动网站爬取，用国内 5 维 + 国外 6 维的双引擎模型评估网站在 AI 搜索引擎中的就绪度，调用 LLM 生成 FAQ、结构化数据与多平台优化内容，并支持以 CLI、Web 平台、MCP 服务、Agent SKILL 四种形态使用。

### 🎯 核心价值

- **🔍 真实爬取**：Playwright 驱动，支持 JS 渲染页面，稳健适配重埋点站点
- **🎯 双引擎评分**：国内 5 维度 + 国外 6 维度 GEO 就绪度评估，覆盖 11 个 AI 引擎
- **🤖 LLM 内容优化**：兼容 OpenAI 协议（百炼 / Token Plan / 自定义端点），自动生成 FAQ、Schema、优化正文
- **📤 多平台导出**：微信公众号、知乎、头条号、Medium、Quora、Reddit 六种格式
- **👥 多用户平台**：自助注册 + 后台审批、配额治理、算力方案多源切换、审计日志、任务队列与失败重试
- **🔌 MCP 服务**：streamable-HTTP 模式，把平台能力暴露给任意 MCP 客户端
- **🧩 Agent SKILL**：ClawHub 格式技能包，用自然语言提示词即可提交评估任务

### 🛠️ 架构总览

项目由四条可独立使用的链路组成：

```
src/geo_optimizer/            — 核心库 + CLI（analyze/optimize/export/eval/check/monitor/report）
├── crawler.py                — Playwright 网站爬取
├── analyzer.py               — GEO 就绪度双引擎评分
├── generators/               — LLM 内容 / FAQ / Schema 生成
├── evaluation/               — 多引擎评估 / 索引检测 / 排名监控
├── export.py · report.py     — 多平台导出 / 报告生成
└── web/portal/               — Flask 多用户平台（蓝图化：main/auth/user/admin/api/planitems/audit/guide/packaging/tasks）

mcp_server/                   — MCP 服务端（streamable-HTTP / stdio，8 个工具）
docs/geo-skill/               — ClawHub Agent SKILL 包与客户端脚本
client/geo_api_client.py      — 开放 API Python 客户端
deployment/                   — systemd / Nginx 一键部署、初始化脚本与配置样板
data/artifacts/               — 运行期产物（已 .gitignore）
```

---

## ✨ 功能特性

### 核心能力

- **网站爬取分析** — Playwright 驱动，支持 JS 渲染、深度抓取与页面快照留存
- **双引擎评分** — 国内 5 维度 + 国外 6 维度 GEO 就绪度评估
- **LLM 内容优化** — 调用兼容 OpenAI 协议的算力生成优化内容
- **FAQ 自动生成** — 从关键词和场景词生成结构化问答对
- **Schema 结构化数据** — JSON-LD 格式（FAQPage、Article、Organization）
- **多平台导出** — 微信公众号、知乎、头条号、Medium、Quora、Reddit
- **排名监控** — 定时检测各引擎中目标关键词的排名变化
- **GEO 多引擎评估** — 11 个 AI 引擎表现评估与索引状态检测

### Web 平台（多用户）

- **用户与审批** — 自助注册、后台审批激活、角色隔离（普通用户 / 管理员）
- **配额治理** — 评估配额按天重置、用量统计
- **算力方案** — 系统级多算力源（SystemLLMConfig）优先级链 + 用户级自有密钥，来源可标识
- **任务队列** — 后台异步执行、细粒度处理日志、失败重试与任务取消
- **改进方案打包** — 生成方案产物（正文 / FAQ / Schema / 多平台稿）并整体打包下载，PDF 报告

### 🌐 支持的 AI 引擎

| 国内引擎 | 国外引擎 |
|---------|---------|
| 豆包 | Google AI Overviews |
| 通义千问 | ChatGPT Search |
| 混元 | Perplexity |
| 智谱清言 | Claude |
| DeepSeek | Copilot |
| — | Gemini |

---

## 🚀 快速开始

### 📋 环境要求

| 软件 | 版本要求 | 说明 |
|---|---|---|
| **Python** | **3.10+** | 主运行环境 |
| **Playwright** | 1.40+ | 浏览器自动化（需 `playwright install chromium`） |
| **MySQL** | 8.0+ | 仅 Web 平台需要；CLI 工具链无需数据库 |

### 📥 安装

```bash
# 克隆项目
git clone https://github.com/duducat2026/geo-optimizer.git
cd geo-optimizer

# 创建虚拟环境并安装（开发模式，含测试依赖）
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 如需 Web 平台：pip install -e ".[web]"
# 如需 MCP 服务端：pip install -e ".[mcp]"

# 安装 Playwright 浏览器（下载慢时设镜像）
playwright install chromium
# 国内加速：export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
```

> 依赖以 `pyproject.toml` 为准；根 `requirements.txt` 仅为兼容 `pip install -r` 保留。

### ⚙️ 配置

1. 复制配置：`cp geo_config.yaml geo_config.local.yaml`，编辑其中的 `target.url`、`keywords`。
2. 配置 LLM 算力（三选一）：
   - 环境变量：`export DASHSCOPE_API_KEY="sk-xxx"`（`geo_config.yaml` 的 `llm.api_key` 留空时自动读取）
   - 或直接在 `geo_config.local.yaml` 填入 `llm.api_key` / `base_url` / `model`

### ▶️ 使用示例

```bash
# CLI —— 分析 GEO 就绪度 / 完整优化 / 多平台导出
geo-optimizer analyze https://example.com
geo-optimizer optimize https://example.com
geo-optimizer export  https://example.com
geo-optimizer eval    https://example.com -k "关键词1,关键词2"
geo-optimizer check   https://example.com
geo-optimizer report  https://example.com

# Web 多用户平台（默认端口 5000；macOS 若 5000 被占用可用 5001）
geo-web --host 127.0.0.1 --port 5001

# MCP 服务端（streamable-HTTP，默认 127.0.0.1:8000/mcp）
python -m mcp_server
```

> 未安装入口脚本时可用模块方式：`python -m geo_optimizer analyze <url>`。

---

## ⌨️ 命令详解

| 命令 | 作用 | 常用选项 |
|---|---|---|
| `analyze` | 爬取页面 + GEO 就绪度分析 | `-o` 输出目录，`-f` markdown/html/json，`-v` 详细 |
| `optimize` | 完整优化（爬取→分析→LLM 优化→FAQ→Schema） | |
| `export` | 优化 + 多平台导出（6 平台） | |
| `faq` / `schema` | 仅生成 FAQ / 仅生成 Schema | |
| `eval` | GEO 多引擎表现评估 | `-k` 关键词，`-e` 指定引擎，`--no-check` 跳过索引检测 |
| `check` | 索引状态检测（HTTPS / robots / sitemap） | |
| `monitor` | 引擎引用监控 | `-i` 检测间隔（天），`--notify` |
| `report` | 生成综合分析报告 | `-f` markdown/html，`-o` 输出目录 |
| `full` | 完整流水线（optimize + export + monitor） | |

---

## 📊 评分维度

### 国内引擎（5 维度）

| 维度 | 评估内容 | 权重 |
|------|---------|------|
| 内容质量 | E-E-A-T 评估、原创性、专业深度 | 30% |
| 结构化数据 | Schema 标记、FAQ 格式、表格结构 | 20% |
| 引用友好性 | 数据来源标注、权威引用、可验证性 | 20% |
| AI 爬虫兼容 | robots.txt 规则、加载速度、移动适配 | 15% |
| 用户体验 | 页面结构、可读性、交互设计 | 15% |

### 国外引擎（6 维度）

| 维度 | 评估内容 | 权重 |
|------|---------|------|
| Content Quality | 原创性、深度、E-E-A-T | 25% |
| Citation Readiness | 引用格式、数据来源、权威背书 | 20% |
| Structured Data | JSON-LD、FAQ Schema、Article Schema | 15% |
| AI Crawler Compatibility | GPTBot/CCBot/Claude-Web 规则 | 15% |
| User Experience | Core Web Vitals、移动友好 | 15% |
| Platform Optimization | 内容格式、多语言支持 | 10% |

---

## 🗂️ 多平台导出

一份分析结果可导出为六种平台友好格式，位于运行产物目录：

| 平台 | 文件前缀 |
|---|---|
| 微信公众号 | `wechat_*` |
| 知乎 | `zhihu_*` |
| 头条号 | `toutiao_*` |
| Medium | `medium_*` |
| Quora | `quora_*` |
| Reddit | `reddit_*` |

---

## ⚙️ 配置说明

### geo_config.yaml（CLI / 核心库）

```yaml
target:
  url: "https://example.com"
  crawl_depth: 3
  max_pages: 50
keywords:
  zh: { primary: [], longtail: [], scenarios: [] }
  en: { primary: [], longtail: [], scenarios: [] }
llm:
  api_key: ""            # 留空则读取环境变量 DASHSCOPE_API_KEY
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen-plus"     # qwen-plus / qwen-max 等
  temperature: 0.7
  max_tokens: 4096
playwright:
  headless: true
  timeout_ms: 30000
  wait_until: "domcontentloaded"   # 重埋点站点最稳健
  settle_ms: 3000
```

### 环境变量

| 变量 | 说明 |
|------|------|
| `GEO_CONFIG` | 指定配置文件路径（默认 `geo_config.yaml`） |
| `DASHSCOPE_API_KEY` | 百炼 / OpenAI 兼容 API Key |
| `OPENAI_API_KEY` | OpenAI API Key（国外引擎可选） |

### Web 平台配置

- 复制 `deployment/settings.example.py` → `deployment/settings.py`（已在 `.gitignore`），填入 MySQL 连接、`SECRET_KEY`、管理员默认账号。
- 环境变量以 `GEO_` 前缀覆盖同名配置项（如 `GEO_DB_PASSWORD`、`GEO_GTM_CONTAINER`）。
- AI 算力（Key / Base URL / 模型）在**管理员配置页面**维护并入库，支持多算力源与优先级链，无需改环境变量。
- `GTM_CONTAINER` 配置项用于全站流量监测（Google Tag Manager）容器 ID；留默认占位值 `GTM-XXXXXXX` 则不注入真实埋点，部署方填入自有容器 ID 即生效。

### MCP 服务端环境变量

| 变量 | 命令行 | 默认 | 说明 |
|---|---|---|---|
| `GEO_BASE_URL` | — | `http://localhost:5000` | 平台开放 API 地址 |
| `GEO_API_KEY` | — | 无 | 服务端默认 Key（`geo_` 开头） |
| `GEO_MCP_HOST` | `--host` | `127.0.0.1` | 监听地址 |
| `GEO_MCP_PORT` | `--port` | `8000` | 监听端口 |
| `GEO_MCP_PATH` | `--path` | `/mcp` | 挂载路径 |
| `GEO_MCP_ALLOWED_HOSTS` | — | 回环 | 反代公网域名时必填（防 DNS rebinding） |

---

## 🔌 MCP 服务端

`mcp_server/` 以 streamable-HTTP 暴露 8 个工具，供任意 MCP 客户端调用平台能力：

`geo_submit_task` · `geo_list_tasks` · `geo_get_task_status` · `geo_get_task_logs` · `geo_get_task_result` · `geo_cancel_task` · `geo_get_usage` · `geo_download_report`

```bash
python -m mcp_server                                  # 默认 127.0.0.1:8000/mcp
python -m mcp_server --host 0.0.0.0 --port 8000       # 对外
python -m mcp_server --transport stdio                # stdio 本地模式
```

> 详见 [`mcp_server/README.md`](mcp_server/README.md)。

## 🧩 Agent SKILL

`docs/geo-skill/` 是 ClawHub 格式的技能包：用户用自然语言（如"请评估网站 www.example.com"）即可触发，客户端脚本提交任务后按需查询进度与结果，不定时轮询。

- `SKILL.md` — 技能定义与交互范式
- `scripts/geo_skill_client.py` · `geo_skill_api.py` · `geo_skill_common.py` — 提交 / 查询 / 下载

---

## 📦 部署指南

### 🐳 Docker（推荐，一条命令起全栈）

镜像内置 Python 3.12 + Chromium，编排拉起 **Web 平台 + MySQL 8.4**（首次启动自动建库建表、创建管理员）：

```bash
docker compose up -d
# 需要同机提供 MCP 服务端时（可选组件）：
docker compose --profile mcp up -d
```

启动后访问 `http://localhost:5000`，默认端口：Web 5000、MCP 8000、MySQL 宿主侧 3307。
生产部署前请先修改 `docker-compose.yml` 中的口令/密钥：

| 环境变量 | 说明 |
|---|---|
| `GEO_SECRET_KEY` | Flask 会话密钥（必改） |
| `GEO_ADMIN_PASSWORD` | 首次初始化创建的管理员口令（必改） |
| `GEO_DB_PASSWORD` / `MYSQL_PASSWORD` | 数据库口令，两处需一致（必改） |
| `DASHSCOPE_API_KEY` | LLM API Key（也可登录后在管理后台配置） |
| `GEO_GTM_CONTAINER` | GTM 容器 ID，不用埋点保持占位即可 |

- 构建参数面向国内网络优化，可用 `--build-arg` 覆盖：`PIP_INDEX`（pip 源）、`APT_MIRROR`（Debian 源）、`PLAYWRIGHT_DOWNLOAD_HOST`（Chromium 下载镜像）。
- 评估产物与日志挂载在宿主 `./data` 与 `./logs`；MySQL 数据在 `mysql-data` 卷。
- 仅想自己构建镜像不用编排：`docker build -t geo-optimizer .`。

### 🚀 systemd + Nginx（生产云部署）

Web 平台与 MCP 服务均以 **systemd + Nginx 反向代理**部署，脚本在 `deployment/`：

```bash
# 1. 初始化数据库与平台账号
cp deployment/settings.example.py deployment/settings.py   # 填入真实 MySQL / SECRET_KEY
mysql < deployment/init_db.sql
python deployment/init_platform.py

# 2. 本机启动平台（gunicorn 或开发用 run）
geo-web --host 127.0.0.1 --port 5000

# 3. 云端一键部署（平台 + MCP + Nginx 同步，需 ~/.ssh/config 免密）
bash deployment/deploy.sh
```

| 脚本 / 单元 | 作用 |
|---|---|
| `deployment/deploy.sh` | 平台 + MCP 一键发布（打包上传 → 装依赖 → systemd → Nginx 校验回滚） |
| `deployment/init_server.sh` | 云主机初始化 |
| `deployment/geotool.service` | 平台 systemd 服务单元 |
| `deployment/geo-mcp.service` | MCP systemd 服务单元 |
| `deployment/nginx_geotool.conf` | Nginx 反代模板（HTTPS、`/mcp` 子路径、SSE 关缓冲） |
| `deployment/init_db.sql` | 建库建表 SQL |
| `deployment/setup_mysql.sh` | MySQL 8 安装 + 本地数据迁移（口令/主机用环境变量覆盖） |

**首次使用**：平台默认管理员由 `settings.py` 的 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 在初始化时创建，**登录后请立即修改默认口令**。

---

## 🧪 开发指南

```bash
pip install -e ".[dev]"
pytest tests/ -v                    # 默认跳过联网集成测试
pytest tests/ -v -m integration     # 显式运行集成测试
```

- 测试基于 SQLite 内存库（`tests/conftest.py`），不依赖 MySQL。
- 添加新引擎：`geo_config.yaml` 增配置 → `evaluation/evaluator.py` 增评估逻辑 → `analyzer.py` 增评分维度。
- 代码风格：Python 3.10+、类型注解、Docstring、模块化。

---

## ❓ 常见问题

**Q: 提示 `Missing credentials` / API 调用失败？**
A: 检查 `llm.api_key` 或环境变量 `DASHSCOPE_API_KEY`；确认 Key 与 `base_url` 配套（百炼通用 Key 与 Token Plan Key 不可混用）。

**Q: Playwright 报 `Executable doesn't exist`？**
A: 执行 `playwright install chromium`；下载慢设 `PLAYWRIGHT_DOWNLOAD_HOST` 镜像。

**Q: 爬取超时？**
A: 重埋点站点用 `wait_until: "domcontentloaded"`（默认已如此），必要时调大 `timeout_ms`。

**Q: 页面无样式 / MCP 返回 421 Invalid Host？**
A: 平台静态资源路径见 `deployment/nginx_geotool.conf`；MCP 经反代暴露公网域名时须设 `GEO_MCP_ALLOWED_HOSTS` / `GEO_MCP_ALLOWED_ORIGINS`。

**Q: Web 平台连不上数据库？**
A: 确认 `deployment/settings.py` 的 MySQL 配置与 `init_db.sql` 已执行；库名含连字符时连接串已正确转义。

---

## 📋 更新日志

### v1.0.0 (2026-07-26)

- 初始版本：11 个 AI 引擎评估、双语内容生成、多平台导出
- Web 多用户平台（注册审批 / 配额 / 算力方案 / 任务队列 / 审计）
- MCP 服务端（streamable-HTTP）与 Agent SKILL 技能包

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目并克隆
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 提交改动（`git commit -m 'feat: add amazing feature'`，建议沿用 `feat:` / `fix:` / `docs:` 前缀）
4. 推送到分支（`git push origin feature/amazing-feature`）
5. 开启 Pull Request，说明影响环节与验证方式

提交前请运行 `pytest tests/` 确保用例通过。

---

## 📜 许可证

本项目采用 **GNU Affero General Public License v3.0（AGPL-3.0）** 开源，完整条款见 [LICENSE](./LICENSE)。

> ⚠️ **商业授权**：AGPL-3.0 要求网络服务分发同样开源。如你希望将本项目用于闭源商用、SaaS 集成或需要免除 AGPL 传染性约束，请联系获取单独的商业授权：**`52859273@qq.com`**。

---

## 📚 参考文献 / References

- Aggarwal, P. et al. "GEO: Generative Engine Optimization." arXiv:2311.09735 (2024)
- Google. "Search Quality Evaluator Guidelines." (2024)
- Schema.org. "Schema.org Official Documentation." https://schema.org

## 📎 引用 / Citation

如果本项目对你有帮助，欢迎引用：

```bibtex
@software{geo_optimizer,
  title  = {GEO-Optimizer: Generative Engine Optimization Toolchain},
  author = {GEO-Optimizer},
  year   = {2026},
  url    = {https://github.com/duducat2026/geo-optimizer},
  license = {AGPL-3.0}
}
```

详见 [`CITATION.cff`](./CITATION.cff)。

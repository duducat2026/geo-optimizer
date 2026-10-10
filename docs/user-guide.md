# GEO-Optimizer 用户使用指南

> 本指南帮助您通过 **Web 控制台** 和 **开放 API** 两种方式完成网站 GEO（生成式引擎优化）评估与优化。

---

## 目录

1. [平台简介](#1-平台简介)
2. [快速开始](#2-快速开始)
3. [控制台操作指南](#3-控制台操作指南)
4. [开放 API 调用指南](#4-开放-api-调用指南)
5. [CLI 命令行工具](#5-cli-命令行工具)
6. [Skill 客户端（AI Agent 集成）](#6-skill-客户端ai-agent-集成)
7. [常见问题](#7-常见问题)

---

## 1. 平台简介

GEO-Optimizer 是面向 AI 搜索引擎的生成式引擎优化（GEO）平台，核心能力：

| 能力 | 说明 |
|------|------|
| 网站爬取分析 | Playwright 驱动，支持 JS 渲染 |
| 双引擎 GEO 评分 | 国内 5 维 + 国外 6 维 |
| 11 引擎全覆盖 | 豆包、通义千问、混元、智谱清言、DeepSeek + Google AI、ChatGPT Search、Perplexity、Claude、Copilot、Gemini |
| LLM 内容优化 | 自动生成 FAQ、Schema、多平台适配内容 |
| 多平台导出 | 微信公众号、知乎、头条号、Medium、Quora、Reddit |
| 排名监控 | 持续跟踪 AI 引擎引用排名 |

**用户角色：**
- **管理员**：系统配置、用户管理、全量数据访问、审计日志、配额管理
- **普通用户**：评估任务、历史管理、报告下载、API 密钥管理、算力配置

---

## 2. 快速开始

### 2.1 访问平台

浏览器打开平台地址（默认 `http://localhost:5001`），进入登录页。

### 2.2 登录

- 默认管理员账号：`admin` / `admin123`
- 普通用户账号由管理员在后台创建

### 2.3 第一次评估

1. 登录后点击左侧菜单「新建评估」
2. 输入目标网站 URL（如 `https://example.com`）
3. 选择任务类型：
   - **仅评估（eval）**：获取 GEO 评分报告
   - **评估+方案（plan）**：评分 + 改进方案 + 多平台内容 + ZIP 打包下载
4. 点击「提交」，系统自动跳转到任务详情页
5. 等待任务完成（通常 30-120 秒），查看评分与报告

---

## 3. 控制台操作指南

### 3.1 控制台首页（Dashboard）

**管理员视角：**
- 总体概览：用户总数、任务总数、方案总数
- 最近 5 条评估任务列表

**普通用户视角：**
- 个人概览：我的任务数、剩余配额
- 最近 10 条评估历史

### 3.2 新建评估（/eval/new）

| 字段 | 说明 |
|------|------|
| 目标 URL | 必填，待评估的网站地址 |
| 任务类型 | `eval`（仅评分）/ `plan`（评分+方案） |

**限制条件：**
- 配额不足时无法提交（联系管理员增加配额）
- 每用户最多 3 个并发任务
- 全局并发已满时任务自动排队
- 需有可用算力配置（用户侧或平台侧）

### 3.3 任务详情（/eval/<task_id>）

任务提交后自动跳转至详情页，展示：

- **状态进度条**：queued → running → completed/failed
- **实时进度**：百分比 + 当前步骤描述
- **处理日志**：时间倒排，自动刷新（每 3 秒）
- **评分结果**：完成后展示总分、国内/国外分、各维度明细
- **操作按钮**：
  - 排队中/运行中 → 「终止任务」
  - 失败/已取消 → 「重试」
  - 已完成（plan 类型）→ 「查看改进方案」「下载报告 ZIP」

### 3.4 评估历史（/history）

- 分页展示所有历史任务（支持 10/20/50 条每页）
- 每条记录显示：URL、类型、状态、评分、创建时间
- 操作：查看详情、删除（级联删除方案、产出物、日志）

### 3.5 改进方案（/plan/<task_id>）

plan 类型任务完成后生成改进方案：

- **方案条目列表**：按优先级分组（high/mid/low）
- **条目标签**：标注适配的 AI 引擎（如「适配：豆包、ChatGPT」）
- **条目编辑**：点击条目可在线编辑内容
- **产出物管理**（/plan/<task_id>/artifacts）：
  - 查看已生成的产出物（FAQ、Schema、多平台文章等）
  - 在线编辑产出物内容
  - 新增生成尚未创建的产出物
  - 单项下载 / 整体打包下载

### 3.6 API 密钥管理（/api-keys）

用于开放 API 调用的密钥管理：

1. **生成密钥**：填写名称 + 有效期（1-3650 天）→ 获得 `geo_` 开头的密钥
   > ⚠️ 密钥明文仅在生成时展示一次，请妥善保存
2. **查看列表**：显示所有密钥的前缀、名称、调用次数、状态
3. **停用密钥**：点击「停用」使密钥立即失效
4. **调用明细**：点击密钥查看分页调用日志

### 3.7 算力配置（/llm-config）

用户可配置自己的 LLM 算力：

| 算力方案 | Base URL | API Key 格式 |
|---------|----------|-------------|
| 百炼按量付费 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `sk-` 开头 |
| Token Plan 团队版 | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` | `sk-sp-` 开头 |
| 自定义 MaaS | 自行填写 | 视端点而定 |

**操作步骤：**
1. 点击「新增配置」→ 选择方案 → 填写 API Key → 保存
2. 点击「激活」设为当前使用的算力
3. 点击「测试」验证连通性
4. 支持多条配置，同一时间仅一条激活

**算力优先级：** 用户侧算力 > 平台侧算力

### 3.8 管理员功能

#### 系统配置（/admin/config）
- 配置平台侧 LLM 参数（provider/api_key/base_url/model/temperature/max_tokens）
- 支持百炼、Token Plan、自定义三种方案预设

#### 用户管理（/admin/users）
- 创建新用户（设置用户名/密码/角色/配额）
- 修改用户配额
- 启用/停用用户账号
- 开关用户是否可使用平台算力

#### 站点总览（/admin/sites）
- 分页查看所有用户的评估站点
- 支持翻页（10/20/50 条每页）

#### 审计日志（/admin/audit）
- 查看所有操作记录（登录、评估、下载、删除、配置修改等）

#### 用户算力管理（/admin/user-llm）
- 分页查看各用户算力配置
- 支持按账户名称模糊检索
- 支持按日期范围筛选

### 3.9 优化指导（/guide）

内置 AI 引擎收录指南：
- 各引擎站长平台提交入口（Google/Bing/Perplexity/百度/神马）
- 国内 AI 模型收录机制（千问/豆包/混元/文心）
- robots.txt 配置示例
- 实操优先级清单

### 3.10 语言切换

支持中/英双语：点击顶部导航栏语言切换按钮（`/lang/zh` 或 `/lang/en`）。

---

## 4. 开放 API 调用指南

### 4.1 认证

所有 API 请求需携带 Bearer Token：

```
Authorization: Bearer geo_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

密钥在控制台「API 密钥管理」页面生成。

### 4.2 API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/tasks` | 提交评估任务 |
| GET | `/api/v1/tasks/{task_id}` | 查询任务状态 |
| GET | `/api/v1/tasks/{task_id}/result` | 获取任务结果 |
| GET | `/api/v1/tasks/{task_id}/download` | 下载报告 ZIP |
| POST | `/api/v1/tasks/{task_id}/cancel` | 终止任务 |
| GET | `/api/v1/usage` | API 调用统计 |

### 4.3 完整调用流程

#### Step 1: 提交任务

```bash
curl -X POST http://localhost:5001/api/v1/tasks \
  -H "Authorization: Bearer geo_your_key" \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "task_type": "plan"}'
```

响应（201）：
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

#### Step 2: 轮询状态

```bash
curl http://localhost:5001/api/v1/tasks/67dcbe3c-... \
  -H "Authorization: Bearer geo_your_key"
```

响应（200）：
```json
{
  "task_id": "67dcbe3c-...",
  "status": "running",
  "progress": 60,
  "message": "generating_plan",
  "overall_score": 0.0
}
```

状态流转：`queued` → `pending` → `running` → `completed` / `failed` / `cancelled`

#### Step 3: 获取结果

```bash
curl http://localhost:5001/api/v1/tasks/67dcbe3c-.../result \
  -H "Authorization: Bearer geo_your_key"
```

响应（200，仅 completed 状态）：
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

#### Step 4: 下载报告

```bash
curl -o report.zip http://localhost:5001/api/v1/tasks/67dcbe3c-.../download \
  -H "Authorization: Bearer geo_your_key"
```

ZIP 包内容（plan 类型）：
- `geo_analysis_report.md` — 完整分析报告
- `schema.jsonld.html` — Schema.org 结构化数据
- `wechat_*.md` / `zhihu_*.md` / `toutiao_*.md` — 国内平台文章
- `medium_*.md` / `quora_*.md` / `reddit_*.md` — 国际平台文章
- `plan_items/` — 分优先级改进方案

### 4.4 终止任务

```bash
curl -X POST http://localhost:5001/api/v1/tasks/67dcbe3c-.../cancel \
  -H "Authorization: Bearer geo_your_key"
```

### 4.5 错误码

| HTTP 状态 | error 字段 | 说明 |
|-----------|-----------|------|
| 400 | invalid_params | 缺少 target_url |
| 401 | missing_token / invalid_token | 密钥缺失或无效 |
| 403 | quota_exceeded | 配额用尽 |
| 403 | forbidden | 无权访问他人任务 |
| 404 | not_found | 任务不存在 |
| 409 | invalid_state | 无法取消已完成的任务 |
| 429 | concurrent_limit | 并发任务数超限 |

### 4.6 Python 客户端

```python
from client.geo_api_client import GeoApiClient

with GeoApiClient("http://localhost:5001", "geo_your_key") as client:
    # 提交任务
    task_id = client.submit_task("https://example.com", task_type="plan")
    
    # 等待完成（自动轮询）
    result = client.wait_for_completion(task_id, timeout=600)
    print(f"GEO Score: {result['overall_score']}")
    
    # 下载报告
    client.download(task_id, "./output/report.zip")
    
    # 查看用量
    usage = client.get_usage()
    print(f"Total calls: {usage['total_calls']}")
```

---

## 5. CLI 命令行工具

适合本地开发调试，无需启动 Web 服务。

### 5.1 安装

```bash
pip install -e .
# 或未安装时使用: python -m geo_optimizer <子命令>
```

### 5.2 命令一览

| 命令 | 说明 |
|------|------|
| `geo-optimizer analyze <URL>` | 爬取 + GEO 分析 |
| `geo-optimizer optimize <URL>` | 完整优化 pipeline |
| `geo-optimizer export <URL>` | 优化 + 多平台导出 |
| `geo-optimizer report <URL>` | 生成分析报告 |
| `geo-optimizer faq <URL>` | 仅生成 FAQ |
| `geo-optimizer schema <URL>` | 仅生成 Schema |
| `geo-optimizer monitor <URL>` | 引擎引用监控 |

### 5.3 环境变量

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 百炼 API Key |
| `GEO_CONFIG` | 配置文件路径（默认 `geo_config.yaml`） |

### 5.4 示例

```bash
# 完整分析并导出
export DASHSCOPE_API_KEY=sk-xxxxx
geo-optimizer export https://example.com

# 仅评分
geo-optimizer analyze https://example.com
```

---

## 6. Skill 客户端（AI Agent 集成）

面向 AI Agent 的封装客户端，支持一键完成「提交→等待→结果→下载」全流程。

### 6.1 获取 Skill 文件

公开访问（无需登录）：
- SKILL.md: `http://<host>:5001/geo-skill`
- 客户端: `http://<host>:5001/geo-skill/geo_skill_client.py`

### 6.2 使用方式

```python
import sys
sys.path.insert(0, "docs/geo-skill/scripts")
from geo_skill_client import GeoSkillClient

client = GeoSkillClient("http://localhost:5001", "geo_your_key")

# 提交 → 等待完成 → 下载报告
task_id = client.submit("https://example.com", task_type="plan")
result = client.wait_and_get_result(task_id, timeout=600)
print(f"Score: {result['overall_score']}")
client.download(task_id, "./output/report.zip")
```

### 6.3 CLI 模式

默认提交后立即返回（不阻塞、不做定时轮询），进展查询由使用人员发起；交互终端可用 `--wait` 阻塞等待：

```bash
# 提交任务（立即返回，打印评估网站/任务 ID/预计时长）
python docs/geo-skill/scripts/geo_skill_client.py \
  --base-url http://localhost:5001 \
  --api-key geo_your_key \
  --url https://example.com

# 列出最近提交的任务（ID/评估网站/状态），供澄清要查哪个任务
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key --recent

# 查询指定任务进展（返回状态+已产生日志；已完成时返回结果与免登录下载链接）
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --progress <task_id> --after-id 0

# 已完成任务直接下载压缩包
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --progress <task_id> --output ./report.zip

# 交互终端阻塞式完整流程
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --url https://example.com \
  --wait --output ./report.zip

# 查询已有任务状态
python docs/geo-skill/scripts/geo_skill_client.py \
  --api-key geo_your_key \
  --status <task_id>
```

---

## 7. 常见问题

### Q: 提交任务时提示「配额不足」怎么办？
A: 联系管理员在「用户管理」中增加您的评估配额。

### Q: 任务一直处于 queued 状态？
A: 全局并发已满，任务自动排队。等待其他任务完成后自动启动。

### Q: 任务失败如何重试？
A: 在任务详情页点击「重试」按钮，或调用 API `POST /api/v1/tasks/{id}/cancel` 后重新提交。

### Q: API 密钥忘记了怎么办？
A: 密钥明文仅在生成时展示一次。如遗忘，请停用旧密钥并生成新密钥。

### Q: 如何选择算力方案？
A: 优先级为用户侧 > 平台侧。如果您配置了自己的算力（/llm-config），系统优先使用；否则回退到管理员配置的平台算力。

### Q: eval 和 plan 任务有什么区别？
A: `eval` 仅输出评分报告；`plan` 在评分基础上额外生成改进方案、FAQ、Schema、六平台适配文章，并打包为 ZIP 下载。

### Q: 支持哪些 AI 引擎的评估？
A: 国内 5 个（豆包、通义千问、混元、智谱清言、DeepSeek）+ 国际 6 个（Google AI、ChatGPT Search、Perplexity、Claude、Copilot、Gemini），共 11 个。

### Q: 平台支持哪些语言？
A: 中文和英文双语。通过顶部导航栏切换，设置会保存到用户偏好。

---

*文档版本: 1.0.0 | 更新日期: 2026-07-29 | 适用平台版本: 1.0.0*

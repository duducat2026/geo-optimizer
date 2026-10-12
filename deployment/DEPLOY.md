# GEO-Optimizer 平台部署说明

[English](DEPLOY.en.md) | **简体中文**

本文面向**裸机 / 云主机**（非 Docker）部署，串起从数据库构建到 MCP/Skill 导出的完整流程。
所有脚本位于 `deployment/` 目录。Docker 一键编排见根目录 `README.zh-CN.md`（中文版）的「部署指南」，英文文档见 `README.md`。

---

## 0. 前置条件

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.11+ | 平台与 MCP 服务运行时 |
| MySQL | 8.0+ | 仅 Web 平台需要；数据库名 `geo-op`（含连字符，SQL 中用反引号）|
| Nginx | 任意稳定版 | 反向代理：`/` → 127.0.0.1:5000，`/mcp` → 127.0.0.1:8000 |
| systemd | — | 托管 `geotool`（平台）与 `geo-mcp`（MCP）两个服务 |

---

## 1. 构建 MySQL 数据库

两种方式，任选其一：

**A. 脚本安装 MySQL 8 + 建库**
```bash
bash deployment/setup_mysql.sh        # 安装并启动 MySQL8、设置 root 口令
mysql -u root -p < deployment/init_db.sql   # 建库 geo-op（setup 未自动建库时执行）
```

**B. 已有 MySQL，仅建库**
```bash
mysql -u root -p < deployment/init_db.sql
```
> 表结构不需要手写 SQL：应用启动时由 SQLAlchemy `create_all` 自动建表，并通过
> `app.py::_ensure_schema_upgrades()` 为存量表补齐新增列（如 API 密钥每日额度列）。

---

## 2. 配置运行参数

```bash
cp deployment/settings.example.py deployment/settings.py
```
编辑 `deployment/settings.py`（已在 `.gitignore` 中，不会入库）：

```python
SECRET_KEY = "<随机密钥>"
DB_HOST, DB_PORT = "localhost", 3306
DB_USER, DB_PASSWORD = "root", "<数据库口令>"
DB_NAME = "geo-op"
ADMIN_USERNAME = "geoadmin"        # 默认管理员
ADMIN_PASSWORD = "geo-optimizer"
```

---

## 3. 初始化数据（建表 + 种子 + 演示账号 + 通用密钥）

```bash
python deployment/init_platform.py
```

该脚本幂等，会依次完成：

1. 创建数据库 `geo-op`（若不存在）；
2. 建立全部数据表并补齐新增列；
3. 写入系统 LLM 默认配置；
4. 写入**演示数据**（普通用户 + 通用密钥）：

| 类型 | 值 | 说明 |
|---|---|---|
| 普通用户 | `geo_tool` / 口令取自 `deployment/init_platform.py` 中的 `DEMO_USER_PASSWORD` | 评估配额 50，可直接登录 |
| 通用 API 密钥 | 同脚本中的明文常量 `DEMO_API_KEY_PLAIN` | 归属 `geo_tool`，**每日调用额度 50（受限）**，用于 MCP / Skill 导出 |

> **管理员账号不在本脚本初始化**：本脚本只演示普通用户与通用密钥。管理员由 `settings.py`
> 的 `seed_defaults`（仅当不存在时）或后台创建；云端已有管理员时不受任何影响。
> **所有 API 密钥都必须限制额度**，不允许 0/不限。

> ⚠️ **安全提示**：`init_platform.py` 内写死的演示口令与通用密钥仅供**快速起步/演示**。
> 正式对外服务前必须：登录后修改 `geo_tool` 口令；按需调整或删除该通用密钥并重新生成私有密钥。

---

## 4. 部署应用（平台 + MCP）

`deploy.sh` 是主入口，执行「打包 → 上传 → 装依赖 → 同步配置 → 切版本 → 重启 geotool+geo-mcp → 同步 Nginx」七步，
内置回滚（Nginx 配置 `nginx -t` 失败自动还原）。

```bash
REMOTE_HOST=your-ssh-host-alias \
REMOTE_IP=203.0.113.10 \
DOMAIN=geo.tool.example.com \
bash deployment/deploy.sh
```

| 环境变量 | 含义 | 默认 |
|---|---|---|
| `REMOTE_HOST` | SSH 别名（`~/.ssh/config`）| your-ssh-host-alias |
| `REMOTE_IP` | 主机 IP | 203.0.113.10 |
| `DOMAIN` | 对外域名，用于渲染 Nginx 证书/ServerName | geo.tool.example.com |
| `DEPLOY_BASE` | 云端部署根目录 | /opt/geotool |

版本目录格式 `geotool-release-<yyyyMMddHHmmss>-v0.1.0`，`current` 软链指向当前版本，保留最近 5 个。

> 首次部署前需先跑第 1、3 步（`setup_mysql.sh` 与 `init_platform.py`），在云端建好库和种子数据；
> `deploy.sh` 只负责应用发布，不建库。云端 `shared/settings.py`、`shared/mcp.env` 首次由脚本从
> example 生成，之后复用，不会被覆盖。

---

## 5. MCP 与 Skill 导出

1. 以 `geo_tool` 登录平台 → 左侧「API 密钥」；
2. 列表中「通用密钥(演示)」即第 3 步预置的密钥，点「导出 Skill」或「导出 MCP」，选择目标平台即可下载 ZIP；
3. 导出的包内 `config.json`（Skill）/ `mcp-config.json`（MCP）会自动写入这把密钥的明文，开箱可用；
   - 平台变体包不含明文密钥，MCP 配置里以 `${GEO_API_KEY}` 占位，需自行注入环境变量；
4. 若历史密钥无明文，导出时会**自动重生成一把可用密钥**并落库。

MCP 服务在线端点：`https://<DOMAIN>/mcp`（streamable-HTTP，反代到 `127.0.0.1:8000`）。

---

## 6. 部署后验证

```bash
# 服务状态
ssh <REMOTE_HOST> 'systemctl is-active geotool geo-mcp'

# 平台与 MCP 可达
curl -I  https://<DOMAIN>/login                 # 期望 200
curl -sI -X POST https://<DOMAIN>/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'   # 期望 200
```

日志排查：
```bash
ssh <REMOTE_HOST> 'journalctl -u geotool -n 50 --no-pager'
ssh <REMOTE_HOST> 'journalctl -u geo-mcp -n 50 --no-pager'
```

---

## 7. 上线安全检查清单

- [ ] 修改 `geoadmin` / `geo_tool` 默认口令
- [ ] 轮换或删除写死的通用 API 密钥，改用私有密钥
- [ ] `settings.py` 的 `SECRET_KEY`、`DB_PASSWORD` 已改为真实随机值（不入库）
- [ ] `mcp.env` 的 `GEO_API_KEY` 为有效值（chmod 600）
- [ ] 域名 SSL 证书就绪，Nginx `nginx -t` 通过
- [ ] 按需为各 API 密钥在后台「密钥额度」页设置合理的每日调用额度

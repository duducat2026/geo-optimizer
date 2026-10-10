# -*- coding: utf-8 -*-
"""MCP 工具响应格式化：markdown（默认，人类可读）与 json（机器可读）双格式。

所有格式化函数均对平台返回结构做防御性取值（.get / isinstance 校验），
即便服务端字段有增删也不会抛异常。中文输出，便于直接回显给用户。
"""
from __future__ import annotations

import json
from typing import Any

try:  # 作为包导入（python -m mcp_server / import mcp_server.formatting）
    from .config import ESTIMATED_MINUTES
except ImportError:  # 作为脚本平铺导入（python server.py，mcp_server/ 已在 sys.path）
    from config import ESTIMATED_MINUTES

JSON = "json"
MARKDOWN = "markdown"


def _is_json(fmt: str) -> bool:
    return (fmt or MARKDOWN).strip().lower() == JSON


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _score(value: Any) -> str:
    """把评分格式化为易读字符串（缺失时返回 —）。"""
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


# ─── 提交任务 ────────────────────────────────────────────────────────
def format_submit(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    task_id = data.get("task_id", "")
    task_type = data.get("task_type", "plan")
    est = ESTIMATED_MINUTES.get(task_type, 5)
    lines = [
        "## ✅ 任务已提交",
        f"- 评估网站: {data.get('target_url', '')}",
        f"- 任务 ID: `{task_id}`",
        f"- 任务类型: {task_type}（plan=评估+优化方案+多平台内容 / eval=仅评分）",
        f"- 当前状态: {data.get('status', '')}",
        f"- 预计耗时: 约 {est} 分钟",
    ]
    if data.get("queued"):
        lines.append(f"- ⏳ 排队中，当前位置 #{data.get('queue_position', '?')}")
    lines.append(
        "\n> 提交后不会自动轮询。可用 geo_get_task_status / geo_get_task_logs "
        "按需查询进度；完成后用 geo_get_task_result 获取评分与下载链接。"
    )
    return "\n".join(lines)


# ─── 任务列表 ────────────────────────────────────────────────────────
def format_task_list(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    tasks = data.get("tasks", []) or []
    total = data.get("total", len(tasks))
    page = data.get("page", 1)
    pages = data.get("pages", 1)
    header = f"## 📋 最近任务（第 {page}/{pages} 页，共 {total} 条）"
    if not tasks:
        return header + "\n\n当前账号暂无任务。用 geo_submit_task 提交一个评估任务。"
    lines = [header, ""]
    for i, t in enumerate(tasks, 1):
        score = _score(t.get("overall_score"))
        lines.append(f"{i}. `{t.get('task_id', '')}` — {t.get('status', '')} {t.get('progress', 0)}%")
        lines.append(f"   - 网站: {t.get('target_url', '')}")
        lines.append(f"   - 类型: {t.get('task_type', '')} | 评分: {score} | 提交: {t.get('created_at', '')}")
    if pages and page < pages:
        lines.append(f"\n> 还有更多，传 page={page + 1} 查看下一页。")
    return "\n".join(lines)


# ─── 任务状态 ────────────────────────────────────────────────────────
def format_status(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    lines = [
        "## 📊 任务状态",
        f"- 任务 ID: `{data.get('task_id', '')}`",
        f"- 网站: {data.get('target_url', '')}",
        f"- 类型: {data.get('task_type', '')} | 来源: {data.get('source', '')}",
        f"- 状态: {data.get('status', '')} | 进度: {data.get('progress', 0)}%",
    ]
    if data.get("message"):
        lines.append(f"- 说明: {data['message']}")
    if data.get("overall_score"):
        lines.append(f"- GEO 综合评分: {_score(data.get('overall_score'))}")
    if data.get("status") == "queued" and data.get("queue_position") is not None:
        lines.append(f"- 排队位置: #{data.get('queue_position')}")
    if data.get("error"):
        lines.append(f"- 错误: {data['error']}")
    lines.append(f"- 创建: {data.get('created_at', '')} | 完成: {data.get('completed_at') or '—'}")
    return "\n".join(lines)


# ─── 执行日志 ────────────────────────────────────────────────────────
def format_logs(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    logs = data.get("logs", []) or []
    status = data.get("status", "")
    progress = data.get("progress", 0)
    last_id = data.get("last_id", 0)
    header = f"## 📜 任务执行日志（状态 {status}，进度 {progress}%）"
    if not logs:
        return header + f"\n\n暂无新日志。下次查询可继续传 after_id={last_id}。"
    lines = [header, f"新增 {len(logs)} 条：", ""]
    for entry in logs:
        if not isinstance(entry, dict):
            continue
        line = f"- [{entry.get('time', '')}] {entry.get('message', '')}"
        if entry.get("detail"):
            line += f"：{entry['detail']}"
        lines.append(line)
    lines.append(f"\n> 增量拉取：下次传 after_id={last_id} 只获取更新的日志。")
    return "\n".join(lines)


# ─── 任务结果 ────────────────────────────────────────────────────────
def format_result(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    status = data.get("status", "")
    if status != "completed":
        return (f"## ⏳ 任务尚未完成\n- 任务 ID: `{data.get('task_id', '')}`\n"
                f"- 当前状态: {status}\n- 说明: {data.get('message', '')}\n\n"
                f"> 完成后再调用 geo_get_task_result 获取评分与下载链接。")

    result = data.get("result") or {}
    if not isinstance(result, dict):
        result = {}
    lines = [
        "## 🎯 GEO 评估结果",
        f"- 任务 ID: `{data.get('task_id', '')}`",
        f"- 综合评分: **{_score(data.get('overall_score'))}** / 100",
    ]
    if result.get("url"):
        lines.append(f"- 网站: {result.get('url')}")
    if result.get("title"):
        lines.append(f"- 标题: {result.get('title')}")
    if result.get("language"):
        lines.append(f"- 语言: {result.get('language')}")

    engines = result.get("engine_scores") or []
    if isinstance(engines, list) and engines:
        lines.append("\n### 各 AI 引擎评分")
        for e in engines:
            if isinstance(e, dict):
                lines.append(f"- {e.get('engine', '?')}: {_score(e.get('score'))}")

    strengths = result.get("strengths") or []
    if isinstance(strengths, list) and strengths:
        lines.append("\n### ✅ 优势")
        lines.extend(f"- {s}" for s in strengths[:8])
    weaknesses = result.get("weaknesses") or []
    if isinstance(weaknesses, list) and weaknesses:
        lines.append("\n### ⚠️ 待改进")
        lines.extend(f"- {w}" for w in weaknesses[:8])

    share = data.get("share_download_url")
    dl = data.get("download_url")
    if share:
        lines.append(f"\n### 📦 下载\n- 免登录分享链接（可直接给用户）: {share}")
    if dl:
        lines.append(f"- 鉴权下载路径（需 Bearer）: {dl}"
                     f"\n- 提示: 用 geo_download_report 可直接把 ZIP 保存到本地。")
    return "\n".join(lines)


# ─── 终止任务 ────────────────────────────────────────────────────────
def format_cancel(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    return "\n".join([
        "## 🛑 任务终止请求已受理",
        f"- 任务 ID: `{data.get('task_id', '')}`",
        f"- 状态: {data.get('status', '')}",
        f"- 说明: {data.get('message', '')}",
        "\n> 运行中的任务会在下一个检查点协作式停止；排队中的任务立即取消并退回配额。",
    ])


# ─── 用量统计 ────────────────────────────────────────────────────────
def format_usage(data: dict, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps(data)
    keys = data.get("keys", []) or []
    lines = ["## 📈 API 用量统计", f"- 总调用次数: {data.get('total_calls', 0)}"]
    if keys:
        lines.append("\n### API Keys")
        for k in keys:
            if not isinstance(k, dict):
                continue
            active = "启用" if k.get("is_active") else "停用"
            lines.append(
                f"- {k.get('name', '')}（`{k.get('key_prefix', '')}`）— "
                f"调用 {k.get('total_calls', 0)} 次 | {active} | 最近使用 {k.get('last_used_at') or '—'}"
            )
    return "\n".join(lines)


# ─── 下载报告 ────────────────────────────────────────────────────────
def format_download(task_id: str, path: str, size: int, fmt: str = MARKDOWN) -> str:
    if _is_json(fmt):
        return _dumps({"task_id": task_id, "save_path": path, "size_bytes": size})
    return "\n".join([
        "## ⬇️ 报告已下载",
        f"- 任务 ID: `{task_id}`",
        f"- 保存路径: {path}",
        f"- 文件大小: {size} 字节",
    ])

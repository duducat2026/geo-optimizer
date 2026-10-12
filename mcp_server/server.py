#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GEO-Optimizer MCP 服务端 —— streamable-HTTP 模式。

把 GEO-Optimizer 平台的开放 API（`/api/v1/*`）封装为一组 MCP 工具，
让任意 MCP 客户端（Claude Desktop / Cursor / Qoder 等）通过自然语言
提交网站 GEO 评估、查询进度与日志、获取评分与优化方案下载链接。

传输模式：**streamable-HTTP**（默认），适合远程部署与多客户端并发；
亦保留 stdio 模式用于本地单客户端调试。

启动（streamable-HTTP，默认 127.0.0.1:8000/mcp）::

    python -m mcp_server                       # 推荐：包方式启动
    python mcp_server/server.py                # 直接运行脚本
    python -m mcp_server --host 0.0.0.0 --port 8000 --path /mcp

鉴权：调用方可在每个 MCP 请求头携带 `Authorization: Bearer geo_xxx`
（多客户端各自用自己的 key）；若未携带，则回退到服务端配置的
GEO_API_KEY 环境变量 / config.json。

依赖：mcp>=2.1,<3（v2 SDK，入口为 mcp.server.mcpserver.MCPServer）、httpx、pydantic。
"""
from __future__ import annotations

import argparse
import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator, Optional

# ─── sys.path 引导 ───────────────────────────────────────────────────
# 保证无论以 `python server.py` / `python -m mcp_server` / `mcp run server.py`
# 哪种方式启动，都能导入同目录下的 config / api_client / formatting 模块。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from pydantic import Field  # noqa: E402
from mcp.server.mcpserver import Context, MCPServer  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

try:  # 作为包导入（python -m mcp_server / import mcp_server.server）
    from .api_client import GeoApiError, GeoOpenApiClient, describe_error
    from .config import (
        bearer_from_headers,
        normalize_url,
        resolve_allowed_hosts,
        resolve_allowed_origins,
        resolve_base_url,
        resolve_server_api_key,
        resolve_transport_settings,
    )
    from .formatting import (
        JSON,
        format_cancel,
        format_download,
        format_logs,
        format_result,
        format_status,
        format_submit,
        format_task_list,
        format_usage,
    )
except ImportError:  # 作为脚本平铺导入（mcp_server/ 已在 sys.path）
    from api_client import GeoApiError, GeoOpenApiClient, describe_error
    from config import (
        bearer_from_headers,
        normalize_url,
        resolve_allowed_hosts,
        resolve_allowed_origins,
        resolve_base_url,
        resolve_server_api_key,
        resolve_transport_settings,
    )
    from formatting import (
        JSON,
        format_cancel,
        format_download,
        format_logs,
        format_result,
        format_status,
        format_submit,
        format_task_list,
        format_usage,
    )

# ─── MCP 服务端实例 ──────────────────────────────────────────────────
mcp = MCPServer(
    "geo_optimizer_mcp",
    instructions=(
        "GEO（生成式引擎优化）平台工具集：提交网站评估任务、按需查询进度与执行日志、"
        "获取 GEO 综合评分与各 AI 引擎评分、拿到优化方案下载链接、终止任务、查看 API 用量。"
        "覆盖 11 个 AI 引擎。默认任务类型 plan（评估+优化方案+多平台内容），仅需评分时用 eval。"
        "工作流：先 geo_submit_task 提交（立即返回 task_id，不阻塞）；"
        "用户询问进度时用 geo_get_task_status / geo_get_task_logs 查询；"
        "完成后用 geo_get_task_result 获取评分与下载链接。切勿定时轮询阻塞。"
        "开源地址：https://github.com/duducat2026/geo-optimizer（AGPL-3.0，可自建部署）。"
    ),
)

# ─── 复用的入参类型别名（Pydantic Field 约束）────────────────────────
ResponseFormat = Annotated[str, Field(
    description="输出格式：'markdown'（默认，人类可读）或 'json'（机器可读，含全部字段）",
    pattern="^(markdown|json)$",
)]
TaskId = Annotated[str, Field(
    description="任务 ID（geo_submit_task 返回的 task_id，UUID 字符串）",
    min_length=1, max_length=64,
)]
TargetUrl = Annotated[str, Field(
    description="要评估的网站 URL；裸域名会自动补 https://（如 'www.aliyun.com' → 'https://www.aliyun.com'）",
    min_length=1, max_length=512,
)]
TaskType = Annotated[str, Field(
    description="任务类型：'plan'（默认=评估+优化方案+多平台内容）或 'eval'（仅评分）",
    pattern="^(plan|eval)$",
)]


# ─── 鉴权与客户端辅助（DRY）─────────────────────────────────────────
def _resolve_api_key(ctx: Context) -> Optional[str]:
    """按请求解析 API Key。

    优先级：调用方请求头 Authorization: Bearer geo_xxx（多客户端各用自己的 key）
    > 服务端默认 key（GEO_API_KEY 环境变量 / config.json）。均未配置时返回 None。
    """
    headers: Any = None
    try:
        headers = getattr(ctx, "headers", None)
    except Exception:  # 某些传输/上下文不提供 headers，忽略并回退服务端 key
        headers = None
    return bearer_from_headers(headers) or resolve_server_api_key()


@asynccontextmanager
async def _api(ctx: Context) -> AsyncIterator[GeoOpenApiClient]:
    """构建单次调用的开放 API 客户端；无可用 key 时抛 missing_token 错误。

    用 `async with _api(ctx) as api:` 包裹每次工具调用，自动创建与关闭连接。
    """
    api_key = _resolve_api_key(ctx)
    if not api_key:
        raise GeoApiError(401, "missing_token", "")
    client = GeoOpenApiClient(resolve_base_url(), api_key)
    try:
        yield client
    finally:
        await client.aclose()


# ─── 工具 1：提交评估任务 ────────────────────────────────────────────
@mcp.tool(
    name="geo_submit_task",
    title="Submit GEO Task",
    annotations={"readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": True},
)
async def geo_submit_task(
    ctx: Context,
    target_url: TargetUrl,
    task_type: TaskType = "plan",
    response_format: ResponseFormat = "markdown",
) -> str:
    """提交一个网站 GEO 评估任务，立即返回 task_id（不阻塞等待分析完成）。

    这是使用 GEO 平台的起点。任务提交后进入云端异步执行（plan 约 5 分钟、
    eval 约 2 分钟），会消耗一次评估配额。提交后**不要**定时轮询；当用户询问
    进度时再调用 geo_get_task_status / geo_get_task_logs。

    Args:
        ctx (Context): MCP 上下文（自动注入，用于读取请求头中的鉴权信息）。
        target_url (str): 要评估的网站 URL，裸域名自动补 https://。
        task_type (str): 'plan'（默认，评估+优化方案+多平台内容）或 'eval'（仅评分）。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 提交结果。含 task_id、状态、评估网站、预计耗时；排队时含队列位置。
             失败时返回可执行错误提示（如配额不足、并发超限、算力不可用、鉴权失败）。

    Examples:
        - "请评估网站 www.aliyun.com" → target_url="www.aliyun.com"（task_type 默认 plan）
        - "只要 example.com 的评分" → target_url="example.com", task_type="eval"
    """
    try:
        async with _api(ctx) as api:
            data = await api.submit_task(normalize_url(target_url), task_type)
        return format_submit(data, response_format)
    except Exception as exc:  # noqa: BLE001 - 统一转可执行错误文本
        return describe_error(exc)


# ─── 工具 2：任务列表 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_list_tasks",
    title="List GEO Tasks",
    annotations={"readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def geo_list_tasks(
    ctx: Context,
    limit: Annotated[int, Field(description="每页条数，1-50", ge=1, le=50)] = 10,
    page: Annotated[int, Field(description="页码，从 1 开始", ge=1)] = 1,
    start: Annotated[Optional[str], Field(
        description="按提交时间过滤的起始（YYYY-MM-DD 或 ISO 时间，含）",
        max_length=32)] = None,
    end: Annotated[Optional[str], Field(
        description="按提交时间过滤的结束（YYYY-MM-DD 纯日期含当天，或 ISO 时间）",
        max_length=32)] = None,
    response_format: ResponseFormat = "markdown",
) -> str:
    """列出当前 API Key 账号最近提交的任务（含完整 task_id、网站、状态、进度、评分）。

    常用于用户问"进展如何/查一下我的任务"时，先列出候选任务，再据 task_id
    调用 geo_get_task_status / geo_get_task_logs / geo_get_task_result。
    支持分页（page/limit）与提交时间范围过滤（start/end）。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        limit (int): 每页条数，1-50，默认 10。
        page (int): 页码，从 1 开始，默认 1。
        start (Optional[str]): 起始时间过滤（YYYY-MM-DD 或 ISO），默认不过滤。
        end (Optional[str]): 结束时间过滤（纯日期含当天），默认不过滤。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 任务列表。含 total/page/pages 与 tasks 数组（每项：task_id、target_url、
             task_type、status、progress、overall_score、created_at）。
    """
    try:
        async with _api(ctx) as api:
            data = await api.list_tasks(limit=limit, page=page, start=start, end=end)
        return format_task_list(data, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 工具 3：任务状态 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_get_task_status",
    title="Get GEO Task Status",
    annotations={"readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def geo_get_task_status(
    ctx: Context,
    task_id: TaskId,
    response_format: ResponseFormat = "markdown",
) -> str:
    """查询指定任务的当前状态与进度（非阻塞，立即返回）。

    状态流转：queued → running → completed / failed / cancelled。
    进度查询应由用户发起，不要定时轮询。completed 后可用 geo_get_task_result 取结果。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        task_id (str): 任务 ID（geo_submit_task 返回）。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 任务状态。含 status、progress、message、overall_score、created_at 等；
             排队中含 queue_position；失败含 error。任务不存在/无权访问时返回错误提示。
    """
    try:
        async with _api(ctx) as api:
            data = await api.get_status(task_id)
        return format_status(data, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 工具 4：执行日志 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_get_task_logs",
    title="Get GEO Task Logs",
    annotations={"readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def geo_get_task_logs(
    ctx: Context,
    task_id: TaskId,
    after_id: Annotated[int, Field(
        description="只返回 id 大于此值的日志（增量拉取）；首次传 0", ge=0)] = 0,
    response_format: ResponseFormat = "markdown",
) -> str:
    """获取任务的云端执行日志（已翻译为中文），支持增量拉取。

    用于让用户实时了解云端流水线进展（如"页面爬取完成，耗时: 5321ms"）。
    首次调用传 after_id=0 取全部；之后传上次返回的 last_id 只取新增日志，节省上下文。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        task_id (str): 任务 ID。
        after_id (int): 增量游标，只返回 id > after_id 的日志，默认 0（全部）。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 执行日志。含 status、progress、logs 数组（id/level/message/detail/time）
             与 last_id（下次增量拉取的游标）。
    """
    try:
        async with _api(ctx) as api:
            data = await api.get_logs(task_id, after_id=after_id)
        return format_logs(data, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 工具 5：任务结果 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_get_task_result",
    title="Get GEO Task Result",
    annotations={"readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def geo_get_task_result(
    ctx: Context,
    task_id: TaskId,
    response_format: ResponseFormat = "markdown",
) -> str:
    """获取已完成任务的 GEO 评估结果：综合评分、各引擎评分、优势/待改进、下载链接。

    仅当任务 completed 时返回完整结果；否则返回当前状态与"尚未完成"提示。
    结果含免登录分享下载链接（share_download_url，可直接给用户）与鉴权下载路径。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        task_id (str): 任务 ID。
        response_format (str): 'markdown'（默认，摘要）或 'json'（含 result 全部字段）。

    Returns:
        str: 评估结果。含 overall_score(0-100)、engine_scores、strengths、weaknesses、
             download_url、share_download_url。未完成时返回状态提示。
    """
    try:
        async with _api(ctx) as api:
            data = await api.get_result(task_id)
        return format_result(data, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 工具 6：终止任务 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_cancel_task",
    title="Cancel GEO Task",
    annotations={"readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": True},
)
async def geo_cancel_task(
    ctx: Context,
    task_id: TaskId,
    response_format: ResponseFormat = "markdown",
) -> str:
    """终止一个排队中或运行中的任务（会退回其占用的当日配额）。

    排队中的任务立即取消；运行中的任务在下一个检查点协作式停止（当前爬取/LLM
    步骤会先完成）。已处于终态（completed/failed/cancelled）的任务无法取消。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        task_id (str): 要终止的任务 ID。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 终止结果。含 status（cancelling=运行中协作停止 / cancelled=已取消）与说明；
             任务已是终态时返回 invalid_state 错误提示。
    """
    try:
        async with _api(ctx) as api:
            data = await api.cancel_task(task_id)
        return format_cancel(data, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 工具 7：用量统计 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_get_usage",
    title="Get API Usage",
    annotations={"readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def geo_get_usage(
    ctx: Context,
    response_format: ResponseFormat = "markdown",
) -> str:
    """查询当前账号的 API 调用统计（总调用次数与各 API Key 明细）。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 用量统计。含 total_calls 与 keys 数组（name、key_prefix、total_calls、
             is_active、last_used_at）。
    """
    try:
        async with _api(ctx) as api:
            data = await api.get_usage()
        return format_usage(data, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 工具 8：下载报告 ────────────────────────────────────────────────
@mcp.tool(
    name="geo_download_report",
    title="Download GEO Report",
    annotations={"readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def geo_download_report(
    ctx: Context,
    task_id: TaskId,
    save_path: Annotated[str, Field(
        description="本地保存路径（如 './output/report.zip'）；父目录会自动创建",
        min_length=1, max_length=512)],
    response_format: ResponseFormat = "markdown",
) -> str:
    """把已完成任务的评估报告与改进方案 ZIP 包下载到本地指定路径。

    ZIP 内含 geo_analysis_report.md、schema.jsonld.html、多平台内容
    （wechat/zhihu/toutiao/medium/quora/reddit）与 plan_items/ 行动项。
    仅 plan 任务且方案已生成时可下载；eval 任务或无方案包时返回错误提示。

    Args:
        ctx (Context): MCP 上下文（自动注入）。
        task_id (str): 任务 ID。
        save_path (str): 本地保存路径，父目录自动创建。
        response_format (str): 'markdown'（默认）或 'json'。

    Returns:
        str: 下载结果。含保存路径与文件大小（字节）；无下载包时返回 not_found 提示。
    """
    try:
        async with _api(ctx) as api:
            path = await api.download_report(task_id, save_path)
        size = path.stat().st_size if path.exists() else 0
        return format_download(task_id, str(path), size, response_format)
    except Exception as exc:  # noqa: BLE001
        return describe_error(exc)


# ─── 启动入口 ────────────────────────────────────────────────────────
def main(argv: Optional[list] = None) -> None:
    """解析命令行参数并以 streamable-HTTP（默认）或 stdio 模式启动 MCP 服务端。"""
    settings = resolve_transport_settings()
    parser = argparse.ArgumentParser(
        description="GEO-Optimizer MCP 服务端（默认 streamable-HTTP 模式）",
    )
    parser.add_argument(
        "--transport", default=settings.transport,
        choices=["streamable-http", "stdio"],
        help="传输模式，默认 streamable-http（远程/多客户端）；stdio 用于本地调试",
    )
    parser.add_argument("--host", default=settings.host,
                        help=f"streamable-HTTP 监听地址，默认 {settings.host}（回环，安全）")
    parser.add_argument("--port", type=int, default=settings.port,
                        help=f"streamable-HTTP 监听端口，默认 {settings.port}")
    parser.add_argument("--path", default=settings.path,
                        help=f"streamable-HTTP 挂载路径，默认 {settings.path}")
    args = parser.parse_args(argv)

    if args.transport == "stdio":
        # 本地单客户端模式（备用）：协议走标准输入输出，日志走 stderr
        print("[geo_optimizer_mcp] 以 stdio 模式启动", file=sys.stderr)
        mcp.run(transport="stdio")
        return

    # streamable-HTTP 模式（默认）
    path = args.path if args.path.startswith("/") else "/" + args.path
    endpoint = f"http://{args.host}:{args.port}{path}"
    # DNS rebinding 防护：放行回环 + 反代公网域名（GEO_MCP_ALLOWED_HOSTS/ORIGINS），
    # 否则经 Nginx 转发的 Host 头（如 geo.tool.xxx.com）会被 SDK 拒为 421。
    allowed_hosts = resolve_allowed_hosts()
    allowed_origins = resolve_allowed_origins()
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    print(f"[geo_optimizer_mcp] streamable-HTTP 启动: {endpoint}", file=sys.stderr)
    print(f"[geo_optimizer_mcp] 平台 base_url: {resolve_base_url()} | "
          f"服务端默认 key: {'已配置' if resolve_server_api_key() else '未配置(依赖请求头 Bearer)'}",
          file=sys.stderr)
    print(f"[geo_optimizer_mcp] 放行 Host: {allowed_hosts} | Origin: {allowed_origins}",
          file=sys.stderr)
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path=path,
        transport_security=transport_security,
    )


if __name__ == "__main__":
    main()

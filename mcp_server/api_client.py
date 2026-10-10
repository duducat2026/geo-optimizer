# -*- coding: utf-8 -*-
"""GEO-Optimizer 开放 API 异步客户端（供 MCP 服务端调用）。

基于 httpx.AsyncClient，使用 Bearer Token(API Key) 鉴权，封装平台开放 API：
提交任务 / 列表 / 状态 / 日志 / 结果 / 下载 / 终止 / 用量统计。

所有方法均为 async；网络与业务异常统一转成 GeoApiError，
再由 server 层的 describe_error() 转成对智能体友好的可执行错误文本。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import httpx

# 单次请求默认超时（秒）
DEFAULT_TIMEOUT = 30.0
# 下载 ZIP 可能较大，给更长超时
DOWNLOAD_TIMEOUT = 120.0


class GeoApiError(Exception):
    """GEO 开放 API 调用异常（含 HTTP 状态码与业务错误码）。"""

    def __init__(self, status_code: int, error: str = "", message: str = ""):
        self.status_code = status_code
        self.error = error or "unknown"
        self.message = message or ""
        super().__init__(f"[{status_code}] {self.error}: {self.message}")


class GeoOpenApiClient:
    """GEO-Optimizer 平台开放 API 的异步封装。

    用法::

        async with GeoOpenApiClient(base_url, api_key) as api:
            data = await api.submit_task("https://www.aliyun.com", "plan")
    """

    def __init__(self, base_url: str, api_key: str,
                 timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    # ─── 上下文管理 ─────────────────────────────────────────────
    async def aclose(self) -> None:
        """关闭底层 HTTP 连接。"""
        await self._client.aclose()

    async def __aenter__(self) -> "GeoOpenApiClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    # ─── 内部：统一请求与错误处理 ───────────────────────────────
    async def _request_json(self, method: str, path: str, **kwargs: Any) -> dict:
        """发起请求并解析 JSON，非 2xx 抛 GeoApiError。"""
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise GeoApiError(0, "timeout", f"{method} {path} 请求超时: {exc}") from exc
        except httpx.HTTPError as exc:
            raise GeoApiError(0, "network", f"{method} {path} 网络错误: {type(exc).__name__}: {exc}") from exc
        return self._parse_json(resp)

    @staticmethod
    def _parse_json(resp: httpx.Response) -> dict:
        """把响应解析为 dict；>=400 时抛 GeoApiError（带业务 error/message）。"""
        if resp.status_code >= 400:
            error, message = "unknown", ""
            try:
                data = resp.json()
                if isinstance(data, dict):
                    error = data.get("error", "unknown")
                    message = data.get("message", "")
            except (ValueError, KeyError):
                message = resp.text[:200]
            raise GeoApiError(resp.status_code, error, message)
        try:
            data = resp.json()
        except ValueError as exc:
            raise GeoApiError(resp.status_code, "bad_response",
                              f"响应不是合法 JSON: {resp.text[:200]}") from exc
        return data if isinstance(data, dict) else {"data": data}

    # ─── 开放 API 方法 ─────────────────────────────────────────
    async def submit_task(self, target_url: str, task_type: str = "plan") -> dict:
        """提交评估任务。

        返回: {task_id, status, target_url, task_type, queued, queue_position, message}
        错误: 400 invalid_params / 403 quota_exceeded / 429 concurrent_limit / 503 llm_unavailable
        """
        return await self._request_json("POST", "/api/v1/tasks", json={
            "target_url": target_url,
            "task_type": task_type,
        })

    async def list_tasks(self, limit: int = 10, page: int = 1,
                         start: Optional[str] = None,
                         end: Optional[str] = None) -> dict:
        """当前账号最近任务列表。

        返回: {total, page, limit, pages, tasks:[{task_id,target_url,task_type,status,progress,overall_score,created_at}]}
        """
        params: dict[str, Any] = {"limit": limit, "page": page}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self._request_json("GET", "/api/v1/tasks", params=params)

    async def get_status(self, task_id: str) -> dict:
        """查询任务状态。

        返回: {task_id,target_url,task_type,source,status,progress,message,
              overall_score,error,created_at,completed_at[,queue_position]}
        """
        return await self._request_json("GET", f"/api/v1/tasks/{task_id}")

    async def get_logs(self, task_id: str, after_id: int = 0) -> dict:
        """任务执行日志（已翻译），支持增量拉取。

        返回: {task_id,status,progress,logs:[{id,level,message,detail,time}],last_id}
        """
        return await self._request_json("GET", f"/api/v1/tasks/{task_id}/logs",
                                        params={"after_id": after_id})

    async def get_result(self, task_id: str) -> dict:
        """获取任务结果（仅 completed 返回完整数据）。

        返回: {task_id,status,overall_score,result,download_url,share_download_url}
        """
        return await self._request_json("GET", f"/api/v1/tasks/{task_id}/result")

    async def cancel_task(self, task_id: str) -> dict:
        """终止任务（排队中/运行中均可）。

        返回: {task_id,status(cancelling|cancelled),message}；已完成时 409 invalid_state
        """
        return await self._request_json("POST", f"/api/v1/tasks/{task_id}/cancel")

    async def get_usage(self) -> dict:
        """API 调用统计。

        返回: {total_calls, keys:[{id,name,key_prefix,total_calls,is_active,last_used_at}]}
        """
        return await self._request_json("GET", "/api/v1/usage")

    async def download_report(self, task_id: str, save_path: str) -> Path:
        """下载报告与改进方案 ZIP 到本地，返回保存路径。

        错误: 404 not_found（无下载包）
        """
        try:
            resp = await self._client.get(f"/api/v1/tasks/{task_id}/download",
                                          timeout=DOWNLOAD_TIMEOUT)
        except httpx.TimeoutException as exc:
            raise GeoApiError(0, "timeout", f"下载超时: {exc}") from exc
        except httpx.HTTPError as exc:
            raise GeoApiError(0, "network", f"下载网络错误: {type(exc).__name__}: {exc}") from exc

        if resp.status_code >= 400:
            # 错误响应仍是 JSON，复用统一解析
            self._parse_json(resp)

        path = Path(save_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return path


# ─── 错误文本映射：把异常转成对智能体友好、可执行的中文提示 ────────────
def describe_error(exc: Exception) -> str:
    """把 GeoApiError / 其它异常转成清晰、可执行的错误提示文本。

    针对平台已知业务错误码给出下一步建议，帮助智能体自我纠正。
    """
    if isinstance(exc, GeoApiError):
        code, status = exc.error, exc.status_code
        hints = {
            "invalid_token": "API Key 无效或已过期。请检查 GEO_API_KEY，或在 MCP 请求头携带有效的 Authorization: Bearer geo_xxx。",
            "missing_token": "缺少 API Key。请设置环境变量 GEO_API_KEY，或在 MCP 请求头携带 Authorization: Bearer geo_xxx。",
            "quota_exceeded": "评估配额已用尽。请联系平台管理员提升配额，或终止排队中的任务以退回配额。",
            "concurrent_limit": "当前账号并发任务过多（上限 3）。请等待现有任务完成，或用 geo_cancel_task 终止后重试。",
            "llm_unavailable": "该账号算力(LLM)接口不可用。请联系平台管理员为该账号配置可用算力。",
            "not_found": "任务或资源不存在。请用 geo_list_tasks 确认 task_id 是否正确。",
            "forbidden": "无权访问该任务（不属于当前 API Key 账号）。",
            "invalid_state": exc.message or "任务已处于终态（completed/failed/cancelled），无法再执行该操作。",
            "invalid_params": exc.message or "请求参数不合法。请检查 target_url 是否为空、task_type 是否为 plan/eval。",
            "timeout": "请求超时。平台可能负载较高，请稍后重试。",
            "network": f"无法连接平台服务。请确认 GEO_BASE_URL 是否正确、平台是否已启动。（{exc.message}）",
            "download_failed": "下载失败：该任务暂无可下载的方案包（可能为 eval 任务或方案尚未生成）。",
        }
        if code in hints:
            return f"错误[{code}]：{hints[code]}"
        if status == 0:
            return f"错误[{code}]：{exc.message}"
        # 状态码兜底：某些网关/代理会返回裸 401/403/404/429/503（非 JSON、无 error 码），
        # 仍据 HTTP 状态给出可执行提示，避免只回一句“请求失败”。
        if code in ("unknown", "", None):
            status_hints = {
                401: "鉴权失败：API Key 缺失/无效/已过期。请设置 GEO_API_KEY，或在 MCP 请求头携带 Authorization: Bearer geo_xxx。",
                403: "请求被拒绝（403）：可能是 API Key 无效、权限/配额不足，或网关拦截。请检查 key 与 GEO_BASE_URL 是否指向 GEO 平台。",
                404: "资源不存在（404）。请用 geo_list_tasks 确认 task_id 是否正确。",
                429: "请求过于频繁或并发超限（429）。请稍后重试，或用 geo_cancel_task 终止部分任务。",
                503: "服务不可用（503）：算力接口或平台暂不可用，请联系管理员或稍后重试。",
            }
            if status in status_hints:
                return f"错误[HTTP {status}]：{status_hints[status]}"
        return f"错误[HTTP {status} / {code}]：{exc.message or '请求失败'}"

    # 非预期异常：不泄漏内部细节，仅给出类型
    return f"错误[unexpected]：发生未预期异常 {type(exc).__name__}。请重试或检查服务端日志。"

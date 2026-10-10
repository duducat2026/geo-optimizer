#!/usr/bin/env python3
"""
GEO-Optimizer Skill API 客户端 — GeoSkillClient 类实现。

基于 httpx 实现，通过 Bearer Token (API Key) 鉴权，
支持提交 GEO 评估任务、轮询状态、获取结果与下载报告。
"""
import functools
import time
from pathlib import Path
from typing import Optional

import httpx

from geo_skill_common import (
    ESTIMATED_MINUTES,
    GeoSkillError,
    client_log,
    format_log_entry,
    normalize_url,
    resolve_credentials,
    resolve_poll_interval,
)

# 智能体/管道环境双保险：每条 print 强制刷新，避免进度摊到进程结束才输出
print = functools.partial(print, flush=True)


class GeoSkillClient:
    """GEO-Optimizer 平台 Skill 客户端。

    封装平台开放 API，提供完整的任务生命周期管理：
    提交 → 轮询 → 获取结果 → 下载报告。
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        """
        初始化客户端。

        Args:
            base_url: 平台服务地址，如 "http://localhost:5001"
            api_key: API 密钥（以 "geo_" 开头）
            timeout: 单次请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    def close(self) -> None:
        """关闭 HTTP 连接。"""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @classmethod
    def from_config(cls, base_url: Optional[str] = None,
                    api_key: Optional[str] = None,
                    timeout: float = 30.0) -> "GeoSkillClient":
        """从环境变量 / config.json 自动解析凭据并创建客户端。

        Raises:
            ValueError: 未能解析到 API 密钥
        """
        base_url, api_key = resolve_credentials(base_url, api_key)
        if not api_key or api_key.startswith("<"):
            raise ValueError(
                "API key not found. Set GEO_API_KEY env var, provide config.json, "
                "or pass api_key explicitly."
            )
        return cls(base_url, api_key, timeout=timeout)

    # ─── 内部方法 ───────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """发起 HTTP 请求，并以客户端执行日志展示方法/路径/状态码/耗时。"""
        t0 = time.monotonic()
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            # 网络层异常（证书校验失败/连接超时等）先落日志再抛出，便于定位
            client_log(f"{method} {path} 请求失败: {type(exc).__name__}: {exc}")
            raise
        client_log(f"{method} {path} → {resp.status_code} "
                   f"({(time.monotonic() - t0) * 1000:.0f}ms)")
        return resp

    def _handle_response(self, resp: httpx.Response) -> dict:
        """统一响应处理，非 2xx 抛出 GeoSkillError。"""
        if resp.status_code >= 400:
            try:
                data = resp.json()
                error = data.get("error", "unknown")
                message = data.get("message", "")
                # 算力不可用时给出明确提示
                if error == "llm_unavailable":
                    message = message or "算力接口不可用，请联系管理员。"
                raise GeoSkillError(
                    status_code=resp.status_code,
                    error=error,
                    message=message,
                )
            except (ValueError, KeyError):
                raise GeoSkillError(
                    status_code=resp.status_code,
                    error="unknown",
                    message=resp.text[:200],
                )
        return resp.json()

    # ─── 核心 API ───────────────────────────────────────────────

    def submit(self, target_url: str, task_type: str = "plan") -> str:
        """提交 GEO 评估任务，返回 task_id。

        target_url 裸域名自动补全 https://；task_type: "eval"=仅评分 /
        "plan"=评分+优化方案+多平台内容。参数错误/配额不足/并发超限时抛 GeoSkillError。
        """
        url = normalize_url(target_url)
        client_log(f"提交评估任务: {url} (类型: {task_type})")
        resp = self._request("POST", "/api/v1/tasks", json={
            "target_url": url,
            "task_type": task_type,
        })
        data = self._handle_response(resp)
        task_id = data["task_id"]
        queued = data.get("queued", False)
        if queued:
            pos = data.get("queue_position", "?")
            print(f"  [排队中] 任务进入排队，当前位置 #{pos}，任务 ID: {task_id}")
        else:
            print(f"  [已提交] 任务已提交，任务 ID: {task_id}")
        # 提交后提醒预计耗时（不做定时轮询，进度查询由使用人员发起）
        est = ESTIMATED_MINUTES.get(task_type, 5)
        print(f"  [提示] 评估网站: {url} | 任务 ID: {task_id} | 预计约 {est} 分钟完成分析")
        return task_id

    def list_tasks(self, limit: int = 10, page: int = 1,
                   start: str | None = None, end: str | None = None) -> dict:
        """当前账号任务列表: {"total", "page", "limit", "pages", "tasks": [...]}。

        支持分页（page/limit）与日期时间范围过滤（start/end，按 created_at）。
        """
        params: dict = {"limit": limit, "page": page}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = self._request("GET", "/api/v1/tasks", params=params)
        return self._handle_response(resp)

    def get_status(self, task_id: str) -> dict:
        """查询任务状态: {"task_id", "status", "progress", "overall_score", "message", ...}。"""
        resp = self._request("GET", f"/api/v1/tasks/{task_id}")
        return self._handle_response(resp)

    def get_result(self, task_id: str) -> dict:
        """获取任务结果（仅 completed 状态返回完整数据）:
        {"task_id", "status", "overall_score", "result", "download_url"}。"""
        resp = self._request("GET", f"/api/v1/tasks/{task_id}/result")
        return self._handle_response(resp)

    def get_logs(self, task_id: str, after_id: int = 0) -> dict:
        """获取任务云端执行日志（已翻译），支持增量拉取（after_id=只返回更新的日志）:
        {"status", "progress", "logs": [{id, level, message, detail, time}], "last_id"}。"""
        resp = self._request("GET", f"/api/v1/tasks/{task_id}/logs",
                             params={"after_id": after_id})
        return self._handle_response(resp)

    def download(self, task_id: str, save_path: str) -> Path:
        """下载评估报告与改进方案 ZIP 包，返回保存的文件 Path。"""
        resp = self._request("GET", f"/api/v1/tasks/{task_id}/download")
        if resp.status_code >= 400:
            try:
                data = resp.json()
                raise GeoSkillError(resp.status_code, data.get("error", ""), data.get("message", ""))
            except (ValueError, KeyError):
                raise GeoSkillError(resp.status_code, "download_failed", resp.text[:200])

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        print(f"  [下载] 报告已保存: {path} ({len(resp.content)} 字节)")
        return path

    def cancel(self, task_id: str) -> dict:
        """终止任务（排队中/运行中均可）: {"task_id", "status", "message"}。"""
        resp = self._request("POST", f"/api/v1/tasks/{task_id}/cancel")
        return self._handle_response(resp)

    def get_usage(self) -> dict:
        """获取 API 调用统计: {"total_calls", "keys": [...]}。"""
        resp = self._request("GET", "/api/v1/usage")
        return self._handle_response(resp)

    # ─── 高级方法 ───────────────────────────────────────────────

    def wait_and_get_result(self, task_id: str, timeout: float = 600,
                            poll_interval: Optional[float] = None,
                            show_logs: bool = True) -> dict:
        """
        轮询等待任务完成并返回结果（阻塞当前进程，适合交互终端）。

        每隔 poll_interval 秒查询一次任务状态，并将状态/进度/已等待时长
        以及云端新增的任务执行日志实时展示到客户端。
        智能体环境请改用 CLI 的 --poll 单次轮询模式，避免进程长时间阻塞。

        Args:
            task_id: 任务 ID
            timeout: 最大等待时间（秒），默认 600
            poll_interval: 轮询间隔（秒），None 时按优先级解析
                （环境变量 GEO_POLL_INTERVAL > config.json poll_interval > 默认 6）
            show_logs: 是否增量展示云端执行日志（默认开启）

        Returns:
            完整任务结果字典

        Raises:
            TimeoutError: 超时未完成
            GeoSkillError: 任务失败或被取消
        """
        poll_interval = resolve_poll_interval(poll_interval)
        start = time.monotonic()
        last_log_id = 0

        while True:
            status_data = self.get_status(task_id)
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            elapsed = int(time.monotonic() - start)

            # 增量拉取云端执行日志并展示
            if show_logs:
                try:
                    log_data = self.get_logs(task_id, after_id=last_log_id)
                    for entry in log_data.get("logs", []):
                        print(format_log_entry(entry))
                    last_log_id = log_data.get("last_id", last_log_id)
                except GeoSkillError as exc:
                    # 仅端点不存在（404，旧版服务端）时永久停拉；
                    # 其余错误（偶发 403/瞬时 5xx/网络抖动）本轮跳过、下一轮继续重试，
                    # 避免一次抖动就永久关掉云端进度日志展示
                    if exc.status_code == 404:
                        show_logs = False

            # 每次轮询都展示当前状态到客户端
            if status == "running":
                msg = status_data.get("message", "")
                print(f"  [进行中] 进度 {progress}% | 已等待 {elapsed} 秒 | {msg}")

            if status == "completed":
                print(f"  [已完成] GEO 综合评分: {status_data.get('overall_score', 'N/A')}")
                return self.get_result(task_id)
            elif status == "failed":
                raise GeoSkillError(
                    status_code=500,
                    error="task_failed",
                    message=status_data.get("error", "任务执行失败"),
                )
            elif status == "cancelled":
                raise GeoSkillError(
                    status_code=409,
                    error="task_cancelled",
                    message="任务已被取消",
                )
            elif status == "queued":
                pos = status_data.get("queue_position", "?")
                print(f"  [排队中] 排队位置 #{pos} | 已等待 {elapsed} 秒")

            if time.monotonic() - start >= timeout:
                raise TimeoutError(
                    f"任务 {task_id} 在 {timeout} 秒内未完成"
                    f"（当前状态: {status}, 进度: {progress}%）"
                )

            time.sleep(poll_interval)

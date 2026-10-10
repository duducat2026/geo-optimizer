# -*- coding: utf-8 -*-
"""
GEO-Optimizer 开放 API Python 客户端。

基于 httpx 实现，使用 API 密钥（Bearer Token）进行鉴权。

用法示例:
    from client.geo_api_client import GeoApiClient

    client = GeoApiClient("http://localhost:5000", "geo_your_api_key")
    task_id = client.submit_task("https://example.com", task_type="plan")
    result = client.wait_for_completion(task_id, timeout=600)
    print(f"Score: {result['overall_score']}")
    client.download(task_id, "report.zip")
"""
import time
from pathlib import Path
from typing import Optional

import httpx


class GeoApiError(Exception):
    """API 调用异常。"""

    def __init__(self, status_code: int, error: str = "", message: str = ""):
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(f"[{status_code}] {error}: {message}")


class GeoApiClient:
    """GEO-Optimizer 开放 API 客户端。"""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        """
        初始化客户端。

        Args:
            base_url: 服务地址，如 "http://localhost:5000"
            api_key: API 密钥（以 "geo_" 开头）
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )

    def close(self) -> None:
        """关闭 HTTP 连接。"""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _handle_response(self, resp: httpx.Response) -> dict:
        """统一处理响应，非 2xx 抛出异常。"""
        if resp.status_code >= 400:
            try:
                data = resp.json()
                raise GeoApiError(
                    status_code=resp.status_code,
                    error=data.get("error", ""),
                    message=data.get("message", ""),
                )
            except (ValueError, KeyError):
                raise GeoApiError(
                    status_code=resp.status_code,
                    error="unknown",
                    message=resp.text[:200],
                )
        return resp.json()

    def submit_task(self, target_url: str, task_type: str = "plan") -> str:
        """
        提交评估任务。

        Args:
            target_url: 目标网站 URL
            task_type: 任务类型，"eval"（仅评估）或 "plan"（评估+方案）

        Returns:
            task_id: 任务 ID
        """
        resp = self._client.post("/api/v1/tasks", json={
            "target_url": target_url,
            "task_type": task_type,
        })
        data = self._handle_response(resp)
        return data["task_id"]

    def get_task_status(self, task_id: str) -> dict:
        """
        查询任务状态。

        Args:
            task_id: 任务 ID

        Returns:
            包含 status, progress, overall_score 等字段的字典
        """
        resp = self._client.get(f"/api/v1/tasks/{task_id}")
        return self._handle_response(resp)

    def get_task_result(self, task_id: str) -> dict:
        """
        获取任务结果（仅 completed 状态返回完整数据）。

        Args:
            task_id: 任务 ID

        Returns:
            包含 result, overall_score, download_url 等字段的字典
        """
        resp = self._client.get(f"/api/v1/tasks/{task_id}/result")
        return self._handle_response(resp)

    def download(self, task_id: str, save_path: str) -> Path:
        """
        下载评估报告与改进方案 ZIP 包。

        Args:
            task_id: 任务 ID
            save_path: 保存路径

        Returns:
            保存的文件路径
        """
        resp = self._client.get(f"/api/v1/tasks/{task_id}/download")
        if resp.status_code >= 400:
            try:
                data = resp.json()
                raise GeoApiError(resp.status_code, data.get("error", ""), data.get("message", ""))
            except (ValueError, KeyError):
                raise GeoApiError(resp.status_code, "download_failed", resp.text[:200])

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return path

    def wait_for_completion(self, task_id: str, timeout: float = 600,
                            poll_interval: float = 5) -> dict:
        """
        轮询等待任务完成（支持排队状态）。

        Args:
            task_id: 任务 ID
            timeout: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            任务结果字典

        Raises:
            TimeoutError: 超时未完成
            GeoApiError: 任务失败或被取消
        """
        start = time.monotonic()
        while True:
            status_data = self.get_task_status(task_id)
            status = status_data.get("status")

            if status == "completed":
                return self.get_task_result(task_id)
            elif status == "failed":
                raise GeoApiError(
                    status_code=500,
                    error="task_failed",
                    message=status_data.get("error", "Task execution failed"),
                )
            elif status == "cancelled":
                raise GeoApiError(
                    status_code=409,
                    error="task_cancelled",
                    message="Task was cancelled",
                )
            elif status == "queued":
                pos = status_data.get("queue_position", "?")
                print(f"      [queued] position #{pos}, waiting...")

            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Task {task_id} not completed within {timeout}s "
                    f"(current status: {status}, progress: {status_data.get('progress')}%)"
                )

            time.sleep(poll_interval)

    def cancel_task(self, task_id: str) -> dict:
        """
        终止任务（排队中/运行中均可）。

        Args:
            task_id: 任务 ID

        Returns:
            包含 status 和 message 的字典
        """
        resp = self._client.post(f"/api/v1/tasks/{task_id}/cancel")
        return self._handle_response(resp)

    def get_usage(self) -> dict:
        """
        获取 API 调用统计。

        Returns:
            包含 total_calls 和 keys 列表的字典
        """
        resp = self._client.get("/api/v1/usage")
        return self._handle_response(resp)


def main():
    """命令行演示：完整调用流程。"""
    import argparse

    parser = argparse.ArgumentParser(description="GEO-Optimizer API Client")
    parser.add_argument("--base-url", default="http://localhost:5000", help="Server base URL")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--url", required=True, help="Target URL to evaluate")
    parser.add_argument("--type", default="plan", choices=["eval", "plan"], help="Task type")
    parser.add_argument("--output", default="geo_report.zip", help="Download save path")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait seconds")
    args = parser.parse_args()

    with GeoApiClient(args.base_url, args.api_key) as client:
        print(f"[1/4] Submitting task: {args.url} (type={args.type})")
        task_id = client.submit_task(args.url, task_type=args.type)
        print(f"      Task ID: {task_id}")

        print(f"[2/4] Waiting for completion (timeout={args.timeout}s)...")
        result = client.wait_for_completion(task_id, timeout=args.timeout)
        print(f"      Score: {result.get('overall_score', 'N/A')}")

        print("[3/4] Fetching usage stats...")
        usage = client.get_usage()
        print(f"      Total API calls: {usage.get('total_calls', 0)}")

        download_url = result.get("download_url")
        if download_url:
            print(f"[4/4] Downloading report to {args.output}...")
            path = client.download(task_id, args.output)
            print(f"      Saved: {path}")
        else:
            print("[4/4] No download package available (eval-only task or plan not generated)")

        print("\nDone!")


if __name__ == "__main__":
    main()

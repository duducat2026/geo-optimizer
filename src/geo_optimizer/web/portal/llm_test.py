# -*- coding: utf-8 -*-
"""LLM 连通性调用测试（用户侧算力与平台侧算力方案共用）。"""
import time


def test_llm_connection(api_key: str, base_url: str, model: str) -> tuple:
    """尝试调用 LLM API，返回 (success: bool, detail: dict)。

    detail 记录调用过程明细：端点、请求/响应模型、耗时、token 用量、回复或错误。
    """
    detail = {
        "endpoint": base_url,
        "model_requested": model or "qwen-plus",
        "model_responded": "",
        "elapsed_ms": 0,
        "usage": None,
        "reply": "",
        "error": "",
    }
    start = time.monotonic()
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=15)
        resp = client.chat.completions.create(
            model=detail["model_requested"],
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        detail["elapsed_ms"] = int((time.monotonic() - start) * 1000)
        detail["model_responded"] = getattr(resp, "model", "") or ""
        usage = getattr(resp, "usage", None)
        if usage:
            detail["usage"] = {
                "prompt": getattr(usage, "prompt_tokens", 0) or 0,
                "completion": getattr(usage, "completion_tokens", 0) or 0,
                "total": getattr(usage, "total_tokens", 0) or 0,
            }
        reply = resp.choices[0].message.content if resp.choices else ""
        detail["reply"] = (reply or "")[:200]
        return True, detail
    except Exception as exc:  # noqa: BLE001
        detail["elapsed_ms"] = int((time.monotonic() - start) * 1000)
        detail["error"] = str(exc)[:200]
        return False, detail

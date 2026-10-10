# -*- coding: utf-8 -*-
"""任务运行时配置构建：合并基础配置 + 数据库系统配置(LLM) + 目标 URL/输出目录。

算力优先级：用户侧算力 > 平台侧算力。
"""
import copy
import logging

from geo_optimizer.config import load_config
from geo_optimizer.web.portal.models import SystemConfig, SystemLLMConfig

logger = logging.getLogger(__name__)

# 算力方案预设 Base URL 映射
PROVIDER_BASE_URLS = {
    "bailian": {
        "openai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "dashscope_base_url": "https://dashscope.aliyuncs.com/api/v1",
    },
    "token_plan": {
        "openai_base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "dashscope_base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1",
    },
}


def get_user_active_llm(user_id: int):
    """获取用户当前激活的算力配置，无则返回 None。"""
    from geo_optimizer.web.portal.models import UserLLMConfig

    return UserLLMConfig.query.filter_by(user_id=user_id, is_active=True).first()


def user_has_available_llm(user_id: int, can_use_platform: bool) -> bool:
    """判断用户是否有可用算力：用户侧配置优先，其次看平台算力权限。"""
    if get_user_active_llm(user_id):
        return True
    if can_use_platform:
        active = SystemLLMConfig.active()
        if active and active.api_key:
            return True
        sc = SystemConfig.as_dict()
        return bool(sc.get("api_key"))
    return False


def _apply_task_target(config: dict, target_url: str, output_dir: str) -> dict:
    """写入任务目标与产物目录，并限制为单页爬取。

    Web 流水线（eval/plan 共用）只消费首页结果，若沿用全局配置的
    crawl_depth/max_pages 会对链接多的站点逐页深爬几十页，
    导致任务长时间停在 10% 爬取阶段。
    """
    target = config.setdefault("target", {})
    target["url"] = target_url
    target["crawl_depth"] = 0
    target["max_pages"] = 1
    config.setdefault("output", {})["dir"] = output_dir
    return config


def build_config(target_url: str, output_dir: str, user_id: int | None = None) -> dict:
    """构造供爬取/分析/生成链路使用的 config 字典。

    算力优先级：
    1. 用户侧激活的 UserLLMConfig
    2. 平台侧 SystemConfig（需用户有平台算力权限）
    """
    try:
        config = copy.deepcopy(load_config())
    except Exception:
        config = {}

    llm = config.setdefault("llm", {})

    # 1. 尝试用户侧算力
    user_cfg = get_user_active_llm(user_id) if user_id else None
    if user_cfg and user_cfg.api_key:
        llm["api_key"] = user_cfg.api_key
        if user_cfg.base_url:
            llm["base_url"] = user_cfg.base_url
        if user_cfg.model:
            llm["model"] = user_cfg.model
        llm["_source"] = "user"
        llm["_source_label"] = f"用户侧算力 (user_id={user_id}, provider={user_cfg.provider})"
        logger.info(
            "[算力来源] 用户侧配置 | user_id=%s, provider=%s, model=%s, base_url=%s",
            user_id, user_cfg.provider, llm.get("model"), llm.get("base_url"),
        )
        return _apply_task_target(config, target_url, output_dir)

    # 2. 回退到平台侧算力
    sc = SystemConfig.as_dict()

    # 2a. 优先使用启用的平台算力方案（多方案管理）
    sys_cfg = SystemLLMConfig.active()
    if sys_cfg and sys_cfg.api_key:
        provider = sys_cfg.provider
        llm["api_key"] = sys_cfg.api_key
        if sys_cfg.base_url:
            llm["base_url"] = sys_cfg.base_url
        elif provider in PROVIDER_BASE_URLS:
            llm["base_url"] = PROVIDER_BASE_URLS[provider]["openai_base_url"]
        if sys_cfg.model:
            llm["model"] = sys_cfg.model
    else:
        # 2b. 无启用方案时回退旧版单键值配置（存量兼容）
        provider = sc.get("llm_provider", "")
        if provider in PROVIDER_BASE_URLS:
            preset = PROVIDER_BASE_URLS[provider]
            llm["base_url"] = preset["openai_base_url"]

        # 数据库配置覆盖（优先级最高）
        if sc.get("api_key"):
            llm["api_key"] = sc["api_key"]
        if sc.get("openai_base_url"):
            llm["base_url"] = sc["openai_base_url"]
        if sc.get("model"):
            llm["model"] = sc["model"]

    # 模型参数为全局配置，与具体方案无关
    if sc.get("temperature"):
        llm["temperature"] = float(sc["temperature"])
    if sc.get("max_tokens"):
        llm["max_tokens"] = int(sc["max_tokens"])

    llm["_source"] = "platform"
    llm["_source_label"] = f"平台侧算力 (provider={provider or 'custom'})"
    logger.info(
        "[算力来源] 平台侧配置 | provider=%s, model=%s, base_url=%s",
        provider or "custom", llm.get("model"), llm.get("base_url"),
    )

    return _apply_task_target(config, target_url, output_dir)

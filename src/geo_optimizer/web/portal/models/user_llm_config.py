# -*- coding: utf-8 -*-
"""用户侧算力配置模型：每个用户可配置多条 LLM 算力（token_plan / bailian / custom），
其中一条标记为当前使用（is_active）。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db

PROVIDER_BAILIAN = "bailian"
PROVIDER_TOKEN_PLAN = "token_plan"
PROVIDER_CUSTOM = "custom"

USER_LLM_PROVIDERS = (PROVIDER_BAILIAN, PROVIDER_TOKEN_PLAN, PROVIDER_CUSTOM)

# 各方案预设 Base URL
USER_PROVIDER_PRESETS = {
    PROVIDER_BAILIAN: {
        "label": "百炼按量付费",
        "openai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    PROVIDER_TOKEN_PLAN: {
        "label": "Token Plan 团队版",
        "openai_base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    },
    PROVIDER_CUSTOM: {
        "label": "自定义",
        "openai_base_url": "",
    },
}


class UserLLMConfig(db.Model):
    __tablename__ = "user_llm_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False, default=PROVIDER_BAILIAN)
    name = db.Column(db.String(64), default="", nullable=False)  # 用户自定义备注名
    api_key = db.Column(db.String(255), nullable=False, default="")
    base_url = db.Column(db.String(512), nullable=False, default="")
    model = db.Column(db.String(128), nullable=False, default="")
    is_active = db.Column(db.Boolean, default=False, nullable=False)  # 当前使用
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider": self.provider,
            "name": self.name,
            "api_key_masked": self.api_key_masked,
            "base_url": self.base_url,
            "model": self.model,
            "is_active": self.is_active,
            "created_at": fmt_local(self.created_at),
            "updated_at": fmt_local(self.updated_at),
        }

    @property
    def api_key_masked(self) -> str:
        """脱敏展示 API Key：仅保留前 6 位与后 4 位。"""
        if not self.api_key or len(self.api_key) <= 10:
            return "****"
        return self.api_key[:6] + "****" + self.api_key[-4:]

    @property
    def provider_label(self) -> str:
        preset = USER_PROVIDER_PRESETS.get(self.provider)
        return preset["label"] if preset else self.provider

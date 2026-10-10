# -*- coding: utf-8 -*-
"""平台侧算力方案模型：管理员可配置多条平台 LLM 算力方案，
其中一条标记为当前使用（is_active），作为平台统一算力。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models.user_llm_config import (
    PROVIDER_BAILIAN,
    USER_PROVIDER_PRESETS,
)


class SystemLLMConfig(db.Model):
    __tablename__ = "system_llm_configs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    provider = db.Column(db.String(32), nullable=False, default=PROVIDER_BAILIAN)
    name = db.Column(db.String(64), default="", nullable=False)  # 备注名
    api_key = db.Column(db.String(255), nullable=False, default="")
    base_url = db.Column(db.String(512), nullable=False, default="")
    model = db.Column(db.String(128), nullable=False, default="")
    is_active = db.Column(db.Boolean, default=False, nullable=False)  # 当前平台算力
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def active():
        """当前启用的平台算力方案，无则返回 None。"""
        return SystemLLMConfig.query.filter_by(is_active=True).first()

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

# -*- coding: utf-8 -*-
"""开放 API 密钥模型。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    key_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    key_prefix = db.Column(db.String(12), nullable=False)  # 如 "geo_a3Bf9x"
    # 明文密钥（支持事后查看/复制；旧记录可能为空，需重新生成后才有）
    key_plaintext = db.Column(db.String(128), nullable=True)
    name = db.Column(db.String(64), default="", nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_used_at = db.Column(db.DateTime)
    total_calls = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "user_id": self.user_id,
            "key_prefix": self.key_prefix,
            "name": self.name,
            "expires_at": fmt_local(self.expires_at),
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "last_used_at": fmt_local(self.last_used_at),
            "total_calls": self.total_calls,
            "created_at": fmt_local(self.created_at),
        }

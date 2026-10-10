# -*- coding: utf-8 -*-
"""系统配置模型（键值对，存 LLM key/host/model 等）。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db


class SystemConfig(db.Model):
    __tablename__ = "system_config"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, default="", nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key: str, default: str = "") -> str:
        row = db.session.get(SystemConfig, key)
        return row.value if row else default

    @staticmethod
    def set(key: str, value: str) -> None:
        row = db.session.get(SystemConfig, key)
        if row:
            row.value = value
        else:
            db.session.add(SystemConfig(key=key, value=value))

    @staticmethod
    def as_dict() -> dict:
        return {row.key: row.value for row in SystemConfig.query.all()}

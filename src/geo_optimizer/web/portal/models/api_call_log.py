# -*- coding: utf-8 -*-
"""API 调用日志模型。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db


class ApiCallLog(db.Model):
    __tablename__ = "api_call_logs"

    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey("api_keys.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint = db.Column(db.String(256), default="", nullable=False)
    method = db.Column(db.String(16), default="GET", nullable=False)
    status_code = db.Column(db.Integer, default=200, nullable=False)
    ip = db.Column(db.String(64), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "api_key_id": self.api_key_id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "ip": self.ip,
            "created_at": fmt_local(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }

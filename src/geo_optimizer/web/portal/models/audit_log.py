# -*- coding: utf-8 -*-
"""操作审计日志模型。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    username = db.Column(db.String(64), default="", index=True)
    action = db.Column(db.String(64), default="", nullable=False, index=True)
    target = db.Column(db.String(512), default="")
    ip = db.Column(db.String(64), default="")
    detail = db.Column(db.String(512), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "target": self.target,
            "ip": self.ip,
            "detail": self.detail,
            "created_at": fmt_local(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }

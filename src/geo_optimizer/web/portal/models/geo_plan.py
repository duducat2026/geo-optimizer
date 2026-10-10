# -*- coding: utf-8 -*-
"""GEO 方案模型（记录可下载的双语方案包）。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db


class GeoPlan(db.Model):
    __tablename__ = "geo_plans"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey("eval_tasks.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_url = db.Column(db.String(512), nullable=False)
    summary = db.Column(db.String(512), default="")
    zip_path = db.Column(db.String(512), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "target_url": self.target_url,
            "summary": self.summary,
            "has_zip": bool(self.zip_path),
            "created_at": fmt_local(self.created_at),
        }

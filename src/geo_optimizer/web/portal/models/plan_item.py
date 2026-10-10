# -*- coding: utf-8 -*-
"""改进方案条目模型（LLM 生成、用户可编辑、支持单项/整体下载）。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db

PRIORITY_HIGH = "high"
PRIORITY_MID = "mid"
PRIORITY_LOW = "low"
PRIORITIES = (PRIORITY_HIGH, PRIORITY_MID, PRIORITY_LOW)


class PlanItem(db.Model):
    __tablename__ = "plan_items"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey("eval_tasks.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code = db.Column(db.String(64), nullable=False)
    priority = db.Column(db.String(8), default=PRIORITY_MID, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text().with_variant(db.Text(length=4_294_967_295), "mysql"), default="")
    source = db.Column(db.String(16), default="template", nullable=False)  # llm / template
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "task_id": self.task_id,
            "code": self.code,
            "priority": self.priority,
            "title": self.title,
            "source": self.source,
            "updated_at": fmt_local(self.updated_at),
        }

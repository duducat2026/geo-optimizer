# -*- coding: utf-8 -*-
"""任务处理日志模型（控制台展示，按时间倒排）。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db

LEVEL_INFO = "info"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"


class TaskLog(db.Model):
    __tablename__ = "task_logs"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey("eval_tasks.id"),
                        nullable=False, index=True)
    level = db.Column(db.String(8), default=LEVEL_INFO, nullable=False)
    message = db.Column(db.String(255), default="", nullable=False)  # i18n key
    detail = db.Column(db.String(255), default="", nullable=False)   # 动态附加信息
    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           nullable=False, index=True)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "level": self.level,
            "message": self.message,
            "detail": self.detail,
            "time": fmt_local(self.created_at, "%m-%d %H:%M:%S"),
        }

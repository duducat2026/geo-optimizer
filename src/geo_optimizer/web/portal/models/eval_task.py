# -*- coding: utf-8 -*-
"""评估/方案任务模型。"""
import json
from datetime import datetime

from geo_optimizer.web.portal.extensions import db

STATUS_PENDING = "pending"
STATUS_QUEUED = "queued"      # 排队中（全局并发已满）
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"  # 用户终止

TYPE_EVAL = "eval"    # 仅 GEO 评估
TYPE_PLAN = "plan"    # 评估 + 生成方案

SOURCE_WEB = "web"    # 网站提交
SOURCE_API = "api"    # API 调用


class EvalTask(db.Model):
    __tablename__ = "eval_tasks"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_url = db.Column(db.String(512), nullable=False)
    type = db.Column(db.String(16), default=TYPE_EVAL, nullable=False)
    status = db.Column(db.String(16), default=STATUS_PENDING, nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)
    message = db.Column(db.String(255), default="", nullable=False)
    overall_score = db.Column(db.Float, default=0.0, nullable=False)
    result_json = db.Column(db.Text().with_variant(db.Text(length=4_294_967_295), "mysql"), default="")
    artifact_dir = db.Column(db.String(512), default="")
    source = db.Column(db.String(16), default=SOURCE_WEB, nullable=False)
    error = db.Column(db.String(512), default="")
    # 免登录分享链接的下载计数（属主/管理员下载不计入，上限由系统配置 download_limit 控制）
    eval_download_count = db.Column(db.Integer, default=0, nullable=False)
    bundle_download_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = db.Column(db.DateTime)

    def result(self) -> dict:
        if not self.result_json:
            return {}
        try:
            return json.loads(self.result_json)
        except (ValueError, TypeError):
            return {}

    def set_result(self, data: dict) -> None:
        self.result_json = json.dumps(data, ensure_ascii=False)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_url": self.target_url,
            "type": self.type,
            "source": self.source,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "overall_score": self.overall_score,
            "error": self.error,
            "created_at": fmt_local(self.created_at),
            "completed_at": fmt_local(self.completed_at),
        }

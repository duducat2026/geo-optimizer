# -*- coding: utf-8 -*-
"""改进方案产出物模型（sitemap/robots/文章/FAQ 等具体文件，可编辑可下载）。"""
from datetime import datetime

from geo_optimizer.web.portal.extensions import db

SOURCE_RULE = "rule"  # 规则生成（sitemap/robots 等）
SOURCE_LLM = "llm"    # LLM 结合站点内容生成
SOURCE_TEMPLATE = "template"  # LLM 不可用时的骨架模板


class PlanArtifact(db.Model):
    __tablename__ = "plan_artifacts"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("plan_items.id"), nullable=False, index=True)
    task_id = db.Column(db.String(36), db.ForeignKey("eval_tasks.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(32), nullable=False)          # sitemap_xml / faq_html / ...
    filename = db.Column(db.String(128), nullable=False)     # 下载文件名
    content = db.Column(db.Text().with_variant(db.Text(length=4_294_967_295), "mysql"), default="")
    source = db.Column(db.String(16), default=SOURCE_TEMPLATE, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "item_id": self.item_id,
            "task_id": self.task_id,
            "kind": self.kind,
            "filename": self.filename,
            "source": self.source,
            "updated_at": fmt_local(self.updated_at),
        }

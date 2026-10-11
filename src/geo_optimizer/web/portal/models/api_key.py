# -*- coding: utf-8 -*-
"""开放 API 密钥模型。"""
from datetime import date, datetime

from geo_optimizer.web.portal.extensions import db

DEFAULT_DAILY_QUOTA = 50  # 每密钥每日默认调用额度（0 表示不限）


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
    # 每日调用限额：calls_today 对应 quota_date 自然日，跨天重置
    daily_quota = db.Column(db.Integer, default=DEFAULT_DAILY_QUOTA, nullable=False)
    calls_today = db.Column(db.Integer, default=0, nullable=False)
    quota_date = db.Column(db.Date, nullable=True)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    @property
    def used_today(self) -> int:
        """今日已用调用数；跨自然日视为 0。"""
        if self.quota_date != date.today():
            return 0
        return self.calls_today or 0

    @property
    def quota_left(self) -> int:
        """今日剩余调用额度；daily_quota <= 0 表示不限。"""
        if not self.daily_quota or self.daily_quota <= 0:
            return 10 ** 9
        return max(self.daily_quota - self.used_today, 0)

    def touch_usage(self) -> None:
        """记录一次调用：跨天先清零，再累加当日与累计计数。"""
        today = date.today()
        if self.quota_date != today:
            self.calls_today = 0
            self.quota_date = today
        self.calls_today = (self.calls_today or 0) + 1
        self.total_calls = (self.total_calls or 0) + 1
        self.last_used_at = datetime.utcnow()

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
            "daily_quota": self.daily_quota or 0,
            "used_today": self.used_today,
            "quota_left": self.quota_left if (self.daily_quota and self.daily_quota > 0) else None,
            "created_at": fmt_local(self.created_at),
        }

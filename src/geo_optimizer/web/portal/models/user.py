# -*- coding: utf-8 -*-
"""用户模型。"""
import hashlib
from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from geo_optimizer.web.portal.extensions import db

ROLE_ADMIN = "admin"
ROLE_USER = "user"

# 审批状态：自助注册的用户默认 pending，管理员审批后转 active 方可登录
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"

# 注册密码 MD5 加固定密钥存储（格式 md5$<hex>），密钥固定不可变更，否则旧密码全部失效
PASSWORD_MD5_KEY = "GeoOpt#2026@pwd-key"


def _md5_digest(raw: str) -> str:
    return hashlib.md5((raw + PASSWORD_MD5_KEY).encode("utf-8")).hexdigest()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), default=ROLE_USER, nullable=False)
    eval_quota = db.Column(db.Integer, default=10, nullable=False)  # 每日可评估配额
    eval_used = db.Column(db.Integer, default=0, nullable=False)    # 当日已使用
    quota_date = db.Column(db.Date, nullable=True)  # eval_used 对应的自然日，跨天即重置
    locale = db.Column(db.String(8), default="zh", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    can_use_platform_llm = db.Column(db.Boolean, default=True, nullable=False)  # 是否允许使用平台算力
    email = db.Column(db.String(128), default="", nullable=False)
    phone = db.Column(db.String(32), default="", nullable=False)
    # 审批状态：存量/后台创建用户默认 active，自助注册为 pending
    status = db.Column(db.String(16), default=STATUS_ACTIVE, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def set_password_md5(self, raw: str) -> None:
        """注册用户密码：MD5(明文+固定密钥) 存储，带 md5$ 前缀便于识别。"""
        self.password_hash = "md5$" + _md5_digest(raw)

    def check_password(self, raw: str) -> bool:
        # 兼容两种格式：注册用户的 md5$ 与后台创建用户的 werkzeug 哈希
        if self.password_hash.startswith("md5$"):
            return self.password_hash == "md5$" + _md5_digest(raw)
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def used_today(self) -> int:
        """今日已用次数；配额按自然日重置，跨天后视为 0。"""
        if self.quota_date != date.today():
            return 0
        return self.eval_used or 0

    @property
    def quota_left(self) -> int:
        """今日剩余配额；管理员或配额为 0（不限）返回一个很大的值。"""
        if self.is_admin or self.eval_quota <= 0:
            return 10 ** 9
        return max(self.eval_quota - self.used_today, 0)

    def to_dict(self) -> dict:
        from geo_optimizer.web.portal.timeutil import fmt_local

        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "eval_quota": self.eval_quota,
            "eval_used": self.used_today,
            "quota_left": self.quota_left,
            "locale": self.locale,
            "is_active": self.is_active,
            "email": self.email,
            "phone": self.phone,
            "status": self.status,
            "can_use_platform_llm": self.can_use_platform_llm,
            "created_at": fmt_local(self.created_at),
        }

# -*- coding: utf-8 -*-
"""认证与授权服务。"""
from functools import wraps
from typing import Optional

from flask import abort
from flask_login import current_user

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_PENDING,
    User,
)


def authenticate(username: str, password: str) -> Optional[User]:
    """校验用户名密码，成功返回 User，否则 None。"""
    user, _err = authenticate_detail(username, password)
    return user


def authenticate_detail(username: str, password: str) -> tuple[Optional[User], str]:
    """校验登录，返回 (用户, 错误文案key)；审批中的账号单独提示。"""
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return None, "login_failed"
    if user.status == STATUS_PENDING:
        return None, "register_pending_login"
    if not user.is_active:
        return None, "login_failed"
    return user, ""


def create_user(username: str, password: str, role: str = ROLE_USER,
                eval_quota: int = 10) -> User:
    """创建新用户（密码哈希存储）。"""
    role = role if role in (ROLE_ADMIN, ROLE_USER) else ROLE_USER
    user = User(username=username, role=role, eval_quota=eval_quota)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def username_exists(username: str) -> bool:
    return User.query.filter_by(username=username).first() is not None


def register_user(username: str, password: str, email: str, phone: str) -> User:
    """自助注册：密码 MD5+固定密钥存储，状态为待审批，审批后方可登录。

    默认每日评估配额 10 次。
    """
    user = User(username=username, role=ROLE_USER, eval_quota=10,
                email=email, phone=phone, status=STATUS_PENDING)
    user.set_password_md5(password)
    db.session.add(user)
    db.session.commit()
    return user


def admin_required(view):
    """管理员权限装饰器（须在 login_required 之后）。"""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped

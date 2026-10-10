# -*- coding: utf-8 -*-
"""操作审计服务。"""
import logging

from flask import has_request_context, request
from flask_login import current_user

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import AuditLog

logger = logging.getLogger(__name__)

# 常用动作常量
ACTION_LOGIN = "login"
ACTION_LOGOUT = "logout"
ACTION_EVAL_SUBMIT = "eval_submit"
ACTION_EVAL_RETRY = "eval_retry"
ACTION_PLAN_GENERATE = "plan_generate"
ACTION_DOWNLOAD = "download"
ACTION_HISTORY_DELETE = "history_delete"
ACTION_CONFIG_UPDATE = "config_update"
ACTION_USER_CREATE = "user_create"
ACTION_USER_REGISTER = "user_register"
ACTION_USER_APPROVE = "user_approve"
ACTION_USER_UPDATE = "user_update"
ACTION_USER_DISABLE = "user_disable"
ACTION_USER_ENABLE = "user_enable"
ACTION_USER_DELETE = "user_delete"
ACTION_QUOTA_UPDATE = "quota_update"
ACTION_AUDIT_DELETE = "audit_delete"
ACTION_PLAN_ITEM_EDIT = "plan_item_edit"
ACTION_PLAN_ITEM_DOWNLOAD = "plan_item_download"
ACTION_ARTIFACT_GENERATE = "artifact_generate"
ACTION_ARTIFACT_EDIT = "artifact_edit"
ACTION_ARTIFACT_DELETE = "artifact_delete"


def record(action: str, target: str = "", detail: str = "", user=None) -> None:
    """写入一条审计日志（异常不影响主流程）。"""
    try:
        actor = user if user is not None else (current_user if _authenticated() else None)
        ip = request.remote_addr if has_request_context() else ""
        log = AuditLog(
            user_id=getattr(actor, "id", None),
            username=getattr(actor, "username", "") or "",
            action=action,
            target=(target or "")[:512],
            ip=ip or "",
            detail=(detail or "")[:512],
        )
        db.session.add(log)
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("审计写入失败: %s", exc)
        db.session.rollback()


def _authenticated() -> bool:
    try:
        return bool(current_user and current_user.is_authenticated)
    except Exception:
        return False

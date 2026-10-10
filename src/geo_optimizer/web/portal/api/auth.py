# -*- coding: utf-8 -*-
"""开放 API 鉴权服务：密钥生成、验证与装饰器。"""
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Tuple

from flask import g, jsonify, request

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import ApiCallLog, ApiKey, User

KEY_PREFIX = "geo_"
KEY_BYTES = 32  # 生成 32 字节随机密钥


def _hash_key(raw_key: str) -> str:
    """对明文密钥做 SHA-256 哈希。"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(user_id: int, name: str = "", expires_days: int = 365) -> Tuple[ApiKey, str]:
    """生成新 API 密钥，返回 (ApiKey 记录, 明文密钥)。明文同时落库以支持事后查看。"""
    raw_secret = secrets.token_urlsafe(KEY_BYTES)
    raw_key = f"{KEY_PREFIX}{raw_secret}"
    key_hash = _hash_key(raw_key)
    prefix_display = raw_key[:12]  # "geo_xxxxxxxx"

    api_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=prefix_display,
        key_plaintext=raw_key,
        name=(name or "")[:64],
        expires_at=datetime.utcnow() + timedelta(days=expires_days),
        is_active=True,
    )
    db.session.add(api_key)
    db.session.commit()
    return api_key, raw_key


def verify_api_key(raw_key: str) -> Optional[Tuple[User, ApiKey]]:
    """验证明文密钥，有效则返回 (User, ApiKey)，否则 None。"""
    key_hash = _hash_key(raw_key)
    api_key = ApiKey.query.filter_by(key_hash=key_hash).first()
    if not api_key or not api_key.is_valid:
        return None
    user = db.session.get(User, api_key.user_id)
    if not user or not user.is_active:
        return None
    # 更新使用统计
    api_key.last_used_at = datetime.utcnow()
    api_key.total_calls = (api_key.total_calls or 0) + 1
    db.session.commit()
    return user, api_key


def record_call(api_key: ApiKey, user: User, status_code: int = 200) -> None:
    """记录一次 API 调用日志。"""
    try:
        log = ApiCallLog(
            api_key_id=api_key.id,
            user_id=user.id,
            endpoint=request.path,
            method=request.method,
            status_code=status_code,
            ip=request.remote_addr or "",
        )
        db.session.add(log)
        db.session.commit()
    except Exception:  # noqa: BLE001
        db.session.rollback()


def api_key_required(view):
    """API 密钥鉴权装饰器：从 Authorization: Bearer <key> 提取并验证。"""
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing_token", "message": "Authorization header with Bearer token required"}), 401

        raw_key = auth_header[7:].strip()
        if not raw_key:
            return jsonify({"error": "missing_token", "message": "API key is empty"}), 401

        result = verify_api_key(raw_key)
        if result is None:
            return jsonify({"error": "invalid_token", "message": "Invalid or expired API key"}), 401

        user, api_key = result
        g.api_user = user
        g.api_key = api_key

        response = view(*args, **kwargs)

        # 记录调用日志（从 response 提取 status_code）
        status_code = 200
        if isinstance(response, tuple):
            status_code = response[1] if len(response) > 1 else 200
        record_call(api_key, user, status_code)

        return response
    return wrapped

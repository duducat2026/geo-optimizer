# -*- coding: utf-8 -*-
"""i18n 运行时：locale 解析与翻译函数。"""
from flask import session
from flask_login import current_user

from geo_optimizer.web.portal.i18n.messages import MESSAGES

SUPPORTED = ("zh", "en")
DEFAULT_LOCALE = "zh"


def get_locale() -> str:
    """优先 session，其次登录用户偏好，最后默认中文。"""
    loc = session.get("locale")
    if loc in SUPPORTED:
        return loc
    try:
        if current_user.is_authenticated and current_user.locale in SUPPORTED:
            return current_user.locale
    except Exception:
        pass
    return DEFAULT_LOCALE


def set_locale(code: str) -> str:
    code = code if code in SUPPORTED else DEFAULT_LOCALE
    session["locale"] = code
    return code


def translate(key: str, **kwargs) -> str:
    """翻译；缺失 key 直接回退为 key 本身。支持 {name} 占位符。"""
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(get_locale(), entry.get(DEFAULT_LOCALE, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text

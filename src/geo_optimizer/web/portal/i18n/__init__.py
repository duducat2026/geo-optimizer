# -*- coding: utf-8 -*-
"""i18n 包导出。"""
from geo_optimizer.web.portal.i18n.translator import (
    DEFAULT_LOCALE,
    SUPPORTED,
    get_locale,
    set_locale,
    translate,
)

__all__ = ["translate", "get_locale", "set_locale", "SUPPORTED", "DEFAULT_LOCALE"]

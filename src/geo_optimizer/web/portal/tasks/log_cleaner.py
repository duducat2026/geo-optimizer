# -*- coding: utf-8 -*-
"""处理日志定期清理器：保留 LOG_RETENTION_DAYS 天，后台线程周期删除。"""
import logging
import threading
import time

from geo_optimizer.web.portal.tasks import service

logger = logging.getLogger(__name__)

CLEAN_INTERVAL_SECONDS = 12 * 3600  # 每 12 小时清理一次

_started = False
_lock = threading.Lock()


def start(app) -> None:
    """启动日志清理守护线程（进程内幂等）。"""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    thread = threading.Thread(target=_loop, args=(app,), daemon=True)
    thread.start()


def _loop(app) -> None:
    while True:
        try:
            with app.app_context():
                deleted = service.purge_expired_logs()
                if deleted:
                    logger.info("已清理过期处理日志 %s 条（保留 %s 天）",
                                deleted, service.LOG_RETENTION_DAYS)
        except Exception as exc:  # noqa: BLE001
            logger.warning("处理日志清理失败: %s", exc)
        time.sleep(CLEAN_INTERVAL_SECONDS)

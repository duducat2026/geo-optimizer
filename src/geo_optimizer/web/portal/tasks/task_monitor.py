# -*- coding: utf-8 -*-
"""任务监控器：启动时回收上一进程遗留任务，周期检测卡死任务并标记失败。"""
import logging
import threading
import time

from geo_optimizer.web.portal.tasks import service

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60  # 每分钟巡检一次

_started = False
_lock = threading.Lock()


def start(app) -> None:
    """启动任务监控守护线程（进程内幂等）。"""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    thread = threading.Thread(target=_loop, args=(app,), daemon=True)
    thread.start()


def _loop(app) -> None:
    # 启动即回收：上一进程的执行线程已消亡，遗留 pending/running 任务直接判失败
    try:
        with app.app_context():
            recovered = service.fail_interrupted_tasks()
            if recovered:
                logger.info("已回收服务重启遗留任务 %s 个", recovered)
    except Exception as exc:  # noqa: BLE001
        logger.warning("遗留任务回收失败: %s", exc)

    # 周期巡检：超过 STALL_TIMEOUT_MINUTES 无日志活动的任务视为卡死
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)
        try:
            with app.app_context():
                stalled = service.fail_stalled_tasks()
                if stalled:
                    logger.warning("已终止卡死任务 %s 个（%s 分钟无活动）",
                                   stalled, service.STALL_TIMEOUT_MINUTES)
        except Exception as exc:  # noqa: BLE001
            logger.warning("卡死任务巡检失败: %s", exc)

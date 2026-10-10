# -*- coding: utf-8 -*-
"""任务持久化与进度服务。"""
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import (
    LEVEL_ERROR,
    LEVEL_INFO,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_QUEUED,
    STATUS_RUNNING,
    EvalTask,
    TaskLog,
    User,
)
from geo_optimizer.web.portal.settings import _repo_root

LOG_RETENTION_DAYS = 3   # 处理日志保留天数
RECENT_LOGS = 10         # 控制台默认展示条数
STALL_TIMEOUT_MINUTES = 15  # 超过该时长无日志活动的任务视为卡死
MAX_USER_CONCURRENT = 5     # 每用户最多同时运行任务数
MAX_GLOBAL_CONCURRENT = 10  # 全局最大并发运行任务数


def artifacts_root() -> Path:
    root = _repo_root() / "data" / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def artifact_dir_for(task_id: str) -> Path:
    d = artifacts_root() / task_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_task(user_id: int, target_url: str, task_type: str,
                queued: bool = False) -> EvalTask:
    """创建任务。queued=True 时状态为 queued（排队中），否则为 pending。"""
    task = EvalTask(
        id=str(uuid.uuid4()),
        user_id=user_id,
        target_url=target_url,
        type=task_type,
        status=STATUS_QUEUED if queued else STATUS_PENDING,
        progress=0,
    )
    db.session.add(task)
    db.session.commit()
    add_log(task.id, "log_queued" if queued else "log_created", detail=target_url)
    return task


def add_log(task_id: str, message: str, detail: str = "",
            level: str = LEVEL_INFO) -> None:
    """记录一条处理日志（message 为 i18n key，展示时翻译）。"""
    db.session.add(TaskLog(task_id=task_id, level=level,
                           message=(message or "")[:255],
                           detail=(detail or "")[:255]))
    db.session.commit()


def logs_for(task_id: str, limit: int = 0) -> list:
    """任务日志，按时间倒排（最新在前）；limit>0 时只取最近若干条。"""
    query = (
        TaskLog.query.filter_by(task_id=task_id)
        .order_by(TaskLog.created_at.desc(), TaskLog.id.desc())
    )
    if limit > 0:
        query = query.limit(limit)
    return query.all()


def logs_after(task_id: str, after_id: int = 0) -> list:
    """增量日志：id 大于 after_id 的日志，按时间正排（供开放 API 轮询增量拉取）。"""
    return (
        TaskLog.query.filter(TaskLog.task_id == task_id, TaskLog.id > after_id)
        .order_by(TaskLog.created_at.asc(), TaskLog.id.asc())
        .all()
    )


def count_logs(task_id: str) -> int:
    return TaskLog.query.filter_by(task_id=task_id).count()


def purge_expired_logs(days: int = LOG_RETENTION_DAYS) -> int:
    """删除超过保留期的处理日志，返回删除条数。"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = TaskLog.query.filter(TaskLog.created_at < cutoff).delete()
    db.session.commit()
    return deleted


def update_progress(task_id: str, progress: int, message: str = "") -> None:
    task = db.session.get(EvalTask, task_id)
    if not task:
        return
    task.status = STATUS_RUNNING
    task.progress = progress
    task.message = message
    db.session.commit()
    if message:
        add_log(task_id, message)


def mark_completed(task_id: str, result: dict, overall_score: float,
                   artifact_dir: str = "") -> None:
    task = db.session.get(EvalTask, task_id)
    if not task:
        return
    task.status = STATUS_COMPLETED
    task.progress = 100
    task.message = ""
    task.overall_score = overall_score
    task.artifact_dir = artifact_dir
    task.set_result(result)
    task.completed_at = datetime.utcnow()
    db.session.commit()
    add_log(task_id, "log_done")


def mark_failed(task_id: str, error: str) -> None:
    task = db.session.get(EvalTask, task_id)
    if not task:
        return
    task.status = STATUS_FAILED
    task.error = (error or "")[:512]
    task.completed_at = datetime.utcnow()
    db.session.commit()
    add_log(task_id, "log_failed", detail=(error or "")[:255], level=LEVEL_ERROR)


def reset_for_retry(task_id: str) -> None:
    """重试前重置失败任务状态（清空错误/结果/进度），保留历史日志。"""
    task = db.session.get(EvalTask, task_id)
    if not task:
        return
    task.status = STATUS_PENDING
    task.progress = 0
    task.message = ""
    task.error = ""
    task.overall_score = 0.0
    task.result_json = ""
    task.completed_at = None
    db.session.commit()
    add_log(task_id, "log_retry")


def active_tasks() -> list:
    """仍在执行中的任务（pending / running）。"""
    return EvalTask.query.filter(
        EvalTask.status.in_((STATUS_PENDING, STATUS_RUNNING))
    ).all()


def queued_tasks() -> list:
    """排队中的任务，按创建时间升序。"""
    return (
        EvalTask.query.filter_by(status=STATUS_QUEUED)
        .order_by(EvalTask.created_at.asc())
        .all()
    )


def queue_position(task_id: str) -> int:
    """返回任务在队列中的位置（1-based），非排队状态返回 0。"""
    tasks = queued_tasks()
    for i, t in enumerate(tasks, 1):
        if t.id == task_id:
            return i
    return 0


def user_active_count(user_id: int) -> int:
    """指定用户正在执行中/排队中的任务数。"""
    return EvalTask.query.filter(
        EvalTask.user_id == user_id,
        EvalTask.status.in_((STATUS_PENDING, STATUS_QUEUED, STATUS_RUNNING)),
    ).count()


def global_running_count() -> int:
    """全局正在运行中的任务数（仅 pending + running 占用并发槽位）。"""
    return EvalTask.query.filter(
        EvalTask.status.in_((STATUS_PENDING, STATUS_RUNNING))
    ).count()


def global_active_count() -> int:
    """全局活跃任务数（含排队）。"""
    return EvalTask.query.filter(
        EvalTask.status.in_((STATUS_PENDING, STATUS_QUEUED, STATUS_RUNNING))
    ).count()


def fail_interrupted_tasks() -> int:
    """服务启动时回收上一进程遗留的未完成任务（线程已随进程消亡）。"""
    count = 0
    for task in active_tasks():
        mark_failed(task.id, "task_interrupted")
        refund_quota(task.user_id)
        count += 1
    return count


def fail_stalled_tasks(timeout_minutes: int = STALL_TIMEOUT_MINUTES) -> int:
    """将长时间无日志活动的任务标记为失败，返回处理条数。"""
    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    count = 0
    for task in active_tasks():
        last = (
            TaskLog.query.filter_by(task_id=task.id)
            .order_by(TaskLog.created_at.desc(), TaskLog.id.desc())
            .first()
        )
        last_at = last.created_at if last else task.created_at
        if last_at and last_at < cutoff:
            mark_failed(task.id, "task_stalled")
            refund_quota(task.user_id)
            count += 1
    return count


# ---- 分享下载限流 ----
DOWNLOAD_LIMIT_KEY = "download_limit"
DOWNLOAD_LIMIT_DEFAULT = 20


def consume_download_quota(task: EvalTask, counter_field: str) -> bool:
    """消耗一次分享链接下载次数，超限返回 False。

    上限取系统配置 download_limit（默认 20，0 表示不限制）；
    counter_field 为 EvalTask 上的计数列名（eval_download_count / bundle_download_count）。
    """
    from geo_optimizer.web.portal.models import SystemConfig

    try:
        limit = int(SystemConfig.get(DOWNLOAD_LIMIT_KEY, str(DOWNLOAD_LIMIT_DEFAULT)))
    except ValueError:
        limit = DOWNLOAD_LIMIT_DEFAULT
    if limit <= 0:
        return True
    used = getattr(task, counter_field) or 0
    if used >= limit:
        return False
    setattr(task, counter_field, used + 1)
    db.session.commit()
    return True


def delete_task_cascade(task: EvalTask) -> None:
    """删除任务及其关联记录与产物文件（方案/条目/产出物/处理日志/产物目录）。"""
    from geo_optimizer.web.portal.models import GeoPlan, PlanArtifact, PlanItem

    GeoPlan.query.filter_by(task_id=task.id).delete()
    PlanArtifact.query.filter_by(task_id=task.id).delete()
    PlanItem.query.filter_by(task_id=task.id).delete()
    TaskLog.query.filter_by(task_id=task.id).delete()
    if task.artifact_dir and Path(task.artifact_dir).is_dir():
        shutil.rmtree(task.artifact_dir, ignore_errors=True)
    db.session.delete(task)
    db.session.commit()


def reserve_quota(user_id: int) -> None:
    """提交任务时预扣配额（eval_used +1）；配额按自然日重置。"""
    from datetime import date

    user = db.session.get(User, user_id)
    if user and not user.is_admin:
        today = date.today()
        if user.quota_date != today:
            # 跨天首次提交：重置当日计数
            user.eval_used = 0
            user.quota_date = today
        user.eval_used = (user.eval_used or 0) + 1
        db.session.commit()


def refund_quota(user_id: int) -> None:
    """任务失败/取消时归还预扣的配额（仅归还当日计数）。"""
    from datetime import date

    user = db.session.get(User, user_id)
    if (user and not user.is_admin and user.quota_date == date.today()
            and (user.eval_used or 0) > 0):
        user.eval_used -= 1
        db.session.commit()


# ─── 任务取消 ────────────────────────────────────────────────

# 内存中记录被取消的任务 ID，供 runner 线程检查
_cancelled_tasks: set = set()


def cancel_task(task_id: str) -> bool:
    """取消任务。排队中直接标记取消；运行中设置取消标志等待 runner 中止。
    返回是否成功发起取消。"""
    task = db.session.get(EvalTask, task_id)
    if not task:
        return False
    if task.status == STATUS_QUEUED:
        task.status = STATUS_CANCELLED
        task.completed_at = datetime.utcnow()
        db.session.commit()
        add_log(task_id, "log_cancelled")
        refund_quota(task.user_id)
        return True
    if task.status in (STATUS_PENDING, STATUS_RUNNING):
        _cancelled_tasks.add(task_id)
        add_log(task_id, "log_cancelling")
        return True
    return False


def is_cancelled(task_id: str) -> bool:
    """检查任务是否已被标记取消（供 runner 检查点调用）。"""
    return task_id in _cancelled_tasks


def mark_cancelled(task_id: str) -> None:
    """将任务正式标记为已取消（runner 中止后调用）。"""
    _cancelled_tasks.discard(task_id)
    task = db.session.get(EvalTask, task_id)
    if not task:
        return
    task.status = STATUS_CANCELLED
    task.completed_at = datetime.utcnow()
    db.session.commit()
    add_log(task_id, "log_cancelled")
    refund_quota(task.user_id)


class TaskCancelledError(Exception):
    """任务被用户取消时抛出。"""
    pass


def check_cancelled(task_id: str) -> None:
    """runner 检查点：若已取消则抛出 TaskCancelledError。"""
    if is_cancelled(task_id):
        raise TaskCancelledError(f"Task {task_id} cancelled by user")

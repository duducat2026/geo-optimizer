# -*- coding: utf-8 -*-
"""开放 API 蓝图：提交任务、查询状态、获取结果、下载、用量统计。"""
import os

from flask import Blueprint, g, jsonify, request, send_file

from geo_optimizer.web.portal.api.auth import api_key_required
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import (
    SOURCE_API,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_QUEUED,
    TYPE_EVAL,
    TYPE_PLAN,
    ApiCallLog,
    ApiKey,
    EvalTask,
    GeoPlan,
    PlanItem,
)
from geo_optimizer.web.portal.tasks import runner, service
from geo_optimizer.web.portal.tasks.config_builder import user_has_available_llm

bp = Blueprint("open_api", __name__, url_prefix="/api/v1")


def _parse_dt(value, end_of_day: bool = False):
    """解析日期/时间过滤参数（UTC naive），无法解析时返回 None。

    支持 YYYY-MM-DD 与常见 ISO 时间格式；纯日期且 end_of_day=True 时
    置为当日 23:59:59.999999，以便 end 过滤包含整天。
    """
    if not value:
        return None
    from datetime import datetime

    value = value.strip().replace("Z", "").replace("z", "")
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return d.replace(hour=23, minute=59, second=59, microsecond=999999) if end_of_day else d
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@bp.route("/tasks", methods=["POST"])
@api_key_required
def submit_task():
    """提交评估任务。全局并发已满时进入排队。"""
    user = g.api_user
    data = request.get_json(force=True, silent=True) or {}
    target_url = (data.get("target_url") or "").strip()
    task_type = data.get("task_type") or TYPE_EVAL
    task_type = task_type if task_type in (TYPE_EVAL, TYPE_PLAN) else TYPE_EVAL

    if not target_url:
        return jsonify({"error": "invalid_params", "message": "target_url is required"}), 400

    if user.quota_left <= 0:
        return jsonify({"error": "quota_exceeded", "message": "Evaluation quota exhausted"}), 403

    if not user_has_available_llm(user.id, user.can_use_platform_llm):
        key_prefix = g.api_key.key_prefix if g.api_key else "unknown"
        return jsonify({
            "error": "llm_unavailable",
            "message": f"当前账号 {key_prefix} 算力接口不可用，请联系管理员。",
        }), 503

    if service.user_active_count(user.id) >= service.MAX_USER_CONCURRENT:
        return jsonify({"error": "concurrent_limit", "message": "Too many concurrent tasks for this user"}), 429

    # 全局并发已满时进入排队
    need_queue = service.global_running_count() >= service.MAX_GLOBAL_CONCURRENT

    # 配额预扣
    service.reserve_quota(user.id)
    task = service.create_task(user.id, target_url, task_type, queued=need_queue)
    # 标记来源为 API
    task.source = SOURCE_API
    db.session.commit()

    if not need_queue:
        from flask import current_app
        runner.start(current_app._get_current_object(), task.id, target_url, task_type)

    return jsonify({
        "task_id": task.id,
        "status": task.status,
        "target_url": target_url,
        "task_type": task_type,
        "queued": need_queue,
        "queue_position": service.queue_position(task.id) if need_queue else 0,
        "message": ("Task queued, waiting for available slot"
                   if need_queue else "Task submitted successfully"),
    }), 201


@bp.route("/tasks", methods=["GET"])
@api_key_required
def list_tasks():
    """当前 API-KEY 用户最近提交的任务列表。

    返回总条数 total 与当页数据（默认每页 10 条），支持：
    - 分页：page（从 1 开始）+ limit（1-50）
    - 日期时间范围：start / end（按 created_at 过滤，UTC），
      支持 YYYY-MM-DD 或 ISO 时间；end 为纯日期时含当日。
    """
    user = g.api_user
    try:
        limit = min(max(int(request.args.get("limit", 10)), 1), 50)
    except (TypeError, ValueError):
        limit = 10
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1

    query = EvalTask.query.filter_by(user_id=user.id)
    start = _parse_dt(request.args.get("start"))
    end = _parse_dt(request.args.get("end"), end_of_day=True)
    if start:
        query = query.filter(EvalTask.created_at >= start)
    if end:
        query = query.filter(EvalTask.created_at <= end)

    total = query.count()
    tasks = (query.order_by(EvalTask.created_at.desc())
             .offset((page - 1) * limit).limit(limit).all())
    return jsonify({
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total else 0,
        "tasks": [
            {
                "task_id": t.id,
                "target_url": t.target_url,
                "task_type": t.type,
                "status": t.status,
                "progress": t.progress,
                "overall_score": t.overall_score,
                "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
            }
            for t in tasks
        ],
    }), 200


@bp.route("/tasks/<task_id>", methods=["GET"])
@api_key_required
def task_status(task_id):
    """查询任务状态。"""
    user = g.api_user
    task = db.session.get(EvalTask, task_id)
    if not task:
        return jsonify({"error": "not_found", "message": "Task not found"}), 404
    if task.user_id != user.id and not user.is_admin:
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    resp = {
        "task_id": task.id,
        "target_url": task.target_url,
        "task_type": task.type,
        "source": task.source,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "overall_score": task.overall_score,
        "error": task.error,
        "created_at": task.created_at.isoformat() + "Z" if task.created_at else None,
        "completed_at": task.completed_at.isoformat() + "Z" if task.completed_at else None,
    }
    # 排队中额外返回队列位置
    if task.status == STATUS_QUEUED:
        resp["queue_position"] = service.queue_position(task_id)
    return jsonify(resp), 200


@bp.route("/tasks/<task_id>/logs", methods=["GET"])
@api_key_required
def task_logs(task_id):
    """任务执行日志（已翻译）。支持 ?after_id= 增量拉取，供 skill 客户端轮询展示。"""
    user = g.api_user
    task = db.session.get(EvalTask, task_id)
    if not task:
        return jsonify({"error": "not_found", "message": "Task not found"}), 404
    if task.user_id != user.id and not user.is_admin:
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    try:
        after_id = int(request.args.get("after_id", 0))
    except (TypeError, ValueError):
        after_id = 0

    from geo_optimizer.web.portal.i18n.translator import translate as _

    logs = []
    last_id = after_id
    for log in service.logs_after(task_id, after_id):
        entry = log.to_dict()
        entry["id"] = log.id
        entry["message"] = _(entry["message"])
        if entry["detail"]:
            entry["detail"] = _(entry["detail"])
        logs.append(entry)
        last_id = max(last_id, log.id)

    return jsonify({
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress,
        "logs": logs,
        "last_id": last_id,
    }), 200


@bp.route("/tasks/<task_id>/result", methods=["GET"])
@api_key_required
def task_result(task_id):
    """获取任务结果（仅 completed 状态可用）。"""
    user = g.api_user
    task = db.session.get(EvalTask, task_id)
    if not task:
        return jsonify({"error": "not_found", "message": "Task not found"}), 404
    if task.user_id != user.id and not user.is_admin:
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    if task.status != STATUS_COMPLETED:
        return jsonify({
            "task_id": task.id,
            "status": task.status,
            "message": f"Task is not completed yet (current: {task.status})",
        }), 200

    # 检查是否有下载包
    plan = GeoPlan.query.filter_by(task_id=task_id).first()
    download_url = None
    if plan and plan.zip_path and os.path.exists(plan.zip_path):
        download_url = f"/api/v1/tasks/{task_id}/download"

    # 免登录分享下载链接（“生成与改进方案”打包，链接即凭证）
    share_download_url = None
    if PlanItem.query.filter_by(task_id=task_id).count():
        share_download_url = request.host_url.rstrip("/") + f"/plan/{task_id}/download"

    return jsonify({
        "task_id": task.id,
        "status": task.status,
        "overall_score": task.overall_score,
        "result": task.result(),
        "download_url": download_url,
        "share_download_url": share_download_url,
    }), 200


@bp.route("/tasks/<task_id>/download", methods=["GET"])
@api_key_required
def task_download(task_id):
    """下载评估报告与改进方案 ZIP 包。"""
    user = g.api_user
    task = db.session.get(EvalTask, task_id)
    if not task:
        return jsonify({"error": "not_found", "message": "Task not found"}), 404
    if task.user_id != user.id and not user.is_admin:
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    plan = GeoPlan.query.filter_by(task_id=task_id).first()
    if not plan or not plan.zip_path or not os.path.exists(plan.zip_path):
        return jsonify({"error": "not_found", "message": "Download package not available"}), 404

    from geo_optimizer.web.portal.packaging.bundler import download_filename
    return send_file(plan.zip_path, as_attachment=True,
                     download_name=download_filename(task.target_url))


@bp.route("/usage", methods=["GET"])
@api_key_required
def usage_stats():
    """当前用户 API 调用统计。"""
    user = g.api_user
    keys = ApiKey.query.filter_by(user_id=user.id).all()
    total_calls = sum(k.total_calls or 0 for k in keys)

    return jsonify({
        "total_calls": total_calls,
        "current_key": {
            "id": g.api_key.id,
            "daily_quota": g.api_key.daily_quota,
            "used_today": g.api_key.used_today,
            "quota_left": g.api_key.quota_left if (g.api_key.daily_quota and g.api_key.daily_quota > 0) else None,
        },
        "keys": [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "total_calls": k.total_calls,
                "daily_quota": k.daily_quota,
                "used_today": k.used_today,
                "is_active": k.is_active,
                "last_used_at": k.last_used_at.isoformat() + "Z" if k.last_used_at else None,
            }
            for k in keys
        ],
    }), 200


@bp.route("/tasks/<task_id>/cancel", methods=["POST"])
@api_key_required
def task_cancel(task_id):
    """终止任务（排队中/运行中均可）。"""
    user = g.api_user
    task = db.session.get(EvalTask, task_id)
    if not task:
        return jsonify({"error": "not_found", "message": "Task not found"}), 404
    if task.user_id != user.id and not user.is_admin:
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    if task.status in (STATUS_QUEUED, "pending", "running"):
        service.cancel_task(task_id)
        return jsonify({
            "task_id": task_id,
            "status": "cancelling" if task.status == "running" else STATUS_CANCELLED,
            "message": "Task cancellation requested",
        }), 200

    return jsonify({
        "error": "invalid_state",
        "message": f"Cannot cancel task in '{task.status}' state",
    }), 409

# -*- coding: utf-8 -*-
"""管理员蓝图：系统配置、用户管理、站点总览、操作审计。"""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from geo_optimizer.web.portal.audit import service as audit
from geo_optimizer.web.portal.auth.service import admin_required, create_user, username_exists
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.i18n import translate as _
from geo_optimizer.web.portal.llm_test import test_llm_connection as _test_llm_connection
from geo_optimizer.web.portal.models import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    STATUS_PENDING,
    ApiCallLog,
    ApiKey,
    AuditLog,
    EvalTask,
    GeoPlan,
    PlanArtifact,
    PlanItem,
    SystemConfig,
    SystemLLMConfig,
    User,
    UserLLMConfig,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

# 站点总览每页条数可选项
PER_PAGE_CHOICES = (10, 20, 50)

# 配置页面可编辑的键
CONFIG_KEYS = (
    "llm_provider",
    "api_host",
    "api_key",
    "openai_base_url",
    "dashscope_base_url",
    "model",
    "temperature",
    "max_tokens",
    "download_limit",
)

# 算力方案预设
LLM_PROVIDERS = {
    "bailian": {
        "label": "百炼按量付费",
        "openai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "dashscope_base_url": "https://dashscope.aliyuncs.com/api/v1",
        "hint": "使用百炼通用 API Key（sk- 开头），按 Token 用量计费",
    },
    "token_plan": {
        "label": "Token Plan 团队版",
        "openai_base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "dashscope_base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1",
        "hint": "使用 Token Plan 专属 API Key（sk-sp- 开头），Credits 统一抵扣",
    },
    "custom": {
        "label": "自定义 MaaS 端点",
        "openai_base_url": "",
        "dashscope_base_url": "",
        "hint": "自行填写 Base URL，兼容 OpenAI 协议的任意端点",
    },
}


@bp.route("/")
@login_required
@admin_required
def index():
    """后台管理默认落地页：用户列表。"""
    return redirect(url_for("admin.users"))


@bp.route("/config", methods=["GET", "POST"])
@login_required
@admin_required
def config():
    if request.method == "POST":
        changed = []
        # 旧版单键表单提交了 llm_provider 时才联动填充 base_url（存量兼容）
        provider = (request.form.get("llm_provider") or "").strip()
        preset = LLM_PROVIDERS.get(provider, LLM_PROVIDERS["custom"])
        if provider and provider != "custom" and preset["openai_base_url"]:
            current_url = (request.form.get("openai_base_url") or "").strip()
            # 用户未手动修改时自动填充
            if not current_url or current_url != preset["openai_base_url"]:
                SystemConfig.set("openai_base_url", preset["openai_base_url"])
                SystemConfig.set("dashscope_base_url", preset["dashscope_base_url"])
                if "openai_base_url" not in changed:
                    changed.append("openai_base_url")
        for key in CONFIG_KEYS:
            value = (request.form.get(key) or "").strip()
            if value and value != SystemConfig.get(key, ""):
                SystemConfig.set(key, value)
                changed.append(key)
        if changed:
            db.session.commit()
            audit.record(audit.ACTION_CONFIG_UPDATE, target="system_config",
                         detail=",".join(changed))
        flash(_("config_saved"), "info")
        return redirect(url_for("admin.config"))

    values = {key: SystemConfig.get(key, "") for key in CONFIG_KEYS}
    # 单链接下载次数上限：未配置时展示默认值
    from geo_optimizer.web.portal.tasks.service import DOWNLOAD_LIMIT_DEFAULT
    values["download_limit"] = values["download_limit"] or str(DOWNLOAD_LIMIT_DEFAULT)
    # 平台算力方案列表（启用的置顶）
    sys_llm_configs = (
        SystemLLMConfig.query
        .order_by(SystemLLMConfig.is_active.desc(), SystemLLMConfig.created_at.desc())
        .all()
    )
    # 无方案时提示旧版单键配置仍在生效（存量回退）
    legacy_key = values.get("api_key", "")
    legacy_masked = (legacy_key[:6] + "****" + legacy_key[-4:]) if len(legacy_key) > 10 else ""
    return render_template("admin_config.html", values=values, keys=CONFIG_KEYS,
                           providers=LLM_PROVIDERS,
                           sys_llm_configs=sys_llm_configs,
                           legacy_masked=legacy_masked)


# ─── 平台算力方案管理 ─────────────────────────────────────────────


@bp.route("/llm-configs/save", methods=["POST"])
@login_required
@admin_required
def sys_llm_save():
    """新建或更新平台算力方案。"""
    config_id = _to_int(request.form.get("id"), 0)
    provider = (request.form.get("provider") or "bailian").strip()
    if provider not in LLM_PROVIDERS:
        provider = "bailian"
    name = (request.form.get("name") or "").strip()[:64]
    api_key = (request.form.get("api_key") or "").strip()
    base_url = (request.form.get("base_url") or "").strip()
    model = (request.form.get("model") or "").strip()

    # 非自定义方案自动填充 base_url
    if provider != "custom" and not base_url:
        base_url = LLM_PROVIDERS[provider]["openai_base_url"]

    # 新建时 API Key 必填；编辑时留空表示保留原 Key
    if not config_id and not api_key:
        flash(_("llm_cfg_key_required"), "error")
        return redirect(url_for("admin.config"))

    if config_id:
        cfg = db.session.get(SystemLLMConfig, config_id)
        if not cfg:
            flash(_("no_data"), "error")
            return redirect(url_for("admin.config"))
        cfg.provider, cfg.name = provider, name
        cfg.base_url, cfg.model = base_url, model
        if api_key:
            cfg.api_key = api_key
    else:
        cfg = SystemLLMConfig(provider=provider, name=name, api_key=api_key,
                              base_url=base_url, model=model,
                              is_active=SystemLLMConfig.query.count() == 0)
        db.session.add(cfg)
    db.session.commit()
    audit.record("sys_llm_config_save", target=name or provider)
    flash(_("llm_cfg_saved"), "info")
    return redirect(url_for("admin.config"))


@bp.route("/llm-configs/<int:config_id>/activate", methods=["POST"])
@login_required
@admin_required
def sys_llm_activate(config_id):
    """将某条平台算力方案设为当前使用。"""
    cfg = db.session.get(SystemLLMConfig, config_id)
    if not cfg:
        flash(_("no_data"), "error")
        return redirect(url_for("admin.config"))
    SystemLLMConfig.query.update({"is_active": False})
    cfg.is_active = True
    db.session.commit()
    audit.record("sys_llm_config_activate", target=cfg.name or cfg.provider)
    flash(_("llm_cfg_activated"), "info")
    return redirect(url_for("admin.config"))


@bp.route("/llm-configs/<int:config_id>/delete", methods=["POST"])
@login_required
@admin_required
def sys_llm_delete(config_id):
    """删除平台算力方案。"""
    cfg = db.session.get(SystemLLMConfig, config_id)
    if cfg:
        db.session.delete(cfg)
        db.session.commit()
        audit.record("sys_llm_config_delete", target=cfg.name or cfg.provider)
        flash(_("llm_cfg_deleted"), "info")
    return redirect(url_for("admin.config"))


@bp.route("/llm-configs/<int:config_id>/test", methods=["POST"])
@login_required
@admin_required
def sys_llm_test(config_id):
    """平台算力方案调用测试：结果由前端浮层展示。"""
    cfg = db.session.get(SystemLLMConfig, config_id)
    if not cfg:
        return jsonify({"ok": False, "error": "config not found"}), 404

    ok, detail = _test_llm_connection(cfg.api_key, cfg.base_url, cfg.model)
    detail.update({
        "ok": ok,
        "provider_label": cfg.provider_label,
        "config_name": cfg.name,
        "api_key_masked": cfg.api_key_masked,
    })
    audit.record("sys_llm_config_test", target=cfg.name or cfg.provider,
                 detail=f"ok={ok}")
    # AJAX 调用直接返回 JSON，由前端浮层展示结果
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(detail)
    # 无 JS 回退：flash 摘要后重定向回配置页
    model_used = detail["model_responded"] or detail["model_requested"]
    if ok:
        flash(f"{_('llm_cfg_test_ok')} · {cfg.provider_label} · {model_used}", "info")
    else:
        flash(f"{_('llm_cfg_test_fail')} · {cfg.provider_label} · "
              f"{detail['model_requested']}: {detail['error']}", "error")
    return redirect(url_for("admin.config"))


@bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        user_id = _to_int(request.form.get("user_id"), 0)
        if user_id:
            return _update_user(user_id)
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        role = request.form.get("role") or ROLE_USER
        quota = _to_int(request.form.get("eval_quota"), 10)
        if username and password and not username_exists(username):
            user = create_user(username, password, role=role, eval_quota=quota)
            # 后台建用户也可录入邮箱/手机号
            user.email = (request.form.get("email") or "").strip()[:128]
            user.phone = (request.form.get("phone") or "").strip()[:32]
            db.session.commit()
            audit.record(audit.ACTION_USER_CREATE, target=username,
                         detail=f"role={user.role},quota={user.eval_quota}")
            flash(_("create") + ": " + username, "info")
        else:
            flash(_("username") + " ?", "error")
        return redirect(url_for("admin.users"))

    per_page = _to_int(request.args.get("per_page"), 10)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 10
    # 待审批用户置顶展示，便于管理员及时处理
    query = User.query.order_by(
        (User.status == STATUS_PENDING).desc(), User.created_at.asc())
    total = query.count()
    pages = max(1, -(-total // per_page))  # 向上取整
    page = min(max(1, _to_int(request.args.get("page"), 1)), pages)
    page_users = query.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("admin_users.html", users=page_users,
                           roles=(ROLE_USER, ROLE_ADMIN),
                           page=page, pages=pages, per_page=per_page, total=total,
                           per_page_choices=PER_PAGE_CHOICES)


def _update_user(user_id: int):
    """编辑用户信息：邮箱/手机号/角色/配额；密码留空表示不修改。"""
    user = db.session.get(User, user_id)
    if not user:
        flash(_("no_data"), "error")
        return redirect(url_for("admin.users"))
    user.email = (request.form.get("email") or "").strip()[:128]
    user.phone = (request.form.get("phone") or "").strip()[:32]
    role = request.form.get("role")
    if role in (ROLE_ADMIN, ROLE_USER):
        user.role = role
    user.eval_quota = _to_int(request.form.get("eval_quota"), user.eval_quota)
    user.can_use_platform_llm = request.form.get("can_use_platform_llm") == "on"
    password = (request.form.get("password") or "").strip()
    if password:
        user.set_password(password)
    db.session.commit()
    audit.record(audit.ACTION_USER_UPDATE, target=user.username,
                 detail=f"role={user.role},quota={user.eval_quota},"
                        f"pwd_changed={bool(password)}")
    flash(_("user_updated") + ": " + user.username, "info")
    return redirect(url_for("admin.users",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10)))


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    """禁用/启用用户账号；禁用后无法登录。"""
    from flask_login import current_user

    user = db.session.get(User, user_id)
    if not user:
        flash(_("no_data"), "error")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash(_("cannot_operate_self"), "error")
        return redirect(url_for("admin.users"))
    user.is_active = not user.is_active
    db.session.commit()
    action = audit.ACTION_USER_ENABLE if user.is_active else audit.ACTION_USER_DISABLE
    audit.record(action, target=user.username)
    flash((_("user_enable") if user.is_active else _("user_disable"))
          + ": " + user.username, "info")
    return redirect(url_for("admin.users",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10)))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户及其全部任务/密钥/算力配置（审计日志保留作为历史记录）。"""
    from flask_login import current_user

    from geo_optimizer.web.portal.tasks import service as task_service

    user = db.session.get(User, user_id)
    if not user:
        flash(_("no_data"), "error")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash(_("cannot_operate_self"), "error")
        return redirect(url_for("admin.users"))
    username = user.username
    # 逐个级联删除任务（含方案/条目/产物/日志/产物目录）
    for task in EvalTask.query.filter_by(user_id=user.id).all():
        task_service.delete_task_cascade(task)
    ApiCallLog.query.filter_by(user_id=user.id).delete()
    ApiKey.query.filter_by(user_id=user.id).delete()
    UserLLMConfig.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    audit.record(audit.ACTION_USER_DELETE, target=username)
    flash(_("user_deleted") + ": " + username, "info")
    return redirect(url_for("admin.users",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10)))


@bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id):
    """审批通过注册用户，激活后方可登录。"""
    user = db.session.get(User, user_id)
    if user and user.status == STATUS_PENDING:
        user.status = STATUS_ACTIVE
        db.session.commit()
        audit.record(audit.ACTION_USER_APPROVE, target=user.username,
                     detail=f"email={user.email},phone={user.phone}")
        flash(_("user_approved") + ": " + user.username, "info")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/quota", methods=["POST"])
@login_required
@admin_required
def update_quota(user_id):
    user = db.session.get(User, user_id) or None
    if user:
        user.eval_quota = _to_int(request.form.get("eval_quota"), user.eval_quota)
        role = request.form.get("role")
        if role in (ROLE_ADMIN, ROLE_USER):
            user.role = role
        # 平台算力开关
        platform_llm = request.form.get("can_use_platform_llm")
        user.can_use_platform_llm = platform_llm == "on"
        db.session.commit()
        audit.record(audit.ACTION_QUOTA_UPDATE, target=user.username,
                     detail=f"quota={user.eval_quota},role={user.role},"
                            f"platform_llm={user.can_use_platform_llm}")
        flash(_("update_quota"), "info")
    return redirect(url_for("admin.users"))


@bp.route("/sites")
@login_required
@admin_required
def sites():
    per_page = _to_int(request.args.get("per_page"), 10)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 10
    query = (
        db.session.query(EvalTask, User.username)
        .join(User, EvalTask.user_id == User.id)
        .order_by(EvalTask.created_at.desc())
    )
    total = query.count()
    pages = max(1, -(-total // per_page))  # 向上取整
    page = min(max(1, _to_int(request.args.get("page"), 1)), pages)
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    plan_task_ids = {p.task_id for p in GeoPlan.query.all()}
    return render_template("admin_sites.html", rows=rows, plan_task_ids=plan_task_ids,
                           page=page, pages=pages, per_page=per_page, total=total,
                           per_page_choices=PER_PAGE_CHOICES)


@bp.route("/sites/<task_id>/delete", methods=["POST"])
@login_required
@admin_required
def site_delete(task_id):
    """删除任意用户的任务记录及关联文件（方案/条目/日志/产物）。"""
    from geo_optimizer.web.portal.tasks import service as task_service

    task = db.session.get(EvalTask, task_id)
    if task:
        target_url = task.target_url
        task_service.delete_task_cascade(task)
        audit.record(audit.ACTION_HISTORY_DELETE, target=target_url,
                     detail=f"task={task_id} (admin)")
        flash(_("delete"), "info")
    return redirect(url_for("admin.sites",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10)))


@bp.route("/artifacts")
@login_required
@admin_required
def artifacts():
    """平台级生成内容管理：按评估任务筛选，支持翻页。"""
    per_page = _to_int(request.args.get("per_page"), 10)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 10
    task_id = (request.args.get("task_id") or "").strip()

    query = (
        db.session.query(PlanArtifact, PlanItem, EvalTask, User.username)
        .join(PlanItem, PlanArtifact.item_id == PlanItem.id)
        .join(EvalTask, PlanArtifact.task_id == EvalTask.id)
        .join(User, PlanArtifact.user_id == User.id)
        .order_by(PlanArtifact.updated_at.desc())
    )
    if task_id:
        query = query.filter(PlanArtifact.task_id == task_id)
    total = query.count()
    pages = max(1, -(-total // per_page))
    page = min(max(1, _to_int(request.args.get("page"), 1)), pages)
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    # 筛选下拉：存在产出物的任务清单（选入 created_at 以兼容 MySQL 的 DISTINCT+ORDER BY）
    task_choices = (
        db.session.query(EvalTask.id, EvalTask.target_url, EvalTask.created_at)
        .join(PlanArtifact, PlanArtifact.task_id == EvalTask.id)
        .distinct().order_by(EvalTask.created_at.desc()).all()
    )
    return render_template("admin_artifacts.html", rows=rows, page=page,
                           pages=pages, per_page=per_page, total=total,
                           per_page_choices=PER_PAGE_CHOICES,
                           task_choices=task_choices, f_task_id=task_id)


@bp.route("/audit")
@login_required
@admin_required
def audit_page():
    username = (request.args.get("username") or "").strip()
    action = (request.args.get("action") or "").strip()

    query = AuditLog.query
    if username:
        query = query.filter(AuditLog.username == username)
    if action:
        query = query.filter(AuditLog.action == action)

    per_page = _to_int(request.args.get("per_page"), 10)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 10
    ordered = query.order_by(AuditLog.created_at.desc())
    total = ordered.count()
    pages = max(1, -(-total // per_page))  # 向上取整
    page = min(max(1, _to_int(request.args.get("page"), 1)), pages)
    logs = ordered.offset((page - 1) * per_page).limit(per_page).all()

    # 各动作计数统计
    stats = (
        db.session.query(AuditLog.action, db.func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .all()
    )
    actions = [row[0] for row in db.session.query(AuditLog.action).distinct().all()]
    return render_template("admin_audit.html", logs=logs, stats=stats,
                           actions=actions, f_username=username, f_action=action,
                           page=page, pages=pages, per_page=per_page, total=total,
                           per_page_choices=PER_PAGE_CHOICES)


@bp.route("/audit/batch-delete", methods=["POST"])
@login_required
@admin_required
def audit_batch_delete():
    """批量删除操作审计日志。"""
    log_ids = [_to_int(v, 0) for v in request.form.getlist("log_ids")]
    log_ids = [v for v in log_ids if v]
    deleted = 0
    if log_ids:
        deleted = (AuditLog.query.filter(AuditLog.id.in_(log_ids))
                   .delete(synchronize_session=False))
        db.session.commit()
        audit.record(audit.ACTION_AUDIT_DELETE, target=f"{deleted} logs",
                     detail=f"ids={log_ids[:20]}")
    flash(f"{_('batch_deleted')}: {deleted}", "info")
    return redirect(url_for("admin.audit_page",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10),
                            username=request.args.get("username", ""),
                            action=request.args.get("action", "")))


def _to_int(value, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


# ─── 用户算力配置管理 ───────────────────────────────────────────────────────


@bp.route("/user-llm")
@login_required
@admin_required
def user_llm_configs():
    """查看各用户侧算力配置，支持分页、按日期或账户名称检索。"""
    per_page = _to_int(request.args.get("per_page"), 10)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 10

    username = (request.args.get("username") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()

    query = (
        db.session.query(UserLLMConfig, User.username)
        .join(User, UserLLMConfig.user_id == User.id)
        .order_by(UserLLMConfig.created_at.desc())
    )
    if username:
        query = query.filter(User.username.like(f"%{username}%"))
    if date_from:
        try:
            from datetime import datetime
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(UserLLMConfig.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime, timedelta
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(UserLLMConfig.created_at < dt_to)
        except ValueError:
            pass

    total = query.count()
    pages = max(1, -(-total // per_page))
    page = min(max(1, _to_int(request.args.get("page"), 1)), pages)
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    return render_template("admin_user_llm.html", rows=rows, page=page,
                           pages=pages, per_page=per_page, total=total,
                           per_page_choices=PER_PAGE_CHOICES,
                           f_username=username, f_date_from=date_from,
                           f_date_to=date_to)

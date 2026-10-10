# -*- coding: utf-8 -*-
"""主蓝图：控制台首页与语言切换。"""
import os

from flask import Blueprint, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.guide import guide_data
from geo_optimizer.web.portal.i18n import set_locale
from geo_optimizer.web.portal.main import landing_data
from geo_optimizer.web.portal.models import EvalTask, GeoPlan

bp = Blueprint("main", __name__)

# geo-skill 公开目录（免登录访问）
_SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "docs", "geo-skill"
)
_SKILL_DIR = os.path.normpath(_SKILL_DIR)

# docs 公开目录（用户指南等）
_DOCS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "docs"
)
_DOCS_DIR = os.path.normpath(_DOCS_DIR)

DASHBOARD_RECENT = 5  # 管理员控制台总体概览仅展示最近 5 条任务
DASHBOARD_RECENT_USER = 10  # 普通用户控制台评估历史仅展示最近 10 条任务


@bp.route("/")
def index():
    """平台首页：未登录展示公开 Landing 页，已登录直接进入控制台。"""
    if current_user.is_authenticated:
        return _dashboard()
    return render_template(
        "landing.html",
        faq=landing_data.FAQ_ITEMS,
        engines=landing_data.ENGINES,
    )


@bp.route("/dashboard")
@login_required
def dashboard():
    return _dashboard()


def _dashboard():
    if current_user.is_admin:
        stats = {
            "users": _count("users"),
            "tasks": EvalTask.query.count(),
            "plans": GeoPlan.query.count(),
        }
        recent = (
            EvalTask.query.order_by(EvalTask.created_at.desc())
            .limit(DASHBOARD_RECENT)
            .all()
        )
    else:
        stats = {
            "tasks": EvalTask.query.filter_by(user_id=current_user.id).count(),
            "quota_left": current_user.quota_left,
        }
        recent = (
            EvalTask.query.filter_by(user_id=current_user.id)
            .order_by(EvalTask.created_at.desc())
            .limit(DASHBOARD_RECENT_USER)
            .all()
        )
    return render_template("dashboard.html", stats=stats, recent=recent)


@bp.route("/guide")
@login_required
def guide():
    return render_template("guide.html", g=guide_data)


@bp.route("/api-docs")
@login_required
def api_docs():
    return render_template("api_docs.html")


@bp.route("/llm-setup-guide")
@login_required
def llm_setup_guide():
    """Token Plan / 百炼 算力方案接入指引。"""
    return render_template("llm_setup_guide.html")


@bp.route("/lang/<code>")
def switch_lang(code):
    set_locale(code)
    # 已登录则持久化到用户偏好
    if current_user.is_authenticated:
        current_user.locale = code if code in ("zh", "en") else "zh"
        db.session.commit()
    return redirect(request.referrer or url_for("main.dashboard"))


# ─── GEO-Skill 公开访问（免登录） ───────────────────────────────────

@bp.route("/geo-skill")
@bp.route("/geo-skill/")
def geo_skill_index():
    """GEO-Skill 公开首页：展示 SKILL.md 内容。"""
    skill_md = os.path.join(_SKILL_DIR, "SKILL.md")
    if os.path.isfile(skill_md):
        return send_from_directory(_SKILL_DIR, "SKILL.md", mimetype="text/markdown")
    return "GEO-Skill not found", 404


@bp.route("/geo-skill/<path:filename>")
def geo_skill_file(filename):
    """GEO-Skill 公开静态文件访问（免登录）。"""
    # 安全检查：防止路径穿越
    safe_name = os.path.normpath(filename)
    if safe_name.startswith("..") or os.path.isabs(safe_name):
        return "Forbidden", 403
    return send_from_directory(_SKILL_DIR, safe_name)


@bp.route("/user-guide")
def user_guide():
    """用户使用指南 HTML 页面（免登录）。"""
    return render_template("user_guide.html")


@bp.route("/user-guide.md")
def user_guide_raw():
    """用户使用指南原始 Markdown 文件（免登录）。"""
    guide_file = os.path.join(_DOCS_DIR, "user-guide.md")
    if os.path.isfile(guide_file):
        return send_from_directory(_DOCS_DIR, "user-guide.md", mimetype="text/markdown")
    return "User guide not found", 404


def _count(table_model_name: str) -> int:
    from geo_optimizer.web.portal.models import User

    return User.query.count()

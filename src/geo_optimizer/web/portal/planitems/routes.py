# -*- coding: utf-8 -*-
"""改进方案蓝图：条目列表、可编辑操作页、单项与整体打包下载。"""
import io
import zipfile

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from geo_optimizer.web.portal.audit import service as audit
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.i18n import translate as _
from geo_optimizer.web.portal.models import EvalTask, PlanArtifact, PlanItem
from geo_optimizer.web.portal.planitems import artifact_catalog, artifact_generator
from geo_optimizer.web.portal.planitems.catalog import engines_map

bp = Blueprint("plan", __name__, url_prefix="/plan")

_PRIORITY_ORDER = ("high", "mid", "low")


@bp.route("/<task_id>")
@login_required
def item_list(task_id):
    task = _owned_task_or_404(task_id)
    items = PlanItem.query.filter_by(task_id=task_id).all()
    grouped = {p: [i for i in items if i.priority == p] for p in _PRIORITY_ORDER}
    artifact_counts = {}
    for art in PlanArtifact.query.filter_by(task_id=task_id).all():
        artifact_counts[art.item_id] = artifact_counts.get(art.item_id, 0) + 1
    return render_template("plan_items.html", task=task, grouped=grouped,
                           total=len(items), engines_map=engines_map(),
                           artifact_counts=artifact_counts)


@bp.route("/item/<int:item_id>", methods=["GET", "POST"])
@login_required
def item_edit(item_id):
    item = _owned_item_or_404(item_id)
    if request.method == "POST":
        content = request.form.get("content") or ""
        item.content = content
        db.session.commit()
        audit.record(audit.ACTION_PLAN_ITEM_EDIT, target=item.code,
                     detail=f"task={item.task_id}")
        flash(_("item_saved"), "info")
        return redirect(url_for("plan.item_edit", item_id=item.id))
    specs = artifact_catalog.specs_for(item.code)
    existing = {a.kind: a for a in PlanArtifact.query.filter_by(item_id=item.id).all()}
    return render_template("plan_item_edit.html", item=item,
                           artifact_specs=specs, artifacts=existing)


@bp.route("/<task_id>/artifacts")
@login_required
def artifact_list(task_id):
    """任务维度的产出物统一管理列表：支持新增生成/编辑/删除/下载。"""
    task = _owned_task_or_404(task_id)
    items = {i.id: i for i in PlanItem.query.filter_by(task_id=task_id).all()}
    artifacts = (PlanArtifact.query.filter_by(task_id=task_id)
                 .order_by(PlanArtifact.updated_at.desc()).all())
    rows = [(a, items.get(a.item_id)) for a in artifacts]
    # 尚未生成的规格，供“新增生成”
    generated = {(a.item_id, a.kind) for a in artifacts}
    missing = []
    for item in items.values():
        for spec in artifact_catalog.specs_for(item.code):
            if (item.id, spec["kind"]) not in generated:
                missing.append((item, spec))
    return render_template("plan_artifacts.html", task=task, rows=rows,
                           missing=missing)


@bp.route("/artifact/<int:artifact_id>/delete", methods=["POST"])
@login_required
def artifact_delete(artifact_id):
    artifact, _item = _owned_artifact_or_404(artifact_id)
    task_id, kind = artifact.task_id, artifact.kind
    db.session.delete(artifact)
    db.session.commit()
    audit.record(audit.ACTION_ARTIFACT_DELETE, target=kind,
                 detail=f"task={task_id}")
    flash(_("artifact_deleted"), "info")
    next_url = request.form.get("next") or url_for("plan.artifact_list",
                                                   task_id=task_id)
    return redirect(next_url)


@bp.route("/item/<int:item_id>/artifact/<kind>", methods=["POST"])
@login_required
def artifact_generate(item_id, kind):
    """结合站点实际内容（页面快照）生成/重新生成具体产出物。"""
    item = _owned_item_or_404(item_id)
    spec = artifact_catalog.get_spec(item.code, kind)
    if spec is None:
        abort(404)
    task = db.session.get(EvalTask, item.task_id)
    from geo_optimizer.web.portal.tasks.config_builder import build_config
    from geo_optimizer.web.portal.tasks.snapshot import load_snapshot

    snapshot = load_snapshot(task.artifact_dir if task else None)
    config = build_config(task.target_url, task.artifact_dir or "") if task else {}
    content, source = artifact_generator.generate(
        spec, task.target_url if task else "", snapshot, config)
    artifact = artifact_generator.upsert(item, spec, content, source)
    audit.record(audit.ACTION_ARTIFACT_GENERATE, target=kind,
                 detail=f"task={item.task_id} source={source}")
    flash(_("artifact_generated") if source != "template"
          else _("artifact_generated_fallback"), "info")
    next_url = request.form.get("next")
    return redirect(next_url or url_for("plan.artifact_edit",
                                        artifact_id=artifact.id))


@bp.route("/artifact/<int:artifact_id>", methods=["GET", "POST"])
@login_required
def artifact_edit(artifact_id):
    artifact, item = _owned_artifact_or_404(artifact_id)
    if request.method == "POST":
        artifact.content = request.form.get("content") or ""
        db.session.commit()
        audit.record(audit.ACTION_ARTIFACT_EDIT, target=artifact.kind,
                     detail=f"task={artifact.task_id}")
        flash(_("artifact_saved"), "info")
        return redirect(url_for("plan.artifact_edit", artifact_id=artifact.id))
    spec = artifact_catalog.get_spec(item.code, artifact.kind) or {}
    return render_template("plan_artifact_edit.html", artifact=artifact,
                           item=item, spec=spec)


@bp.route("/artifact/<int:artifact_id>/download")
@login_required
def artifact_download(artifact_id):
    artifact, _item = _owned_artifact_or_404(artifact_id)
    audit.record(audit.ACTION_PLAN_ITEM_DOWNLOAD, target=artifact.kind,
                 detail=f"task={artifact.task_id}")
    buf = io.BytesIO(artifact.content.encode("utf-8"))
    return send_file(buf, as_attachment=True, mimetype="application/octet-stream",
                     download_name=artifact.filename)


@bp.route("/item/<int:item_id>/download")
@login_required
def item_download(item_id):
    item = _owned_item_or_404(item_id)
    audit.record(audit.ACTION_PLAN_ITEM_DOWNLOAD, target=item.code,
                 detail=f"task={item.task_id}")
    buf = io.BytesIO(item.content.encode("utf-8"))
    return send_file(buf, as_attachment=True, mimetype="text/markdown",
                     download_name=f"{item.priority}_{item.code}.md")


@bp.route("/<task_id>/download")
def bundle_download(task_id):
    """整体打包下载（免登录：task_id 为不可枚举的 UUID，链接即凭证，支持分享）。

    属主/管理员下载不限次数；其他下载受系统配置 download_limit 限流。
    """
    from geo_optimizer.web.portal.tasks import service as task_service

    task = db.session.get(EvalTask, task_id)
    if not task:
        abort(404)
    items = PlanItem.query.filter_by(task_id=task_id).all()
    if not items:
        abort(404)
    privileged = current_user.is_authenticated and (
        current_user.id == task.user_id or current_user.is_admin)
    if not privileged and not task_service.consume_download_quota(task, "bundle_download_count"):
        abort(403)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 评估报告 PDF（若已生成）
        _add_report_files(zf, task)
        for item in items:
            zf.writestr(f"{item.priority}_{item.code}.md",
                        item.content.encode("utf-8"))
        for art in PlanArtifact.query.filter_by(task_id=task_id).all():
            zf.writestr(f"artifacts/{art.filename}", art.content.encode("utf-8"))
    buf.seek(0)
    audit.record(audit.ACTION_PLAN_ITEM_DOWNLOAD, target=task.target_url,
                 detail=f"task={task_id} bundle={len(items)}")
    from geo_optimizer.web.portal.packaging.bundler import download_filename
    return send_file(buf, as_attachment=True, mimetype="application/zip",
                     download_name=download_filename(task.target_url))


def _add_report_files(zf, task) -> None:
    """将任务产物目录中的评估报告（PDF/MD）加入 ZIP。"""
    from pathlib import Path

    if not task.artifact_dir:
        return
    base = Path(task.artifact_dir)
    for name in ("geo_analysis_report.pdf", "geo_analysis_report.md"):
        fp = base / name
        if fp.is_file():
            zf.write(fp, arcname=f"report/{name}")


def _owned_task_or_404(task_id: str) -> EvalTask:
    task = db.session.get(EvalTask, task_id)
    if not task:
        abort(404)
    if task.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return task


def _owned_item_or_404(item_id: int) -> PlanItem:
    item = db.session.get(PlanItem, item_id)
    if not item:
        abort(404)
    if item.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return item


def _owned_artifact_or_404(artifact_id: int):
    artifact = db.session.get(PlanArtifact, artifact_id)
    if not artifact:
        abort(404)
    if artifact.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    item = db.session.get(PlanItem, artifact.item_id)
    if not item:
        abort(404)
    return artifact, item

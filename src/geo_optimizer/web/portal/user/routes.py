# -*- coding: utf-8 -*-
"""普通用户蓝图：GEO 评估、历史、下载、删除、API 密钥管理。"""
import os

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required

from geo_optimizer.web.portal.audit import service as audit
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.i18n import translate as _
from geo_optimizer.web.portal.llm_test import test_llm_connection as _test_llm_connection
from geo_optimizer.web.portal.models import (
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_QUEUED,
    TYPE_EVAL,
    TYPE_PLAN,
    USER_LLM_PROVIDERS,
    USER_PROVIDER_PRESETS,
    ApiCallLog,
    ApiKey,
    EvalTask,
    GeoPlan,
    PlanItem,
    UserLLMConfig,
)
from geo_optimizer.web.portal.tasks import runner, service
from geo_optimizer.web.portal.tasks.config_builder import user_has_available_llm

bp = Blueprint("user", __name__)

# 评估历史每页条数可选项
PER_PAGE_CHOICES = (10, 20, 50)


def _to_int(value, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


@bp.route("/eval/new", methods=["GET", "POST"])
@login_required
def eval_new():
    if request.method == "POST":
        url = (request.form.get("target_url") or "").strip()
        task_type = request.form.get("task_type") or TYPE_EVAL
        task_type = task_type if task_type in (TYPE_EVAL, TYPE_PLAN) else TYPE_EVAL

        if not url:
            flash(_("target_url"), "error")
            return render_template("eval_new.html")
        if current_user.quota_left <= 0:
            flash(_("quota_exceeded"), "error")
            return render_template("eval_new.html")
        if not user_has_available_llm(current_user.id, current_user.can_use_platform_llm):
            flash(_("llm_cfg_unavailable"), "error")
            return render_template("eval_new.html")
        if service.user_active_count(current_user.id) >= service.MAX_USER_CONCURRENT:
            flash(_("user_concurrent_limit"), "error")
            return render_template("eval_new.html")

        # 全局并发已满时进入排队，否则立即执行
        need_queue = service.global_running_count() >= service.MAX_GLOBAL_CONCURRENT
        service.reserve_quota(current_user.id)
        task = service.create_task(current_user.id, url, task_type, queued=need_queue)
        action = audit.ACTION_PLAN_GENERATE if task_type == TYPE_PLAN else audit.ACTION_EVAL_SUBMIT
        audit.record(action, target=url, detail=f"task={task.id}")
        if not need_queue:
            runner.start(_current_app(), task.id, url, task_type)
        else:
            flash(_("task_queued"), "info")
        return redirect(url_for("user.eval_detail", task_id=task.id))

    return render_template("eval_new.html")


@bp.route("/eval/<task_id>")
@login_required
def eval_detail(task_id):
    task = _owned_task_or_404(task_id)
    item_count = PlanItem.query.filter_by(task_id=task_id).count()
    queue_pos = service.queue_position(task_id) if task.status == STATUS_QUEUED else 0
    return render_template("eval_detail.html", task=task, result=task.result(),
                           item_count=item_count, queue_pos=queue_pos,
                           logs=_translated_logs(task_id, limit=service.RECENT_LOGS),
                           log_total=service.count_logs(task_id))


@bp.route("/eval/<task_id>/status")
@login_required
def eval_status(task_id):
    task = _owned_task_or_404(task_id)
    data = task.to_dict()
    data["result"] = task.result()
    data["message_text"] = _(task.message) if task.message else ""
    data["logs"] = _translated_logs(task_id, limit=service.RECENT_LOGS)
    data["log_total"] = service.count_logs(task_id)
    if task.status == STATUS_QUEUED:
        data["queue_position"] = service.queue_position(task_id)
    return jsonify(data)


@bp.route("/eval/<task_id>/logs")
@login_required
def eval_logs(task_id):
    """全量历史处理日志（保留期内，时间倒排）。"""
    _owned_task_or_404(task_id)
    return jsonify({"logs": _translated_logs(task_id)})


@bp.route("/eval/<task_id>/retry", methods=["POST"])
@login_required
def eval_retry(task_id):
    """重试失败任务：重置同一任务并重新执行（失败时配额已归还，重试重新预扣）。"""
    task = _owned_task_or_404(task_id)
    if task.status not in (STATUS_FAILED, STATUS_CANCELLED):
        flash(_("retry_not_failed"), "error")
        return redirect(url_for("user.eval_detail", task_id=task_id))
    if current_user.quota_left <= 0:
        flash(_("quota_exceeded"), "error")
        return redirect(url_for("user.eval_detail", task_id=task_id))
    if not user_has_available_llm(current_user.id, current_user.can_use_platform_llm):
        flash(_("llm_cfg_unavailable"), "error")
        return redirect(url_for("user.eval_detail", task_id=task_id))
    if service.user_active_count(current_user.id) >= service.MAX_USER_CONCURRENT:
        flash(_("user_concurrent_limit"), "error")
        return redirect(url_for("user.eval_detail", task_id=task_id))

    need_queue = service.global_running_count() >= service.MAX_GLOBAL_CONCURRENT
    service.reserve_quota(current_user.id)
    service.reset_for_retry(task.id)
    if need_queue:
        task.status = STATUS_QUEUED
        db.session.commit()
        flash(_("task_queued"), "info")
    else:
        audit.record(audit.ACTION_EVAL_RETRY, target=task.target_url,
                     detail=f"task={task.id}")
        runner.start(_current_app(), task.id, task.target_url, task.type)
        flash(_("retry_started"), "info")
    return redirect(url_for("user.eval_detail", task_id=task.id))


@bp.route("/eval/<task_id>/cancel", methods=["POST"])
@login_required
def eval_cancel(task_id):
    """用户终止任务（排队中/运行中均可）。"""
    task = _owned_task_or_404(task_id)
    if task.status in (STATUS_QUEUED, "pending", "running"):
        service.cancel_task(task_id)
        flash(_("task_cancelled"), "info")
    else:
        flash(_("cancel_not_allowed"), "error")
    return redirect(url_for("user.eval_detail", task_id=task_id))


def _translated_logs(task_id: str, limit: int = 0) -> list:
    """任务日志（时间倒排），message/detail 按当前语言翻译（非 i18n key 原文回退）。"""
    logs = [log.to_dict() for log in service.logs_for(task_id, limit=limit)]
    for entry in logs:
        entry["message"] = _(entry["message"])
        if entry["detail"]:
            entry["detail"] = _(entry["detail"])
    return logs


@bp.route("/eval/<task_id>/download")
def eval_download(task_id):
    """下载方案 ZIP（免登录：task_id 为不可枚举的 UUID，链接即凭证，支持分享）。

    属主/管理员下载不限次数；其他下载受系统配置 download_limit 限流。
    """
    task = db.session.get(EvalTask, task_id)
    if not task:
        abort(404)
    plan = GeoPlan.query.filter_by(task_id=task_id).first()
    if not plan or not plan.zip_path or not os.path.exists(plan.zip_path):
        abort(404)
    privileged = current_user.is_authenticated and (
        current_user.id == task.user_id or current_user.is_admin)
    if not privileged and not service.consume_download_quota(task, "eval_download_count"):
        abort(403)
    audit.record(audit.ACTION_DOWNLOAD, target=task.target_url, detail=f"task={task_id}")
    from geo_optimizer.web.portal.packaging.bundler import download_filename
    return send_file(plan.zip_path, as_attachment=True,
                     download_name=download_filename(task.target_url))


@bp.route("/history")
@login_required
def history():
    per_page = _to_int(request.args.get("per_page"), 10)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 10
    query = (
        EvalTask.query.filter_by(user_id=current_user.id)
        .order_by(EvalTask.created_at.desc())
    )
    total = query.count()
    pages = max(1, -(-total // per_page))  # 向上取整
    page = min(max(1, _to_int(request.args.get("page"), 1)), pages)
    tasks = query.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("history.html", tasks=tasks, page=page, pages=pages,
                           per_page=per_page, total=total,
                           per_page_choices=PER_PAGE_CHOICES)


@bp.route("/history/batch-delete", methods=["POST"])
@login_required
def history_batch_delete():
    """批量删除历史评估（仅限本人任务，逐个级联删除）。"""
    task_ids = request.form.getlist("task_ids")
    deleted = 0
    for task_id in task_ids:
        task = db.session.get(EvalTask, task_id)
        # 跳过不存在或非本人的任务（管理员可删任意）
        if not task or (task.user_id != current_user.id and not current_user.is_admin):
            continue
        target_url = task.target_url
        service.delete_task_cascade(task)
        audit.record(audit.ACTION_HISTORY_DELETE, target=target_url,
                     detail=f"task={task_id} batch")
        deleted += 1
    flash(f"{_('batch_deleted')}: {deleted}", "info")
    return redirect(url_for("user.history",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10)))


@bp.route("/history/<task_id>/delete", methods=["POST"])
@login_required
def history_delete(task_id):
    task = _owned_task_or_404(task_id)
    target_url = task.target_url
    # 级联删除方案记录、改进条目、处理日志与产物目录
    service.delete_task_cascade(task)
    audit.record(audit.ACTION_HISTORY_DELETE, target=target_url, detail=f"task={task_id}")
    flash(_("delete"), "info")
    # 控制台删除后回控制台，历史页删除后回历史页（保留翻页参数）
    if request.args.get("next") == "dashboard":
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("user.history",
                            page=request.args.get("page", 1),
                            per_page=request.args.get("per_page", 10)))


def _owned_task_or_404(task_id: str) -> EvalTask:
    task = db.session.get(EvalTask, task_id)
    if not task:
        abort(404)
    if task.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return task


def _current_app():
    from flask import current_app

    return current_app._get_current_object()


# ─── API 密钥管理 ────────────────────────────────────────────────────────────


def _build_skill_zip(key_prefix: str, raw_key: str | None, key_name: str) -> bytes:
    """生成符合 ClawHub skill 规范的技能包 ZIP。

    目录结构（根目录名与 frontmatter name 一致）:
        geo-optimizer/
        ├── SKILL.md              # ClawHub frontmatter + 使用说明
        ├── .clawhubignore        # 发布时忽略 config.json，防止密钥泄露
        ├── config.json           # 个人凭据（仅导出包含，不发布）
        └── scripts/              # 客户端模块（单文件不超过 300 行）
            ├── geo_skill_client.py   # CLI 入口
            ├── geo_skill_api.py      # GeoSkillClient 类
            └── geo_skill_common.py   # 配置解析/工具函数/异常
    """
    import io
    import json
    from pathlib import Path
    import zipfile

    # 平台地址：优先取请求 host，回退 localhost:5001
    base_url = request.host_url.rstrip("/") if request else "http://localhost:5001"

    skill_dir = Path(__file__).resolve().parents[5] / "docs" / "geo-skill"
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    clawhubignore = (skill_dir / ".clawhubignore").read_text(encoding="utf-8")
    # 客户端拆分为多模块（单文件≤300行），全部打包进 scripts/
    script_names = ("geo_skill_client.py", "geo_skill_api.py", "geo_skill_common.py")
    scripts = {
        name: (skill_dir / "scripts" / name).read_text(encoding="utf-8")
        for name in script_names
    }

    # ClawHub 规范校验：SKILL.md 必须以 --- 开头且 frontmatter 为合法 YAML，
    # 导出前提前拦截，避免用户导入时才发现头部解析失败
    import yaml
    if not skill_md.startswith("---"):
        raise ValueError("SKILL.md 缺少 YAML frontmatter（需以 --- 开头）")
    try:
        front = yaml.safe_load(skill_md.split("---", 2)[1])
    except yaml.YAMLError as exc:
        raise ValueError(f"SKILL.md frontmatter 不是合法 YAML: {exc}") from exc
    if not isinstance(front, dict) or front.get("name") != "geo-optimizer":
        raise ValueError("SKILL.md frontmatter 缺少 name: geo-optimizer")

    # 生成 config.json（含明文密钥，已被 .clawhubignore 排除在发布之外）
    config = {
        "base_url": base_url,
        "api_key": raw_key or f"<YOUR_API_KEY ({key_prefix}...)>",
        "key_name": key_name,
        "key_prefix": key_prefix,
        "poll_interval": 6,  # 任务状态轮询间隔（秒），客户端可改
    }
    config_json = json.dumps(config, ensure_ascii=False, indent=2)

    # ClawHub 规范：根目录名必须与 frontmatter name 一致（小写字母/数字/连字符）
    buf = io.BytesIO()
    folder = "geo-optimizer"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{folder}/SKILL.md", skill_md)
        zf.writestr(f"{folder}/.clawhubignore", clawhubignore)
        zf.writestr(f"{folder}/config.json", config_json)
        for name, content in scripts.items():
            zf.writestr(f"{folder}/scripts/{name}", content)
    return buf.getvalue()


# MCP 本地部署包 README 模板（__BASE_URL__ / __KEY_PREFIX__ 为占位符）
_MCP_README_TEMPLATE = """# GEO-Optimizer MCP 服务端（本地 stdio 部署包）

把 GEO-Optimizer 平台开放 API 封装为 MCP 工具，供 Claude Desktop / Cursor / Qoder
等 MCP 客户端调用。本包为**本地 stdio 模式**：MCP 客户端拉起本地进程，进程用你的
API Key 直接调用平台开放 API（无需依赖任何在线 MCP 服务）。

> config.json 内的 API Key 与你在平台「导出 Skill」得到的**是同一把密钥**。

## 目录结构

```
geo-optimizer-mcp/
├── README.md            本文件
├── requirements.txt     依赖：mcp[cli]>=2.1,<3
├── config.json          凭据：base_url + api_key（已注入，含明文密钥）
├── mcp-config.json      可直接粘贴到 MCP 客户端的 mcpServers 片段（stdio）
└── mcp_server/          MCP 服务端包（server / api_client / config / formatting）
```

## 使用步骤

1. 解压到任意目录，例如 `~/geo-optimizer-mcp`。
2. 安装依赖（需 Python 3.10+）：
   ```bash
   cd ~/geo-optimizer-mcp
   pip install -r requirements.txt
   ```
3. 打开 `mcp-config.json`，把其中的 `mcpServers` 合并进你的 MCP 客户端配置文件，
   并把 `cwd` 改成解压后的**绝对路径**（如 `/Users/you/geo-optimizer-mcp`）。
4. 重启 MCP 客户端，即可看到 8 个 `geo_*` 工具。

## mcpServers 配置（stdio）

```json
{
  "mcpServers": {
    "geo-optimizer": {
      "command": "python3",
      "args": ["-m", "mcp_server", "--transport", "stdio"],
      "cwd": "/ABSOLUTE/PATH/TO/geo-optimizer-mcp"
    }
  }
}
```

凭据默认由 `mcp_server/config.py` 从同目录 `config.json` 读取（base_url / api_key）；
也可改用环境变量 `GEO_API_KEY` / `GEO_BASE_URL`（见 `mcp-config.json` 的 `env` 示例）。

## 平台地址与密钥

- 平台地址 base_url：`__BASE_URL__`
- 密钥前缀 key_prefix：`__KEY_PREFIX__...`
- 完整密钥见 `config.json`（与 Skill 导出共用同一把）

## 工具一览（8 个）

| 工具 | 作用 |
| --- | --- |
| geo_submit_task | 提交网站 GEO 评估任务，立即返回 task_id |
| geo_list_tasks | 列出最近任务（分页 + 时间范围过滤） |
| geo_get_task_status | 查询任务状态与进度 |
| geo_get_task_logs | 获取云端执行日志（中文，支持增量拉取） |
| geo_get_task_result | 获取评分、优势/待改进、下载链接 |
| geo_cancel_task | 终止排队中/运行中的任务（退回配额） |
| geo_get_usage | 查看 API 调用统计 |
| geo_download_report | 把报告与方案 ZIP 下载到本地 |

## 安全提示

`config.json` 含明文 API Key，请勿提交到公共仓库或分享。如需轮换，在平台
「API 密钥」页重新生成后重新导出本包即可。
"""


def _build_mcp_zip(key_prefix: str, raw_key: str | None, key_name: str) -> bytes:
    """生成 MCP 服务端本地部署包 ZIP（stdio 模式，与 Skill 导出共用同一把密钥）。

    目录结构:
        geo-optimizer-mcp/
        ├── README.md            # 安装与接入说明
        ├── requirements.txt     # mcp[cli]>=2.1,<3
        ├── config.json          # 凭据（base_url + api_key，被 mcp_server/config.py 读取）
        ├── mcp-config.json      # 可粘贴到 MCP 客户端的 mcpServers 片段（stdio）
        └── mcp_server/          # MCP 服务端包（6 个模块）
    """
    import io
    import json
    import zipfile
    from pathlib import Path

    # 平台地址：优先取请求 host（云端即 https://域名），回退 localhost:5001
    base_url = request.host_url.rstrip("/") if request else "http://localhost:5001"
    api_key = raw_key or f"<YOUR_API_KEY ({key_prefix}...)>"

    mcp_src = Path(__file__).resolve().parents[5] / "mcp_server"
    module_names = ("__init__.py", "__main__.py", "server.py",
                    "api_client.py", "config.py", "formatting.py")
    modules = {}
    for name in module_names:
        fp = mcp_src / name
        if not fp.is_file():
            raise ValueError(f"MCP 服务端模块缺失: {fp}")
        modules[name] = fp.read_text(encoding="utf-8")

    # config.json —— 被 mcp_server/config.py 自动读取（_REPO_ROOT/config.json）
    config = {
        "base_url": base_url,
        "api_key": api_key,
        "key_name": key_name,
        "key_prefix": key_prefix,
    }
    # mcp-config.json —— 直接粘贴到 MCP 客户端（stdio 本地运行）
    mcp_config = {
        "mcpServers": {
            "geo-optimizer": {
                "command": "python3",
                "args": ["-m", "mcp_server", "--transport", "stdio"],
                "cwd": "<解压后 geo-optimizer-mcp 的绝对路径>",
                "env": {"GEO_API_KEY": api_key, "GEO_BASE_URL": base_url},
            }
        }
    }
    readme = (_MCP_README_TEMPLATE
              .replace("__BASE_URL__", base_url)
              .replace("__KEY_PREFIX__", key_prefix))

    folder = "geo-optimizer-mcp"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{folder}/README.md", readme)
        zf.writestr(f"{folder}/requirements.txt", "mcp[cli]>=2.1,<3\n")
        zf.writestr(f"{folder}/config.json",
                    json.dumps(config, ensure_ascii=False, indent=2))
        zf.writestr(f"{folder}/mcp-config.json",
                    json.dumps(mcp_config, ensure_ascii=False, indent=2))
        for name, content in modules.items():
            zf.writestr(f"{folder}/mcp_server/{name}", content)
    return buf.getvalue()


@bp.route("/api-keys")
@login_required
def api_keys():
    """API 密钥列表。"""
    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    total_calls = sum(k.total_calls or 0 for k in keys)
    return render_template("user_api_keys.html", keys=keys, total_calls=total_calls,
                           new_key=None, regenerated_key_id=None)


@bp.route("/api-keys/generate", methods=["POST"])
@login_required
def api_key_generate():
    """生成新 API 密钥。"""
    from geo_optimizer.web.portal.api.auth import generate_api_key

    name = (request.form.get("name") or "").strip()[:64]
    expires_days = _to_int(request.form.get("expires_days"), 365)
    if expires_days < 1:
        expires_days = 365
    if expires_days > 3650:
        expires_days = 3650

    api_key, raw_key = generate_api_key(current_user.id, name=name, expires_days=expires_days)
    audit.record("api_key_create", target=name or api_key.key_prefix,
                 detail=f"expires_days={expires_days}")

    # 重新查询列表并携带新密钥明文（仅此次展示）
    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    total_calls = sum(k.total_calls or 0 for k in keys)
    return render_template("user_api_keys.html", keys=keys, total_calls=total_calls,
                           new_key=raw_key, regenerated_key_id=None)


@bp.route("/api-keys/<int:key_id>/revoke", methods=["POST"])
@login_required
def api_key_revoke(key_id):
    """停用 API 密钥。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)
    key.is_active = False
    db.session.commit()
    audit.record("api_key_revoke", target=key.name or key.key_prefix)
    flash(_("api_key_revoked"), "info")
    return redirect(url_for("user.api_keys"))


@bp.route("/api-keys/<int:key_id>/regenerate", methods=["POST"])
@login_required
def api_key_regenerate(key_id):
    """重新生成 API 密钥：原地重置当前记录的密钥内容，保持同一 ID/名称。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)

    old_prefix = key.key_prefix
    raw_key = _regenerate_key_inplace(key)

    audit.record("api_key_regenerate", target=key.name or key.key_prefix,
                 detail=f"old_prefix={old_prefix}")

    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    total_calls = sum(k.total_calls or 0 for k in keys)
    return render_template("user_api_keys.html", keys=keys, total_calls=total_calls,
                           new_key=raw_key, regenerated_key_id=key.id)


@bp.route("/api-keys/<int:key_id>/delete", methods=["POST"])
@login_required
def api_key_delete(key_id):
    """删除 API 密钥记录（级联删除调用日志）。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)
    target_name = key.name or key.key_prefix
    # 级联删除关联的调用日志
    ApiCallLog.query.filter_by(api_key_id=key_id).delete()
    db.session.delete(key)
    db.session.commit()
    audit.record("api_key_delete", target=target_name)
    flash(_("api_key_deleted"), "info")
    return redirect(url_for("user.api_keys"))


@bp.route("/api-keys/<int:key_id>/reveal")
@login_required
def api_key_reveal(key_id):
    """查看 API 密钥明文（仅限本人，记录审计）。旧记录无明文时返回提示。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)
    if not key.key_plaintext:
        return jsonify({"error": "no_plaintext", "message": _("api_key_no_plaintext")}), 404
    audit.record("api_key_reveal", target=key.name or key.key_prefix,
                 detail=f"key={key_id}")
    return jsonify({"api_key": key.key_plaintext})


@bp.route("/api-keys/<int:key_id>/logs")
@login_required
def api_key_logs(key_id):
    """API 密钥调用明细（分页）。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)

    per_page = 20
    page = max(1, _to_int(request.args.get("page"), 1))
    query = (
        ApiCallLog.query.filter_by(api_key_id=key_id)
        .order_by(ApiCallLog.created_at.desc())
    )
    total = query.count()
    pages = max(1, -(-total // per_page))
    page = min(page, pages)
    logs = query.offset((page - 1) * per_page).limit(per_page).all()

    if request.headers.get("Accept") == "application/json":
        return jsonify({"logs": [l.to_dict() for l in logs], "total": total,
                        "page": page, "pages": pages})
    return render_template("user_api_key_logs.html", key=key, logs=logs,
                           page=page, pages=pages, total=total)


def _regenerate_key_inplace(key) -> str:
    """原地重置密钥内容（保持同一 ID/名称），返回新明文。"""
    import hashlib
    import secrets
    from datetime import datetime, timedelta

    raw_key = f"geo_{secrets.token_urlsafe(32)}"
    key.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key.key_prefix = raw_key[:12]
    key.key_plaintext = raw_key
    key.is_active = True
    key.total_calls = 0
    key.last_used_at = None
    key.expires_at = datetime.utcnow() + timedelta(days=365)
    db.session.commit()
    return raw_key


@bp.route("/api-keys/<int:key_id>/export-skill", methods=["POST"])
@login_required
def api_key_export_skill(key_id):
    """导出符合 ClawHub skill 规范的技能包 ZIP（默认含 API Key 配置）。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)

    # 明文优先取表单传入（创建/重生成时），其次取落库明文
    raw_key = (request.form.get("raw_key") or "").strip() or key.key_plaintext or None
    if not raw_key:
        # 历史密钥无明文：原地重生成，确保导出的 config.json 默认含可用密钥
        raw_key = _regenerate_key_inplace(key)
        audit.record("api_key_regenerate", target=key.name or key.key_prefix,
                     detail="auto on skill export (no plaintext)")
    # config.json 的 key_name 用当前登录用户名填充，便于识别归属
    zip_bytes = _build_skill_zip(key.key_prefix, raw_key, current_user.username)

    audit.record("api_key_export_skill", target=key.name or key.key_prefix)

    import io
    from datetime import datetime

    # 导出包命名格式: geo-用户名-时间戳.zip
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"geo-{current_user.username}-{timestamp}.zip",
    )


@bp.route("/api-keys/<int:key_id>/export-mcp", methods=["POST"])
@login_required
def api_key_export_mcp(key_id):
    """导出 MCP 服务端本地部署包 ZIP（stdio，与 Skill 导出共用同一把密钥）。"""
    key = db.session.get(ApiKey, key_id)
    if not key or key.user_id != current_user.id:
        abort(404)
    # 与 Skill 导出共用同一密钥：表单 raw_key 优先，其次落库明文，都无则原地重生成
    raw_key = (request.form.get("raw_key") or "").strip() or key.key_plaintext or None
    if not raw_key:
        raw_key = _regenerate_key_inplace(key)
        audit.record("api_key_regenerate", target=key.name or key.key_prefix,
                     detail="auto on mcp export (no plaintext)")
    zip_bytes = _build_mcp_zip(key.key_prefix, raw_key, current_user.username)

    audit.record("api_key_export_mcp", target=key.name or key.key_prefix)

    import io
    from datetime import datetime

    # 导出包命名格式: geo-mcp-用户名-时间戳.zip
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"geo-mcp-{current_user.username}-{timestamp}.zip",
    )


# ─── 用户侧算力配置 ─────────────────────────────────────────────────────────


@bp.route("/llm-config")
@login_required
def llm_config():
    """用户算力配置列表。"""
    configs = (
        UserLLMConfig.query.filter_by(user_id=current_user.id)
        .order_by(UserLLMConfig.is_active.desc(), UserLLMConfig.created_at.desc())
        .all()
    )
    # 调用测试后的过程明细（一次性展示）
    test_detail = session.pop("llm_test_detail", None)
    return render_template("user_llm_config.html", configs=configs,
                           providers=USER_PROVIDER_PRESETS,
                           provider_keys=USER_LLM_PROVIDERS,
                           test_detail=test_detail)


@bp.route("/llm-config/save", methods=["POST"])
@login_required
def llm_config_save():
    """新建或更新算力配置。"""
    config_id = _to_int(request.form.get("id"), 0)
    provider = (request.form.get("provider") or "bailian").strip()
    if provider not in USER_LLM_PROVIDERS:
        provider = "bailian"
    name = (request.form.get("name") or "").strip()[:64]
    api_key = (request.form.get("api_key") or "").strip()
    base_url = (request.form.get("base_url") or "").strip()
    model = (request.form.get("model") or "").strip()

    # 非自定义方案自动填充 base_url
    if provider != "custom" and not base_url:
        preset = USER_PROVIDER_PRESETS.get(provider, {})
        base_url = preset.get("openai_base_url", "")

    if not api_key:
        flash(_("llm_cfg_key_required"), "error")
        return redirect(url_for("user.llm_config"))

    if config_id:
        cfg = db.session.get(UserLLMConfig, config_id)
        if not cfg or cfg.user_id != current_user.id:
            abort(404)
        cfg.provider = provider
        cfg.name = name
        cfg.api_key = api_key
        cfg.base_url = base_url
        cfg.model = model
    else:
        cfg = UserLLMConfig(
            user_id=current_user.id,
            provider=provider,
            name=name,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        db.session.add(cfg)

    db.session.commit()
    audit.record("llm_config_save", target=name or provider)
    flash(_("llm_cfg_saved"), "info")
    return redirect(url_for("user.llm_config"))


@bp.route("/llm-config/<int:config_id>/activate", methods=["POST"])
@login_required
def llm_config_activate(config_id):
    """将某条算力配置设为当前使用。"""
    cfg = db.session.get(UserLLMConfig, config_id)
    if not cfg or cfg.user_id != current_user.id:
        abort(404)
    # 取消同用户其他配置的激活状态
    UserLLMConfig.query.filter_by(user_id=current_user.id).update({"is_active": False})
    cfg.is_active = True
    db.session.commit()
    audit.record("llm_config_activate", target=cfg.name or cfg.provider)
    flash(_("llm_cfg_activated"), "info")
    return redirect(url_for("user.llm_config"))


@bp.route("/llm-config/<int:config_id>/delete", methods=["POST"])
@login_required
def llm_config_delete(config_id):
    """删除算力配置。"""
    cfg = db.session.get(UserLLMConfig, config_id)
    if not cfg or cfg.user_id != current_user.id:
        abort(404)
    db.session.delete(cfg)
    db.session.commit()
    audit.record("llm_config_delete", target=cfg.name or cfg.provider)
    flash(_("llm_cfg_deleted"), "info")
    return redirect(url_for("user.llm_config"))


@bp.route("/llm-config/<int:config_id>/key")
@login_required
def llm_config_reveal_key(config_id):
    """查看算力配置的明文 API Key（仅限本人，记录审计）。"""
    cfg = db.session.get(UserLLMConfig, config_id)
    if not cfg or cfg.user_id != current_user.id:
        abort(404)
    audit.record("llm_config_reveal_key", target=cfg.name or cfg.provider,
                 detail=f"config={config_id}")
    return jsonify({"api_key": cfg.api_key})


@bp.route("/llm-config/<int:config_id>/test", methods=["POST"])
@login_required
def llm_config_test(config_id):
    """调用测试：向配置的 LLM 端点发送一个简单请求验证连通性。"""
    cfg = db.session.get(UserLLMConfig, config_id)
    if not cfg or cfg.user_id != current_user.id:
        abort(404)

    ok, detail = _test_llm_connection(cfg.api_key, cfg.base_url, cfg.model)
    detail.update({
        "ok": ok,
        "provider_label": cfg.provider_label,
        "config_name": cfg.name,
        "api_key_masked": cfg.api_key_masked,
    })
    # AJAX 调用直接返回 JSON，由前端浮层展示结果
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(detail)
    # 无 JS 回退：过程明细存入 session，重定向回列表页后一次性展示
    session["llm_test_detail"] = detail
    model_used = detail["model_responded"] or detail["model_requested"]
    if ok:
        flash(f"{_('llm_cfg_test_ok')} · {cfg.provider_label} · {model_used}", "info")
    else:
        flash(f"{_('llm_cfg_test_fail')} · {cfg.provider_label} · "
              f"{detail['model_requested']}: {detail['error']}", "error")
    return redirect(url_for("user.llm_config"))

# -*- coding: utf-8 -*-
"""认证路由蓝图。"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from geo_optimizer.web.portal.audit import service as audit
from geo_optimizer.web.portal.auth.service import (
    authenticate_detail,
    register_user,
    username_exists,
)
from geo_optimizer.web.portal.i18n import translate as _

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user, error_key = authenticate_detail(username, password)
        if user:
            login_user(user)
            audit.record(audit.ACTION_LOGIN, target=username, user=user)
            next_url = request.args.get("next")
            # 管理员默认落地后台用户列表，普通用户进控制台
            home = url_for("admin.users") if user.is_admin else url_for("main.dashboard")
            return redirect(next_url or home)
        flash(_(error_key), "error")

    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = {"username": "", "email": "", "phone": ""}
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        form.update(username=username, email=email, phone=phone)

        error = None
        if not (username and password and email and phone):
            error = "register_fields_required"
        elif username_exists(username):
            error = "register_username_taken"
        elif password != password2:
            error = "register_password_mismatch"

        if error:
            flash(_(error), "error")
        else:
            user = register_user(username, password, email, phone)
            audit.record(audit.ACTION_USER_REGISTER, target=username,
                         detail=f"email={email},phone={phone}", user=user)
            flash(_("register_success"), "info")
            return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    audit.record(audit.ACTION_LOGOUT, target=current_user.username)
    logout_user()
    return redirect(url_for("main.index"))

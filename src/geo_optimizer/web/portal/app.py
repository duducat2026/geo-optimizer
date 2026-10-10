# -*- coding: utf-8 -*-
"""GEO 多用户平台 App Factory。"""
import logging

from flask import Flask, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from geo_optimizer.web.portal import settings as deploy_settings
from geo_optimizer.web.portal.extensions import db, login_manager
from geo_optimizer.web.portal.i18n import get_locale, translate
from geo_optimizer.web.portal.models import ROLE_ADMIN, SystemConfig, User

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """创建并装配 Flask 应用。"""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # 信任 Nginx 反向代理传递的 X-Forwarded-* 头
    # 避免 HTTPS 下 url_for 生成 http:// 链接及无限重定向
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

    conf = deploy_settings.get_settings()
    app.config["SECRET_KEY"] = conf["SECRET_KEY"]
    app.config["GTM_CONTAINER"] = conf.get("GTM_CONTAINER", "")
    app.config["SQLALCHEMY_DATABASE_URI"] = deploy_settings.sqlalchemy_uri()
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 3600}

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):  # noqa: ANN001
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for("auth.login"))

    _register_blueprints(app)

    # Jinja 全局注入：翻译函数、当前语言与 GTM 容器 ID
    @app.context_processor
    def inject_i18n():
        return {
            "_": translate,
            "current_locale": get_locale(),
            "GTM_CONTAINER": app.config.get("GTM_CONTAINER", ""),
        }

    # Jinja 过滤器：UTC 时间转北京时间展示
    from geo_optimizer.web.portal.timeutil import fmt_local

    app.add_template_filter(fmt_local, "localtime")

    with app.app_context():
        db.create_all()
        seed_defaults(conf)

    # 处理日志保留 3 天定期清理；任务监控回收遗留/卡死任务；队列调度器
    if not app.config.get("TESTING"):
        from geo_optimizer.web.portal.tasks import log_cleaner, task_monitor
        from geo_optimizer.web.portal.tasks.runner import start_queue_dispatcher

        log_cleaner.start(app)
        task_monitor.start(app)
        start_queue_dispatcher(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from geo_optimizer.web.portal.admin.routes import bp as admin_bp
    from geo_optimizer.web.portal.api.routes import bp as api_bp
    from geo_optimizer.web.portal.auth.routes import bp as auth_bp
    from geo_optimizer.web.portal.main.routes import bp as main_bp
    from geo_optimizer.web.portal.planitems.routes import bp as plan_bp
    from geo_optimizer.web.portal.user.routes import bp as user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)


def seed_defaults(conf: dict) -> None:
    """首次初始化：默认管理员 + 系统 LLM 默认配置。"""
    if not User.query.filter_by(username=conf["ADMIN_USERNAME"]).first():
        admin = User(
            username=conf["ADMIN_USERNAME"],
            role=ROLE_ADMIN,
            eval_quota=0,
        )
        admin.set_password(conf["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
        logger.info("已创建默认管理员账号: %s", conf["ADMIN_USERNAME"])

    for key, value in (conf.get("LLM_DEFAULTS") or {}).items():
        if SystemConfig.get(key, None) is None:
            SystemConfig.set(key, str(value))
    db.session.commit()
    logger.info("系统配置种子完成")

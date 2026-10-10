# -*- coding: utf-8 -*-
"""Flask 扩展实例（全局单例，供 app factory 初始化）。"""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

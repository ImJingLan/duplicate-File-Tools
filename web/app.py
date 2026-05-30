"""
Flask Web 应用工厂模块
=====================
提供应用创建、蓝图注册、CORS 配置、日志设置及错误处理功能。
"""

import logging
import os

from flask import Flask, render_template, jsonify
from flask_cors import CORS

from config.settings import setup_logging, load_user_preferences

logger = logging.getLogger("web.app")


def create_app(config_overrides=None):
    """
    创建并配置 Flask 应用实例。

    完成以下初始化步骤：
    1. 创建 Flask 应用并指定模板目录和静态文件目录
    2. 配置 CORS，允许 /api/* 路由的跨域请求
    3. 设置日志系统
    4. 加载用户偏好配置
    5. 注册扫描、去重、模式管理、历史记录四个蓝图
    6. 注册错误处理器和主页路由

    Args:
        config_overrides: 可选的配置覆盖字典，用于测试或自定义场景

    Returns:
        Flask: 配置完成的 Flask 应用实例
    """
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
        static_url_path='/static',
    )

    app.config.setdefault('SECRET_KEY', os.urandom(24).hex())
    if config_overrides:
        app.config.update(config_overrides)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    _configure_logging(app)
    _load_preferences(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_routes(app)

    logger.info("Flask 应用创建完成")
    return app


def _configure_logging(app):
    """
    配置应用日志系统。

    从 config.settings.setup_logging 初始化日志，并设置
    Werkzeug 访问日志级别。

    Args:
        app: Flask 应用实例
    """
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    setup_logging(app_name="web_dedup", log_level=log_level)
    logger.info("日志系统已配置，级别: %s", log_level)


def _load_preferences(app):
    """
    加载用户偏好配置并注入到 Flask 应用配置中。

    将 config.settings.load_user_preferences() 返回的
    所有配置项存入 app.config。

    Args:
        app: Flask 应用实例
    """
    prefs = load_user_preferences()
    for key, value in prefs.items():
        app.config[key.upper()] = value
    logger.info("用户偏好已加载，共 %d 项", len(prefs))


def _register_blueprints(app):
    """
    注册所有功能模块的蓝图。

    蓝图及其 URL 前缀：
    - scan_bp:     /api/scan      扫描任务管理
    - dedup_bp:    /api/dedup     智能去重操作
    - pattern_bp:  /api/patterns  保护模式管理
    - history_bp:  /api/history   历史记录管理

    Args:
        app: Flask 应用实例
    """
    from .routes.scan_routes import scan_bp
    from .routes.dedup_routes import dedup_bp
    from .routes.pattern_routes import pattern_bp
    from .routes.history_routes import history_bp

    app.register_blueprint(scan_bp, url_prefix='/api/scan')
    app.register_blueprint(dedup_bp, url_prefix='/api/dedup')
    app.register_blueprint(pattern_bp, url_prefix='/api/patterns')
    app.register_blueprint(history_bp, url_prefix='/api/history')

    logger.info("蓝图注册完成: scan, dedup, patterns, history")


def _register_error_handlers(app):
    """
    注册全局 HTTP 错误处理器。

    提供统一的 JSON 格式错误响应。

    Args:
        app: Flask 应用实例
    """

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "请求参数无效", "detail": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "资源未找到", "detail": str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "不支持的请求方法", "detail": str(e)}), 405

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("服务器内部错误")
        return jsonify({"error": "服务器内部错误", "detail": str(e)}), 500


def _register_routes(app):
    """
    注册非蓝图的前端页面路由。

    Args:
        app: Flask 应用实例
    """

    @app.route('/')
    def index():
        """前端主页"""
        return render_template('index.html')

    @app.route('/health')
    def health():
        """健康检查端点"""
        return jsonify({"status": "ok", "service": "web_dedup"})


if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5000, debug=True)

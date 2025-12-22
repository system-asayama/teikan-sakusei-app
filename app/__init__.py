from __future__ import annotations

import os
from flask import Flask


def create_app() -> Flask:
    """
    Flask アプリケーションを生成して返します。
    Heroku で実行する場合もローカルで実行する場合もこの関数が呼ばれます。
    """
    app = Flask(__name__)

    # デフォルト設定を読み込み(環境変数が無ければ標準値を使う)
    app.config.update(
        APP_NAME=os.getenv("APP_NAME", "survey-system-app"),
        ENVIRONMENT=os.getenv("ENV", "dev"),
        DEBUG=os.getenv("DEBUG", "1") in ("1", "true", "True"),
        VERSION=os.getenv("APP_VERSION", "0.1.0"),
        TZ=os.getenv("TZ", "Asia/Tokyo"),
    )

    # config.py があれば上書き
    try:
        from .config import settings  # type: ignore
        app.config.update(
            ENVIRONMENT=getattr(settings, "ENV", app.config["ENVIRONMENT"]),
            DEBUG=getattr(settings, "DEBUG", app.config["DEBUG"]),
            VERSION=getattr(settings, "VERSION", app.config["VERSION"]),
            TZ=getattr(settings, "TZ", app.config["TZ"]),
            SECRET_KEY=getattr(settings, "SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")),
        )
    except Exception:
        # 存在しない場合は無視
        pass

    # logging.py があればロガーを初期化
    try:
        from .logging import setup_logging  # type: ignore
        setup_logging(debug=app.config["DEBUG"])
    except Exception:
        pass

    # blueprints/health.py があれば登録
    try:
        from .blueprints.health import bp as health_bp  # type: ignore
        app.register_blueprint(health_bp)
    except Exception:
        pass

    # blueprints/auth.py があれば登録
    try:
        from .blueprints.auth import bp as auth_bp  # type: ignore
        app.register_blueprint(auth_bp)
    except Exception:
        pass

    # テンプレート用のget_csrf関数を登録
    try:
        from .utils.security import get_csrf  # type: ignore
        app.jinja_env.globals['get_csrf'] = get_csrf
    except Exception:
        pass

    # ルートは auth.index にリダイレクト
    @app.get("/")
    def root():
        """トップページ"""
        try:
            from flask import redirect, url_for
            return redirect(url_for('auth.index'))
        except:
            return "OK", 200

    return app

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

    @app.get("/")
    def root():
        """ヘルスチェック用のルート"""
        return "OK", 200

    return app

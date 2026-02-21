"""
データベースマイグレーション管理モジュール
アプリ起動時に自動的に必要なカラム追加などを実行する
"""


def run_migrations():
    """全マイグレーションを順番に実行する"""
    _migrate_teikan_status_column()
    _migrate_teikan_updated_at_column()


def _migrate_teikan_status_column():
    """T_定款テーブルにstatusカラムを追加する（存在しない場合のみ）"""
    try:
        from app.db import engine
        from sqlalchemy import text, inspect

        insp = inspect(engine)
        # T_定款テーブルが存在するか確認
        tables = insp.get_table_names()
        if 'T_定款' not in tables:
            return  # テーブルがまだ存在しない場合はスキップ

        # 既存カラムを確認
        columns = [col['name'] for col in insp.get_columns('T_定款')]
        if 'status' in columns:
            return  # 既に存在する場合はスキップ

        # statusカラムを追加（既存レコードはcompletedとして扱う）
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE \"T_定款\" ADD COLUMN status VARCHAR(20) DEFAULT 'completed'"
            ))
            conn.commit()
        print("✅ マイグレーション: T_定款.status カラムを追加しました")
    except Exception as e:
        print(f"⚠️ マイグレーション (status): {e}")


def _migrate_teikan_updated_at_column():
    """T_定款テーブルにupdated_atカラムを追加する（存在しない場合のみ）"""
    try:
        from app.db import engine
        from sqlalchemy import text, inspect

        insp = inspect(engine)
        tables = insp.get_table_names()
        if 'T_定款' not in tables:
            return

        columns = [col['name'] for col in insp.get_columns('T_定款')]
        if 'updated_at' in columns:
            return

        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE \"T_定款\" ADD COLUMN updated_at TIMESTAMP"
            ))
            conn.commit()
        print("✅ マイグレーション: T_定款.updated_at カラムを追加しました")
    except Exception as e:
        print(f"⚠️ マイグレーション (updated_at): {e}")

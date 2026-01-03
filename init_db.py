#!/usr/bin/env python3
"""
Heroku用データベース初期化スクリプト

このスクリプトは、Herokuの release フェーズで実行され、
データベーステーブルを作成し、初期データを投入します。
"""

import os
import sys
from datetime import datetime

def init_database():
    """データベースを初期化"""
    try:
        # アプリケーションのインポート
        from app.db import Base, engine, SessionLocal
        from app import models_login, models_auth
        from app.models_login import M_管理者, M_テナント, M_店舗
        from app.models_auth import M_テナントレベルアプリ
        from app.utils import hash_password
        
        print("📦 データベーステーブルを作成中...")
        Base.metadata.create_all(bind=engine)
        print("✅ データベーステーブル作成完了")
        
        # セッションを作成
        db = SessionLocal()
        
        try:
            # システム管理者が既に存在するか確認
            existing_admin = db.query(M_管理者).filter_by(login_id='admin').first()
            
            if existing_admin:
                print("ℹ️  システム管理者は既に存在します。初期データの投入をスキップします。")
                return
            
            print("📝 初期データを投入中...")
            
            # 1. システム管理者を作成
            admin = M_管理者(
                login_id='admin',
                password=hash_password('admin123'),
                name='システム管理者',
                email='admin@example.com',
                role='system_admin',
                is_owner=True,
                can_manage_admins=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(admin)
            db.flush()  # IDを取得するためにflush
            
            # 2. サンプルテナントを作成
            tenant = M_テナント(
                名称='サンプル株式会社',
                slug='sample-corp',
                有効=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(tenant)
            db.flush()
            
            # 3. 店舗を作成
            stores = [
                M_店舗(
                    名称='本店',
                    tenant_id=tenant.id,
                    有効=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                M_店舗(
                    名称='支店A',
                    tenant_id=tenant.id,
                    有効=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                M_店舗(
                    名称='支店B',
                    tenant_id=tenant.id,
                    有効=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            ]
            for store in stores:
                db.add(store)
            
            # 4. 定款作成アプリをテナントレベルアプリとして有効化
            teikan_app = M_テナントレベルアプリ(
                tenant_id=tenant.id,
                app_key='teikan',
                有効=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(teikan_app)
            
            # コミット
            db.commit()
            print("✅ 初期データ投入完了")
            print(f"   - システム管理者: admin / admin123")
            print(f"   - テナント: {tenant.名称}")
            print(f"   - 店舗: {len(stores)}件")
            print(f"   - アプリ: 定款作成（有効）")
            
        except Exception as e:
            db.rollback()
            print(f"❌ 初期データ投入エラー: {e}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ データベース初期化エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    print("🚀 Heroku データベース初期化スクリプト開始")
    print(f"   DATABASE_URL: {os.environ.get('DATABASE_URL', '(未設定)')[:50]}...")
    init_database()
    print("🎉 データベース初期化完了")

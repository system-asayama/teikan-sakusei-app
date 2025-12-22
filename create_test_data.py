#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
テストデータ作成スクリプト
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.utils.db import get_db, _sql, _is_pg
from werkzeug.security import generate_password_hash

def create_test_data():
    """テストデータを作成する"""
    app = create_app()
    
    with app.app_context():
        conn = get_db()
        try:
            cur = conn.cursor()
            
            # 1. システム管理者を作成
            print("システム管理者を作成中...")
            password_hash = generate_password_hash("admin12345")
            
            sql_admin = _sql(conn, '''
                INSERT INTO "T_管理者"(login_id, name, password_hash, role, tenant_id, active, is_owner, can_manage_admins)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''')
            
            if _is_pg(conn):
                sql_admin += ' RETURNING id'
                cur.execute(sql_admin, ('admin', 'テスト管理者', password_hash, 'system_admin', None, 1, 1, 1))
                admin_id = cur.fetchone()[0]
            else:
                cur.execute(sql_admin, ('admin', 'テスト管理者', password_hash, 'system_admin', None, 1, 1, 1))
                conn.commit()
                admin_id = cur.lastrowid
            
            print(f"✓ システム管理者作成完了 (ID: {admin_id})")
            
            # 2. テナントを作成
            print("テナントを作成中...")
            sql_tenant = _sql(conn, '''
                INSERT INTO "T_テナント"(名称, slug, 有効)
                VALUES (%s, %s, %s)
            ''')
            
            if _is_pg(conn):
                sql_tenant += ' RETURNING id'
                cur.execute(sql_tenant, ('サンプル株式会社', 'sample', 1))
                tenant_id = cur.fetchone()[0]
            else:
                cur.execute(sql_tenant, ('サンプル株式会社', 'sample', 1))
                conn.commit()
                tenant_id = cur.lastrowid
            
            print(f"✓ テナント作成完了 (ID: {tenant_id})")
            
            # 3. 定款を作成
            print("定款を作成中...")
            sql_teikan = _sql(conn, '''
                INSERT INTO "T_定款"(
                    tenant_id, created_by, 会社名, 会社名_英語,
                    本店所在地_都道府県, 本店所在地_市区町村, 本店所在地_番地, 本店所在地_建物名,
                    事業年度_決算月, 発行可能株式総数, 設立時発行株式数, 一株の金額, 資本金,
                    譲渡制限, 承認機関, 取締役の人数, 取締役会設置, 監査役設置, 会計参与設置, 公告方法,
                    ステータス
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''')
            
            if _is_pg(conn):
                sql_teikan += ' RETURNING id'
                cur.execute(sql_teikan, (
                    tenant_id, admin_id, '株式会社サンプル', 'Sample Corporation',
                    '東京都', '渋谷区', '渋谷1-1-1', 'サンプルビル5階',
                    3, 10000, 1000, 10000, 10000000,
                    1, '株主総会', 1, 0, 0, 0, '官報',
                    'draft'
                ))
                teikan_id = cur.fetchone()[0]
            else:
                cur.execute(sql_teikan, (
                    tenant_id, admin_id, '株式会社サンプル', 'Sample Corporation',
                    '東京都', '渋谷区', '渋谷1-1-1', 'サンプルビル5階',
                    3, 10000, 1000, 10000, 10000000,
                    1, '株主総会', 1, 0, 0, 0, '官報',
                    'draft'
                ))
                conn.commit()
                teikan_id = cur.lastrowid
            
            print(f"✓ 定款作成完了 (ID: {teikan_id})")
            
            # 4. 事業目的を作成
            print("事業目的を作成中...")
            事業目的リスト = [
                'ソフトウェアの開発、販売及び保守',
                'インターネットを利用した各種情報提供サービス',
                'Webサイトの企画、制作、運営及び管理'
            ]
            
            for idx, 目的 in enumerate(事業目的リスト, start=1):
                sql_mok = _sql(conn, 'INSERT INTO "T_事業目的"(定款_id, 順序, 目的) VALUES (%s, %s, %s)')
                cur.execute(sql_mok, (teikan_id, idx, 目的))
            
            if not _is_pg(conn):
                conn.commit()
            
            print(f"✓ 事業目的作成完了 ({len(事業目的リスト)}件)")
            
            # 5. 発起人を作成
            print("発起人を作成中...")
            発起人リスト = [
                {'氏名': '山田太郎', '住所': '東京都渋谷区渋谷1-1-1', '引受株式数': 1000, '出資金額': 10000000}
            ]
            
            for 発起人 in 発起人リスト:
                sql_hok = _sql(conn, 'INSERT INTO "T_発起人"(定款_id, 氏名, 住所, 引受株式数, 出資金額) VALUES (%s, %s, %s, %s, %s)')
                cur.execute(sql_hok, (teikan_id, 発起人['氏名'], 発起人['住所'], 発起人['引受株式数'], 発起人['出資金額']))
            
            if not _is_pg(conn):
                conn.commit()
            
            print(f"✓ 発起人作成完了 ({len(発起人リスト)}名)")
            
            print("\n✅ テストデータ作成完了!")
            print(f"\nログイン情報:")
            print(f"  ログインID: admin")
            print(f"  パスワード: admin12345")
            
        finally:
            try:
                conn.close()
            except:
                pass

if __name__ == '__main__':
    create_test_data()

# -*- coding: utf-8 -*-
"""
オーナー管理関連ヘルパー
"""

from .db import get_db_connection, _sql


def ensure_tenant_owner(tenant_id):
    """
    テナント内にテナント管理者が一人しかいない場合、自動的にオーナーに設定
    テナント管理者が複数いる場合は何もしない
    """
    if not tenant_id:
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # テナント内のテナント管理者数を確認
        cur.execute(_sql(conn, '''
            SELECT COUNT(*) FROM "T_管理者"
            WHERE tenant_id = %s AND role = 'tenant_admin'
        '''), (tenant_id,))
        count = cur.fetchone()[0]
        
        if count == 1:
            # 一人しかいない場合、その人をオーナーに設定
            cur.execute(_sql(conn, '''
                UPDATE "T_管理者"
                SET is_owner = 1, can_manage_admins = 1
                WHERE tenant_id = %s AND role = 'tenant_admin'
            '''), (tenant_id,))
            conn.commit()
    finally:
        conn.close()


def ensure_store_owner(tenant_id):
    """
    各店舗内に店舗管理者が一人しかいない場合、自動的にオーナーに設定
    """
    if not tenant_id:
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # テナント内の全店舗を取得
        cur.execute(_sql(conn, '''
            SELECT id FROM "T_店舗"
            WHERE tenant_id = %s
        '''), (tenant_id,))
        stores = cur.fetchall()
        
        for store in stores:
            store_id = store[0]
            
            # 各店舗の管理者数を確認
            cur.execute(_sql(conn, '''
                SELECT COUNT(DISTINCT a.id)
                FROM "T_管理者" a
                JOIN "T_管理者_店舗" as_ ON a.id = as_.admin_id
                WHERE as_.store_id = %s AND a.role = 'admin'
            '''), (store_id,))
            count = cur.fetchone()[0]
            
            if count == 1:
                # 一人しかいない場合、その人をオーナーに設定
                cur.execute(_sql(conn, '''
                    UPDATE "T_管理者"
                    SET is_owner = 1, can_manage_admins = 1
                    WHERE id IN (
                        SELECT a.id
                        FROM "T_管理者" a
                        JOIN "T_管理者_店舗" as_ ON a.id = as_.admin_id
                        WHERE as_.store_id = %s AND a.role = 'admin'
                    )
                '''), (store_id,))
        
        conn.commit()
    finally:
        conn.close()

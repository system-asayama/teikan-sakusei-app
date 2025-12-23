# -*- coding: utf-8 -*-
"""
セキュリティ関連ヘルパー
"""

import secrets
from typing import Optional
from flask import session
from .db import get_db, _sql


def login_user(user_id: int, name: str, role: str, tenant_id: Optional[int]):
    """ユーザーをセッションにログインさせる"""
    session.clear()
    session["user_id"] = user_id
    session["user_name"] = name
    session["role"] = role
    session["tenant_id"] = tenant_id  # system_admin は None 可
    
    # is_ownerをセッションに保存
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(_sql(conn, 'SELECT COALESCE(is_owner, 0) FROM "T_管理者" WHERE id = %s'), (user_id,))
        row = cur.fetchone()
        session["is_owner"] = (row[0] == 1) if row and row[0] is not None else False
    finally:
        try:
            conn.close()
        except:
            pass


def admin_exists() -> bool:
    """管理者が1人でも居れば True"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, 'SELECT COUNT(*) FROM "T_管理者"')
        cur.execute(sql)
        row = cur.fetchone()
        cnt = row[0] if row else 0
        return cnt > 0
    finally:
        try:
            conn.close()
        except:
            pass


def _ensure_csrf_token() -> str:
    """CSRF トークンをセッションに確保して返す"""
    tok = session.get("csrf_token")
    if not tok:
        tok = secrets.token_hex(16)
        session["csrf_token"] = tok
    return tok


def get_csrf():
    """テンプレート用のCSRFトークン取得関数"""
    return _ensure_csrf_token()


def is_owner() -> bool:
    """
    現在ログイン中のユーザーがオーナーシステム管理者かどうかを確認
    """
    user_id = session.get('user_id')
    role = session.get('role')
    
    if not user_id or role != 'system_admin':
        return False
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(_sql(conn, 'SELECT is_owner FROM "T_管理者" WHERE id = %s'), (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        return row[0] == 1
    return False


def can_manage_system_admins() -> bool:
    """
    現在ログイン中のユーザーがシステム管理者管理権限を持っているかを確認
    オーナーは常にTrue、それ以外はcan_manage_adminsフラグで判定
    """
    user_id = session.get('user_id')
    role = session.get('role')
    
    if not user_id or role != 'system_admin':
        return False
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(_sql(conn, 'SELECT is_owner, can_manage_admins FROM "T_管理者" WHERE id = %s'), (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        # オーナーは常にTrue、それ以外はcan_manage_adminsで判定
        return row[0] == 1 or row[1] == 1
    return False


from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    """パスワードをハッシュ化する"""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """パスワードを検証する"""
    return check_password_hash(password_hash, password)

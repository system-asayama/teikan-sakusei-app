# -*- coding: utf-8 -*-
"""
認証関連ルート
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils import get_db, _sql, login_user, admin_exists, ROLES

bp = Blueprint('auth', __name__)


@bp.route('/')
def index():
    """トップページ - ロール別リダイレクト"""
    role = session.get("role")
    if role == ROLES["SYSTEM_ADMIN"]:
        return redirect(url_for('auth.system_admin_dashboard'))
    if role == ROLES["ADMIN"]:
        return redirect(url_for('auth.admin_dashboard'))
    return redirect(url_for('auth.select_login'))


@bp.route('/select_login')
def select_login():
    """ログイン選択画面"""
    # 管理者が未作成なら、初回セットアップへ誘導
    if not admin_exists():
        return redirect(url_for('auth.first_admin_setup'))
    return render_template('login_choice.html')


@bp.route('/first_admin_setup', methods=['GET', 'POST'])
def first_admin_setup():
    """初回セットアップ（最初の sysadmin 作成）"""
    # すでに管理者がいれば、このページは出さない
    if admin_exists():
        return redirect(url_for('auth.select_login'))

    error = None
    if request.method == 'POST':
        # --- CSRF チェック ---
        form_token = request.form.get('csrf_token', '')
        if not form_token or form_token != session.get('csrf_token'):
            error = "セッションが無効です。もう一度お試しください。"
        else:
            name = (request.form.get('name') or '').strip()
            login_id = (request.form.get('login_id') or '').strip()
            password = request.form.get('password') or ''
            confirm = request.form.get('confirm') or ''

            # --- 入力バリデーション ---
            if not name or not login_id or not password or not confirm:
                error = "すべての項目を入力してください。"
            elif len(password) < 8:
                error = "パスワードは8文字以上にしてください。"
            elif password != confirm:
                error = "パスワード（確認）が一致しません。"

            if not error:
                # 既存重複確認 & 作成
                conn = get_db()
                try:
                    cur = conn.cursor()
                    # 同じ login_id が無いか
                    sql_chk = _sql(conn, 'SELECT 1 FROM "T_管理者" WHERE login_id=%s')
                    cur.execute(sql_chk, (login_id,))
                    exists = cur.fetchone()
                    if exists:
                        error = "このログインIDはすでに使用されています。"
                    else:
                        ph = generate_password_hash(password)
                        sql_ins = _sql(conn, '''
                            INSERT INTO "T_管理者"(login_id, name, password_hash, role, tenant_id, is_owner, can_manage_admins)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''')
                        cur.execute(sql_ins, (login_id, name, ph, ROLES["SYSTEM_ADMIN"], None, 1, 1))
                        from ..utils.db import _is_pg
                        if not _is_pg(conn):
                            conn.commit()
                        flash("システム管理者を作成しました。ログインできます。", "success")
                        return redirect(url_for('auth.select_login'))
                finally:
                    try:
                        conn.close()
                    except:
                        pass

    return render_template('first_setup.html', error=error)


@bp.route('/system_admin_login', methods=['GET','POST'])
def system_admin_login():
    """システム管理者ログイン"""
    error = None
    if request.method == 'POST':
        login_id = request.form.get('login_id','').strip()
        password = request.form.get('password','')
        conn = get_db()
        try:
            cur = conn.cursor()
            sql = _sql(conn, 'SELECT id, name, password_hash, tenant_id FROM "T_管理者" WHERE login_id=%s AND role=%s')
            cur.execute(sql, (login_id, ROLES["SYSTEM_ADMIN"]))
            row = cur.fetchone()
            if row and check_password_hash(row[2], password):
                user_id, name, tenant_id = row[0], row[1], row[3]
                login_user(user_id, name, ROLES["SYSTEM_ADMIN"], tenant_id)
                return redirect(url_for('auth.system_admin_dashboard'))
            error = "ログインIDまたはパスワードが違います"
        finally:
            try: conn.close()
            except: pass
    return render_template('sysadmin_login.html', error=error)


@bp.route('/admin_login', methods=['GET','POST'])
def admin_login():
    """一般管理者ログイン"""
    error = None
    if request.method == 'POST':
        login_id = request.form.get('login_id','').strip()
        password = request.form.get('password','')
        conn = get_db()
        try:
            cur = conn.cursor()
            sql = _sql(conn, 'SELECT id, name, password_hash, tenant_id FROM "T_管理者" WHERE login_id=%s AND role=%s')
            cur.execute(sql, (login_id, ROLES["ADMIN"]))
            row = cur.fetchone()
            if row and check_password_hash(row[2], password):
                user_id, name, tenant_id = row[0], row[1], row[3]
                login_user(user_id, name, ROLES["ADMIN"], tenant_id)
                return redirect(url_for('auth.admin_dashboard'))
            else:
                error = "ログインIDまたはパスワードが違います"
        finally:
            try: conn.close()
            except: pass
    return render_template('admin_login.html', error=error)


@bp.route('/logout')
def logout():
    """ログアウト"""
    session.clear()
    return redirect(url_for('auth.select_login'))


# ========================================
# 仮のダッシュボード（後で実装）
# ========================================

@bp.route('/system_admin/dashboard')
def system_admin_dashboard():
    """システム管理者ダッシュボード"""
    role = session.get("role")
    if role != ROLES["SYSTEM_ADMIN"]:
        return redirect(url_for('auth.select_login'))
    return f"<h1>システム管理者ダッシュボード</h1><p>ようこそ、{session.get('user_name')}さん</p><a href='/logout'>ログアウト</a>"


@bp.route('/admin/dashboard')
def admin_dashboard():
    """一般管理者ダッシュボード"""
    role = session.get("role")
    if role != ROLES["ADMIN"]:
        return redirect(url_for('auth.select_login'))
    return f"<h1>管理者ダッシュボード</h1><p>ようこそ、{session.get('user_name')}さん</p><a href='/logout'>ログアウト</a>"

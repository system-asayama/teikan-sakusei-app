# -*- coding: utf-8 -*-
"""
管理者用Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.utils.db import get_db, _sql
from app.utils.decorators import require_roles, ROLES
from app.utils.security import hash_password, verify_password

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/mypage', methods=['GET', 'POST'])
@require_roles(ROLES['ADMIN'])
def mypage():
    """管理者マイページ"""
    conn = get_db()
    cur = conn.cursor()
    
    user_id = session.get('user_id')
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            # プロフィール更新
            login_id = request.form.get('login_id', '').strip()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            
            if not login_id or not name:
                flash('ログインIDと氏名は必須です', 'error')
                return redirect(url_for('admin.mypage'))
            
            # ログインID重複チェック
            cur.execute(_sql(conn, '''
                SELECT id FROM "T_管理者"
                WHERE login_id = %s AND id != %s
            '''), (login_id, user_id))
            if cur.fetchone():
                flash('このログインIDは既に使用されています', 'error')
                return redirect(url_for('admin.mypage'))
            
            # 更新
            cur.execute(_sql(conn, '''
                UPDATE "T_管理者"
                SET login_id = %s, name = %s, email = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            '''), (login_id, name, email, user_id))
            if not conn.__class__.__module__.startswith("psycopg2"):
                conn.commit()
            
            # セッション更新
            session['login_id'] = login_id
            session['user_name'] = name
            
            flash('プロフィールを更新しました', 'success')
            return redirect(url_for('admin.mypage'))
        
        elif action == 'change_password':
            # パスワード変更
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not current_password or not new_password or not confirm_password:
                flash('すべてのパスワードフィールドを入力してください', 'error')
                return redirect(url_for('admin.mypage'))
            
            # 現在のパスワード確認
            cur.execute(_sql(conn, '''
                SELECT password_hash FROM "T_管理者" WHERE id = %s
            '''), (user_id,))
            row = cur.fetchone()
            if not row:
                flash('ユーザーが見つかりません', 'error')
                return redirect(url_for('admin.mypage'))
            
            if not verify_password(current_password, row[0]):
                flash('現在のパスワードが正しくありません', 'error')
                return redirect(url_for('admin.mypage'))
            
            # 新しいパスワードの確認
            if new_password != confirm_password:
                flash('新しいパスワードと確認用パスワードが一致しません', 'error')
                return redirect(url_for('admin.mypage'))
            
            if len(new_password) < 8:
                flash('パスワードは8文字以上にしてください', 'error')
                return redirect(url_for('admin.mypage'))
            
            # パスワード更新
            new_hash = hash_password(new_password)
            cur.execute(_sql(conn, '''
                UPDATE "T_管理者"
                SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            '''), (new_hash, user_id))
            if not conn.__class__.__module__.startswith("psycopg2"):
                conn.commit()
            
            flash('パスワードを変更しました', 'success')
            return redirect(url_for('admin.mypage'))
    
    # ユーザー情報取得
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, email, role, tenant_id, active, is_owner, can_manage_admins, created_at, updated_at
        FROM "T_管理者"
        WHERE id = %s
    '''), (user_id,))
    user = cur.fetchone()
    
    if not user:
        flash('ユーザー情報が見つかりません', 'error')
        return redirect(url_for('auth.logout'))
    
    # テナント情報取得
    tenant = None
    if user[5]:  # tenant_id
        cur.execute(_sql(conn, '''
            SELECT id, 名称, slug FROM "T_テナント" WHERE id = %s
        '''), (user[5],))
        tenant = cur.fetchone()
    
    return render_template('admin_mypage.html',
                         user=user,
                         tenant=tenant)


@bp.route('/dashboard')
@require_roles(ROLES['ADMIN'])
def dashboard():
    """管理者ダッシュボード"""
    return render_template('admin_dashboard.html')

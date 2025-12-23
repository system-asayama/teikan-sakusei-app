# -*- coding: utf-8 -*-
"""
システム管理者用Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from ..utils import get_db, _sql, ROLES, require_roles

bp = Blueprint('system_admin', __name__, url_prefix='/system_admin')


@bp.route('/mypage', methods=['GET', 'POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def mypage():
    """システム管理者マイページ"""
    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute(_sql(conn, '''
            SELECT id, login_id, name, email, is_owner, can_manage_admins, created_at, updated_at, role
            FROM "T_管理者"
            WHERE id = %s AND role = %s
        '''), (user_id, ROLES["SYSTEM_ADMIN"]))
        
        row = cur.fetchone()
        
        if not row:
            flash('ユーザー情報が見つかりません', 'error')
            return redirect(url_for('auth.select_login'))
        
        user = {
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'email': row[3] if row[3] else '',
            'is_owner': row[4],
            'can_manage_admins': row[5],
            'created_at': row[6],
            'updated_at': row[7],
            'role': row[8]
        }
        
        # POSTリクエスト（プロフィール編集またはパスワード変更）
        if request.method == 'POST':
            action = request.form.get('action', '')
            
            if action == 'update_profile':
                # プロフィール編集
                login_id = request.form.get('login_id', '').strip()
                name = request.form.get('name', '').strip()
                email = request.form.get('email', '').strip()
                
                if not login_id or not name:
                    flash('ログインIDと氏名は必須です', 'error')
                    return render_template('sys_mypage.html', user=user)
                
                # ログインID重複チェック（自分以外）
                cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s AND id != %s'), (login_id, user_id))
                if cur.fetchone():
                    flash('このログインIDは既に使用されています', 'error')
                    return render_template('sys_mypage.html', user=user)
                
                # プロフィール更新
                cur.execute(_sql(conn, '''
                    UPDATE "T_管理者"
                    SET login_id = %s, name = %s, email = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                '''), (login_id, name, email, user_id))
                conn.commit()
                
                flash('プロフィール情報を更新しました', 'success')
                return redirect(url_for('system_admin.mypage'))
            
            elif action == 'change_password':
                # パスワード変更
                current_password = request.form.get('current_password', '').strip()
                new_password = request.form.get('new_password', '').strip()
                new_password_confirm = request.form.get('new_password_confirm', '').strip()
            
                # パスワード一致チェック
                if new_password != new_password_confirm:
                    flash('新しいパスワードが一致しません', 'error')
                    return render_template('sys_mypage.html', user=user)
                
                # パスワード長チェック
                if len(new_password) < 8:
                    flash('パスワードは8文字以上で設定してください', 'error')
                    return render_template('sys_mypage.html', user=user)
            
                # 現在のパスワードを確認
                cur.execute(_sql(conn, 'SELECT password_hash FROM "T_管理者" WHERE id = %s'), (user_id,))
                row = cur.fetchone()
                if not row or not check_password_hash(row[0], current_password):
                    flash('現在のパスワードが正しくありません', 'error')
                    return render_template('sys_mypage.html', user=user)
                
                # パスワード更新
                new_password_hash = generate_password_hash(new_password)
                cur.execute(_sql(conn, '''
                    UPDATE "T_管理者"
                    SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                '''), (new_password_hash, user_id))
                conn.commit()
                
                flash('パスワードを変更しました', 'success')
                return redirect(url_for('system_admin.mypage'))
        
        return render_template('sys_mypage.html', user=user)
    
    finally:
        try:
            conn.close()
        except:
            pass


@bp.route('/dashboard')
@require_roles(ROLES["SYSTEM_ADMIN"])
def dashboard():
    """システム管理者ダッシュボード"""
    return render_template('system_admin_dashboard.html')

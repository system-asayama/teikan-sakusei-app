# -*- coding: utf-8 -*-
"""
テナント管理者用Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils import get_db, _sql, ROLES, require_roles

bp = Blueprint('tenant_admin', __name__, url_prefix='/tenant_admin')


@bp.route('/mypage', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"])
def mypage():
    """テナント管理者マイページ"""
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
                return redirect(url_for('tenant_admin.mypage'))
            
            # ログインID重複チェック
            cur.execute(_sql(conn, '''
                SELECT id FROM "T_管理者"
                WHERE login_id = %s AND id != %s
            '''), (login_id, user_id))
            if cur.fetchone():
                flash('このログインIDは既に使用されています', 'error')
                return redirect(url_for('tenant_admin.mypage'))
            
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
            return redirect(url_for('tenant_admin.mypage'))
        
        elif action == 'change_password':
            # パスワード変更
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not current_password or not new_password or not confirm_password:
                flash('すべてのパスワードフィールドを入力してください', 'error')
                return redirect(url_for('tenant_admin.mypage'))
            
            # 現在のパスワード確認
            cur.execute(_sql(conn, '''
                SELECT password_hash FROM "T_管理者" WHERE id = %s
            '''), (user_id,))
            row = cur.fetchone()
            if not row:
                flash('ユーザーが見つかりません', 'error')
                return redirect(url_for('tenant_admin.mypage'))
            
            if not check_password_hash(row[0], current_password):
                flash('現在のパスワードが正しくありません', 'error')
                return redirect(url_for('tenant_admin.mypage'))
            
            # 新しいパスワードの確認
            if new_password != confirm_password:
                flash('新しいパスワードと確認用パスワードが一致しません', 'error')
                return redirect(url_for('tenant_admin.mypage'))
            
            if len(new_password) < 8:
                flash('パスワードは8文字以上にしてください', 'error')
                return redirect(url_for('tenant_admin.mypage'))
            
            # パスワード更新
            new_hash = generate_password_hash(new_password)
            cur.execute(_sql(conn, '''
                UPDATE "T_管理者"
                SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            '''), (new_hash, user_id))
            if not conn.__class__.__module__.startswith("psycopg2"):
                conn.commit()
            
            flash('パスワードを変更しました', 'success')
            return redirect(url_for('tenant_admin.mypage'))
    
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
    
    return render_template('tenant_admin_mypage.html',
                         user=user,
                         tenant=tenant)


@bp.route('/dashboard')
@require_roles(ROLES["TENANT_ADMIN"])
def dashboard():
    """テナント管理者ダッシュボード"""
    return render_template('tenant_admin_dashboard.html')


# ========================================
# 管理者管理（自テナント内）
# ========================================

@bp.route('/admins')
@require_roles(ROLES["TENANT_ADMIN"])
def admins():
    """管理者一覧（自テナント内）"""
    user_id = session.get('user_id')
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, '''
            SELECT id, login_id, name, email, role, active, is_owner, can_manage_admins, created_at
            FROM "T_管理者"
            WHERE tenant_id = %s AND role IN (%s, %s)
            ORDER BY id
        ''')
        cur.execute(sql, (tenant_id, ROLES["ADMIN"], ROLES["EMPLOYEE"]))
        rows = cur.fetchall()
        
        role_names = {ROLES["ADMIN"]: "管理者", ROLES["EMPLOYEE"]: "従業員"}
        admin_list = []
        for r in rows:
            admin_list.append({
                'id': r[0],
                'login_id': r[1],
                'name': r[2],
                'email': r[3] if r[3] else '',
                'role': r[4],
                'role_name': role_names.get(r[4], '不明'),
                'active': r[5],
                'is_owner': r[6],
                'can_manage_admins': r[7],
                'created_at': r[8]
            })
        return render_template('tenant_admin/admins.html', admins=admin_list)
    finally:
        try: conn.close()
        except: pass


@bp.route('/admin/<int:aid>')
@require_roles(ROLES["TENANT_ADMIN"])
def admin_detail(aid):
    """管理者詳細（自テナント内）"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, '''
            SELECT id, login_id, name, email, role, tenant_id, active, is_owner, can_manage_admins, created_at, updated_at
            FROM "T_管理者"
            WHERE id=%s AND tenant_id=%s
        ''')
        cur.execute(sql, (aid, tenant_id))
        row = cur.fetchone()
        
        if not row:
            flash('管理者が見つかりません', 'error')
            return redirect(url_for('tenant_admin.admins'))
        
        role_names = {ROLES["ADMIN"]: "管理者", ROLES["EMPLOYEE"]: "従業員"}
        admin = {
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'email': row[3] if row[3] else '',
            'role': row[4],
            'role_name': role_names.get(row[4], '不明'),
            'tenant_id': row[5],
            'active': row[6],
            'is_owner': row[7],
            'can_manage_admins': row[8],
            'created_at': row[9],
            'updated_at': row[10]
        }
        return render_template('tenant_admin/admin_detail.html', admin=admin)
    finally:
        try: conn.close()
        except: pass


@bp.route('/admin/new', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"])
def admin_new():
    """管理者新規作成（自テナント内）"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        role = int(request.form.get('role', ROLES["ADMIN"]))
        active = request.form.get('active') == 'on'
        
        # バリデーション
        if not login_id or not name or not password:
            flash('ログインID、氏名、パスワードは必須です', 'error')
            return render_template('tenant_admin/admin_new.html', roles=ROLES)
        
        if password != password_confirm:
            flash('パスワードが一致しません', 'error')
            return render_template('tenant_admin/admin_new.html', roles=ROLES)
        
        if len(password) < 8:
            flash('パスワードは8文字以上で設定してください', 'error')
            return render_template('tenant_admin/admin_new.html', roles=ROLES)
        
        conn = get_db()
        try:
            cur = conn.cursor()
            
            # ログインID重複チェック
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id=%s'), (login_id,))
            if cur.fetchone():
                flash('このログインIDは既に使用されています', 'error')
                return render_template('tenant_admin/admin_new.html', roles=ROLES)
            
            # 管理者作成
            password_hash = generate_password_hash(password)
            sql = _sql(conn, '''
                INSERT INTO "T_管理者" (login_id, name, email, password_hash, role, tenant_id, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''')
            cur.execute(sql, (login_id, name, email, password_hash, role, tenant_id, 1 if active else 0))
            conn.commit()
            flash('管理者を作成しました', 'success')
            return redirect(url_for('tenant_admin.admins'))
        finally:
            try: conn.close()
            except: pass
    
    return render_template('tenant_admin/admin_new.html', roles=ROLES)


@bp.route('/admin/<int:aid>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"])
def admin_edit(aid):
    """管理者編集（自テナント内）"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if request.method == 'POST':
            login_id = request.form.get('login_id', '').strip()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            role = int(request.form.get('role', ROLES["ADMIN"]))
            active = request.form.get('active') == 'on'
            
            if not login_id or not name:
                flash('ログインIDと氏名は必須です', 'error')
            else:
                # ログインID重複チェック（自分以外）
                cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id=%s AND id!=%s'), (login_id, aid))
                if cur.fetchone():
                    flash('このログインIDは既に使用されています', 'error')
                else:
                    sql = _sql(conn, '''
                        UPDATE "T_管理者"
                        SET login_id=%s, name=%s, email=%s, role=%s, active=%s, updated_at=CURRENT_TIMESTAMP
                        WHERE id=%s AND tenant_id=%s
                    ''')
                    cur.execute(sql, (login_id, name, email, role, 1 if active else 0, aid, tenant_id))
                    conn.commit()
                    flash('管理者情報を更新しました', 'success')
                    return redirect(url_for('tenant_admin.admin_detail', aid=aid))
        
        # 管理者情報を取得
        sql = _sql(conn, 'SELECT id, login_id, name, email, role, active FROM "T_管理者" WHERE id=%s AND tenant_id=%s')
        cur.execute(sql, (aid, tenant_id))
        row = cur.fetchone()
        
        if not row:
            flash('管理者が見つかりません', 'error')
            return redirect(url_for('tenant_admin.admins'))
        
        admin = {
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'email': row[3] if row[3] else '',
            'role': row[4],
            'active': row[5]
        }
        return render_template('tenant_admin/admin_edit.html', admin=admin, roles=ROLES)
    finally:
        try: conn.close()
        except: pass


@bp.route('/admin/<int:aid>/delete', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"])
def admin_delete(aid):
    """管理者削除（自テナント内）"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, 'DELETE FROM "T_管理者" WHERE id=%s AND tenant_id=%s')
        cur.execute(sql, (aid, tenant_id))
        conn.commit()
        flash('管理者を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'error')
    finally:
        try: conn.close()
        except: pass
    return redirect(url_for('tenant_admin.admins'))

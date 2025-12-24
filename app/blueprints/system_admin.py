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
                    # テナントリストを取得
                    cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY id'))
                    tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
                    return render_template('system_admin_mypage.html', user=user, tenant_list=tenant_list, store_list=[])
                
                # ログインID重複チェック（自分以外）
                cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s AND id != %s'), (login_id, user_id))
                if cur.fetchone():
                    flash('このログインIDは既に使用されています', 'error')
                    # テナントリストを取得
                    cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY id'))
                    tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
                    return render_template('system_admin_mypage.html', user=user, tenant_list=tenant_list, store_list=[])
                
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
                    # テナントリストを取得
                    cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY id'))
                    tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
                    return render_template('system_admin_mypage.html', user=user, tenant_list=tenant_list, store_list=[])
                
                # パスワード長チェック
                if len(new_password) < 8:
                    flash('パスワードは8文字以上で設定してください', 'error')
                    # テナントリストを取得
                    cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY id'))
                    tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
                    return render_template('system_admin_mypage.html', user=user, tenant_list=tenant_list, store_list=[])
            
                # 現在のパスワードを確認
                cur.execute(_sql(conn, 'SELECT password_hash FROM "T_管理者" WHERE id = %s'), (user_id,))
                row = cur.fetchone()
                if not row or not check_password_hash(row[0], current_password):
                    flash('現在のパスワードが正しくありません', 'error')
                    # テナントリストを取得
                    cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY id'))
                    tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
                    return render_template('system_admin_mypage.html', user=user, tenant_list=tenant_list, store_list=[])
                
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
        
        # テナントリストを取得
        cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY id'))
        tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
        
        return render_template('system_admin_mypage.html', user=user, tenant_list=tenant_list, store_list=[])
    
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


# ========================================
# テナント管理
# ========================================

@bp.route('/tenants')
@require_roles(ROLES["SYSTEM_ADMIN"])
def tenants():
    """テナント一覧"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, 'SELECT id, "名称", slug, "有効", created_at FROM "T_テナント" ORDER BY id')
        cur.execute(sql)
        rows = cur.fetchall()
        tenant_list = []
        for r in rows:
            tenant_list.append({
                'id': r[0],
                '名称': r[1],
                'slug': r[2],
                '有効': r[3],
                'created_at': r[4]
            })
        return render_template('system_admin/tenants.html', tenants=tenant_list)
    finally:
        try: conn.close()
        except: pass


@bp.route('/tenant/<int:tid>')
@require_roles(ROLES["SYSTEM_ADMIN"])
def tenant_detail(tid):
    """テナント詳細"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, 'SELECT id, "名称", slug, "有効", created_at, updated_at FROM "T_テナント" WHERE id=%s')
        cur.execute(sql, (tid,))
        row = cur.fetchone()
        if not row:
            flash('テナントが見つかりません', 'error')
            return redirect(url_for('system_admin.tenants'))
        tenant = {
            'id': row[0],
            '名称': row[1],
            'slug': row[2],
            '有効': row[3],
            'created_at': row[4],
            'updated_at': row[5]
        }
        return render_template('system_admin/tenant_detail.html', tenant=tenant)
    finally:
        try: conn.close()
        except: pass


@bp.route('/tenant/new', methods=['GET', 'POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def tenant_new():
    """テナント新規作成"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip()
        active = request.form.get('active') == 'on'
        
        if not name or not slug:
            flash('名称とslugは必須です', 'error')
            return render_template('system_admin/tenant_new.html')
        
        conn = get_db()
        try:
            cur = conn.cursor()
            sql = _sql(conn, 'INSERT INTO "T_テナント" ("名称", slug, "有効") VALUES (%s, %s, %s)')
            cur.execute(sql, (name, slug, 1 if active else 0))
            conn.commit()
            flash('テナントを作成しました', 'success')
            return redirect(url_for('system_admin.tenants'))
        except Exception as e:
            flash(f'エラーが発生しました: {str(e)}', 'error')
            return render_template('system_admin/tenant_new.html')
        finally:
            try: conn.close()
            except: pass
    
    return render_template('system_admin/tenant_new.html')


@bp.route('/tenant/<int:tid>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def tenant_edit(tid):
    """テナント編集"""
    conn = get_db()
    try:
        cur = conn.cursor()
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip()
            active = request.form.get('active') == 'on'
            
            if not name or not slug:
                flash('名称とslugは必須です', 'error')
            else:
                sql = _sql(conn, 'UPDATE "T_テナント" SET "名称"=%s, slug=%s, "有効"=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s')
                cur.execute(sql, (name, slug, 1 if active else 0, tid))
                conn.commit()
                flash('テナント情報を更新しました', 'success')
                return redirect(url_for('system_admin.tenant_detail', tid=tid))
        
        sql = _sql(conn, 'SELECT id, "名称", slug, "有効" FROM "T_テナント" WHERE id=%s')
        cur.execute(sql, (tid,))
        row = cur.fetchone()
        if not row:
            flash('テナントが見つかりません', 'error')
            return redirect(url_for('system_admin.tenants'))
        
        tenant = {
            'id': row[0],
            '名称': row[1],
            'slug': row[2],
            '有効': row[3]
        }
        return render_template('system_admin/tenant_edit.html', tenant=tenant)
    finally:
        try: conn.close()
        except: pass


@bp.route('/tenant/<int:tid>/delete', methods=['POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def tenant_delete(tid):
    """テナント削除"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, 'DELETE FROM "T_テナント" WHERE id=%s')
        cur.execute(sql, (tid,))
        conn.commit()
        flash('テナントを削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'error')
    finally:
        try: conn.close()
        except: pass
    return redirect(url_for('system_admin.tenants'))


# ========================================
# ユーザー管理
# ========================================

@bp.route('/users')
@require_roles(ROLES["SYSTEM_ADMIN"])
def users():
    """ユーザー一覧"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, '''
            SELECT u.id, u.login_id, u.name, u.email, u.role, u.tenant_id, t."名称" as tenant_name, u.active, u.created_at
            FROM "T_管理者" u
            LEFT JOIN "T_テナント" t ON u.tenant_id = t.id
            ORDER BY u.id
        ''')
        cur.execute(sql)
        rows = cur.fetchall()
        user_list = []
        role_names = {v: k for k, v in ROLES.items()}
        for r in rows:
            user_list.append({
                'id': r[0],
                'login_id': r[1],
                'name': r[2],
                'email': r[3] if r[3] else '',
                'role': r[4],
                'role_name': role_names.get(r[4], '不明'),
                'tenant_id': r[5],
                'tenant_name': r[6] if r[6] else 'なし',
                'active': r[7],
                'created_at': r[8]
            })
        return render_template('system_admin/users.html', users=user_list)
    finally:
        try: conn.close()
        except: pass


@bp.route('/user/<int:uid>')
@require_roles(ROLES["SYSTEM_ADMIN"])
def user_detail(uid):
    """ユーザー詳細"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, '''
            SELECT u.id, u.login_id, u.name, u.email, u.role, u.tenant_id, t."名称" as tenant_name, 
                   u.active, u.is_owner, u.can_manage_admins, u.created_at, u.updated_at
            FROM "T_管理者" u
            LEFT JOIN "T_テナント" t ON u.tenant_id = t.id
            WHERE u.id=%s
        ''')
        cur.execute(sql, (uid,))
        row = cur.fetchone()
        if not row:
            flash('ユーザーが見つかりません', 'error')
            return redirect(url_for('system_admin.users'))
        
        role_names = {v: k for k, v in ROLES.items()}
        user = {
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'email': row[3] if row[3] else '',
            'role': row[4],
            'role_name': role_names.get(row[4], '不明'),
            'tenant_id': row[5],
            'tenant_name': row[6] if row[6] else 'なし',
            'active': row[7],
            'is_owner': row[8],
            'can_manage_admins': row[9],
            'created_at': row[10],
            'updated_at': row[11]
        }
        return render_template('system_admin/user_detail.html', user=user)
    finally:
        try: conn.close()
        except: pass


@bp.route('/user/new', methods=['GET', 'POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def user_new():
    """ユーザー新規作成"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # テナント一覧を取得
        sql = _sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効"=1 ORDER BY id')
        cur.execute(sql)
        tenants = [{'id': r[0], '名称': r[1]} for r in cur.fetchall()]
        
        if request.method == 'POST':
            login_id = request.form.get('login_id', '').strip()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            password_confirm = request.form.get('password_confirm', '').strip()
            role = int(request.form.get('role', 0))
            tenant_id = request.form.get('tenant_id', '')
            tenant_id = int(tenant_id) if tenant_id else None
            active = request.form.get('active') == 'on'
            
            # バリデーション
            if not login_id or not name or not password:
                flash('ログインID、氏名、パスワードは必須です', 'error')
                return render_template('system_admin/user_new.html', tenants=tenants, roles=ROLES)
            
            if password != password_confirm:
                flash('パスワードが一致しません', 'error')
                return render_template('system_admin/user_new.html', tenants=tenants, roles=ROLES)
            
            if len(password) < 8:
                flash('パスワードは8文字以上で設定してください', 'error')
                return render_template('system_admin/user_new.html', tenants=tenants, roles=ROLES)
            
            # ログインID重複チェック
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id=%s'), (login_id,))
            if cur.fetchone():
                flash('このログインIDは既に使用されています', 'error')
                return render_template('system_admin/user_new.html', tenants=tenants, roles=ROLES)
            
            # ユーザー作成
            password_hash = generate_password_hash(password)
            sql = _sql(conn, '''
                INSERT INTO "T_管理者" (login_id, name, email, password_hash, role, tenant_id, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''')
            cur.execute(sql, (login_id, name, email, password_hash, role, tenant_id, 1 if active else 0))
            conn.commit()
            flash('ユーザーを作成しました', 'success')
            return redirect(url_for('system_admin.users'))
        
        return render_template('system_admin/user_new.html', tenants=tenants, roles=ROLES)
    finally:
        try: conn.close()
        except: pass


@bp.route('/user/<int:uid>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def user_edit(uid):
    """ユーザー編集"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # テナント一覧を取得
        sql = _sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効"=1 ORDER BY id')
        cur.execute(sql)
        tenants = [{'id': r[0], '名称': r[1]} for r in cur.fetchall()]
        
        if request.method == 'POST':
            login_id = request.form.get('login_id', '').strip()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            role = int(request.form.get('role', 0))
            tenant_id = request.form.get('tenant_id', '')
            tenant_id = int(tenant_id) if tenant_id else None
            active = request.form.get('active') == 'on'
            
            if not login_id or not name:
                flash('ログインIDと氏名は必須です', 'error')
            else:
                # ログインID重複チェック（自分以外）
                cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id=%s AND id!=%s'), (login_id, uid))
                if cur.fetchone():
                    flash('このログインIDは既に使用されています', 'error')
                else:
                    sql = _sql(conn, '''
                        UPDATE "T_管理者"
                        SET login_id=%s, name=%s, email=%s, role=%s, tenant_id=%s, active=%s, updated_at=CURRENT_TIMESTAMP
                        WHERE id=%s
                    ''')
                    cur.execute(sql, (login_id, name, email, role, tenant_id, 1 if active else 0, uid))
                    conn.commit()
                    flash('ユーザー情報を更新しました', 'success')
                    return redirect(url_for('system_admin.user_detail', uid=uid))
        
        # ユーザー情報を取得
        sql = _sql(conn, 'SELECT id, login_id, name, email, role, tenant_id, active FROM "T_管理者" WHERE id=%s')
        cur.execute(sql, (uid,))
        row = cur.fetchone()
        if not row:
            flash('ユーザーが見つかりません', 'error')
            return redirect(url_for('system_admin.users'))
        
        user = {
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'email': row[3] if row[3] else '',
            'role': row[4],
            'tenant_id': row[5],
            'active': row[6]
        }
        return render_template('system_admin/user_edit.html', user=user, tenants=tenants, roles=ROLES)
    finally:
        try: conn.close()
        except: pass


@bp.route('/user/<int:uid>/delete', methods=['POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def user_delete(uid):
    """ユーザー削除"""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = _sql(conn, 'DELETE FROM "T_管理者" WHERE id=%s')
        cur.execute(sql, (uid,))
        conn.commit()
        flash('ユーザーを削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'error')
    finally:
        try: conn.close()
        except: pass
    return redirect(url_for('system_admin.users'))


@bp.route('/select_tenant_from_mypage', methods=['POST'])
@require_roles(ROLES["SYSTEM_ADMIN"])
def select_tenant_from_mypage():
    """マイページからテナントを選択してテナント管理者ダッシュボードへ"""
    tenant_id = request.form.get('tenant_id')
    
    if not tenant_id:
        flash('テナントを選択してください', 'error')
        return redirect(url_for('system_admin.mypage'))
    
    # テナントが存在するか確認
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE id = %s AND "有効" = 1'), (tenant_id,))
        tenant = cur.fetchone()
        
        if not tenant:
            flash('選択したテナントが見つかりません', 'error')
            return redirect(url_for('system_admin.mypage'))
        
        # セッションにテナント情報を保存
        session['tenant_id'] = tenant[0]
        
        flash(f'テナント「{tenant[1]}」を選択しました', 'success')
        
        # テナント管理者ダッシュボードへリダイレクト
        return redirect(url_for('tenant_admin.dashboard'))
    finally:
        try:
            conn.close()
        except:
            pass

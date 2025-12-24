# -*- coding: utf-8 -*-
"""
テナント管理者ダッシュボード
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..utils import require_roles, ROLES, get_db_connection, is_tenant_owner, can_manage_tenant_admins, ensure_tenant_owner
from ..utils.db import _sql
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('tenant_admin', __name__, url_prefix='/tenant_admin')


@bp.route('/')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def dashboard():
    """テナント管理者ダッシュボード"""
    # ロールに応じたマイページURLを設定
    role = session.get('role')
    if role == 'system_admin':
        mypage_url = url_for('system_admin.mypage')
    else:
        mypage_url = url_for('tenant_admin.mypage')
    return render_template('tenant_admin_dashboard.html', tenant_id=session.get('tenant_id'), mypage_url=mypage_url)


# ========================================
# テナント情報管理
# ========================================

@bp.route('/tenant_info')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def tenant_info():
    """テナント情報表示"""
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        flash('テナントIDが取得できません', 'error')
        return redirect(url_for('tenant_admin.dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(_sql(conn, 'SELECT id, 名称, slug, created_at FROM "T_テナント" WHERE id = %s'), (tenant_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.dashboard'))
    
    tenant = {
        'id': row[0],
        '名称': row[1],
        'slug': row[2],
        'created_at': row[3]
    }
    return render_template('tenant_info.html', tenant=tenant)


@bp.route('/me/edit', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def me_edit():
    """テナント情報編集"""
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        flash('テナントIDが取得できません', 'error')
        return redirect(url_for('tenant_admin.dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        name = request.form.get('名称', '').strip()
        slug = request.form.get('slug', '').strip()
        openai_api_key = request.form.get('openai_api_key', '').strip()
        
        if not name or not slug:
            flash('名称とslugは必須です', 'error')
        else:
            cur.execute(_sql(conn, 'UPDATE "T_テナント" SET 名称 = %s, slug = %s, openai_api_key = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s'),
                       (name, slug, openai_api_key if openai_api_key else None, tenant_id))
            conn.commit()
            flash('テナント情報を更新しました', 'success')
            conn.close()
            return redirect(url_for('tenant_admin.dashboard'))
    
    cur.execute(_sql(conn, 'SELECT id, 名称, slug, openai_api_key FROM "T_テナント" WHERE id = %s'), (tenant_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        flash('テナント情報が見つかりません', 'error')
        return redirect(url_for('tenant_admin.dashboard'))
    
    tenant = {'id': row[0], '名称': row[1], 'slug': row[2], 'openai_api_key': row[3] if len(row) > 3 else None}
    return render_template('tenant_me_edit.html', t=tenant, back_url=url_for('tenant_admin.dashboard'))


@bp.route('/portal')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def portal():
    """テナントポータル"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # テナント情報を取得
    cur.execute(_sql(conn, 'SELECT id, "名称", slug FROM "T_テナント" WHERE id = %s'), (tenant_id,))
    tenant_row = cur.fetchone()
    tenant = None
    if tenant_row:
        tenant = {'id': tenant_row[0], '名称': tenant_row[1], 'slug': tenant_row[2]}
    
    # 管理者数を取得
    cur.execute(_sql(conn, 'SELECT COUNT(*) FROM "T_管理者" WHERE tenant_id = %s AND role = %s'),
               (tenant_id, ROLES["ADMIN"]))
    admin_count = cur.fetchone()[0]
    
    # 従業員数を取得
    cur.execute(_sql(conn, 'SELECT COUNT(*) FROM "T_従業員" WHERE tenant_id = %s'),
               (tenant_id,))
    employee_count = cur.fetchone()[0]
    
    conn.close()
    
    return render_template('tenant_portal.html', 
                         tenant=tenant,
                         admin_count=admin_count,
                         employee_count=employee_count,
                         stores=[])


# ========================================
# 店舗管理
# ========================================

@bp.route('/stores')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def stores():
    """店舗一覧"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(_sql(conn, '''
        SELECT id, 名称, slug, created_at, updated_at
        FROM "T_店舗"
        WHERE tenant_id = %s
        ORDER BY id
    '''), (tenant_id,))
    
    stores_list = []
    for row in cur.fetchall():
        stores_list.append({
            'id': row[0],
            '名称': row[1],
            'slug': row[2],
            'created_at': row[3],
            'updated_at': row[4]
        })
    conn.close()
    
    return render_template('tenant_stores.html', stores=stores_list)


@bp.route('/stores/<int:store_id>')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def store_detail(store_id):
    """店舗詳細"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗情報を取得
    cur.execute(_sql(conn, '''
        SELECT id, 名称, slug, created_at, updated_at
        FROM "T_店舗"
        WHERE id = %s AND tenant_id = %s
    '''), (store_id, tenant_id))
    row = cur.fetchone()
    
    if not row:
        flash('店舗が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.stores'))
    
    store = {
        'id': row[0],
        '名称': row[1],
        'slug': row[2],
        'created_at': row[3],
        'updated_at': row[4]
    }
    
    # 店舗管理者数を取得
    cur.execute(_sql(conn, 'SELECT COUNT(*) FROM "T_管理者" WHERE tenant_id = %s AND role = %s'),
               (tenant_id, ROLES["ADMIN"]))
    admin_count = cur.fetchone()[0]
    
    # 従業員数を取得
    cur.execute(_sql(conn, 'SELECT COUNT(*) FROM "T_従業員" WHERE tenant_id = %s'),
               (tenant_id,))
    employee_count = cur.fetchone()[0]
    
    conn.close()
    
    return render_template('tenant_store_detail.html', 
                         store=store,
                         admin_count=admin_count,
                         employee_count=employee_count)


@bp.route('/stores/new', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def store_new():
    """店舗新規作成"""
    tenant_id = session.get('tenant_id')
    
    if request.method == 'POST':
        name = request.form.get('名称', '').strip()
        slug = request.form.get('slug', '').strip()
        
        if not name or not slug:
            flash('名称とslugは必須です', 'error')
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # 重複チェック
            cur.execute(_sql(conn, 'SELECT id FROM "T_店舗" WHERE tenant_id = %s AND slug = %s'), (tenant_id, slug))
            if cur.fetchone():
                flash('このslugは既に使用されています', 'error')
                conn.close()
            else:
                cur.execute(_sql(conn, '''
                    INSERT INTO "T_店舗" (tenant_id, 名称, slug)
                    VALUES (%s, %s, %s)
                    RETURNING id
                '''), (tenant_id, name, slug))
                
                # 新しく作成された店舗IDを取得
                result = cur.fetchone()
                store_id = result[0] if result else None
                
                # デフォルトアンケート設定を作成
                import json
                default_survey_config = {
                    "title": "お店アンケート",
                    "description": "アンケートにご協力いただくと、スロットマシンを1回プレイできます。",
                    "questions": [
                        {
                            "id": 1,
                            "text": "総合的な満足度を教えてください",
                            "type": "radio",
                            "options": ["非常に満足", "満足", "普通", "やや不満", "不満"],
                            "required": True
                        },
                        {
                            "id": 2,
                            "text": "ご来店の目的を教えてください",
                            "type": "radio",
                            "options": ["食事", "カフェ利用", "買い物", "サービス利用", "その他"],
                            "required": True
                        },
                        {
                            "id": 3,
                            "text": "お店の雰囲気で良かった点を教えてください（複数選択可）",
                            "type": "checkbox",
                            "options": ["清潔感", "落ち着いた空間", "スタッフの対応", "内装・デザイン", "音楽・照明"],
                            "required": False
                        },
                        {
                            "id": 4,
                            "text": "友人におすすめしたいと思いますか？",
                            "type": "radio",
                            "options": ["強く思う", "思う", "どちらとも言えない", "あまり思わない", "思わない"],
                            "required": True
                        },
                        {
                            "id": 5,
                            "text": "その他、ご意見・ご要望があればお聞かせください",
                            "type": "text",
                            "placeholder": "自由にご記入ください",
                            "required": False
                        }
                    ]
                }
                
                cur.execute(_sql(conn, '''
                    INSERT INTO "T_店舗_アンケート設定" (store_id, title, config_json)
                    VALUES (%s, %s, %s)
                '''), (store_id, default_survey_config["title"], json.dumps(default_survey_config, ensure_ascii=False)))
                
                conn.commit()
                conn.close()
                flash('店舗を作成しました', 'success')
                return redirect(url_for('tenant_admin.stores'))
    
    return render_template('tenant_store_new.html', back_url=url_for('tenant_admin.stores'))


@bp.route('/stores/<int:store_id>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def store_edit(store_id):
    """店舗編集"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        name = request.form.get('名称', '').strip()
        slug = request.form.get('slug', '').strip()
        openai_api_key = request.form.get('openai_api_key', '').strip()
        
        if not name or not slug:
            flash('名称とslugは必須です', 'error')
        else:
            # 重複チェック（自分以外）
            cur.execute(_sql(conn, 'SELECT id FROM "T_店舗" WHERE tenant_id = %s AND slug = %s AND id != %s'), 
                       (tenant_id, slug, store_id))
            if cur.fetchone():
                flash(f'slug "{slug}" は既に使用されています', 'error')
            else:
                cur.execute(_sql(conn, '''
                    UPDATE "T_店舗"
                    SET 名称 = %s, slug = %s, openai_api_key = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND tenant_id = %s
                '''), (name, slug, openai_api_key if openai_api_key else None, store_id, tenant_id))
                conn.commit()
                flash('店舗情報を更新しました', 'success')
                conn.close()
                return redirect(url_for('tenant_admin.store_detail', store_id=store_id))
    
    # GETリクエスト：店舗情報を取得
    cur.execute(_sql(conn, '''
        SELECT id, 名称, slug, openai_api_key
        FROM "T_店舗"
        WHERE id = %s AND tenant_id = %s
    '''), (store_id, tenant_id))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        flash('店舗が見つかりません', 'error')
        return redirect(url_for('tenant_admin.stores'))
    
    store = {'id': row[0], '名称': row[1], 'slug': row[2], 'openai_api_key': row[3] if len(row) > 3 else None}
    return render_template('tenant_store_edit.html', store=store)


@bp.route('/stores/<int:store_id>/delete', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def store_delete(store_id):
    """店舗削除"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗情報を取得
    cur.execute(_sql(conn, 'SELECT 名称 FROM "T_店舗" WHERE id = %s AND tenant_id = %s'),
               (store_id, tenant_id))
    row = cur.fetchone()
    
    if not row:
        flash('店舗が見つかりません', 'error')
    else:
        cur.execute(_sql(conn, 'DELETE FROM "T_店舗" WHERE id = %s'), (store_id,))
        conn.commit()
        flash(f'{row[0]} を削除しました', 'success')
    
    conn.close()
    return redirect(url_for('tenant_admin.stores'))


# ========================================
# 管理者管理
# ========================================

@bp.route('/admins')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def admins():
    """管理者一覧"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, active, created_at, can_manage_admins, is_owner 
        FROM "T_管理者" 
        WHERE tenant_id = %s AND role = %s 
        ORDER BY is_owner DESC, can_manage_admins DESC, id
    '''), (tenant_id, ROLES["ADMIN"]))
    
    admins_list = []
    for row in cur.fetchall():
        admins_list.append({
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'active': row[3],
            'created_at': row[4],
            'can_manage_admins': row[5],
            'is_owner': row[6]
        })
    conn.close()
    
    role = session.get('role')
    is_system_admin = role == ROLES["SYSTEM_ADMIN"]
    is_tenant_admin = role == ROLES["TENANT_ADMIN"]
    current_user_id = session.get('user_id')
    
    return render_template('tenant_admins.html', admins=admins_list, current_user_id=current_user_id, is_system_admin=is_system_admin, is_tenant_admin=is_tenant_admin)


@bp.route('/admins/new', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def admin_new():
    """管理者新規作成（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('管理者を作成する権限がありません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗一覧を取得
    cur.execute(_sql(conn, 'SELECT id, 名称 FROM "T_店舗" WHERE tenant_id = %s AND 有効 = 1 ORDER BY 名称'), (tenant_id,))
    stores = [{'id': row[0], '名称': row[1]} for row in cur.fetchall()]
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        is_owner = 1 if request.form.get('is_owner') else 0
        store_ids = request.form.getlist('store_ids')  # 複数選択
        
        if not login_id or not name or not password:
            flash('ログインID、氏名、パスワードは必須です', 'error')
        elif password != password_confirm:
            flash('パスワードが一致しません', 'error')
        elif not store_ids:
            flash('少なくとも1つの店舗を選択してください', 'error')
        else:
            # 重複チェック
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s'), (login_id,))
            if cur.fetchone():
                flash('このログインIDは既に使用されています', 'error')
            else:
                ph = generate_password_hash(password)
                cur.execute(_sql(conn, '''
                    INSERT INTO "T_管理者" (login_id, name, email, password_hash, role, tenant_id, active, is_owner)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
                '''), (login_id, name, email, ph, ROLES["ADMIN"], tenant_id, is_owner))
                
                # 新しく作成した管理者のIDを取得
                cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s'), (login_id,))
                new_admin_id = cur.fetchone()[0]
                
                # 中間テーブルに店舗を紐付け
                for store_id in store_ids:
                    cur.execute(_sql(conn, '''
                        INSERT INTO "T_管理者_店舗" (admin_id, store_id)
                        VALUES (%s, %s)
                    '''), (new_admin_id, int(store_id)))
                
                conn.commit()
                flash('管理者を作成しました', 'success')
                conn.close()
                return redirect(url_for('tenant_admin.admins'))
    
    conn.close()
    return render_template('admin_new.html', stores=stores, back_url=url_for('tenant_admin.admins'))
@bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def admin_delete(admin_id):
    """管理者削除（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('管理者を削除する権限がありません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # テナントIDとオーナーフラグの確認
    cur.execute(_sql(conn, 'SELECT name, is_owner FROM "T_管理者" WHERE id = %s AND tenant_id = %s AND role = %s'),
               (admin_id, tenant_id, ROLES["ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        flash('管理者が見つかりません', 'error')
    elif row[1] == 1:
        flash('オーナーは削除できません。先にオーナー権限を移譲してください。', 'error')
    else:
        cur.execute(_sql(conn, 'DELETE FROM "T_管理者" WHERE id = %s'), (admin_id,))
        conn.commit()
        flash(f'{row[0]} を削除しました', 'success')
    
    conn.close()
    return redirect(url_for('tenant_admin.admins'))


@bp.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def admin_edit(admin_id):
    """管理者編集（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('管理者を編集する権限がありません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗一覧を取得
    cur.execute(_sql(conn, 'SELECT id, 名称 FROM "T_店舗" WHERE tenant_id = %s AND 有効 = 1 ORDER BY 名称'), (tenant_id,))
    stores = [{'id': row[0], '名称': row[1]} for row in cur.fetchall()]
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        active = int(request.form.get('active', 1))
        store_ids = request.form.getlist('store_ids')  # 複数選択
        
        # オーナー権限は編集画面では変更できない（一覧画面の「オーナー移譲」で変更）
        cur.execute(_sql(conn, 'SELECT is_owner FROM "T_管理者" WHERE id = %s'), (admin_id,))
        row_owner = cur.fetchone()
        is_owner = row_owner[0] if row_owner else 0
        
        if not login_id or not name:
            flash('ログインIDと氏名は必須です', 'error')
        elif password and password != password_confirm:
            flash('パスワードが一致しません', 'error')
        elif not store_ids:
            flash('少なくとも1つの店舗を選択してください', 'error')
        elif is_owner == 1 and active == 0:
            flash('オーナーを無効にすることはできません。先にオーナー権限を移譲してください。', 'error')
        else:
            # 重複チェック（自分以外）
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s AND id != %s'), (login_id, admin_id))
            if cur.fetchone():
                flash(f'ログインID "{login_id}" は既に使用されています', 'error')
            else:
                if password:
                    # パスワード変更あり
                    ph = generate_password_hash(password)
                    cur.execute(_sql(conn, '''
                        UPDATE "T_管理者"
                        SET login_id = %s, name = %s, email = %s, password_hash = %s, active = %s, is_owner = %s
                        WHERE id = %s AND tenant_id = %s AND role = %s
                    '''), (login_id, name, email, ph, active, is_owner, admin_id, tenant_id, ROLES["ADMIN"]))
                else:
                    # パスワード変更なし
                    cur.execute(_sql(conn, '''
                        UPDATE "T_管理者"
                        SET login_id = %s, name = %s, email = %s, active = %s, is_owner = %s
                        WHERE id = %s AND tenant_id = %s AND role = %s
                    '''), (login_id, name, email, active, is_owner, admin_id, tenant_id, ROLES["ADMIN"]))
                
                # 所属店舗を更新（既存を削除して新しく追加）
                cur.execute(_sql(conn, 'DELETE FROM "T_管理者_店舗" WHERE admin_id = %s'), (admin_id,))
                for store_id in store_ids:
                    cur.execute(_sql(conn, '''
                        INSERT INTO "T_管理者_店舗" (admin_id, store_id)
                        VALUES (%s, %s)
                    '''), (admin_id, int(store_id)))
                
                conn.commit()
                flash('管理者情報を更新しました', 'success')
                conn.close()
                return redirect(url_for('tenant_admin.admins'))
    
    # GETリクエスト：管理者情報を取得
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, email, active, can_manage_admins, is_owner
        FROM "T_管理者"
        WHERE id = %s AND tenant_id = %s AND role = %s
    '''), (admin_id, tenant_id, ROLES["ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        flash('管理者が見つかりません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    admin = {
        'id': row[0],
        'login_id': row[1],
        'name': row[2],
        'email': row[3],
        'active': row[4],
        'can_manage_admins': row[5],
        'is_owner': row[6]
    }
    
    # 現在の所属店舗を取得
    cur.execute(_sql(conn, 'SELECT store_id FROM "T_管理者_店舗" WHERE admin_id = %s'), (admin_id,))
    admin_store_ids = [row[0] for row in cur.fetchall()]
    conn.close()
    
    return render_template('tenant_admin_edit.html', admin=admin, stores=stores, admin_store_ids=admin_store_ids)
@bp.route('/admins/<int:admin_id>/toggle_manage_permission', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def toggle_admin_manage_permission(admin_id):
    """管理者管理権限の付与・剝奪（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('管理者管理権限を変更する権限がありません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    # 自分自身の権限は変更できない
    if admin_id == session.get('user_id'):
        flash('自分自身の権限は変更できません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 現在の状態を取得
    cur.execute(_sql(conn, '''
        SELECT can_manage_admins, name 
        FROM "T_管理者" 
        WHERE id = %s AND tenant_id = %s AND role = %s
    '''), (admin_id, tenant_id, ROLES["ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        flash('管理者が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.admins'))
    
    current_permission = row[0]
    admin_name = row[1]
    new_permission = 0 if current_permission == 1 else 1
    
    # 権限を切り替え
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET can_manage_admins = %s
        WHERE id = %s
    '''), (new_permission, admin_id))
    conn.commit()
    conn.close()
    
    if new_permission == 1:
        flash(f'{admin_name} に管理者管理権限を付与しました', 'success')
    else:
        flash(f'{admin_name} から管理者管理権限を剝奪しました', 'success')
    
    return redirect(url_for('tenant_admin.admins'))


@bp.route('/admins/<int:admin_id>/transfer_ownership', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def transfer_admin_ownership(admin_id):
    """店舗管理者のオーナー権限を他の店舗管理者に移譲"""
    role = session.get('role')
    is_system_admin = role == ROLES["SYSTEM_ADMIN"]
    is_tenant_admin = role == ROLES["TENANT_ADMIN"]
    
    # システム管理者またはテナント管理者のみ実行可能
    if not is_system_admin and not is_tenant_admin:
        flash('オーナー権限を移譲する権限がありません', 'error')
        return redirect(url_for('tenant_admin.admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 移譲先の店舗管理者を確認
    cur.execute(_sql(conn, '''
        SELECT id, name 
        FROM "T_管理者" 
        WHERE id = %s AND tenant_id = %s AND role = %s AND active = 1
    '''), (admin_id, tenant_id, ROLES["ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        flash('移譲先の管理者が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.admins'))
    
    new_owner_name = row[1]
    
    # 現在のオーナーのis_ownerを0に設定
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET is_owner = 0
        WHERE tenant_id = %s AND role = %s AND is_owner = 1
    '''), (tenant_id, ROLES["ADMIN"]))
    
    # 新しいオーナーのis_ownerを1に設定し、can_manage_adminsも1に設定
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET is_owner = 1, can_manage_admins = 1
        WHERE id = %s
    '''), (admin_id,))
    
    conn.commit()
    conn.close()
    
    flash(f'{new_owner_name} にオーナー権限を移譲しました', 'success')
    return redirect(url_for('tenant_admin.admins'))


# ========================================
# 従業員管理
# ========================================

@bp.route('/employees')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def employees():
    """従業員一覧"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, email, created_at 
        FROM "T_従業員" 
        WHERE tenant_id = %s 
        ORDER BY id
    '''), (tenant_id,))
    
    employees_list = []
    for row in cur.fetchall():
        employees_list.append({
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'email': row[3],
            'created_at': row[4],
            'active': 1  # T_従業員テーブルにactiveカラムがないため、常に有効とする
        })
    conn.close()
    
    return render_template('tenant_employees.html', employees=employees_list)


@bp.route('/employees/new', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def employee_new():
    """従業員新規作成"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗一覧を取得
    cur.execute(_sql(conn, 'SELECT id, 名称 FROM "T_店舗" WHERE tenant_id = %s AND 有効 = 1 ORDER BY 名称'), (tenant_id,))
    stores = [{'id': row[0], '名称': row[1]} for row in cur.fetchall()]
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        is_owner = 1 if request.form.get('is_owner') else 0
        store_ids = request.form.getlist('store_ids')  # 複数選択
        
        if not login_id or not name or not email or not password:
            flash('ログインID、氏名、メールアドレス、パスワードは必須です', 'error')
        elif password != password_confirm:
            flash('パスワードが一致しません', 'error')
        elif not store_ids:
            flash('少なくとも1つの店舗を選択してください', 'error')
        else:
            # 重複チェック
            cur.execute(_sql(conn, 'SELECT id FROM "T_従業員" WHERE login_id = %s OR email = %s'), (login_id, email))
            if cur.fetchone():
                flash('このログインIDまたはメールアドレスは既に使用されています', 'error')
            else:
                ph = generate_password_hash(password)
                cur.execute(_sql(conn, '''
                    INSERT INTO "T_従業員" (login_id, name, email, password_hash, tenant_id, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                '''), (login_id, name, email, ph, tenant_id, ROLES['EMPLOYEE']))
                
                # 新しく作成した従業員のIDを取得
                cur.execute(_sql(conn, 'SELECT id FROM "T_従業員" WHERE login_id = %s'), (login_id,))
                new_employee_id = cur.fetchone()[0]
                
                # 中間テーブルに店舗を紐付け
                for store_id in store_ids:
                    cur.execute(_sql(conn, '''
                        INSERT INTO "T_従業員_店舗" (employee_id, store_id)
                        VALUES (%s, %s)
                    '''), (new_employee_id, int(store_id)))
                
                conn.commit()
                flash('従業員を作成しました', 'success')
                conn.close()
                return redirect(url_for('tenant_admin.employees'))
    
    conn.close()
    return render_template('tenant_employee_new.html', stores=stores, back_url=url_for('tenant_admin.employees'))

@bp.route('/employees/<int:employee_id>/delete', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def employee_delete(employee_id):
    """従業員削除"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 従業員が存在するか確認
    cur.execute(_sql(conn, 'SELECT name FROM "T_従業員" WHERE id = %s AND tenant_id = %s'), (employee_id, tenant_id))
    row = cur.fetchone()
    
    if not row:
        flash('従業員が見つかりません', 'error')
    else:
        name = row[0]
        # 中間テーブルのデータも削除
        cur.execute(_sql(conn, 'DELETE FROM "T_従業員_店舗" WHERE employee_id = %s'), (employee_id,))
        cur.execute(_sql(conn, 'DELETE FROM "T_従業員" WHERE id = %s AND tenant_id = %s'), (employee_id, tenant_id))
        conn.commit()
        flash(f'従業員 "{name}" を削除しました', 'success')
    
    conn.close()
    return redirect(url_for('tenant_admin.employees'))

@bp.route('/employees/<int:employee_id>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def employee_edit(employee_id):
    """従業員編集"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗一覧を取得
    cur.execute(_sql(conn, 'SELECT id, 名称 FROM "T_店舗" WHERE tenant_id = %s AND 有効 = 1 ORDER BY 名称'), (tenant_id,))
    stores = [{'id': row[0], '名称': row[1]} for row in cur.fetchall()]
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        store_ids = request.form.getlist('store_ids')  # 複数選択
        
        if not login_id or not name or not email:
            flash('ログインID、氏名、メールアドレスは必須です', 'error')
        elif not store_ids:
            flash('少なくとも1つの店舗を選択してください', 'error')
        else:
            # 重複チェック（自分以外）
            cur.execute(_sql(conn, 'SELECT id FROM "T_従業員" WHERE (login_id = %s OR email = %s) AND id != %s'), (login_id, email, employee_id))
            if cur.fetchone():
                flash('このログインIDまたはメールアドレスは既に使用されています', 'error')
            else:
                if password:
                    # パスワード変更あり
                    ph = generate_password_hash(password)
                    cur.execute(_sql(conn, '''
                        UPDATE "T_従業員"
                        SET login_id = %s, name = %s, email = %s, password_hash = %s
                        WHERE id = %s AND tenant_id = %s
                    '''), (login_id, name, email, ph, employee_id, tenant_id))
                else:
                    # パスワード変更なし
                    cur.execute(_sql(conn, '''
                        UPDATE "T_従業員"
                        SET login_id = %s, name = %s, email = %s
                        WHERE id = %s AND tenant_id = %s
                    '''), (login_id, name, email, employee_id, tenant_id))
                
                # 所属店舗を更新（既存を削除して新しく追加）
                cur.execute(_sql(conn, 'DELETE FROM "T_従業員_店舗" WHERE employee_id = %s'), (employee_id,))
                for store_id in store_ids:
                    cur.execute(_sql(conn, '''
                        INSERT INTO "T_従業員_店舗" (employee_id, store_id)
                        VALUES (%s, %s)
                    '''), (employee_id, int(store_id)))
                
                conn.commit()
                flash('従業員情報を更新しました', 'success')
                conn.close()
                return redirect(url_for('tenant_admin.employees'))
    
    # GETリクエスト：従業員情報を取得
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, email
        FROM "T_従業員"
        WHERE id = %s AND tenant_id = %s
    '''), (employee_id, tenant_id))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        flash('従業員が見つかりません', 'error')
        return redirect(url_for('tenant_admin.employees'))
    
    employee = {
        'id': row[0],
        'login_id': row[1],
        'name': row[2],
        'email': row[3]
    }
    
    # 現在の所属店舗を取得
    cur.execute(_sql(conn, 'SELECT store_id FROM "T_従業員_店舗" WHERE employee_id = %s'), (employee_id,))
    employee_store_ids = [row[0] for row in cur.fetchall()]
    conn.close()
    
    return render_template('tenant_employee_edit.html', employee=employee, stores=stores, employee_store_ids=employee_store_ids)

def employee_delete(employee_id):
    """従業員削除"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # テナントIDの確認
    cur.execute(_sql(conn, 'SELECT name FROM "T_従業員" WHERE id = %s AND tenant_id = %s'),
               (employee_id, tenant_id))
    row = cur.fetchone()
    
    if not row:
        flash('従業員が見つかりません', 'error')
    else:
        cur.execute(_sql(conn, 'DELETE FROM "T_従業員" WHERE id = %s'), (employee_id,))
        conn.commit()
        flash(f'{row[0]} を削除しました', 'success')
    
    conn.close()
    return redirect(url_for('tenant_admin.employees'))


# ========================================
# テナント管理者管理
# ========================================

@bp.route('/tenant_admins')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def tenant_admins():
    """テナント管理者一覧"""
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, active, created_at, is_owner, can_manage_admins 
        FROM "T_管理者" 
        WHERE tenant_id = %s AND role = %s 
        ORDER BY is_owner DESC, can_manage_admins DESC, id
    '''), (tenant_id, ROLES["TENANT_ADMIN"]))
    
    tenant_admins_list = []
    for row in cur.fetchall():
        tenant_admins_list.append({
            'id': row[0],
            'login_id': row[1],
            'name': row[2],
            'active': row[3],
            'created_at': row[4],
            'is_owner': row[5],
            'can_manage_admins': row[6]
        })
    conn.close()
    
    current_user_id = session.get('user_id')
    is_system_admin = session.get('role') == ROLES["SYSTEM_ADMIN"]
    return render_template('tenant_tenant_admins.html', tenant_admins=tenant_admins_list, current_user_id=current_user_id, is_system_admin=is_system_admin)


@bp.route('/tenant_admins/new', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def tenant_admin_new():
    """テナント管理者新規作成（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('テナント管理者を作成する権限がありません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    tenant_id = session.get('tenant_id')
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '').strip()
        
        if not login_id or not name or not password:
            flash('全ての項目を入力してください', 'error')
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # 重複チェック
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s'), (login_id,))
            if cur.fetchone():
                flash('このログインIDは既に使用されています', 'error')
                conn.close()
            else:
                ph = generate_password_hash(password)
                cur.execute(_sql(conn, '''
                    INSERT INTO "T_管理者" (login_id, name, password_hash, role, tenant_id, active, can_manage_admins)
                    VALUES (%s, %s, %s, %s, %s, 1, 0)
                '''), (login_id, name, ph, ROLES["TENANT_ADMIN"], tenant_id))
                conn.commit()
                conn.close()
                
                # テナント管理者が一人の場合、自動的にオーナーに設定
                ensure_tenant_owner(tenant_id)
                
                flash('テナント管理者を作成しました', 'success')
                return redirect(url_for('tenant_admin.tenant_admins'))
    
    return render_template('tenant_tenant_admin_new.html', back_url=url_for('tenant_admin.tenant_admins'))


@bp.route('/tenant_admins/<int:tadmin_id>/edit', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def tenant_admin_edit(tadmin_id):
    """テナント管理者編集（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('テナント管理者を編集する権限がありません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    tenant_id = session.get('tenant_id')
    role = session.get('role')
    is_system_admin = role == ROLES["SYSTEM_ADMIN"]
    conn = get_db_connection()
    cur = conn.cursor()
    
    # システム管理者の場合、全テナント一覧を取得
    tenants = []
    if is_system_admin:
        cur.execute(_sql(conn, 'SELECT id, "名称" FROM "T_テナント" WHERE "有効" = 1 ORDER BY "名称"'))
        tenants = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
    
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        active = int(request.form.get('active', 1))
        tenant_ids = request.form.getlist('tenant_ids') if is_system_admin else [str(tenant_id)]
        
        # オーナー権限は編集画面では変更できない（一覧画面の「オーナー移譲」で変更）
        cur.execute(_sql(conn, 'SELECT is_owner FROM "T_管理者" WHERE id = %s'), (tadmin_id,))
        row_owner = cur.fetchone()
        is_owner = row_owner[0] if row_owner else 0
        
        password_confirm = request.form.get('password_confirm', '').strip()
        
        if not login_id or not name:
            flash('ログインIDと氏名は必須です', 'error')
        elif password and password != password_confirm:
            flash('パスワードが一致しません', 'error')
        elif is_system_admin and not tenant_ids:
            flash('少なくとも1つのテナントを選択してください', 'error')
        elif is_owner == 1 and active == 0:
            flash('オーナーを無効にすることはできません。先にオーナー権限を移譲してください。', 'error')
        else:
            # 重複チェック（自分以外）
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s AND id != %s'), (login_id, tadmin_id))
            if cur.fetchone():
                flash(f'ログインID "{login_id}" は既に使用されています', 'error')
            else:
                if password:
                    # パスワード変更あり
                    ph = generate_password_hash(password)
                    cur.execute(_sql(conn, '''
                        UPDATE "T_管理者"
                        SET login_id = %s, name = %s, email = %s, password_hash = %s, active = %s, is_owner = %s
                        WHERE id = %s AND tenant_id = %s AND role = %s
                    '''), (login_id, name, email, ph, active, is_owner, tadmin_id, tenant_id, ROLES["TENANT_ADMIN"]))
                else:
                    # パスワード変更なし
                    cur.execute(_sql(conn, '''
                        UPDATE "T_管理者"
                        SET login_id = %s, name = %s, email = %s, active = %s, is_owner = %s
                        WHERE id = %s AND tenant_id = %s AND role = %s
                    '''), (login_id, name, email, active, is_owner, tadmin_id, tenant_id, ROLES["TENANT_ADMIN"]))
                
                # システム管理者の場合、所属テナントを更新
                if is_system_admin:
                    cur.execute(_sql(conn, 'DELETE FROM "T_テナント管理者_テナント" WHERE tenant_admin_id = %s'), (tadmin_id,))
                    for tid in tenant_ids:
                        cur.execute(_sql(conn, '''
                            INSERT INTO "T_テナント管理者_テナント" (tenant_admin_id, tenant_id)
                            VALUES (%s, %s)
                        '''), (tadmin_id, int(tid)))
                
                conn.commit()
                flash('テナント管理者情報を更新しました', 'success')
                conn.close()
                return redirect(url_for('tenant_admin.tenant_admins'))
    
    # GETリクエスト：テナント管理者情報を取得
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, email, active, can_manage_admins, is_owner
        FROM "T_管理者"
        WHERE id = %s AND tenant_id = %s AND role = %s
    '''), (tadmin_id, tenant_id, ROLES["TENANT_ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        flash('テナント管理者が見つかりません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    tadmin = {
        'id': row[0],
        'login_id': row[1],
        'name': row[2],
        'email': row[3],
        'active': row[4],
        'can_manage_admins': row[5],
        'is_owner': row[6]
    }
    
    # 現在の所属テナントを取得
    tadmin_tenant_ids = []
    if is_system_admin:
        cur.execute(_sql(conn, 'SELECT tenant_id FROM "T_テナント管理者_テナント" WHERE tenant_admin_id = %s'), (tadmin_id,))
        tadmin_tenant_ids = [row[0] for row in cur.fetchall()]
        # 所属テナントがない場合は現在のテナントを追加
        if not tadmin_tenant_ids:
            tadmin_tenant_ids = [tenant_id]
    
    conn.close()
    
    return render_template('tenant_tenant_admin_edit.html', tadmin=tadmin, tenants=tenants, tadmin_tenant_ids=tadmin_tenant_ids)


@bp.route('/tenant_admins/<int:tadmin_id>/delete', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def tenant_admin_delete(tadmin_id):
    """テナント管理者削除（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('テナント管理者を削除する権限がありません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    # 自分自身は削除できない
    if tadmin_id == session.get('user_id'):
        flash('自分自身は削除できません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # テナントIDとオーナーフラグの確認
    cur.execute(_sql(conn, 'SELECT name, is_owner FROM "T_管理者" WHERE id = %s AND tenant_id = %s AND role = %s'),
               (tadmin_id, tenant_id, ROLES["TENANT_ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        flash('テナント管理者が見つかりません', 'error')
    elif row[1] == 1:
        flash('オーナーは削除できません。先にオーナー権限を移譲してください。', 'error')
    else:
        cur.execute(_sql(conn, 'DELETE FROM "T_管理者" WHERE id = %s'), (tadmin_id,))
        conn.commit()
        flash(f'{row[0]} を削除しました', 'success')
        
        # 削除後、テナント管理者が一人の場合、自動的にオーナーに設定
        ensure_tenant_owner(tenant_id)
    
    conn.close()
    return redirect(url_for('tenant_admin.tenant_admins'))


@bp.route('/tenant_admins/<int:tadmin_id>/toggle_manage_permission', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def toggle_tenant_admin_manage_permission(tadmin_id):
    """テナント管理者管理権限の付与・剝奪（管理者管理権限が必要）"""
    # 管理者管理権限チェック
    if not can_manage_tenant_admins():
        flash('管理者管理権限を変更する権限がありません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    # 自分自身の権限は変更できない
    if tadmin_id == session.get('user_id'):
        flash('自分自身の権限は変更できません', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 現在の状態を取得
    cur.execute(_sql(conn, '''
        SELECT can_manage_admins, name, is_owner 
        FROM "T_管理者" 
        WHERE id = %s AND tenant_id = %s AND role = %s
    '''), (tadmin_id, tenant_id, ROLES["TENANT_ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        flash('テナント管理者が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    current_permission = row[0]
    tadmin_name = row[1]
    is_owner = row[2]
    
    # オーナーの権限は変更できない
    if is_owner == 1:
        flash('オーナーの管理権限は変更できません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.tenant_admins'))
    new_permission = 0 if current_permission == 1 else 1
    
    # 権限を切り替え
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET can_manage_admins = %s
        WHERE id = %s
    '''), (new_permission, tadmin_id))
    conn.commit()
    conn.close()
    
    if new_permission == 1:
        flash(f'{tadmin_name} に管理者管理権限を付与しました', 'success')
    else:
        flash(f'{tadmin_name} から管理者管理権限を剝奪しました', 'success')
    
    return redirect(url_for('tenant_admin.tenant_admins'))


@bp.route('/tenant_admins/<int:tadmin_id>/transfer_ownership', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def transfer_tenant_ownership(tadmin_id):
    """テナントオーナー権限を他のテナント管理者に移譲"""
    role = session.get('role')
    is_system_admin = role == ROLES["SYSTEM_ADMIN"]
    
    # システム管理者またはオーナーのみ実行可能
    if not is_system_admin and not is_tenant_owner():
        flash('オーナーのみがオーナー権限を移譲できます', 'error')
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 移譲先のテナント管理者を確認
    cur.execute(_sql(conn, '''
        SELECT id, name 
        FROM "T_管理者" 
        WHERE id = %s AND tenant_id = %s AND role = %s AND active = 1
    '''), (tadmin_id, tenant_id, ROLES["TENANT_ADMIN"]))
    row = cur.fetchone()
    
    if not row:
        flash('移譲先のテナント管理者が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.tenant_admins'))
    
    new_owner_name = row[1]
    
    # 現在のオーナーのis_ownerを0に設定
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET is_owner = 0
        WHERE tenant_id = %s AND role = %s AND is_owner = 1
    '''), (tenant_id, ROLES["TENANT_ADMIN"]))
    
    # 新しいオーナーのis_ownerを1に設定し、can_manage_adminsも1に設定
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET is_owner = 1, can_manage_admins = 1
        WHERE id = %s
    '''), (tadmin_id,))
    
    conn.commit()
    conn.close()
    
    flash(f'{new_owner_name} にオーナー権限を移譲しました', 'success')
    return redirect(url_for('tenant_admin.tenant_admins'))


# ========================================
# テナント管理者マイページ
# ========================================

@bp.route('/mypage', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def mypage():
    """テナント管理者マイページ"""
    user_id = session.get('user_id')
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # ユーザー情報を取得
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, email, can_manage_admins, created_at, updated_at
        FROM "T_管理者"
        WHERE id = %s AND role = %s
    '''), (user_id, ROLES["TENANT_ADMIN"]))
    
    row = cur.fetchone()
    
    if not row:
        flash('ユーザー情報が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.dashboard'))
    
    user = {
        'id': row[0],
        'login_id': row[1],
        'name': row[2],
        'email': row[3],
        'can_manage_admins': row[4],
        'created_at': row[5],
        'updated_at': row[6]
    }
    
    # テナント名を取得
    tenant_name = '未選択'
    if tenant_id:
        cur.execute(_sql(conn, 'SELECT 名称 FROM "T_テナント" WHERE id = %s'), (tenant_id,))
        tenant_row = cur.fetchone()
        tenant_name = tenant_row[0] if tenant_row else '不明'
    
    # テナントリストを取得（テナント管理者が管理するテナント）
    cur.execute(_sql(conn, '''
        SELECT DISTINCT t.id, t.名称
        FROM "T_テナント" t
        INNER JOIN "T_管理者" a ON a.tenant_id = t.id
        WHERE a.id = %s AND a.role = %s
        ORDER BY t.名称
    '''), (user_id, ROLES["TENANT_ADMIN"]))
    tenant_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
    
    # 店舗リストを取得（テナント管理者が管理するテナントの店舗）
    store_list = []
    if tenant_list:
        tenant_ids = [t['id'] for t in tenant_list]
        placeholders = ','.join(['%s'] * len(tenant_ids))
        cur.execute(_sql(conn, f'''
            SELECT id, 名称
            FROM "T_店舗"
            WHERE tenant_id IN ({placeholders})
            ORDER BY 名称
        '''), tenant_ids)
        store_list = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
    
    # POSTリクエスト（プロフィール編集またはパスワード変更）
    if request.method == 'POST':
        action = request.form.get('action', '')
        
        if action == 'update_profile':
            # プロフィール編集
            login_id = request.form.get('login_id', '').strip()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            
            if not login_id or not name:
                conn.close()
                flash('ログインIDと氏名は必須です', 'error')
                return render_template('tenant_mypage.html', user=user, tenant_name=tenant_name, tenant_list=tenant_list, store_list=store_list)
            
            # ログインID重複チェック（自分以外）
            cur.execute(_sql(conn, 'SELECT id FROM "T_管理者" WHERE login_id = %s AND id != %s'), (login_id, user_id))
            if cur.fetchone():
                conn.close()
                flash('このログインIDは既に使用されています', 'error')
                return render_template('tenant_mypage.html', user=user, tenant_name=tenant_name, tenant_list=tenant_list, store_list=store_list)
            
            # プロフィール更新
            cur.execute(_sql(conn, '''
                UPDATE "T_管理者"
                SET login_id = %s, name = %s, email = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            '''), (login_id, name, email, user_id))
            conn.commit()
            conn.close()
            
            flash('プロフィール情報を更新しました', 'success')
            return redirect(url_for('tenant_admin.mypage'))
        
        elif action == 'change_password':
            # パスワード変更
            current_password = request.form.get('current_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            new_password_confirm = request.form.get('new_password_confirm', '').strip()
        
            # パスワード一致チェック
            if new_password != new_password_confirm:
                flash('パスワードが一致しません', 'error')
                conn.close()
                return render_template('tenant_mypage.html', user=user, tenant_name=tenant_name, tenant_list=tenant_list, store_list=store_list)
            
            # 現在のパスワードを確認
            cur.execute(_sql(conn, 'SELECT password_hash FROM "T_管理者" WHERE id = %s'), (user_id,))
            row = cur.fetchone()
            if not row or not check_password_hash(row[0], current_password):
                conn.close()
                flash('現在のパスワードが正しくありません', 'error')
                return render_template('tenant_mypage.html', user=user, tenant_name=tenant_name, tenant_list=tenant_list, store_list=store_list)
            
            # パスワードを更新
            password_hash = generate_password_hash(new_password)
            cur.execute(_sql(conn, '''
                UPDATE "T_管理者"
                SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            '''), (password_hash, user_id))
            conn.commit()
            conn.close()
            
            flash('パスワードを変更しました', 'success')
            return redirect(url_for('tenant_admin.mypage'))
    
    conn.close()
    return render_template('tenant_mypage.html', user=user, tenant_name=tenant_name, tenant_list=tenant_list, store_list=store_list)


@bp.route('/mypage/select_tenant', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def select_tenant_from_mypage():
    """マイページからテナントを選択してダッシュボードへ進む"""
    tenant_id = request.form.get('tenant_id')
    
    if not tenant_id:
        flash('テナントを選択してください', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    # テナントIDをセッションに保存
    session['tenant_id'] = int(tenant_id)
    flash('テナントを選択しました', 'success')
    
    return redirect(url_for('tenant_admin.dashboard'))


@bp.route('/mypage/select_store', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def select_store_from_mypage():
    """マイページから店舗を選択して店舗ダッシュボードへ進む"""
    store_id = request.form.get('store_id')
    
    if not store_id:
        flash('店舗を選択してください', 'error')
        return redirect(url_for('tenant_admin.mypage'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 店舗情報を取得
    cur.execute(_sql(conn, 'SELECT tenant_id, 名称 FROM "T_店舗" WHERE id = %s'), (store_id,))
    store_row = cur.fetchone()
    
    if not store_row:
        flash('店舗が見つかりません', 'error')
        conn.close()
        return redirect(url_for('tenant_admin.mypage'))
    
    tenant_id = store_row[0]
    store_name = store_row[1]
    
    # テナント名を取得
    cur.execute(_sql(conn, 'SELECT 名称 FROM "T_テナント" WHERE id = %s'), (tenant_id,))
    tenant_row = cur.fetchone()
    tenant_name = tenant_row[0] if tenant_row else '不明'
    
    conn.close()
    
    # セッションに店舗情報を保存
    session['store_id'] = int(store_id)
    session['tenant_id'] = tenant_id
    session['store_name'] = store_name
    session['tenant_name'] = tenant_name
    
    flash(f'{store_name} を選択しました', 'success')
    
    return redirect(url_for('admin.dashboard'))


# ========================================
# 一時的なオーナー設定エンドポイント（デバッグ用）
# ========================================

@bp.route('/fix_owner')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def fix_owner():
    """テナント管理者が一人の場合、自動的にオーナーに設定"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        return "テナントIDが見つかりません", 400
    
    # ensure_tenant_ownerを実行
    ensure_tenant_owner(tenant_id)
    
    return f"テナント {tenant_id} のオーナー設定を実行しました。<br><a href='/tenant_admin/tenant_admins'>テナント管理者一覧に戻る</a>"


@bp.route('/check_owner')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def check_owner():
    """現在のユーザーのオーナー状態を確認"""
    user_id = session.get('user_id')
    tenant_id = session.get('tenant_id')
    session_is_owner = session.get('is_owner')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # データベースの状態を確認
    cur.execute(_sql(conn, '''
        SELECT id, login_id, name, role, is_owner, can_manage_admins, tenant_id
        FROM "T_管理者"
        WHERE id = %s
    '''), (user_id,))
    row = cur.fetchone()
    
    if row:
        db_tenant_id = row[6]
        db_info = f"""
        <h2>データベースの状態</h2>
        <ul>
            <li>ID: {row[0]}</li>
            <li>ログインID: {row[1]}</li>
            <li>名前: {row[2]}</li>
            <li>ロール: {row[3]}</li>
            <li>is_owner: {row[4]}</li>
            <li>can_manage_admins: {row[5]}</li>
            <li>tenant_id: {db_tenant_id}</li>
        </ul>
        """
    else:
        db_info = "<p>ユーザーが見つかりません</p>"
        db_tenant_id = None
    
    # テナント一覧を取得
    cur.execute(_sql(conn, 'SELECT id, 名称 FROM "T_テナント"'))
    tenants = cur.fetchall()
    
    # テナント内のテナント管理者数を確認
    cur.execute(_sql(conn, '''
        SELECT COUNT(*) FROM "T_管理者"
        WHERE tenant_id = %s AND role = 'tenant_admin'
    '''), (tenant_id,))
    tenant_admin_count = cur.fetchone()[0]
    
    conn.close()
    
    # テナント選択フォーム
    tenant_options = ''.join([f'<option value="{t[0]}">{t[1]}</option>' for t in tenants])
    tenant_form = f'''
    <h2>テナント設定</h2>
    <form method="post" action="/tenant_admin/set_tenant">
        <select name="tenant_id">
            <option value="">選択してください</option>
            {tenant_options}
        </select>
        <button type="submit">テナントを設定</button>
    </form>
    '''
    
    session_info = f"""
    <h2>セッションの状態</h2>
    <ul>
        <li>user_id: {user_id}</li>
        <li>tenant_id: {tenant_id}</li>
        <li>is_owner: {session_is_owner}</li>
        <li>role: {session.get('role')}</li>
    </ul>
    
    <h2>テナント情報</h2>
    <ul>
        <li>テナント内のテナント管理者数: {tenant_admin_count}</li>
    </ul>
    """
    
    return f"""
    <h1>オーナー状態確認</h1>
    {db_info}
    {session_info}
    {tenant_form}
    <br>
    <a href="/tenant_admin/fix_owner">オーナー設定を実行</a> |
    <a href="/tenant_admin/tenant_admins">テナント管理者一覧に戻る</a> |
    <a href="/logout">ログアウト</a>
    """


@bp.route('/set_tenant', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def set_tenant():
    """テナント管理者のtenant_idを設定"""
    user_id = session.get('user_id')
    new_tenant_id = request.form.get('tenant_id')
    
    if not new_tenant_id:
        return "テナントIDが指定されていません", 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # データベースのtenant_idを更新
    cur.execute(_sql(conn, '''
        UPDATE "T_管理者"
        SET tenant_id = %s
        WHERE id = %s
    '''), (int(new_tenant_id), user_id))
    conn.commit()
    
    # セッションも更新
    session['tenant_id'] = int(new_tenant_id)
    
    # is_ownerを再取得
    cur.execute(_sql(conn, 'SELECT is_owner FROM "T_管理者" WHERE id = %s'), (user_id,))
    row = cur.fetchone()
    session['is_owner'] = row[0] == 1 if row else False
    
    conn.close()
    
    return f"テナントID {new_tenant_id} を設定しました。<br><a href='/tenant_admin/check_owner'>確認ページに戻る</a> | <a href='/logout'>ログアウトして再ログイン</a>"

# -*- coding: utf-8 -*-
"""
予約システム - 管理画面Blueprint
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, timedelta
import store_db
from db_config import get_db_connection, get_cursor
from app.utils.admin_auth import require_admin_login as admin_required

reservation_admin_bp = Blueprint('reservation_admin', __name__, url_prefix='/admin/store/<int:store_id>/reservation')

@reservation_admin_bp.route('/settings')
@admin_required
def settings(store_id):
    """予約設定画面"""
    # 店舗情報を取得
    store = store_db.get_store_by_id(store_id)
    if not store:
        return "店舗が見つかりません", 404
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # 予約設定を取得
    cur.execute('''
        SELECT * FROM "T_店舗_予約設定"
        WHERE store_id = ?
    ''', (store_id,))
    settings = cur.fetchone()
    
    # テーブル設定を取得
    cur.execute('''
        SELECT * FROM "T_テーブル設定"
        WHERE store_id = ?
        ORDER BY 表示順序, 座席数
    ''', (store_id,))
    tables = cur.fetchall()
    
    conn.close()
    
    return render_template('admin_reservation_settings.html',
                         store=store,
                         settings=settings,
                         tables=tables)

@reservation_admin_bp.route('/settings/save', methods=['POST'])
@admin_required
def save_settings(store_id):
    """予約設定を保存"""
    data = request.form
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # 既存設定を確認
    cur.execute('''
        SELECT id FROM "T_店舗_予約設定"
        WHERE store_id = ?
    ''', (store_id,))
    existing = cur.fetchone()
    
    if existing:
        # 更新
        cur.execute('''
            UPDATE "T_店舗_予約設定"
            SET 営業開始時刻 = ?,
                営業終了時刻 = ?,
                最終入店時刻 = ?,
                予約単位_分 = ?,
                予約受付日数 = ?,
                定休日 = ?,
                予約受付可否 = ?,
                特記事項 = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE store_id = ?
        ''', (
            data.get('営業開始時刻', '11:00'),
            data.get('営業終了時刻', '22:00'),
            data.get('最終入店時刻', '21:00'),
            int(data.get('予約単位_分', 30)),
            int(data.get('予約受付日数', 60)),
            data.get('定休日', ''),
            1 if data.get('予約受付可否') == 'on' else 0,
            data.get('特記事項', ''),
            store_id
        ))
    else:
        # 新規作成
        cur.execute('''
            INSERT INTO "T_店舗_予約設定" (
                store_id, 営業開始時刻, 営業終了時刻, 最終入店時刻,
                予約単位_分, 予約受付日数, 定休日, 予約受付可否, 特記事項
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            store_id,
            data.get('営業開始時刻', '11:00'),
            data.get('営業終了時刻', '22:00'),
            data.get('最終入店時刻', '21:00'),
            int(data.get('予約単位_分', 30)),
            int(data.get('予約受付日数', 60)),
            data.get('定休日', ''),
            1 if data.get('予約受付可否') == 'on' else 0,
            data.get('特記事項', '')
        ))
    
    conn.commit()
    conn.close()
    
    flash('予約設定を保存しました', 'success')
    return redirect(url_for('reservation_admin.settings', store_id=store_id))

@reservation_admin_bp.route('/tables/add', methods=['POST'])
@admin_required
def add_table(store_id):
    """テーブル設定を追加"""
    data = request.form
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    cur.execute('''
        INSERT INTO "T_テーブル設定" (
            store_id, テーブル名, 座席数, テーブル数, 表示順序, 有効
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        store_id,
        data.get('テーブル名'),
        int(data.get('座席数')),
        int(data.get('テーブル数', 1)),
        int(data.get('表示順序', 0)),
        1
    ))
    
    conn.commit()
    conn.close()
    
    flash('テーブル設定を追加しました', 'success')
    return redirect(url_for('reservation_admin.settings', store_id=store_id))

@reservation_admin_bp.route('/tables/<int:table_id>/delete', methods=['POST'])
@admin_required
def delete_table(store_id, table_id):
    """テーブル設定を削除"""
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    cur.execute('''
        DELETE FROM "T_テーブル設定"
        WHERE id = ? AND store_id = ?
    ''', (table_id, store_id))
    
    conn.commit()
    conn.close()
    
    flash('テーブル設定を削除しました', 'success')
    return redirect(url_for('reservation_admin.settings', store_id=store_id))

@reservation_admin_bp.route('/list')
@admin_required
def reservation_list(store_id):
    """予約一覧画面"""
    # 店舗情報を取得
    store = store_db.get_store_by_id(store_id)
    if not store:
        return "店舗が見つかりません", 404
    
    # 日付フィルター（デフォルトは今日）
    filter_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # 予約一覧を取得
    cur.execute('''
        SELECT * FROM "T_予約"
        WHERE store_id = ? AND 予約日 = ?
        ORDER BY 予約時刻
    ''', (store_id, filter_date))
    
    reservations = cur.fetchall()
    
    # 統計情報を取得
    cur.execute('''
        SELECT 
            COUNT(*) as total_count,
            SUM(人数) as total_guests,
            COUNT(CASE WHEN ステータス = 'confirmed' THEN 1 END) as confirmed_count,
            COUNT(CASE WHEN ステータス = 'cancelled' THEN 1 END) as cancelled_count
        FROM "T_予約"
        WHERE store_id = ? AND 予約日 = ?
    ''', (store_id, filter_date))
    
    stats = cur.fetchone()
    
    conn.close()
    
    return render_template('admin_reservation_list.html',
                         store=store,
                         reservations=reservations,
                         stats=stats,
                         filter_date=filter_date)

@reservation_admin_bp.route('/<int:reservation_id>/cancel', methods=['POST'])
@admin_required
def cancel_reservation(store_id, reservation_id):
    """予約をキャンセル"""
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    cur.execute('''
        UPDATE "T_予約"
        SET ステータス = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND store_id = ?
    ''', (reservation_id, store_id))
    
    conn.commit()
    conn.close()
    
    flash('予約をキャンセルしました', 'success')
    return redirect(url_for('reservation_admin.reservation_list', store_id=store_id))

@reservation_admin_bp.route('/<int:reservation_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_reservation(store_id, reservation_id):
    """予約を編集"""
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    if request.method == 'POST':
        data = request.form
        
        cur.execute('''
            UPDATE "T_予約"
            SET 予約日 = ?,
                予約時刻 = ?,
                人数 = ?,
                顧客名 = ?,
                顧客電話番号 = ?,
                顧客メール = ?,
                特記事項 = ?,
                テーブル割当 = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND store_id = ?
        ''', (
            data.get('予約日'),
            data.get('予約時刻'),
            int(data.get('人数')),
            data.get('顧客名'),
            data.get('顧客電話番号'),
            data.get('顧客メール', ''),
            data.get('特記事項', ''),
            data.get('テーブル割当', ''),
            reservation_id,
            store_id
        ))
        
        conn.commit()
        conn.close()
        
        flash('予約を更新しました', 'success')
        return redirect(url_for('reservation_admin.reservation_list', store_id=store_id))
    
    # GET: 編集フォーム表示
    cur.execute('''
        SELECT * FROM "T_予約"
        WHERE id = ? AND store_id = ?
    ''', (reservation_id, store_id))
    
    reservation = cur.fetchone()
    
    # テーブル設定を取得
    cur.execute('''
        SELECT * FROM "T_テーブル設定"
        WHERE store_id = ? AND 有効 = 1
        ORDER BY 表示順序, 座席数
    ''', (store_id,))
    
    tables = cur.fetchall()
    
    conn.close()
    
    if not reservation:
        return "予約が見つかりません", 404
    
    # 店舗情報を取得
    store = store_db.get_store_by_id(store_id)
    
    return render_template('admin_reservation_edit.html',
                         store=store,
                         reservation=reservation,
                         tables=tables)

@reservation_admin_bp.route('/calendar')
@admin_required
def calendar(store_id):
    """予約カレンダー表示"""
    # 店舗情報を取得
    store = store_db.get_store_by_id(store_id)
    if not store:
        return "店舗が見つかりません", 404
    
    # 月フィルター（デフォルトは今月）
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    # 月の最初と最後の日
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # 月間の予約データを取得
    cur.execute('''
        SELECT 予約日, COUNT(*) as count, SUM(人数) as guests
        FROM "T_予約"
        WHERE store_id = ? 
          AND 予約日 >= ? 
          AND 予約日 <= ?
          AND ステータス = 'confirmed'
        GROUP BY 予約日
    ''', (store_id, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
    
    reservations_by_date = {}
    for row in cur.fetchall():
        reservations_by_date[row['予約日']] = {
            'count': row['count'],
            'guests': row['guests']
        }
    
    conn.close()
    
    return render_template('admin_reservation_calendar.html',
                         store=store,
                         year=year,
                         month=month,
                         reservations_by_date=reservations_by_date)

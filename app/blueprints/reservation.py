# -*- coding: utf-8 -*-
"""
予約システム - 顧客向けBlueprint
"""
from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime, timedelta
import secrets
import store_db
from db_config import get_db_connection, get_cursor, execute_query

reservation_bp = Blueprint('reservation', __name__, url_prefix='/store/<store_slug>/reservation')

def generate_reservation_number():
    """予約番号を生成（例: RES20231221-ABC123）"""
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = secrets.token_hex(3).upper()
    return f"RES{date_str}-{random_str}"

@reservation_bp.route('/')
def index(store_slug):
    """予約フォーム表示"""
    # 店舗情報を取得
    store = store_db.get_store_by_slug(store_slug)
    if not store:
        return "店舗が見つかりません", 404
    
    # 予約設定を取得
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    execute_query(cur, '''
        SELECT * FROM "T_店舗_予約設定"
        WHERE store_id = ?
    ''', (store['id'],))
    settings = cur.fetchone()
    
    # テーブル設定を取得
    execute_query(cur, '''
        SELECT * FROM "T_テーブル設定"
        WHERE store_id = ? AND 有効 = 1
        ORDER BY 表示順序, 座席数
    ''', (store['id'],))
    tables = cur.fetchall()
    
    conn.close()
    
    # デフォルト設定
    if not settings:
        settings = {
            '営業開始時刻': '11:00',
            '営業終了時刻': '22:00',
            '最終入店時刻': '21:00',
            '予約単位_分': 30,
            '予約受付日数': 60,
            '予約受付可否': 1
        }
    
    return render_template('reservation_form.html', 
                         store=store, 
                         settings=settings,
                         tables=tables)

@reservation_bp.route('/api/availability', methods=['POST'])
def check_availability(store_slug):
    """指定日時の空席状況を確認"""
    data = request.get_json()
    reservation_date = data.get('date')
    reservation_time = data.get('time')
    party_size = int(data.get('party_size', 1))
    
    # 店舗情報を取得
    store = store_db.get_store_by_slug(store_slug)
    if not store:
        return jsonify({'error': '店舗が見つかりません'}), 404
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # テーブル設定を取得
    execute_query(cur, '''
        SELECT * FROM "T_テーブル設定"
        WHERE store_id = ? AND 有効 = 1 AND 座席数 >= ?
        ORDER BY 座席数
    ''', (store['id'], party_size))
    available_tables = cur.fetchall()
    
    if not available_tables:
        conn.close()
        return jsonify({
            'available': False,
            'message': f'{party_size}名様のテーブルがありません'
        })
    
    # 既存の予約を確認
    execute_query(cur, '''
        SELECT テーブル割当, COUNT(*) as count
        FROM "T_予約"
        WHERE store_id = ? 
          AND 予約日 = ? 
          AND 予約時刻 = ?
          AND ステータス = 'confirmed'
        GROUP BY テーブル割当
    ''', (store['id'], reservation_date, reservation_time))
    
    reserved_tables = {}
    for row in cur.fetchall():
        if row['テーブル割当']:
            reserved_tables[row['テーブル割当']] = row['count']
    
    conn.close()
    
    # 空席チェック
    for table in available_tables:
        table_name = table['テーブル名']
        total_count = table['テーブル数']
        reserved_count = reserved_tables.get(table_name, 0)
        
        if reserved_count < total_count:
            return jsonify({
                'available': True,
                'table_type': table_name,
                'seats': table['座席数'],
                'available_count': total_count - reserved_count
            })
    
    return jsonify({
        'available': False,
        'message': 'この時間帯は満席です'
    })

@reservation_bp.route('/api/time_slots', methods=['POST'])
def get_time_slots(store_slug):
    """指定日の予約可能時間枠を取得"""
    data = request.get_json()
    reservation_date = data.get('date')
    party_size = int(data.get('party_size', 1))
    
    # 店舗情報を取得
    store = store_db.get_store_by_slug(store_slug)
    if not store:
        return jsonify({'error': '店舗が見つかりません'}), 404
    
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # 予約設定を取得
    execute_query(cur, '''
        SELECT * FROM "T_店舗_予約設定"
        WHERE store_id = ?
    ''', (store['id'],))
    settings = cur.fetchone()
    
    conn.close()
    
    # デフォルト設定
    if not settings:
        settings = {
            '営業開始時刻': '11:00',
            '最終入店時刻': '21:00',
            '予約単位_分': 30
        }
    
    # 時間枠を生成
    start_time = datetime.strptime(settings['営業開始時刻'], '%H:%M')
    end_time = datetime.strptime(settings['最終入店時刻'], '%H:%M')
    interval = timedelta(minutes=settings['予約単位_分'])
    
    time_slots = []
    current_time = start_time
    
    while current_time <= end_time:
        time_str = current_time.strftime('%H:%M')
        
        # この時間枠の空席状況を確認
        availability_check = check_availability_internal(
            store['id'], 
            reservation_date, 
            time_str, 
            party_size
        )
        
        time_slots.append({
            'time': time_str,
            'available': availability_check['available'],
            'display': current_time.strftime('%H:%M')
        })
        
        current_time += interval
    
    return jsonify({'time_slots': time_slots})

def check_availability_internal(store_id, reservation_date, reservation_time, party_size):
    """内部用の空席確認関数"""
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    # テーブル設定を取得
    execute_query(cur, '''
        SELECT * FROM "T_テーブル設定"
        WHERE store_id = ? AND 有効 = 1 AND 座席数 >= ?
        ORDER BY 座席数
    ''', (store_id, party_size))
    available_tables = cur.fetchall()
    
    if not available_tables:
        conn.close()
        return {'available': False}
    
    # 既存の予約を確認
    execute_query(cur, '''
        SELECT テーブル割当, COUNT(*) as count
        FROM "T_予約"
        WHERE store_id = ? 
          AND 予約日 = ? 
          AND 予約時刻 = ?
          AND ステータス = 'confirmed'
        GROUP BY テーブル割当
    ''', (store_id, reservation_date, reservation_time))
    
    reserved_tables = {}
    for row in cur.fetchall():
        if row['テーブル割当']:
            reserved_tables[row['テーブル割当']] = row['count']
    
    conn.close()
    
    # 空席チェック
    for table in available_tables:
        table_name = table['テーブル名']
        total_count = table['テーブル数']
        reserved_count = reserved_tables.get(table_name, 0)
        
        if reserved_count < total_count:
            return {'available': True, 'table_type': table_name}
    
    return {'available': False}

@reservation_bp.route('/api/submit', methods=['POST'])
def submit_reservation(store_slug):
    """予約を登録"""
    data = request.get_json()
    
    # 店舗情報を取得
    store = store_db.get_store_by_slug(store_slug)
    if not store:
        return jsonify({'error': '店舗が見つかりません'}), 404
    
    # バリデーション
    required_fields = ['date', 'time', 'party_size', 'name', 'phone']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field}は必須です'}), 400
    
    reservation_date = data.get('date')
    reservation_time = data.get('time')
    party_size = int(data.get('party_size'))
    customer_name = data.get('name')
    customer_phone = data.get('phone')
    customer_email = data.get('email', '')
    notes = data.get('notes', '')
    
    # 空席確認
    availability = check_availability_internal(
        store['id'], 
        reservation_date, 
        reservation_time, 
        party_size
    )
    
    if not availability['available']:
        return jsonify({'error': 'この時間帯は満席です'}), 400
    
    # 予約番号を生成
    reservation_number = generate_reservation_number()
    
    # 予約を登録
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    execute_query(cur, '''
        INSERT INTO "T_予約" (
            store_id, 予約番号, 予約日, 予約時刻, 人数,
            顧客名, 顧客電話番号, 顧客メール, 特記事項,
            ステータス, テーブル割当
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        store['id'],
        reservation_number,
        reservation_date,
        reservation_time,
        party_size,
        customer_name,
        customer_phone,
        customer_email,
        notes,
        'confirmed',
        availability.get('table_type')
    ))
    
    conn.commit()
    reservation_id = cur.lastrowid
    conn.close()
    
    return jsonify({
        'success': True,
        'reservation_number': reservation_number,
        'reservation_id': reservation_id
    })

@reservation_bp.route('/confirmation/<reservation_number>')
def confirmation(store_slug, reservation_number):
    """予約確認画面"""
    # 店舗情報を取得
    store = store_db.get_store_by_slug(store_slug)
    if not store:
        return "店舗が見つかりません", 404
    
    # 予約情報を取得
    conn = get_db_connection()
    cur = get_cursor(conn)
    
    execute_query(cur, '''
        SELECT * FROM "T_予約"
        WHERE store_id = ? AND 予約番号 = ?
    ''', (store['id'], reservation_number))
    
    reservation = cur.fetchone()
    conn.close()
    
    if not reservation:
        return "予約が見つかりません", 404
    
    return render_template('reservation_confirmation.html',
                         store=store,
                         reservation=reservation)

"""
スタンプカード機能のBlueprint
顧客向けのスタンプカード機能を提供
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
import store_db
from functools import wraps
from datetime import datetime, timedelta

stampcard_bp = Blueprint('stampcard', __name__, url_prefix='/store/<store_slug>/stampcard')

def customer_login_required(f):
    """顧客ログインが必要なルートのデコレーター"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'customer_id' not in session:
            flash('ログインが必要です', 'error')
            return redirect(url_for('stampcard.customer_login', store_slug=kwargs.get('store_slug')))
        return f(*args, **kwargs)
    return decorated_function

@stampcard_bp.before_request
def load_store():
    """リクエスト前に店舗情報を読み込む"""
    store_slug = request.view_args.get('store_slug')
    if store_slug:
        conn = store_db.get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, 名称 as name FROM "T_店舗" WHERE slug = %s', (store_slug,))
        store = cur.fetchone()
        conn.close()
        
        if store:
            g.store_id = store[0]
            g.store_name = store[1]
            g.store_slug = store_slug
        else:
            g.store_id = None
            g.store_name = None
            g.store_slug = store_slug

# ===== 顧客認証 =====

@stampcard_bp.route('/register', methods=['GET', 'POST'])
def customer_register(store_slug):
    """顧客登録"""
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # バリデーション
        if not name or not password:
            flash('名前とパスワードは必須です', 'error')
            return render_template('stampcard_register.html', store_name=g.store_name)
        
        if not phone and not email:
            flash('電話番号またはメールアドレスのいずれかは必須です', 'error')
            return render_template('stampcard_register.html', store_name=g.store_name)
        
        conn = store_db.get_db_connection()
        cur = conn.cursor()
        
        try:
            # 重複チェック
            if phone:
                cur.execute('SELECT id FROM "T_顧客" WHERE store_id = %s AND phone = %s', (g.store_id, phone))
                if cur.fetchone():
                    flash('この電話番号は既に登録されています', 'error')
                    conn.close()
                    return render_template('stampcard_register.html', store_name=g.store_name)
            
            if email:
                cur.execute('SELECT id FROM "T_顧客" WHERE store_id = %s AND email = %s', (g.store_id, email))
                if cur.fetchone():
                    flash('このメールアドレスは既に登録されています', 'error')
                    conn.close()
                    return render_template('stampcard_register.html', store_name=g.store_name)
            
            # 顧客登録
            password_hash = generate_password_hash(password)
            cur.execute('''
                INSERT INTO "T_顧客" (store_id, name, phone, email, password_hash, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (g.store_id, name, phone, email, password_hash))
            
            customer_id = cur.lastrowid
            
            # スタンプカード作成
            cur.execute('''
                INSERT INTO "T_スタンプカード" (customer_id, store_id, current_stamps, total_stamps, rewards_used, created_at, updated_at)
                VALUES (%s, %s, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (customer_id, g.store_id))
            
            conn.commit()
            conn.close()
            
            # 自動ログイン
            session['customer_id'] = customer_id
            session['customer_name'] = name
            session['store_id'] = g.store_id
            
            flash('登録が完了しました！', 'success')
            return redirect(url_for('stampcard.customer_mypage', store_slug=store_slug))
            
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f'登録に失敗しました: {str(e)}', 'error')
            return render_template('stampcard_register.html', store_name=g.store_name)
    
    return render_template('stampcard_register.html', store_name=g.store_name)

@stampcard_bp.route('/login', methods=['GET', 'POST'])
def customer_login(store_slug):
    """顧客ログイン"""
    if request.method == 'POST':
        login_id = request.form.get('login_id')  # 電話番号またはメールアドレス
        password = request.form.get('password')
        
        if not login_id or not password:
            flash('ログインIDとパスワードを入力してください', 'error')
            return render_template('stampcard_login.html', store_name=g.store_name)
        
        conn = store_db.get_db_connection()
        cur = conn.cursor()
        
        # 電話番号またはメールアドレスで検索
        cur.execute('''
            SELECT id, name, password_hash 
            FROM "T_顧客" 
            WHERE store_id = %s AND (phone = %s OR email = %s)
        ''', (g.store_id, login_id, login_id))
        
        customer = cur.fetchone()
        
        if customer and check_password_hash(customer[2], password):
            # ログイン成功
            session['customer_id'] = customer[0]
            session['customer_name'] = customer[1]
            session['store_id'] = g.store_id
            
            # 最終ログイン時刻を更新
            cur.execute('UPDATE "T_顧客" SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (customer[0],))
            conn.commit()
            conn.close()
            
            flash('ログインしました', 'success')
            return redirect(url_for('stampcard.customer_mypage', store_slug=store_slug))
        else:
            conn.close()
            flash('ログインIDまたはパスワードが正しくありません', 'error')
            return render_template('stampcard_login.html', store_name=g.store_name)
    
    return render_template('stampcard_login.html', store_name=g.store_name)

@stampcard_bp.route('/logout')
def customer_logout(store_slug):
    """顧客ログアウト"""
    session.pop('customer_id', None)
    session.pop('customer_name', None)
    session.pop('store_id', None)
    flash('ログアウトしました', 'info')
    return redirect(url_for('stampcard.customer_login', store_slug=store_slug))

# ===== 顧客向け画面 =====

@stampcard_bp.route('/mypage')
@customer_login_required
def customer_mypage(store_slug):
    """顧客マイページ"""
    customer_id = session.get('customer_id')
    
    conn = store_db.get_db_connection()
    cur = conn.cursor()
    
    # スタンプカード情報取得
    cur.execute('''
        SELECT id, current_stamps, total_stamps, rewards_used, created_at
        FROM "T_スタンプカード"
        WHERE customer_id = %s AND store_id = %s
    ''', (customer_id, g.store_id))
    card = cur.fetchone()
    
    # スタンプカード設定取得
    cur.execute('''
        SELECT required_stamps, reward_description, card_title, use_multi_rewards
        FROM "T_店舗_スタンプカード設定"
        WHERE store_id = %s
    ''', (g.store_id,))
    settings = cur.fetchone()
    
    # 複数特典設定取得
    cur.execute('''
        SELECT id, required_stamps, reward_description, is_repeatable
        FROM "T_特典設定"
        WHERE store_id = %s AND enabled = 1
        ORDER BY required_stamps
    ''', (g.store_id,))
    multi_rewards = cur.fetchall()
    
    # スタンプ履歴取得（最新10件）
    cur.execute('''
        SELECT stamps_added, action_type, note, created_at
        FROM "T_スタンプ履歴"
        WHERE customer_id = %s AND store_id = %s
        ORDER BY created_at DESC
        LIMIT 10
    ''', (customer_id, g.store_id))
    history = cur.fetchall()
    
    # 特典利用履歴取得（最新5件）
    cur.execute('''
        SELECT stamps_used, reward_description, created_at
        FROM "T_特典利用履歴"
        WHERE customer_id = %s AND store_id = %s
        ORDER BY created_at DESC
        LIMIT 5
    ''', (customer_id, g.store_id))
    reward_history = cur.fetchall()
    
    conn.close()
    
    # デフォルト設定
    if not settings:
        settings = (10, '1品無料', 'スタンプカード', 0)
    
    required_stamps = settings[0]
    reward_description = settings[1]
    card_title = settings[2]
    use_multi_rewards = settings[3] if len(settings) > 3 else 0
    
    # スタンプカードがない場合は作成
    if not card:
        conn = store_db.get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO "T_スタンプカード" (customer_id, store_id, current_stamps, total_stamps, rewards_used, created_at, updated_at)
            VALUES (%s, %s, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (customer_id, g.store_id))
        conn.commit()
        card_id = cur.lastrowid
        conn.close()
        card = (card_id, 0, 0, 0, datetime.now())
    
    # 特典データの準備
    rewards_list = []
    if use_multi_rewards and multi_rewards:
        # 複数特典モード
        for reward in multi_rewards:
            reward_id = reward[0]
            req_stamps = reward[1]
            desc = reward[2]
            is_repeatable = reward[3]
            
            # この特典が利用可能かチェック
            can_use = False
            if card[1] >= req_stamps:
                if is_repeatable:
                    # 繰り返し可能な場合、常に利用可能
                    can_use = True
                else:
                    # 初回のみの場合、利用済みかチェック
                    cur.execute('''
                        SELECT id FROM "T_特典利用履歴"
                        WHERE customer_id = %s AND store_id = %s AND reward_id = %s
                    ''', (customer_id, g.store_id, reward_id))
                    if not cur.fetchone():
                        can_use = True
            
            rewards_list.append({
                'id': reward_id,
                'required_stamps': req_stamps,
                'description': desc,
                'is_repeatable': is_repeatable,
                'can_use': can_use,
                'achieved': card[1] >= req_stamps
            })
    
    card_data = {
        'id': card[0],
        'current_stamps': card[1],
        'total_stamps': card[2],
        'rewards_used': card[3],
        'created_at': card[4],
        'required_stamps': required_stamps,
        'reward_description': reward_description,
        'card_title': card_title,
        'can_use_reward': card[1] >= required_stamps if not use_multi_rewards else False,
        'use_multi_rewards': use_multi_rewards,
        'rewards_list': rewards_list
    }
    
    return render_template('stampcard_mypage.html',
                         store_name=g.store_name,
                         customer_name=session.get('customer_name'),
                         card=card_data,
                         history=history,
                         reward_history=reward_history)

@stampcard_bp.route('/scan', methods=['GET', 'POST'])
@customer_login_required
def scan_qr(store_slug):
    """QRコードスキャン（スタンプ付与）"""
    if request.method == 'POST':
        customer_id = session.get('customer_id')
        
        conn = store_db.get_db_connection()
        cur = conn.cursor()
        
        try:
            # 今日既にスタンプを取得しているかチェック
            today = datetime.now().date()
            cur.execute('''
                SELECT id FROM "T_スタンプ履歴"
                WHERE customer_id = %s AND store_id = %s 
                AND DATE(created_at) = %s
                AND action_type = 'add'
            ''', (customer_id, g.store_id, today))
            
            if cur.fetchone():
                conn.close()
                flash('本日は既にスタンプを取得しています', 'warning')
                return redirect(url_for('stampcard.customer_mypage', store_slug=store_slug))
            
            # スタンプカード取得
            cur.execute('''
                SELECT id, current_stamps, total_stamps
                FROM "T_スタンプカード"
                WHERE customer_id = %s AND store_id = %s
            ''', (customer_id, g.store_id))
            card = cur.fetchone()
            
            if not card:
                conn.close()
                flash('スタンプカードが見つかりません', 'error')
                return redirect(url_for('stampcard.customer_mypage', store_slug=store_slug))
            
            card_id = card[0]
            current_stamps = card[1]
            total_stamps = card[2]
            
            # スタンプを追加
            cur.execute('''
                UPDATE "T_スタンプカード"
                SET current_stamps = current_stamps + 1,
                    total_stamps = total_stamps + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (card_id,))
            
            # スタンプ履歴を記録
            cur.execute('''
                INSERT INTO "T_スタンプ履歴" (card_id, customer_id, store_id, stamps_added, action_type, note, created_by, created_at)
                VALUES (%s, %s, %s, 1, 'add', 'QRコードスキャン', 'customer', CURRENT_TIMESTAMP)
            ''', (card_id, customer_id, g.store_id))
            
            conn.commit()
            conn.close()
            
            flash(f'スタンプを1個獲得しました！（現在: {current_stamps + 1}個）', 'success')
            return redirect(url_for('stampcard.customer_mypage', store_slug=store_slug))
            
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f'スタンプの付与に失敗しました: {str(e)}', 'error')
            return redirect(url_for('stampcard.customer_mypage', store_slug=store_slug))
    
    return render_template('stampcard_scan.html', store_name=g.store_name)

@stampcard_bp.route('/use_reward', methods=['POST'])
@customer_login_required
def use_reward(store_slug):
    """特典を使用する"""
    customer_id = session.get('customer_id')
    
    conn = store_db.get_db_connection()
    cur = conn.cursor()
    
    try:
        # スタンプカード取得
        cur.execute('''
            SELECT id, current_stamps
            FROM "T_スタンプカード"
            WHERE customer_id = %s AND store_id = %s
        ''', (customer_id, g.store_id))
        card = cur.fetchone()
        
        if not card:
            conn.close()
            return jsonify({'success': False, 'message': 'スタンプカードが見つかりません'})
        
        card_id = card[0]
        current_stamps = card[1]
        
        # 必要スタンプ数取得
        cur.execute('''
            SELECT required_stamps, reward_description
            FROM "T_店舗_スタンプカード設定"
            WHERE store_id = %s
        ''', (g.store_id,))
        settings = cur.fetchone()
        
        required_stamps = settings[0] if settings else 10
        reward_description = settings[1] if settings else '1品無料'
        
        # スタンプが足りるかチェック
        if current_stamps < required_stamps:
            conn.close()
            return jsonify({'success': False, 'message': f'スタンプが足りません（現在: {current_stamps}個、必要: {required_stamps}個）'})
        
        # スタンプを消費
        cur.execute('''
            UPDATE "T_スタンプカード"
            SET current_stamps = current_stamps - %s,
                rewards_used = rewards_used + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (required_stamps, card_id))
        
        # 特典利用履歴を記録
        cur.execute('''
            INSERT INTO "T_特典利用履歴" (card_id, customer_id, store_id, stamps_used, reward_description, used_by, created_at)
            VALUES (%s, %s, %s, %s, %s, 'customer', CURRENT_TIMESTAMP)
        ''', (card_id, customer_id, g.store_id, required_stamps, reward_description))
        
        # スタンプ履歴を記録
        cur.execute('''
            INSERT INTO "T_スタンプ履歴" (card_id, customer_id, store_id, stamps_added, action_type, note, created_by, created_at)
            VALUES (%s, %s, %s, %s, 'use', %s, 'customer', CURRENT_TIMESTAMP)
        ''', (card_id, customer_id, g.store_id, -required_stamps, f'特典利用: {reward_description}'))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '特典を利用しました！', 'remaining_stamps': current_stamps - required_stamps})
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'message': f'特典の利用に失敗しました: {str(e)}'})

@stampcard_bp.route('/use_multi_reward', methods=['POST'])
@customer_login_required
def use_multi_reward(store_slug):
    """複数特典を使用する"""
    customer_id = session.get('customer_id')
    data = request.get_json()
    reward_id = data.get('reward_id')
    
    if not reward_id:
        return jsonify({'success': False, 'message': '特典IDが指定されていません'})
    
    conn = store_db.get_db_connection()
    cur = conn.cursor()
    
    try:
        # 特典設定取得
        cur.execute('''
            SELECT required_stamps, reward_description, is_repeatable
            FROM "T_特典設定"
            WHERE id = %s AND store_id = %s AND enabled = 1
        ''', (reward_id, g.store_id))
        reward = cur.fetchone()
        
        if not reward:
            conn.close()
            return jsonify({'success': False, 'message': '特典が見つかりません'})
        
        required_stamps = reward[0]
        reward_description = reward[1]
        is_repeatable = reward[2]
        
        # スタンプカード取得
        cur.execute('''
            SELECT id, current_stamps
            FROM "T_スタンプカード"
            WHERE customer_id = %s AND store_id = %s
        ''', (customer_id, g.store_id))
        card = cur.fetchone()
        
        if not card:
            conn.close()
            return jsonify({'success': False, 'message': 'スタンプカードが見つかりません'})
        
        card_id = card[0]
        current_stamps = card[1]
        
        # スタンプが足りるかチェック
        if current_stamps < required_stamps:
            conn.close()
            return jsonify({'success': False, 'message': f'スタンプが足りません（現在: {current_stamps}個、必要: {required_stamps}個）'})
        
        # 繰り返し不可の場合、利用済みかチェック
        if not is_repeatable:
            cur.execute('''
                SELECT id FROM "T_特典利用履歴"
                WHERE customer_id = %s AND store_id = %s AND reward_id = %s
            ''', (customer_id, g.store_id, reward_id))
            if cur.fetchone():
                conn.close()
                return jsonify({'success': False, 'message': 'この特典は既に利用済みです'})
        
        # スタンプを消費（複数特典モードではスタンプを減らさない）
        # 特典利用履歴を記録
        cur.execute('''
            INSERT INTO "T_特典利用履歴" (card_id, customer_id, store_id, stamps_used, reward_description, reward_id, used_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'customer', CURRENT_TIMESTAMP)
        ''', (card_id, customer_id, g.store_id, 0, reward_description, reward_id))
        
        # 特典利用回数を更新
        cur.execute('''
            UPDATE "T_スタンプカード"
            SET rewards_used = rewards_used + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (card_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '特典を利用しました！'})
        
    except Exception as e:
        conn.rollback()
        conn.close()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'特典の利用に失敗しました: {str(e)}'})

# ===== 店舗用QRコード =====

@stampcard_bp.route('/qr')
def store_qr(store_slug):
    """店舗用QRコード表示"""
    return render_template('stampcard_store_qr.html', 
                         store_name=g.store_name,
                         store_slug=store_slug)

# -*- coding: utf-8 -*-
"""
アンケート管理画面 Blueprint
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, session, g
import os
import json
import csv
from io import StringIO
from dataclasses import asdict
from ..utils.decorators import require_roles
from ..utils import ROLES
from ..utils.admin_auth import (
    require_admin_login,
    get_current_admin,
    authenticate_admin,
    login_admin_session
)
from ..utils.config import load_config, save_config
from ..models import Symbol

bp = Blueprint('survey_admin', __name__, url_prefix='/admin')

# パス設定
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
SURVEY_DATA_PATH = os.path.join(DATA_DIR, "survey_responses.json")


# ===== 認証 =====
@bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """管理者ログイン"""
    if request.method == "POST":
        store_code = request.form.get("store_code", "").strip()
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")
        
        admin = authenticate_admin(store_code, login_id, password)
        
        if admin:
            login_admin_session(admin)
            flash(f"ようこそ、{admin['name']}さん", "success")
            next_url = request.args.get("next") or url_for("survey_admin.admin_dashboard")
            return redirect(next_url)
        else:
            flash("店舗コード、ログインID、またはパスワードが正しくありません", "error")
            return render_template("admin_login.html", 
                                 store_code=store_code, 
                                 login_id=login_id)
    
    return render_template("admin_login.html")


@bp.route("/logout")
def admin_logout():
    """管理者ログアウト"""
    logout_admin_session()
    flash("ログアウトしました", "info")
    return redirect(url_for("survey_admin.admin_login"))


# ===== ダッシュボード =====
@bp.route("")
@require_roles(ROLES["ADMIN"])
def admin_dashboard():
    """管理画面ダッシュボード"""
# 統一認証システムからユーザー情報を取得
    admin = {
        'name': session.get('user_name', '管理者'),
        'login_id': session.get('login_id', ''),
        'store_name': session.get('store_name', '')
    }
    
    # アンケート回答データを読み込み
    survey_responses = []
    if os.path.exists(SURVEY_DATA_PATH):
        with open(SURVEY_DATA_PATH, "r", encoding="utf-8") as f:
            survey_responses = json.load(f)
    
    # 統計情報を計算
    total_responses = len(survey_responses)
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for response in survey_responses:
        rating = response.get("rating", 0)
        if rating in rating_counts:
            rating_counts[rating] += 1
    
    avg_rating = 0
    if total_responses > 0:
        total_rating = sum(r.get("rating", 0) for r in survey_responses)
        avg_rating = round(total_rating / total_responses, 2)
    
    return render_template("admin_dashboard.html",
                         admin=admin,
                         total_responses=total_responses,
                         rating_counts=rating_counts,
                         avg_rating=avg_rating,
                         recent_responses=survey_responses[-10:][::-1])


@bp.route("/responses")
@require_roles(ROLES["ADMIN"])
def admin_responses():
    """全回答データを表示"""
# 統一認証システムからユーザー情報を取得
    admin = {
        'name': session.get('user_name', '管理者'),
        'login_id': session.get('login_id', ''),
        'store_name': session.get('store_name', '')
    }
    
    survey_responses = []
    if os.path.exists(SURVEY_DATA_PATH):
        with open(SURVEY_DATA_PATH, "r", encoding="utf-8") as f:
            survey_responses = json.load(f)
    
    # 最新順にソート
    survey_responses.reverse()
    
    return render_template("admin_responses.html",
                         admin=admin,
                         responses=survey_responses)


@bp.route("/export/csv")
@require_roles(ROLES["ADMIN"])
def admin_export_csv():
    """回答データをCSVでエクスポート"""
    survey_responses = []
    if os.path.exists(SURVEY_DATA_PATH):
        with open(SURVEY_DATA_PATH, "r", encoding="utf-8") as f:
            survey_responses = json.load(f)
    
    # CSV作成
    si = StringIO()
    writer = csv.writer(si)
    
    # ヘッダー
    writer.writerow(['ID', '回答日時', '評価', '訪問目的', '雰囲気', 'おすすめ度', 'コメント', 'AI生成口コミ'])
    
    # データ
    for r in survey_responses:
        writer.writerow([
            r.get('id', ''),
            r.get('timestamp', ''),
            r.get('rating', ''),
            r.get('visit_purpose', ''),
            ', '.join(r.get('atmosphere', [])),
            r.get('recommend', ''),
            r.get('comment', ''),
            r.get('generated_review', '')
        ])
    
    # レスポンス作成
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=survey_responses.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    
    return output


# ===== 設定 =====
@bp.route("/settings", methods=["GET", "POST"])
@require_roles(ROLES["SYSTEM_ADMIN"], ROLES["TENANT_ADMIN"], ROLES["ADMIN"])
def admin_settings():
    """管理画面設定"""
# 統一認証システムからユーザー情報を取得
    admin = {
        'name': session.get('user_name', '管理者'),
        'login_id': session.get('login_id', ''),
        'store_name': session.get('store_name', '')
    }
    
    # 設定ファイルのパス
    settings_path = os.path.join(DATA_DIR, "settings.json")
    
    # 設定を読み込み
    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    else:
        settings = {
            "google_review_url": "#",
            "survey_complete_message": "アンケートにご協力いただきありがとうございます！スロットをお楽しみください。"
        }
    
    if request.method == "POST":
        # フォームデータを取得
        google_url = request.form.get("google_review_url", "").strip()
        survey_message = request.form.get("survey_complete_message", "").strip()
        
        # 景品設定を取得
        prize_count = int(request.form.get("prize_count", 0))
        prizes = []
        for i in range(prize_count):
            min_score = int(request.form.get(f"prize_min_score_{i}", 0))
            max_score_str = request.form.get(f"prize_max_score_{i}", "").strip()
            max_score = int(max_score_str) if max_score_str else None
            rank = request.form.get(f"prize_rank_{i}", "").strip()
            name = request.form.get(f"prize_name_{i}", "").strip()
            if rank and name:
                prize = {
                    "min_score": min_score,
                    "rank": rank,
                    "name": name
                }
                if max_score is not None:
                    prize["max_score"] = max_score
                prizes.append(prize)
        
        # 点数で降順ソート
        prizes.sort(key=lambda x: x["min_score"], reverse=True)
        
        # 設定を更新
        settings["google_review_url"] = google_url
        settings["survey_complete_message"] = survey_message
        settings["prizes"] = prizes
        
        # ファイルに保存
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        
        flash("設定を更新しました", "success")
        return redirect(url_for("survey_admin.admin_settings"))
    
    # デフォルトの景品設定
    default_prizes = [
        {"min_score": 500, "rank": "1等", "name": "ランチ無料券"},
        {"min_score": 100, "rank": "2等", "name": "ドリンク1杯無料"},
        {"min_score": 50, "rank": "3等", "name": "デザート50円引き"},
        {"min_score": 20, "rank": "4等", "name": "次回5%オフ"},
        {"min_score": 0, "rank": "参加賞", "name": "ご参加ありがとうございました"}
    ]
    
    # スロット設定を読み込み
    slot_config = load_config()
    
    # 店舗情報を取得
    from ..utils.db import get_db_connection, _sql
    db = get_db_connection()
    store_id = session.get('store_id')
    import sys
    sys.stderr.write(f"DEBUG admin_settings: store_id from session = {store_id}\n")
    sys.stderr.write(f"DEBUG admin_settings: session keys = {list(session.keys())}\n")
    sys.stderr.flush()
    store = None
    if store_id:
        cur = db.cursor()
        cur.execute(_sql(db, 'SELECT id, tenant_id, 名称, slug, openai_api_key FROM "T_店舗" WHERE id = %s'), (store_id,))
        row = cur.fetchone()
        if row:
            store = {
                'id': row[0],
                'tenant_id': row[1],
                '名称': row[2],
                'slug': row[3],
                'openai_api_key': row[4]
            }
        sys.stderr.write(f"DEBUG admin_settings: store = {store}\n")
        sys.stderr.flush()
    else:
        sys.stderr.write("DEBUG admin_settings: store_id is None, cannot fetch store\n")
        sys.stderr.flush()
    
    return render_template("admin_settings.html",
                         admin=admin,
                         store=store,
                         slot_app=store,  # slot_appとstoreは同じオブジェクト
                         google_review_url=settings.get("google_review_url", "#"),
                         survey_complete_message=settings.get("survey_complete_message", "アンケートにご協力いただきありがとうございます！スロットをお楽しみください。"),
                         prizes=settings.get("prizes", default_prizes),
                         slot_config=asdict(slot_config))


# 以下のルートはstore_slot_settings_routes.pyで定義されているためコメントアウト
# @bp.route("/save_prizes", methods=["POST"])
# @require_roles(ROLES["ADMIN"])
# def admin_save_prizes():
#     """景品設定を保存"""
#     try:
#         data = request.get_json()
#         prizes = data.get('prizes', [])
#         
#         # 点数で降順ソート
#         prizes.sort(key=lambda x: x["min_score"], reverse=True)
#         
#         # 設定ファイルのパス
#         settings_path = os.path.join(DATA_DIR, "settings.json")
#         
#         # 設定を読み込み
#         if os.path.exists(settings_path):
#             with open(settings_path, "r", encoding="utf-8") as f:
#                 settings = json.load(f)
#         else:
#             settings = {}
#         
#         # 景品設定を更新
#         settings["prizes"] = prizes
#         
#         # ファイルに保存
#         with open(settings_path, "w", encoding="utf-8") as f:
#             json.dump(settings, f, ensure_ascii=False, indent=2)
#         
#         return jsonify({"ok": True})
#     except Exception as e:
#         return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/save_slot_config", methods=["POST"])
@require_roles(ROLES["ADMIN"])
def admin_save_slot_config():
    """スロット設定を保存"""
    from ..utils.slot_logic import recalc_probs_inverse_and_expected
    
    try:
        data = request.get_json()
        symbols_data = data.get('symbols', [])
        
        # シンボルデータを変換
        symbols = [Symbol(**s) for s in symbols_data]
        
        # 設定を読み込み
        cfg = load_config()
        cfg.symbols = symbols
        
        # 確率を再計算
        recalc_probs_inverse_and_expected(cfg)
        
        # 保存
        save_config(cfg)
        
        return jsonify({"ok": True, "expected_total_5": cfg.expected_total_5})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/optimize_probabilities", methods=["POST"])
@require_roles(ROLES["ADMIN"])
def admin_optimize_probabilities():
    """確率を最適化"""
    try:
        from optimizer import optimize_symbol_probabilities
        
        data = request.get_json()
        symbols_data = data.get('symbols', [])
        target_probs = data.get('target_probabilities', {})
        
        # シンボルデータを変換
        symbols = [Symbol(**s) for s in symbols_data]
        
        # 最適化実行
        optimized_symbols = optimize_symbol_probabilities(symbols, target_probs)
        
        # 設定を更新
        cfg = load_config()
        cfg.symbols = optimized_symbols
        cfg.target_probabilities = target_probs
        save_config(cfg)
        
        return jsonify({
            "ok": True,
            "symbols": [asdict(s) for s in optimized_symbols]
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



@bp.route("/save_openai_key", methods=["POST"])
@require_roles(ROLES["ADMIN"])
def admin_save_openai_key():
    """店舗別OpenAI APIキーを保存"""
    store_id = session.get('store_id')
    if not store_id:
        flash("店舗情報がセッションにありません", "error")
        return redirect(url_for("survey_admin.admin_settings"))

    openai_api_key = request.form.get("openai_api_key", "").strip()
    
    from ..utils.db import get_db_connection, _sql
    db = get_db_connection()
    cur = db.cursor()
    
    try:
        # T_店舗テーブルのopenai_api_keyを更新
        cur.execute(_sql(db, '''
            UPDATE "T_店舗"
            SET openai_api_key = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        '''), (openai_api_key if openai_api_key else None, store_id))
        db.commit()
        flash("OpenAI APIキーを保存しました", "success")
    except Exception as e:
        db.rollback()
        flash(f"APIキーの保存に失敗しました: {e}", "error")
    finally:
        db.close()
        
    return redirect(url_for("survey_admin.admin_settings"))


@bp.route("/survey_editor", methods=["GET", "POST"])
@require_roles(ROLES["ADMIN"], ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def admin_survey_editor():
    """アンケート作成・編集画面"""
    from datetime import datetime
    from flask import session
    admin = {
        'id': session.get('user_id'),
        'name': session.get('user_name'),
        'store_code': ''
    }
    
    # アンケート設定ファイルのパス
    survey_config_path = os.path.join(DATA_DIR, "survey_config.json")
    
    if request.method == "POST":
        # フォームデータを取得
        survey_title = request.form.get("survey_title", "").strip()
        survey_description = request.form.get("survey_description", "").strip()
        
        # 質問データを解析
        questions = []
        question_indices = set()
        
        # すべてのフォームキーから質問インデックスを抽出
        for key in request.form.keys():
            if key.startswith("questions["):
                index_str = key.split("[")[1].split("]")[0]
                try:
                    question_indices.add(int(index_str))
                except ValueError:
                    continue
        
        # 各質問を処理
        for idx in sorted(question_indices):
            question_text = request.form.get(f"questions[{idx}][text]", "").strip()
            question_type = request.form.get(f"questions[{idx}][type]", "text")
            
            if not question_text:
                continue
            
            # 必須フラグをフォームから取得（チェックボックスがオンの場合のみtrue）
            is_required = request.form.get(f"questions[{idx}][required]") == "true"
            
            question = {
                "id": idx + 1,
                "text": question_text,
                "type": question_type,
                "required": is_required
            }
            
            # 選択肢がある場合
            if question_type in ["radio", "checkbox"]:
                options = request.form.getlist(f"questions[{idx}][options][]")
                question["options"] = [opt.strip() for opt in options if opt.strip()]
            
            questions.append(question)
        
        # 設定を保存
        survey_config = {
            "title": survey_title,
            "description": survey_description,
            "questions": questions,
            "updated_at": datetime.now().isoformat()
        }
        
        # JSONファイルに保存
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(survey_config_path, "w", encoding="utf-8") as f:
            json.dump(survey_config, f, ensure_ascii=False, indent=2)
        
        # データベースに保存（現在の店舗に対して）
        store_id = session.get('store_id')
        from flask import current_app
        current_app.logger.info(f"DEBUG: store_id = {store_id}")
        current_app.logger.info(f"DEBUG: questions count = {len(questions)}")
        current_app.logger.info(f"DEBUG: survey_config = {json.dumps(survey_config, ensure_ascii=False)[:200]}")
        if store_id:
            import store_db
            store_db.save_survey_config(store_id, survey_config)
            current_app.logger.info(f"DEBUG: Saved to database for store_id {store_id}")
        else:
            current_app.logger.warning("DEBUG: No store_id in session, not saved to database")
        
        flash("アンケート設定を保存しました", "success")
        return redirect(url_for("survey_admin.admin_survey_editor"))
    
    # GET: データベースから設定を読み込み
    store_id = session.get('store_id')
    survey_config = None
    
    if store_id:
        import store_db
        survey_config = store_db.get_survey_config(store_id)
        if survey_config and survey_config.get('questions'):
            # データベースから読み込めた
            pass
        else:
            survey_config = None
    
    if not survey_config:
        # データベースになければJSONファイルから
        if os.path.exists(survey_config_path):
            with open(survey_config_path, "r", encoding="utf-8") as f:
                survey_config = json.load(f)
        else:
            survey_config = None
    
    if not survey_config:
        # デフォルト設定
        survey_config = {
            "title": "お店アンケート",
            "description": "ご来店ありがとうございます！",
            "questions": [
                {
                    "id": 1,
                    "text": "総合評価",
                    "type": "rating",
                    "required": True
                },
                {
                    "id": 2,
                    "text": "訪問目的",
                    "type": "radio",
                    "required": True,
                    "options": ["食事", "カフェ", "買い物", "その他"]
                },
                {
                    "id": 3,
                    "text": "お店の雰囲気（複数選択可）",
                    "type": "checkbox",
                    "required": False,
                    "options": ["静か", "賑やか", "落ち着く", "おしゃれ", "カジュアル"]
                },
                {
                    "id": 4,
                    "text": "おすすめ度",
                    "type": "radio",
                    "required": True,
                    "options": ["ぜひおすすめしたい", "おすすめしたい", "どちらでもない", "おすすめしない"]
                },
                {
                    "id": 5,
                    "text": "ご感想・ご意見（任意）",
                    "type": "text",
                    "required": False
                }
            ]
        }
    
    return render_template("admin_survey_editor.html",
                         admin=admin,
                         survey_config=survey_config)

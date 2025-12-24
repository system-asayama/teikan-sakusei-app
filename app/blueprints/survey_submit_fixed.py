@bp.post("/store/<store_slug>/submit_survey")
@require_store
def submit_survey():
    """アンケート送信"""
    try:
        body = request.get_json(silent=True) or {}
        print(f"DEBUG submit_survey: body = {body}")
    
        # 最初の質問の回答を評価として使用（５段階評価の場合）
        rating = 3  # デフォルト
        first_answer = body.get('q1', '')
        if '非常に満足' in first_answer or '強く思う' in first_answer or '非常に良い' in first_answer:
            rating = 5
        elif '満足' in first_answer or '思う' in first_answer or '良い' in first_answer:
            rating = 4
        elif '普通' in first_answer or 'どちらとも' in first_answer:
            rating = 3
        elif 'やや' in first_answer:
            rating = 2
        else:
            rating = 1
        
        # ratingをbodyに追加
        body['rating'] = rating
        
        # アンケート回答を保存
        print(f"DEBUG submit_survey: rating = {rating}, store_id = {g.store_id}")
        store_db.save_survey_response(g.store_id, body)
        
        # 星4以上の場合のAI投稿文を生成（OpenAI APIキーが必要）
        generated_review = ''
        # 一時的に無効化：有効なOpenAI APIキーが必要です
        # if rating >= 4:
        #     try:
        #         generated_review = _generate_review_text(body, g.store_id)
        #     except Exception as e:
        #         print(f"Error generating review: {e}")
        
        # セッションにアンケート完了フラグと評価を設定
        session[f'survey_completed_{g.store_id}'] = True
        session[f'survey_rating_{g.store_id}'] = rating
        session[f'generated_review_{g.store_id}'] = generated_review
        
        # 星3以下の場合はメッセージを表示
        if rating <= 3:
            return jsonify({
                "ok": True, 
                "message": "貴重なご意見をありがとうございます。社内で改善に活用させていただきます。",
                "rating": rating
            })
        
        # 星4以上の場合は口コミ投稿文を表示
        return jsonify({
            "ok": True, 
            "message": "アンケートにご協力いただきありがとうございます！",
            "rating": rating,
            "generated_review": generated_review
        })
    except Exception as e:
        print(f"ERROR submit_survey: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 400

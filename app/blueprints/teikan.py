# -*- coding: utf-8 -*-
"""
定款管理ルート
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..utils import get_db, _sql, require_roles, ROLES, current_tenant_filter_sql
from ..utils.db import _is_pg
from ..utils.teikan_template import generate_teikan_text

bp = Blueprint('teikan', __name__, url_prefix='/teikan')


@bp.route('/')
@require_roles(ROLES["SYSTEM_ADMIN"], ROLES["ADMIN"])
def index():
    """定款一覧"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # テナントフィルタリング
        where_clause, params = current_tenant_filter_sql('"T_定款"."tenant_id"')
        
        sql = _sql(conn, f'''
            SELECT id, 会社名, ステータス, created_at, updated_at
            FROM "T_定款"
            WHERE {where_clause}
            ORDER BY created_at DESC
        ''')
        cur.execute(sql, params)
        
        teikans = []
        for row in cur.fetchall():
            teikans.append({
                'id': row[0],
                '会社名': row[1],
                'ステータス': row[2],
                'created_at': row[3],
                'updated_at': row[4]
            })
        
        return render_template('teikan/index.html', teikans=teikans)
    finally:
        try:
            conn.close()
        except:
            pass


@bp.route('/new', methods=['GET', 'POST'])
@require_roles(ROLES["SYSTEM_ADMIN"], ROLES["ADMIN"])
def new():
    """定款新規作成"""
    error = None
    
    if request.method == 'POST':
        # CSRF チェック
        form_token = request.form.get('csrf_token', '')
        if not form_token or form_token != session.get('csrf_token'):
            error = "セッションが無効です。もう一度お試しください。"
        else:
            # フォームデータ取得
            会社名 = (request.form.get('会社名') or '').strip()
            会社名_英語 = (request.form.get('会社名_英語') or '').strip()
            本店所在地_都道府県 = (request.form.get('本店所在地_都道府県') or '').strip()
            本店所在地_市区町村 = (request.form.get('本店所在地_市区町村') or '').strip()
            本店所在地_番地 = (request.form.get('本店所在地_番地') or '').strip()
            本店所在地_建物名 = (request.form.get('本店所在地_建物名') or '').strip()
            事業年度_決算月 = request.form.get('事業年度_決算月', type=int)
            発行可能株式総数 = request.form.get('発行可能株式総数', type=int)
            設立時発行株式数 = request.form.get('設立時発行株式数', type=int)
            一株の金額 = request.form.get('一株の金額', type=int)
            譲渡制限 = 1 if request.form.get('譲渡制限') == 'on' else 0
            承認機関 = request.form.get('承認機関', '株主総会')
            取締役の人数 = request.form.get('取締役の人数', type=int, default=1)
            取締役会設置 = 1 if request.form.get('取締役会設置') == 'on' else 0
            監査役設置 = 1 if request.form.get('監査役設置') == 'on' else 0
            会計参与設置 = 1 if request.form.get('会計参与設置') == 'on' else 0
            公告方法 = request.form.get('公告方法', '官報')
            
            # 事業目的（複数）
            事業目的リスト = []
            for i in range(1, 21):  # 最大20個
                目的 = (request.form.get(f'事業目的_{i}') or '').strip()
                if 目的:
                    事業目的リスト.append(目的)
            
            # 発起人情報（複数）
            発起人リスト = []
            for i in range(1, 11):  # 最大10名
                氏名 = (request.form.get(f'発起人_氏名_{i}') or '').strip()
                住所 = (request.form.get(f'発起人_住所_{i}') or '').strip()
                引受株式数 = request.form.get(f'発起人_引受株式数_{i}', type=int)
                if 氏名 and 住所 and 引受株式数:
                    出資金額 = 引受株式数 * 一株の金額
                    発起人リスト.append({
                        '氏名': 氏名,
                        '住所': 住所,
                        '引受株式数': 引受株式数,
                        '出資金額': 出資金額
                    })
            
            # バリデーション
            if not 会社名:
                error = "会社名を入力してください。"
            elif not 本店所在地_都道府県 or not 本店所在地_市区町村 or not 本店所在地_番地:
                error = "本店所在地を入力してください。"
            elif not 事業年度_決算月 or 事業年度_決算月 < 1 or 事業年度_決算月 > 12:
                error = "事業年度（決算月）は1〜12の範囲で入力してください。"
            elif not 発行可能株式総数 or 発行可能株式総数 <= 0:
                error = "発行可能株式総数を入力してください。"
            elif not 設立時発行株式数 or 設立時発行株式数 <= 0:
                error = "設立時発行株式数を入力してください。"
            elif 設立時発行株式数 > 発行可能株式総数:
                error = "設立時発行株式数は発行可能株式総数以下にしてください。"
            elif not 一株の金額 or 一株の金額 <= 0:
                error = "1株の金額を入力してください。"
            elif not 事業目的リスト:
                error = "事業目的を最低1つ入力してください。"
            elif not 発起人リスト:
                error = "発起人情報を最低1名入力してください。"
            
            if not error:
                # 資本金計算
                資本金 = 設立時発行株式数 * 一株の金額
                
                # データベースに保存
                conn = get_db()
                try:
                    cur = conn.cursor()
                    
                    # 定款マスタ登録
                    sql_ins = _sql(conn, '''
                        INSERT INTO "T_定款"(
                            tenant_id, created_by, 会社名, 会社名_英語,
                            本店所在地_都道府県, 本店所在地_市区町村, 本店所在地_番地, 本店所在地_建物名,
                            事業年度_決算月, 発行可能株式総数, 設立時発行株式数, 一株の金額, 資本金,
                            譲渡制限, 承認機関, 取締役の人数, 取締役会設置, 監査役設置, 会計参与設置, 公告方法,
                            ステータス
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''')
                    
                    if _is_pg(conn):
                        sql_ins += ' RETURNING id'
                        cur.execute(sql_ins, (
                            session.get('tenant_id'), session.get('user_id'), 会社名, 会社名_英語,
                            本店所在地_都道府県, 本店所在地_市区町村, 本店所在地_番地, 本店所在地_建物名,
                            事業年度_決算月, 発行可能株式総数, 設立時発行株式数, 一株の金額, 資本金,
                            譲渡制限, 承認機関, 取締役の人数, 取締役会設置, 監査役設置, 会計参与設置, 公告方法,
                            'draft'
                        ))
                        定款_id = cur.fetchone()[0]
                    else:
                        cur.execute(sql_ins, (
                            session.get('tenant_id'), session.get('user_id'), 会社名, 会社名_英語,
                            本店所在地_都道府県, 本店所在地_市区町村, 本店所在地_番地, 本店所在地_建物名,
                            事業年度_決算月, 発行可能株式総数, 設立時発行株式数, 一株の金額, 資本金,
                            譲渡制限, 承認機関, 取締役の人数, 取締役会設置, 監査役設置, 会計参与設置, 公告方法,
                            'draft'
                        ))
                        conn.commit()
                        定款_id = cur.lastrowid
                    
                    # 事業目的登録
                    for idx, 目的 in enumerate(事業目的リスト, start=1):
                        sql_mok = _sql(conn, 'INSERT INTO "T_事業目的"(定款_id, 順序, 目的) VALUES (%s, %s, %s)')
                        cur.execute(sql_mok, (定款_id, idx, 目的))
                    
                    # 発起人登録
                    for 発起人 in 発起人リスト:
                        sql_hok = _sql(conn, 'INSERT INTO "T_発起人"(定款_id, 氏名, 住所, 引受株式数, 出資金額) VALUES (%s, %s, %s, %s, %s)')
                        cur.execute(sql_hok, (定款_id, 発起人['氏名'], 発起人['住所'], 発起人['引受株式数'], 発起人['出資金額']))
                    
                    if not _is_pg(conn):
                        conn.commit()
                    
                    flash("定款を作成しました。", "success")
                    return redirect(url_for('teikan.detail', id=定款_id))
                finally:
                    try:
                        conn.close()
                    except:
                        pass
    
    return render_template('teikan/new.html', error=error)


@bp.route('/<int:id>')
@require_roles(ROLES["SYSTEM_ADMIN"], ROLES["ADMIN"])
def detail(id):
    """定款詳細"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # テナントフィルタリング
        where_clause, params = current_tenant_filter_sql('"T_定款"."tenant_id"')
        params = params + (id,)
        
        sql = _sql(conn, f'''
            SELECT * FROM "T_定款"
            WHERE {where_clause} AND id = %s
        ''')
        cur.execute(sql, params)
        row = cur.fetchone()
        
        if not row:
            flash("定款が見つかりません。", "error")
            return redirect(url_for('teikan.index'))
        
        # 定款データ
        teikan = {
            'id': row[0],
            'tenant_id': row[1],
            'created_by': row[2],
            '会社名': row[3],
            '会社名_英語': row[4],
            '本店所在地_都道府県': row[5],
            '本店所在地_市区町村': row[6],
            '本店所在地_番地': row[7],
            '本店所在地_建物名': row[8],
            '事業年度_決算月': row[9],
            '発行可能株式総数': row[10],
            '設立時発行株式数': row[11],
            '一株の金額': row[12],
            '資本金': row[13],
            '譲渡制限': row[14],
            '承認機関': row[15],
            '取締役の人数': row[16],
            '取締役会設置': row[17],
            '監査役設置': row[18],
            '会計参与設置': row[19],
            '公告方法': row[20],
            'ステータス': row[21],
            'created_at': row[22],
            'updated_at': row[23]
        }
        
        # 事業目的取得
        sql_mok = _sql(conn, 'SELECT 目的 FROM "T_事業目的" WHERE 定款_id = %s ORDER BY 順序')
        cur.execute(sql_mok, (id,))
        事業目的リスト = [row[0] for row in cur.fetchall()]
        
        # 発起人取得
        sql_hok = _sql(conn, 'SELECT 氏名, 住所, 引受株式数, 出資金額 FROM "T_発起人" WHERE 定款_id = %s')
        cur.execute(sql_hok, (id,))
        発起人リスト = []
        for row in cur.fetchall():
            発起人リスト.append({
                '氏名': row[0],
                '住所': row[1],
                '引受株式数': row[2],
                '出資金額': row[3]
            })
        
        # 定款本文生成
        定款本文 = generate_teikan_text(teikan, 事業目的リスト, 発起人リスト)
        
        return render_template('teikan/detail.html', teikan=teikan, 事業目的リスト=事業目的リスト, 発起人リスト=発起人リスト, 定款本文=定款本文)
    finally:
        try:
            conn.close()
        except:
            pass


@bp.route('/<int:id>/delete', methods=['POST'])
@require_roles(ROLES["SYSTEM_ADMIN"], ROLES["ADMIN"])
def delete(id):
    """定款削除"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # テナントフィルタリング
        where_clause, params = current_tenant_filter_sql('"T_定款"."tenant_id"')
        params = params + (id,)
        
        # 存在確認
        sql_chk = _sql(conn, f'SELECT 1 FROM "T_定款" WHERE {where_clause} AND id = %s')
        cur.execute(sql_chk, params)
        if not cur.fetchone():
            flash("定款が見つかりません。", "error")
            return redirect(url_for('teikan.index'))
        
        # 関連データ削除
        sql_del_mok = _sql(conn, 'DELETE FROM "T_事業目的" WHERE 定款_id = %s')
        cur.execute(sql_del_mok, (id,))
        
        sql_del_hok = _sql(conn, 'DELETE FROM "T_発起人" WHERE 定款_id = %s')
        cur.execute(sql_del_hok, (id,))
        
        sql_del = _sql(conn, 'DELETE FROM "T_定款" WHERE id = %s')
        cur.execute(sql_del, (id,))
        
        if not _is_pg(conn):
            conn.commit()
        
        flash("定款を削除しました。", "success")
        return redirect(url_for('teikan.index'))
    finally:
        try:
            conn.close()
        except:
            pass

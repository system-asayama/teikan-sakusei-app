# -*- coding: utf-8 -*-
"""
定款作成アプリ Blueprint
freee会社設立と同様のステップ形式UIで定款を作成する
"""
import io
import json
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, send_file
)
from app.utils import require_roles, ROLES
from app.db import SessionLocal
from app.models_login import TeikanDocument

bp = Blueprint('teikan', __name__, url_prefix='/apps/teikan')


def get_session_data():
    """セッションから定款データを取得する"""
    return session.get('teikan_data', {})


def save_session_data(data):
    """定款データをセッションに保存する"""
    session['teikan_data'] = data
    session.modified = True


def autosave_draft(data):
    """各ステップ保存時に自動的にDBに下書き保存するヘルパー関数"""
    tenant_id = session.get('tenant_id')
    user_id = session.get('user_id')
    draft_id = session.get('teikan_draft_id')  # 現在編集中の下書きID

    db = SessionLocal()
    try:
        from app.db import Base, engine
        Base.metadata.create_all(bind=engine)

        company_name = data.get('company_name', '')
        company_type = data.get('company_type', '合同会社')
        data_json = json.dumps(data, ensure_ascii=False)

        if draft_id:
            # 既存の下書きを更新
            doc = db.query(TeikanDocument).filter(
                TeikanDocument.id == draft_id,
                TeikanDocument.tenant_id == tenant_id
            ).first()
            if doc and doc.status == 'draft':
                doc.company_name = company_name
                doc.company_type = company_type
                doc.data_json = data_json
                db.commit()
                return  # 更新成功

        # 新規下書き作成
        doc = TeikanDocument(
            tenant_id=tenant_id,
            created_by=user_id,
            company_name=company_name,
            company_type=company_type,
            status='draft',
            data_json=data_json
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        session['teikan_draft_id'] = doc.id  # 下書きIDをセッションに保存
        session.modified = True
    except Exception:
        db.rollback()
    finally:
        db.close()


@bp.route('/')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def index():
    """定款アプリトップページ"""
    return render_template('teikan/index.html')


@bp.route('/select_type')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def select_type():
    """法人形態選択画面"""
    return render_template('teikan/select_type.html')


@bp.route('/new')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def new_document():
    """新規定款作成：セッションをクリアして法人形態選択画面へ"""
    session.pop('teikan_data', None)
    session.pop('teikan_draft_id', None)
    session.modified = True
    return redirect(url_for('teikan.select_type'))


@bp.route('/start/<company_type>')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def start_with_type(company_type):
    """法人形態を選択して定款作成を開始する"""
    session.pop('teikan_data', None)
    session.pop('teikan_draft_id', None)
    data = {'company_type': company_type}
    save_session_data(data)
    return redirect(url_for('teikan.confirm'))


@bp.route('/step1', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def step1():
    """ステップ1: 基本情報入力（法人形態・商号・住所・登記方法）"""
    data = get_session_data()

    if request.method == 'POST':
        data['company_type'] = request.form.get('company_type', '合同会社')
        data['company_name'] = request.form.get('company_name', '')
        data['company_name_kana'] = request.form.get('company_name_kana', '')
        data['company_type_position'] = request.form.get('company_type_position', 'before')
        data['registration_method'] = request.form.get('registration_method', '法務局に直接提出')
        data['postal_code'] = request.form.get('postal_code', '')
        data['address'] = request.form.get('address', '')
        data['address_detail'] = request.form.get('address_detail', '')
        if request.form.get('capital_from_step1'):
            data['capital'] = request.form.get('capital', '0')
        data['phone'] = request.form.get('phone', '')
        save_session_data(data)
        autosave_draft(data)
        return redirect(url_for('teikan.confirm'))

    return render_template('teikan/step1.html', data=data)


@bp.route('/step2', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def step2():
    """ステップ2: 社員情報入力（代表社員・出資金・資本金）"""
    data = get_session_data()

    if request.method == 'POST':
        members = []
        member_count = int(request.form.get('member_count', 1))
        for i in range(member_count):
            member = {
                'name': request.form.get(f'member_name_{i}', ''),
                'name_kana': request.form.get(f'member_name_kana_{i}', ''),
                'is_representative': request.form.get(f'is_representative_{i}') == 'on',
                'contribution': request.form.get(f'contribution_{i}', '0'),
                'postal_code': request.form.get(f'member_postal_{i}', ''),
                'address': request.form.get(f'member_address_{i}', ''),
                'phone': request.form.get(f'member_phone_{i}', ''),
            }
            if member['name']:
                members.append(member)

        data['members'] = members
        save_session_data(data)
        autosave_draft(data)
        return redirect(url_for('teikan.confirm'))

    return render_template('teikan/step2.html', data=data)


@bp.route('/step3', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def step3():
    """ステップ3: 事業目的入力"""
    data = get_session_data()

    if request.method == 'POST':
        purposes = []
        purpose_count = int(request.form.get('purpose_count', 1))
        for i in range(purpose_count):
            p = request.form.get(f'purpose_{i}', '').strip()
            if p:
                purposes.append(p)
        last_item = '前（各）号に附帯関連する一切の事業'
        if purposes and purposes[-1] != last_item:
            purposes.append(last_item)

        data['purposes'] = purposes
        save_session_data(data)
        autosave_draft(data)
        return redirect(url_for('teikan.confirm'))

    return render_template('teikan/step3.html', data=data)


@bp.route('/step4', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def step4():
    """ステップ4: 決算期・その他設定"""
    data = get_session_data()

    if request.method == 'POST':
        data['fiscal_start_month'] = request.form.get('fiscal_start_month', '3')
        data['fiscal_start_day'] = request.form.get('fiscal_start_day', '1')
        data['fiscal_end_month'] = request.form.get('fiscal_end_month', '2')
        data['fiscal_end_day'] = request.form.get('fiscal_end_day', '末日')
        data['established_date'] = request.form.get('established_date', '')
        save_session_data(data)
        autosave_draft(data)
        return redirect(url_for('teikan.confirm'))

    return render_template('teikan/step4.html', data=data)


@bp.route('/confirm')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def confirm():
    """確認画面：入力内容の確認（未入力でも表示、各項目から編集）"""
    data = get_session_data()
    return render_template('teikan/confirm.html', data=data)


@bp.route('/preview')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def preview():
    """定款プレビュー（HTML表示）"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    return render_template('teikan/preview.html', data=data)


@bp.route('/download_pdf')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_pdf():
    """定款PDFをダウンロードする"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))

    try:
        pdf_bytes = generate_teikan_pdf(data)
        company_name = data.get('company_name', '定款')
        filename = f"{company_name}_定款.pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.preview'))


@bp.route('/reset')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def reset():
    """セッションデータをリセットして最初から"""
    session.pop('teikan_data', None)
    return redirect(url_for('teikan.step1'))


@bp.route('/save', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def save():
    """定款データをDBに完成保存する（下書きがあれば更新、なければ新規作成）"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.confirm'))

    tenant_id = session.get('tenant_id')
    user_id = session.get('user_id')
    draft_id = session.get('teikan_draft_id')
    db = SessionLocal()
    try:
        from app.db import Base, engine
        Base.metadata.create_all(bind=engine)

        company_name = data.get('company_name', '')
        company_type = data.get('company_type', '合同会社')
        data_json = json.dumps(data, ensure_ascii=False)

        if draft_id:
            # 既存の下書きを完成に更新
            doc = db.query(TeikanDocument).filter(
                TeikanDocument.id == draft_id,
                TeikanDocument.tenant_id == tenant_id
            ).first()
            if doc:
                doc.company_name = company_name
                doc.company_type = company_type
                doc.status = 'completed'
                doc.data_json = data_json
                db.commit()
                flash(f'「{company_type}{company_name}」の定款を保存しました', 'success')
                session.pop('teikan_data', None)
                session.pop('teikan_draft_id', None)
                return redirect(url_for('teikan.history'))

        # 新規完成保存
        doc = TeikanDocument(
            tenant_id=tenant_id,
            created_by=user_id,
            company_name=company_name,
            company_type=company_type,
            status='completed',
            data_json=data_json
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        flash(f'「{doc.company_type}{doc.company_name}」の定款を保存しました', 'success')
        session.pop('teikan_data', None)
        session.pop('teikan_draft_id', None)
        return redirect(url_for('teikan.history'))
    except Exception as e:
        db.rollback()
        flash(f'保存エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.confirm'))
    finally:
        db.close()


@bp.route('/new_setup')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def new_setup():
    """新しい法人を設立する中間ページ"""
    data = get_session_data()
    has_data = bool(data.get('company_name'))
    return render_template('teikan/new_setup.html', has_data=has_data)


@bp.route('/history')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def history():
    """作成済み定款一覧"""
    tenant_id = session.get('tenant_id')
    db = SessionLocal()
    try:
        from app.db import Base, engine
        Base.metadata.create_all(bind=engine)

        docs = db.query(TeikanDocument).filter(
            TeikanDocument.tenant_id == tenant_id
        ).order_by(TeikanDocument.created_at.desc()).all()
        return render_template('teikan/history.html', docs=docs)
    except Exception as e:
        flash(f'一覧取得エラー: {str(e)}', 'error')
        return render_template('teikan/history.html', docs=[])
    finally:
        db.close()


@bp.route('/history/<int:doc_id>')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def history_detail(doc_id):
    """保存済み定款の詳細プレビュー"""
    tenant_id = session.get('tenant_id')
    db = SessionLocal()
    try:
        doc = db.query(TeikanDocument).filter(
            TeikanDocument.id == doc_id,
            TeikanDocument.tenant_id == tenant_id
        ).first()
        if not doc:
            flash('定款が見つかりません', 'error')
            return redirect(url_for('teikan.history'))
        data = json.loads(doc.data_json)
        return render_template('teikan/preview.html', data=data, doc=doc, readonly=True)
    finally:
        db.close()


@bp.route('/history/<int:doc_id>/download')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def history_download(doc_id):
    """保存済み定款のPDFダウンロード"""
    tenant_id = session.get('tenant_id')
    db = SessionLocal()
    try:
        doc = db.query(TeikanDocument).filter(
            TeikanDocument.id == doc_id,
            TeikanDocument.tenant_id == tenant_id
        ).first()
        if not doc:
            flash('定款が見つかりません', 'error')
            return redirect(url_for('teikan.history'))
        data = json.loads(doc.data_json)
        pdf_bytes = generate_teikan_pdf(data)
        filename = f"{doc.company_type}{doc.company_name}_定款.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.history'))
    finally:
        db.close()


@bp.route('/history/<int:doc_id>/delete', methods=['POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def history_delete(doc_id):
    """保存済み定款の削除"""
    tenant_id = session.get('tenant_id')
    db = SessionLocal()
    try:
        doc = db.query(TeikanDocument).filter(
            TeikanDocument.id == doc_id,
            TeikanDocument.tenant_id == tenant_id
        ).first()
        if not doc:
            flash('定款が見つかりません', 'error')
            return redirect(url_for('teikan.history'))
        name = f"{doc.company_type}{doc.company_name}"
        db.delete(doc)
        db.commit()
        flash(f'「{name}」の定款を削除しました', 'success')
        return redirect(url_for('teikan.history'))
    except Exception as e:
        db.rollback()
        flash(f'削除エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.history'))
    finally:
        db.close()


@bp.route('/history/<int:doc_id>/edit')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def history_edit(doc_id):
    """保存済み定款をセッションに読み込んで編集再開"""
    tenant_id = session.get('tenant_id')
    db = SessionLocal()
    try:
        doc = db.query(TeikanDocument).filter(
            TeikanDocument.id == doc_id,
            TeikanDocument.tenant_id == tenant_id
        ).first()
        if not doc:
            flash('定款が見つかりません', 'error')
            return redirect(url_for('teikan.history'))
        data = json.loads(doc.data_json)
        save_session_data(data)
        session['teikan_draft_id'] = doc.id  # 編集中のドキュメントIDをセッションに保存
        session.modified = True
        flash('法人データを読み込みました', 'info')
        return redirect(url_for('teikan.new_setup'))
    finally:
        db.close()


def generate_teikan_pdf(data):
    """
    定款PDFを生成する（ReportLabを使用）
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # 日本語フォントの設定
    jp_font_path = '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf'
    if os.path.exists(jp_font_path):
        try:
            pdfmetrics.registerFont(TTFont('JapaneseGothic', jp_font_path))
            font_name = 'JapaneseGothic'
            font_bold = 'JapaneseGothic'
        except Exception:
            font_name = 'Helvetica'
            font_bold = 'Helvetica-Bold'
    else:
        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_left = 25 * mm
    margin_right = 25 * mm
    margin_top = 25 * mm
    margin_bottom = 20 * mm
    content_width = width - margin_left - margin_right

    y_ref = [height - margin_top]

    def get_y():
        return y_ref[0]

    def set_y(val):
        y_ref[0] = val

    def new_page():
        c.showPage()
        set_y(height - margin_top)

    def check_page_break(needed_mm=25):
        if get_y() < margin_bottom + needed_mm * mm:
            new_page()

    def draw_wrapped_text(text, x, y_pos, max_width, font=font_name, size=10.5, line_height=16):
        c.setFont(font, size)
        line = ''
        lines = []
        for char in text:
            test_line = line + char
            if c.stringWidth(test_line, font, size) <= max_width:
                line = test_line
            else:
                if line:
                    lines.append(line)
                line = char
        if line:
            lines.append(line)

        for ln in lines:
            if y_pos < margin_bottom + 10 * mm:
                new_page()
                y_pos = height - margin_top
            c.drawString(x, y_pos, ln)
            y_pos -= line_height
        return y_pos

    def draw_chapter(title_text):
        check_page_break(30)
        c.setFont(font_bold, 12)
        tw = c.stringWidth(title_text, font_bold, 12)
        c.drawString((width - tw) / 2, get_y(), title_text)
        set_y(get_y() - 25)

    def draw_article(article_num, title_text, content_lines):
        check_page_break(25)
        c.setFont(font_bold, 10.5)
        header = f'第{article_num}条（{title_text}）'
        c.drawString(margin_left, get_y(), header)
        set_y(get_y() - 18)
        for line in content_lines:
            if not line:
                set_y(get_y() - 8)
                continue
            check_page_break(15)
            indent = margin_left + 5 * mm
            new_y = draw_wrapped_text(line, indent, get_y(), content_width - 10 * mm, size=10.5, line_height=16)
            set_y(new_y - 2)
        set_y(get_y() - 8)

    # ===== 共通データ取得 =====
    company_name = data.get('company_name', '')
    company_type = data.get('company_type', '合同会社')
    purposes = data.get('purposes', [])
    address = data.get('address', '') + data.get('address_detail', '')
    capital = data.get('capital', '0')
    try:
        capital_int = int(str(capital).replace(',', '').replace('円', ''))
        capital_str = f'{capital_int:,}円'
    except Exception:
        capital_str = f'{capital}円'
    members = data.get('members', [])
    fiscal_start_month = data.get('fiscal_start_month', '3')
    fiscal_start_day = data.get('fiscal_start_day', '1')
    fiscal_end_month = data.get('fiscal_end_month', '2')
    fiscal_end_day = data.get('fiscal_end_day', '末日')
    if fiscal_end_day == '末日':
        fiscal_end_str = f'{fiscal_end_month}月末日'
    else:
        fiscal_end_str = f'{fiscal_end_month}月{fiscal_end_day}日'
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    rep_lines = [f'　{m.get("name", "")}' for m in rep_members] or ['　（代表者氏名）']

    # ===== 表紙 =====
    c.setFont(font_bold, 18)
    title = '定　　款'
    title_width = c.stringWidth(title, font_bold, 18)
    c.drawString((width - title_width) / 2, get_y(), title)
    set_y(get_y() - 40)
    c.setFont(font_bold, 14)
    cn = f'{company_type}{company_name}'
    cn_width = c.stringWidth(cn, font_bold, 14)
    c.drawString((width - cn_width) / 2, get_y(), cn)
    set_y(get_y() - 60)

    # ===== 法人形態別テンプレート =====
    if company_type == '合同会社':
        # ---------- 合同会社 ----------
        draw_chapter('第一章　総則')
        draw_article('1', '商号', [f'当会社は、合同会社{company_name}と称する。'])
        purpose_lines = ['当会社は、次の事業を営むことを目的とする。']
        for i, p in enumerate(purposes, 1):
            purpose_lines.append(f'　{i}．{p}')
        draw_article('2', '目的', purpose_lines)
        draw_article('3', '本店の所在地', [f'当会社は、本店を{address}に置く。'])
        draw_article('4', '公告方法', ['当会社の公告は、官報に掲載する方法により行う。'])

        draw_chapter('第二章　社員及び出資')
        contribution_lines = ['社員の氏名、住所及び出資の目的並びにその価額は、次のとおりである。']
        for m in members:
            contrib = m.get('contribution', '0')
            try:
                contrib_str = f"{int(str(contrib).replace(',','').replace('円','')):,}円"
            except Exception:
                contrib_str = f'{contrib}円'
            contribution_lines += [f'　氏名：{m.get("name","")}', f'　住所：{m.get("address","")}', f'　出資の価額：金{contrib_str}', '']
        draw_article('5', '社員の出資', contribution_lines)
        draw_article('6', '資本金の額', [f'当会社の資本金の額は、金{capital_str}とする。'])

        draw_chapter('第三章　業務執行及び代表')
        draw_article('7', '業務執行社員', ['当会社の業務は、社員全員が執行する。', '業務を執行する社員は、当会社を代表する。'])
        draw_article('8', '代表社員', ['当会社を代表する社員は、次のとおりとする。'] + rep_lines)
        draw_article('9', '業務執行の決定', ['当会社の業務執行は、社員の過半数をもって決定する。'])

        draw_chapter('第四章　計算')
        draw_article('10', '事業年度', [f'当会社の事業年度は、毎年{fiscal_start_month}月{fiscal_start_day}日から翌年{fiscal_end_str}までとする。'])
        draw_article('11', '利益の配当', ['当会社は、毎事業年度終了後、社員の出資の価額に応じて利益の配当を行う。'])

        draw_chapter('第五章　附則')
        draw_article('12', '設立に際して出資される財産の価額', [f'当会社の設立に際して出資される財産の価額は、金{capital_str}とする。'])
        draw_article('13', '最初の事業年度', [f'当会社の最初の事業年度は、当会社成立の日から{fiscal_end_str}までとする。'])
        draw_article('14', '設立時代表社員', ['当会社の設立時の代表社員は、次のとおりとする。'] + rep_lines)
        draw_article('15', '附則', [f'当会社の定款は、{established_date}に作成した。'])

        check_page_break(60)
        set_y(get_y() - 20)
        c.setFont(font_name, 10.5)
        c.drawString(margin_left, get_y(), '以上、合同会社設立のため、この定款を作成し、社員が記名押印する。')
        set_y(get_y() - 30)
        c.drawString(margin_left, get_y(), f'　　　　　　　　　　　　　　　　　　　　{established_date}')
        set_y(get_y() - 30)
        for m in members:
            check_page_break(20)
            c.drawString(margin_left + 20 * mm, get_y(), f'社員　{m.get("name", "")}　　　　　　　印')
            set_y(get_y() - 25)

    elif company_type == '株式会社':
        # ---------- 株式会社 ----------
        total_shares = data.get('total_shares', '400')
        draw_chapter('第一章　総則')
        draw_article('1', '商号', [f'当会社は、株式会社{company_name}と称する。'])
        purpose_lines = ['当会社は、次の事業を営むことを目的とする。']
        for i, p in enumerate(purposes, 1):
            purpose_lines.append(f'　{i}．{p}')
        draw_article('2', '目的', purpose_lines)
        draw_article('3', '本店の所在地', [f'当会社は、本店を{address}に置く。'])
        draw_article('4', '公告方法', ['当会社の公告は、官報に掲載する方法により行う。'])

        draw_chapter('第二章　株式')
        draw_article('5', '発行可能株式総数', [f'当会社の発行可能株式総数は、{total_shares}株とする。'])
        draw_article('6', '株券の不発行', ['当会社の株式については、株券を発行しない。'])
        draw_article('7', '株式の譲渡制限', ['当会社の株式を譲渡するには、取締役会の承認を要する。ただし、当会社の株主に譲渡する場合は、この限りでない。'])

        draw_chapter('第三章　株主総会')
        draw_article('8', '招集', ['当会社の定時株主総会は、毎事業年度終了後３ヶ月以内に招集し、臨時株主総会は、必要に応じて招集する。'])
        draw_article('9', '議長', ['株主総会の議長は、代表取締役社長がこれに当たる。'])
        draw_article('10', '決議', ['株主総会の普通決議は、法令に別段の定めがある場合を除き、議決権を行使することができる株主の議決権の過半数を有する株主が出席し、出席した当該株主の議決権の過半数をもって行う。'])

        draw_chapter('第四章　取締役')
        draw_article('11', '取締役の員数', ['当会社の取締役は、１名以上とする。'])
        draw_article('12', '取締役の選任', ['取締役は、株主総会の決議によって選任する。'])
        draw_article('13', '代表取締役', ['当会社の代表取締役は、取締役の互選によって定める。'])
        draw_article('14', '取締役の任期', ['取締役の任期は、選任後２年以内に終了する事業年度のうち最終のものに関する定時株主総会の終結の時までとする。ただし、定款変更その他正当な事由がある場合には、株主総会の決議によって短縮することができる。'])

        draw_chapter('第五章　計算')
        draw_article('15', '事業年度', [f'当会社の事業年度は、毎年{fiscal_start_month}月{fiscal_start_day}日から翌年{fiscal_end_str}までとする。'])
        draw_article('16', '剰余金の配当', ['当会社の剰余金の配当は、毎事業年度末日の最終の株主名簿に記載された株主又は登録株式質権者に対して行う。'])

        draw_chapter('第六章　附則')
        draw_article('17', '設立に際して出資される財産の価額', [f'当会社の設立に際して出資される財産の価額は、金{capital_str}とする。'])
        draw_article('18', '最初の事業年度', [f'当会社の最初の事業年度は、当会社成立の日から{fiscal_end_str}までとする。'])
        draw_article('19', '設立時取締役', ['当会社の設立時取締役は、次のとおりとする。'] + rep_lines)
        draw_article('20', '附則', [f'当会社の定款は、{established_date}に作成した。'])

        check_page_break(60)
        set_y(get_y() - 20)
        c.setFont(font_name, 10.5)
        c.drawString(margin_left, get_y(), '以上、株式会社設立のため、この定款を作成し、発起人が記名押印する。')
        set_y(get_y() - 30)
        c.drawString(margin_left, get_y(), f'　　　　　　　　　　　　　　　　　　　　{established_date}')
        set_y(get_y() - 30)
        for m in members:
            check_page_break(20)
            c.drawString(margin_left + 20 * mm, get_y(), f'発起人　{m.get("name", "")}　　　　　　　印')
            set_y(get_y() - 25)

    elif company_type == '一般社団法人':
        # ---------- 一般社団法人 ----------
        draw_chapter('第一章　総則')
        draw_article('1', '名称', [f'当法人は、一般社団法人{company_name}と称する。'])
        purpose_lines = ['当法人は、次の事業を行うことを目的とする。']
        for i, p in enumerate(purposes, 1):
            purpose_lines.append(f'　{i}．{p}')
        draw_article('2', '目的', purpose_lines)
        draw_article('3', '主たる事務所の所在地', [f'当法人は、主たる事務所を{address}に置く。'])
        draw_article('4', '公告方法', ['当法人の公告は、官報に掲載する方法により行う。'])

        draw_chapter('第二章　会員')
        draw_article('5', '会員の種別', ['当法人の会員は、次の２種とする。', '　１．正会員　当法人の目的に賛同して入会した個人又は団体', '　２．賛助会員　当法人の事業を賛助するために入会した個人又は団体'])
        draw_article('6', '入会', ['当法人の会員になろうとする者は、理事会が別に定める入会申込書を提出し、理事会の承認を得なければならない。'])
        draw_article('7', '会費', ['会員は、社員総会において別に定める会費を納入しなければならない。'])

        draw_chapter('第三章　社員総会')
        draw_article('8', '社員総会の構成', ['当法人の社員総会は、正会員をもって構成する。'])
        draw_article('9', '社員総会の開催', ['当法人の定時社員総会は、毎事業年度終了後３ヶ月以内に開催し、臨時社員総会は、必要に応じて開催する。'])
        draw_article('10', '社員総会の決議', ['社員総会の決議は、法令又はこの定款に別段の定めがある場合を除き、総社員の議決権の過半数を有する社員が出席し、出席した当該社員の議決権の過半数をもって行う。'])

        draw_chapter('第四章　役員')
        draw_article('11', '役員の設置', ['当法人に、理事１名以上及び監事１名を置く。'])
        draw_article('12', '役員の選任', ['理事及び監事は、社員総会の決議によって選任する。'])
        draw_article('13', '代表理事', ['当法人の代表理事は、理事の互選によって定める。'])
        draw_article('14', '役員の任期', ['理事の任期は、選任後２年以内に終了する事業年度のうち最終のものに関する定時社員総会の終結の時までとする。', '監事の任期は、選任後２年以内に終了する事業年度のうち最終のものに関する定時社員総会の終結の時までとする。'])

        draw_chapter('第五章　計算')
        draw_article('15', '事業年度', [f'当法人の事業年度は、毎年{fiscal_start_month}月{fiscal_start_day}日から翌年{fiscal_end_str}までとする。'])
        draw_article('16', '剰余金の分配の禁止', ['当法人は、剰余金の分配を行わない。'])

        draw_chapter('第六章　附則')
        draw_article('17', '最初の事業年度', [f'当法人の最初の事業年度は、当法人成立の日から{fiscal_end_str}までとする。'])
        draw_article('18', '設立時役員', ['当法人の設立時理事は、次のとおりとする。'] + rep_lines)
        draw_article('19', '附則', [f'当法人の定款は、{established_date}に作成した。'])

        check_page_break(60)
        set_y(get_y() - 20)
        c.setFont(font_name, 10.5)
        c.drawString(margin_left, get_y(), '以上、一般社団法人設立のため、この定款を作成し、設立時社員が記名押印する。')
        set_y(get_y() - 30)
        c.drawString(margin_left, get_y(), f'　　　　　　　　　　　　　　　　　　　　{established_date}')
        set_y(get_y() - 30)
        for m in members:
            check_page_break(20)
            c.drawString(margin_left + 20 * mm, get_y(), f'設立時社員　{m.get("name", "")}　　　　　　　印')
            set_y(get_y() - 25)

    c.save()
    buffer.seek(0)
    return buffer.read()


# ============================================================
# 登記書類作成 ルート
# ============================================================

@bp.route('/registration_docs')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def registration_docs():
    """登記書類作成画面"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    return render_template('teikan/registration_docs.html', data=data)


@bp.route('/registration_docs/preview/application')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def preview_registration_application():
    """設立登記申請書プレビュー"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    return render_template('teikan/registration_application_preview.html', data=data)


@bp.route('/registration_docs/download/application')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_registration_application():
    """設立登記申請書PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_registration_application_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_設立登記申請書.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/download/payment_certificate')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_payment_certificate():
    """払込証明書PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_payment_certificate_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_払込証明書.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/preview/payment_certificate')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def preview_payment_certificate():
    """払込証明書プレビュー"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    return render_template('teikan/payment_certificate_preview.html', data=data)


@bp.route('/registration_docs/download/capital_certificate')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_capital_certificate():
    """資本金の額の決定を証する書面PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_capital_certificate_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_資本金の額の決定を証する書面.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/download/office_location')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_office_location():
    """本店所在場所の決定を証する書面PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_office_location_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_本店所在場所の決定を証する書面.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/download/acceptance_letter')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_acceptance_letter():
    """就任承諾書PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_acceptance_letter_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_就任承諾書.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/download/founder_resolution')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_founder_resolution():
    """発起人の決定書 / 設立時社員の決議書PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_founder_resolution_pdf(data)
        company_type = data.get('company_type', '株式会社')
        company_name = data.get('company_name', '会社')
        if company_type == '一般社団法人':
            doc_name = '設立時社員の決議書'
        else:
            doc_name = '発起人の決定書'
        filename = f"{company_type}{company_name}_{doc_name}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/download/seal_registration')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_seal_registration():
    """印鑑届出書PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_seal_registration_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_印鑑届出書.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'PDF生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


@bp.route('/registration_docs/download/all')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_all_docs():
    """全登記書類をZIPでダウンロード"""
    import zipfile
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        full_name = f"{company_type}{company_name}"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 定款
            teikan_pdf = generate_teikan_pdf(data)
            zf.writestr(f"{full_name}_定款.pdf", teikan_pdf)

            # 設立登記申請書
            app_pdf = generate_registration_application_pdf(data)
            zf.writestr(f"{full_name}_設立登記申請書.pdf", app_pdf)

            # 印鑑届出書
            seal_pdf = generate_seal_registration_pdf(data)
            zf.writestr(f"{full_name}_印鑑届出書.pdf", seal_pdf)

            if company_type != '一般社団法人':
                # 払込証明書
                payment_pdf = generate_payment_certificate_pdf(data)
                zf.writestr(f"{full_name}_払込証明書.pdf", payment_pdf)

                # 資本金の額の決定を証する書面
                capital_pdf = generate_capital_certificate_pdf(data)
                zf.writestr(f"{full_name}_資本金の額の決定を証する書面.pdf", capital_pdf)

            if company_type == '合同会社':
                # 本店所在場所の決定を証する書面
                office_pdf = generate_office_location_pdf(data)
                zf.writestr(f"{full_name}_本店所在場所の決定を証する書面.pdf", office_pdf)

                # 就任承諾書
                accept_pdf = generate_acceptance_letter_pdf(data)
                zf.writestr(f"{full_name}_就任承諾書.pdf", accept_pdf)

            elif company_type in ['株式会社', '一般社団法人']:
                # 発起人の決定書 / 設立時社員の決議書
                resolution_pdf = generate_founder_resolution_pdf(data)
                doc_name = '設立時社員の決議書' if company_type == '一般社団法人' else '発起人の決定書'
                zf.writestr(f"{full_name}_{doc_name}.pdf", resolution_pdf)

                # 就任承諾書
                accept_pdf = generate_acceptance_letter_pdf(data)
                zf.writestr(f"{full_name}_就任承諾書.pdf", accept_pdf)

        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip',
                         as_attachment=True,
                         download_name=f"{full_name}_登記書類一式.zip")
    except Exception as e:
        flash(f'ZIP生成エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.registration_docs'))


# ============================================================
# 登記書類 PDF生成関数
# ============================================================

def _setup_pdf_canvas():
    """ReportLab PDF生成の共通セットアップ"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    jp_font_path = '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf'
    if os.path.exists(jp_font_path):
        try:
            if 'JapaneseGothic' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('JapaneseGothic', jp_font_path))
            font_name = 'JapaneseGothic'
        except Exception:
            font_name = 'Helvetica'
    else:
        font_name = 'Helvetica'

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_left = 25 * mm
    margin_right = 25 * mm
    margin_top = 25 * mm
    margin_bottom = 20 * mm
    content_width = width - margin_left - margin_right

    return c, buffer, width, height, margin_left, margin_right, margin_top, margin_bottom, content_width, font_name, mm


def _get_full_company_name(data):
    """法人種別位置を考慮した完全な会社名を返す"""
    company_type = data.get('company_type', '合同会社')
    company_name = data.get('company_name', '')
    position = data.get('company_type_position', 'before')
    if position == 'before':
        return f"{company_type}{company_name}"
    else:
        return f"{company_name}{company_type}"


def generate_registration_application_pdf(data):
    """設立登記申請書PDFを生成する"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    capital = data.get('capital', '0')
    try:
        capital_int = int(str(capital).replace(',', '').replace('円', ''))
        capital_str = f'金{capital_int:,}円'
    except Exception:
        capital_str = f'金{capital}円'
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    y = height - mt

    def draw_line(text, x=ml, size=10.5, bold=False, center=False, spacing=18):
        nonlocal y
        c.setFont(fn, size)
        if center:
            tw = c.stringWidth(text, fn, size)
            c.drawString((width - tw) / 2, y, text)
        else:
            c.drawString(x, y, text)
        y -= spacing

    def draw_separator():
        nonlocal y
        c.setLineWidth(0.5)
        c.line(ml, y + 5, width - mr, y + 5)
        y -= 8

    def draw_field(label, value, label_size=9, value_size=10.5):
        nonlocal y
        c.setFont(fn, label_size)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(ml, y, label)
        y -= 14
        c.setFont(fn, value_size)
        c.setFillColorRGB(0, 0, 0)
        # 長いテキストの折り返し
        line = ''
        lines = []
        for char in value:
            test = line + char
            if c.stringWidth(test, fn, value_size) <= cw - 5 * mm:
                line = test
            else:
                if line:
                    lines.append(line)
                line = char
        if line:
            lines.append(line)
        for ln in lines:
            c.drawString(ml + 3 * mm, y, ln)
            y -= 16
        y -= 4

    # タイトル
    if company_type == '合同会社':
        title = '合同会社設立登記申請書'
    elif company_type == '株式会社':
        title = '株式会社設立登記申請書'
    else:
        title = '一般社団法人設立登記申請書'

    c.setFont(fn, 18)
    tw = c.stringWidth(title, fn, 18)
    c.drawString((width - tw) / 2, y, title)
    y -= 40

    # 申請日
    draw_field('申請年月日', established_date)
    draw_separator()

    # 商号・名称
    label = '商号' if company_type != '一般社団法人' else '名称'
    draw_field(label, full_name)
    draw_separator()

    # 本店・主たる事務所
    office_label = '本店' if company_type != '一般社団法人' else '主たる事務所'
    draw_field(office_label, address)
    draw_separator()

    if company_type != '一般社団法人':
        # 資本金
        draw_field('資本金の額', capital_str)
        draw_separator()

    # 登記すべき事項
    draw_line('登記すべき事項', size=10.5)
    y -= 4
    c.setFont(fn, 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(ml, y, '（別紙または電磁的記録媒体に記録して添付）')
    c.setFillColorRGB(0, 0, 0)
    y -= 20
    draw_separator()

    # 登録免許税
    if company_type == '株式会社':
        try:
            tax = max(150000, int(capital_int * 7 / 1000))
            tax_str = f'金{tax:,}円'
        except Exception:
            tax_str = '金150,000円（最低額）'
        draw_field('登録免許税', tax_str)
    elif company_type == '一般社団法人':
        draw_field('登録免許税', '金60,000円')
    else:
        try:
            tax = max(60000, int(capital_int * 7 / 1000))
            tax_str = f'金{tax:,}円'
        except Exception:
            tax_str = '金60,000円（最低額）'
        draw_field('登録免許税', tax_str)
    draw_separator()

    # 添付書類
    y -= 4
    draw_line('添付書類', size=10.5)
    y -= 4
    c.setFont(fn, 9.5)
    docs = ['定款　１通']
    if company_type == '合同会社':
        docs += [
            '代表社員・業務執行社員の就任承諾書　各１通',
            '払込みがあったことを証する書面　１通',
            '資本金の額の決定を証する書面　１通',
            '本店所在場所の決定を証する書面　１通',
            '代表社員の印鑑証明書　１通',
            '印鑑届出書　１通',
        ]
    elif company_type == '株式会社':
        docs += [
            '発起人の決定書　１通',
            '設立時取締役・代表取締役の就任承諾書　各１通',
            '払込みがあったことを証する書面　１通',
            '資本金の額の決定を証する書面　１通',
            '代表取締役の印鑑証明書　１通',
            '印鑑届出書　１通',
        ]
    else:
        docs += [
            '設立時社員の決議書　１通',
            '設立時理事・代表理事の就任承諾書　各１通',
            '代表理事の印鑑証明書　１通',
            '印鑑届出書　１通',
        ]
    for doc in docs:
        c.drawString(ml + 5 * mm, y, f'・{doc}')
        y -= 16
    y -= 10
    draw_separator()

    # 申請人
    y -= 8
    draw_line('申請人（代表者）', size=10.5)
    y -= 4
    for m in rep_members:
        c.setFont(fn, 10.5)
        c.drawString(ml + 5 * mm, y, f'住所　{m.get("address", "")}')
        y -= 18
        c.drawString(ml + 5 * mm, y, f'氏名　{m.get("name", "")}　　　　　　　　　　　　　　印')
        y -= 25

    y -= 10
    draw_line('上記のとおり登記の申請をします。', size=9.5)

    # 法務局宛
    y -= 10
    c.setFont(fn, 10.5)
    c.drawString(ml, y, '　　　　法務局　御中')

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_payment_certificate_pdf(data):
    """払込みがあったことを証する書面（払込証明書）PDFを生成する"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    capital = data.get('capital', '0')
    try:
        capital_int = int(str(capital).replace(',', '').replace('円', ''))
        capital_str = f'金{capital_int:,}円'
    except Exception:
        capital_str = f'金{capital}円'
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    y = height - mt

    # タイトル
    title = '払込みがあったことを証する書面'
    c.setFont(fn, 16)
    tw = c.stringWidth(title, fn, 16)
    c.drawString((width - tw) / 2, y, title)
    y -= 50

    # 本文
    c.setFont(fn, 10.5)
    lines = [
        f'　　当{("会社" if company_type != "一般社団法人" else "法人")}の設立に際して、',
        f'　　次のとおり出資の払込みがあったことを証明します。',
        '',
        f'　　払込みを受けた金額　　{capital_str}',
        '',
        f'　　　　　　　　　　　　　　　　{established_date}',
        '',
    ]
    for line in lines:
        c.drawString(ml, y, line)
        y -= 20

    # 会社名
    c.setFont(fn, 10.5)
    c.drawString(ml + 20 * mm, y, full_name)
    y -= 25

    # 代表者
    for m in rep_members:
        if company_type == '合同会社':
            role = '代表社員'
        elif company_type == '株式会社':
            role = '代表取締役'
        else:
            role = '代表理事'
        c.drawString(ml + 20 * mm, y, f'{role}　{m.get("name", "")}　　　　　　　　　印')
        y -= 30

    y -= 20
    # 払込明細
    c.setFont(fn, 10.5)
    c.drawString(ml, y, '【払込明細】')
    y -= 20
    c.setFont(fn, 9.5)
    for m in members:
        contrib = m.get('contribution', '0')
        try:
            contrib_str = f'金{int(str(contrib).replace(",","").replace("円","")):,}円'
        except Exception:
            contrib_str = f'金{contrib}円'
        c.drawString(ml + 5 * mm, y, f'{m.get("name", "")}　　{contrib_str}')
        y -= 18
    y -= 10
    c.setFont(fn, 9.5)
    c.drawString(ml, y, f'合計　{capital_str}')

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_capital_certificate_pdf(data):
    """資本金の額の決定を証する書面PDFを生成する"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    capital = data.get('capital', '0')
    try:
        capital_int = int(str(capital).replace(',', '').replace('円', ''))
        capital_str = f'金{capital_int:,}円'
    except Exception:
        capital_str = f'金{capital}円'
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    y = height - mt

    title = '資本金の額の決定を証する書面'
    c.setFont(fn, 16)
    tw = c.stringWidth(title, fn, 16)
    c.drawString((width - tw) / 2, y, title)
    y -= 50

    c.setFont(fn, 10.5)
    lines = [
        f'　　設立に際して出資される財産の価額　　{capital_str}',
        '',
        f'　　上記の額から資本金として計上した額　　{capital_str}',
        '',
        '　　上記のとおり資本金の額が会社法及び会社計算規則の規定に',
        '　　従って計上されたことを証明します。',
        '',
        f'　　　　　　　　　　　　　　　　{established_date}',
        '',
    ]
    for line in lines:
        c.drawString(ml, y, line)
        y -= 20

    c.drawString(ml + 20 * mm, y, full_name)
    y -= 25

    for m in rep_members:
        if company_type == '合同会社':
            role = '代表社員'
        elif company_type == '株式会社':
            role = '代表取締役'
        else:
            role = '代表理事'
        c.drawString(ml + 20 * mm, y, f'{role}　{m.get("name", "")}　　　　　　　　　印')
        y -= 30

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_office_location_pdf(data):
    """本店所在場所の決定を証する書面PDFを生成する（合同会社用）"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    full_name = _get_full_company_name(data)
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    members = data.get('members', [])
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    y = height - mt

    title = '本店所在場所の決定を証する書面'
    c.setFont(fn, 16)
    tw = c.stringWidth(title, fn, 16)
    c.drawString((width - tw) / 2, y, title)
    y -= 50

    c.setFont(fn, 10.5)
    lines = [
        f'　　{full_name}の設立に際し、',
        '　　社員全員の同意により本店の所在場所を次のとおり決定しました。',
        '',
        f'　　本店所在場所　　{address}',
        '',
        f'　　　　　　　　　　　　　　　　{established_date}',
        '',
        f'　　{full_name}',
        '',
    ]
    for line in lines:
        c.drawString(ml, y, line)
        y -= 20

    c.setFont(fn, 10.5)
    for m in members:
        c.drawString(ml + 5 * mm, y, f'社員　{m.get("name", "")}　　　　　　　　　　　　　印')
        y -= 28

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_acceptance_letter_pdf(data):
    """就任承諾書PDFを生成する（全社員分）"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    members = data.get('members', [])
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    if company_type == '合同会社':
        role = '代表社員兼業務執行社員'
    elif company_type == '株式会社':
        role = '設立時取締役'
    else:
        role = '設立時理事'

    first_page = True
    for m in members:
        if not first_page:
            c.showPage()
        first_page = False

        y = height - mt

        title = '就任承諾書'
        c.setFont(fn, 18)
        tw = c.stringWidth(title, fn, 18)
        c.drawString((width - tw) / 2, y, title)
        y -= 50

        c.setFont(fn, 10.5)
        lines = [
            f'　　私は、{full_name}の{role}に就任することを',
            '　　承諾します。',
            '',
            f'　　　　　　　　　　　　　　　　{established_date}',
            '',
        ]
        for line in lines:
            c.drawString(ml, y, line)
            y -= 20

        c.drawString(ml + 10 * mm, y, f'住所　{m.get("address", "")}')
        y -= 25
        c.drawString(ml + 10 * mm, y, f'氏名　{m.get("name", "")}　　　　　　　　　　　　　印')

        # 代表者の場合は代表就任承諾書も追加
        if m.get('is_representative'):
            c.showPage()
            y = height - mt

            if company_type == '合同会社':
                rep_role = '代表社員'
            elif company_type == '株式会社':
                rep_role = '設立時代表取締役'
            else:
                rep_role = '設立時代表理事'

            c.setFont(fn, 18)
            tw = c.stringWidth(title, fn, 18)
            c.drawString((width - tw) / 2, y, title)
            y -= 50

            c.setFont(fn, 10.5)
            lines = [
                f'　　私は、{full_name}の{rep_role}に就任することを',
                '　　承諾します。',
                '',
                f'　　　　　　　　　　　　　　　　{established_date}',
                '',
            ]
            for line in lines:
                c.drawString(ml, y, line)
                y -= 20

            c.drawString(ml + 10 * mm, y, f'住所　{m.get("address", "")}')
            y -= 25
            c.drawString(ml + 10 * mm, y, f'氏名　{m.get("name", "")}　　　　　　　　　　　　　印')

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_founder_resolution_pdf(data):
    """発起人の決定書（株式会社）/ 設立時社員の決議書（一般社団法人）PDFを生成する"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    company_type = data.get('company_type', '株式会社')
    full_name = _get_full_company_name(data)
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    y = height - mt

    if company_type == '一般社団法人':
        title = '設立時社員の決議書'
        signer_role = '設立時社員'
        content_lines = [
            f'　　{full_name}の設立に際し、設立時社員全員の',
            '　　同意により次のとおり決議しました。',
            '',
            '　　記',
            '',
            f'　　１．本店所在場所を次のとおり定める。',
            f'　　　　{address}',
            '',
        ]
        for i, m in enumerate(rep_members):
            content_lines.append(f'　　２．設立時理事として次の者を選任する。')
            content_lines.append(f'　　　　{m.get("name", "")}')
            content_lines.append('')
        for i, m in enumerate(rep_members):
            content_lines.append(f'　　３．設立時代表理事として次の者を選定する。')
            content_lines.append(f'　　　　{m.get("name", "")}')
            content_lines.append('')
    else:
        title = '発起人の決定書'
        signer_role = '発起人'
        content_lines = [
            f'　　{full_name}の設立に際し、発起人全員の',
            '　　同意により次のとおり決定しました。',
            '',
            '　　記',
            '',
            f'　　１．本店所在場所を次のとおり定める。',
            f'　　　　{address}',
            '',
        ]
        for i, m in enumerate(rep_members):
            content_lines.append(f'　　２．設立時取締役として次の者を選任する。')
            content_lines.append(f'　　　　{m.get("name", "")}')
            content_lines.append('')
        for i, m in enumerate(rep_members):
            content_lines.append(f'　　３．設立時代表取締役として次の者を選定する。')
            content_lines.append(f'　　　　{m.get("name", "")}')
            content_lines.append('')

    c.setFont(fn, 16)
    tw = c.stringWidth(title, fn, 16)
    c.drawString((width - tw) / 2, y, title)
    y -= 40

    c.setFont(fn, 10.5)
    for line in content_lines:
        c.drawString(ml, y, line)
        y -= 18

    y -= 10
    c.drawString(ml, y, f'　　　　　　　　　　　　　　　　{established_date}')
    y -= 30
    c.drawString(ml + 20 * mm, y, full_name)
    y -= 25

    for m in members:
        c.drawString(ml + 20 * mm, y, f'{signer_role}　{m.get("name", "")}　　　　　　　　　印')
        y -= 28

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_seal_registration_pdf(data):
    """印鑑届出書PDFを生成する"""
    c, buffer, width, height, ml, mr, mt, mb, cw, fn, mm = _setup_pdf_canvas()

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    y = height - mt

    title = '印　鑑　届　出　書'
    c.setFont(fn, 18)
    tw = c.stringWidth(title, fn, 18)
    c.drawString((width - tw) / 2, y, title)
    y -= 50

    c.setFont(fn, 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(ml, y, '（商業・法人登記用）')
    c.setFillColorRGB(0, 0, 0)
    y -= 25

    c.setFont(fn, 10.5)

    def draw_field_line(label, value):
        nonlocal y
        c.setFont(fn, 9)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(ml, y, label)
        c.setFillColorRGB(0, 0, 0)
        y -= 14
        c.setFont(fn, 10.5)
        c.drawString(ml + 3 * mm, y, value)
        y -= 22
        c.setLineWidth(0.3)
        c.line(ml, y + 4, width - mr, y + 4)
        y -= 8

    if company_type == '合同会社':
        role = '代表社員'
    elif company_type == '株式会社':
        role = '代表取締役'
    else:
        role = '代表理事'

    draw_field_line('商号・名称', full_name)
    draw_field_line('本店・主たる事務所', address)

    for m in rep_members:
        draw_field_line(f'{role}の氏名', m.get('name', ''))
        draw_field_line(f'{role}の住所', m.get('address', ''))

    y -= 10
    c.setFont(fn, 10.5)
    c.drawString(ml, y, '印鑑（右枠内に押印してください）')
    y -= 10

    # 印鑑押印枠
    seal_size = 40 * mm
    seal_x = (width - seal_size) / 2
    c.setLineWidth(1)
    c.rect(seal_x, y - seal_size, seal_size, seal_size)
    c.setFont(fn, 8)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawString(seal_x + 5 * mm, y - seal_size / 2, '（代表印を押印）')
    c.setFillColorRGB(0, 0, 0)
    y -= seal_size + 20

    c.setFont(fn, 10.5)
    c.drawString(ml, y, f'　　　　　　　　　　　　　　　　{established_date}')
    y -= 30

    for m in rep_members:
        c.drawString(ml + 10 * mm, y, f'届出人（{role}）　{m.get("name", "")}　　　　　　　印')
        y -= 28

    y -= 10
    c.setFont(fn, 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(ml, y, '※ 印鑑証明書（市区町村発行）を添付してください。')

    c.save()
    buffer.seek(0)
    return buffer.read()

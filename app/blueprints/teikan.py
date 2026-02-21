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


@bp.route('/')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def index():
    """定款アプリトップページ"""
    return render_template('teikan/index.html')


@bp.route('/step1', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def step1():
    """ステップ1: 基本情報入力（法人形態・商号・住所・登記方法）"""
    data = get_session_data()

    if request.method == 'POST':
        data['company_type'] = request.form.get('company_type', '合同会社')
        data['company_name'] = request.form.get('company_name', '')
        data['company_name_kana'] = request.form.get('company_name_kana', '')
        data['registration_method'] = request.form.get('registration_method', '法務局に直接提出')
        data['postal_code'] = request.form.get('postal_code', '')
        data['address'] = request.form.get('address', '')
        data['address_detail'] = request.form.get('address_detail', '')
        save_session_data(data)
        return redirect(url_for('teikan.step2'))

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
            }
            if member['name']:
                members.append(member)

        data['members'] = members
        data['capital'] = request.form.get('capital', '0')
        data['phone'] = request.form.get('phone', '')
        save_session_data(data)
        return redirect(url_for('teikan.step3'))

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
        return redirect(url_for('teikan.step4'))

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
        return redirect(url_for('teikan.confirm'))

    return render_template('teikan/step4.html', data=data)


@bp.route('/confirm')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def confirm():
    """確認画面：入力内容の確認"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
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
    """定款データをDBに保存する"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))

    tenant_id = session.get('tenant_id')
    user_id = session.get('user_id')
    db = SessionLocal()
    try:
        # テーブルが存在しない場合は作成
        from app.db import Base, engine
        Base.metadata.create_all(bind=engine)

        doc = TeikanDocument(
            tenant_id=tenant_id,
            created_by=user_id,
            company_name=data.get('company_name', ''),
            company_type=data.get('company_type', '合同会社'),
            data_json=json.dumps(data, ensure_ascii=False)
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        flash(f'「{doc.company_type}{doc.company_name}」の定款を保存しました', 'success')
        session.pop('teikan_data', None)
        return redirect(url_for('teikan.history'))
    except Exception as e:
        db.rollback()
        flash(f'保存エラー: {str(e)}', 'error')
        return redirect(url_for('teikan.confirm'))
    finally:
        db.close()


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
        flash('定款データを読み込みました。内容を確認・編集してください', 'info')
        return redirect(url_for('teikan.confirm'))
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

    # ===== 表紙 =====
    company_name = data.get('company_name', '')
    company_type = data.get('company_type', '合同会社')

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

    # ===== 第一章 総則 =====
    draw_chapter('第一章　総則')

    draw_article('1', '商号',
        [f'当会社は、{company_type}{company_name}と称する。'])

    purposes = data.get('purposes', [])
    purpose_lines = ['当会社は、次の事業を営むことを目的とする。']
    for i, p in enumerate(purposes, 1):
        purpose_lines.append(f'　{i}．{p}')
    draw_article('2', '目的', purpose_lines)

    address = data.get('address', '') + data.get('address_detail', '')
    draw_article('3', '本店の所在地',
        [f'当会社は、本店を{address}に置く。'])

    draw_article('4', '公告方法',
        ['当会社の公告は、官報に掲載する方法により行う。'])

    # ===== 第二章 社員及び出資 =====
    draw_chapter('第二章　社員及び出資')

    capital = data.get('capital', '0')
    try:
        capital_int = int(str(capital).replace(',', '').replace('円', ''))
        capital_str = f'{capital_int:,}円'
    except Exception:
        capital_str = f'{capital}円'

    members = data.get('members', [])
    contribution_lines = ['社員の氏名、住所及び出資の目的並びにその価額は、次のとおりである。']
    for m in members:
        name = m.get('name', '')
        addr = m.get('address', '')
        contrib = m.get('contribution', '0')
        try:
            contrib_int = int(str(contrib).replace(',', '').replace('円', ''))
            contrib_str = f'{contrib_int:,}円'
        except Exception:
            contrib_str = f'{contrib}円'
        contribution_lines.append(f'　氏名：{name}')
        contribution_lines.append(f'　住所：{addr}')
        contribution_lines.append(f'　出資の価額：金{contrib_str}')
        contribution_lines.append('')

    draw_article('5', '社員の出資', contribution_lines)
    draw_article('6', '資本金の額',
        [f'当会社の資本金の額は、金{capital_str}とする。'])

    # ===== 第三章 業務執行及び代表 =====
    draw_chapter('第三章　業務執行及び代表')

    draw_article('7', '業務執行社員',
        ['当会社の業務は、社員全員が執行する。',
         '業務を執行する社員は、当会社を代表する。'])

    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]

    rep_lines = []
    for m in rep_members:
        rep_lines.append(f'　{m.get("name", "")}')
    if not rep_lines:
        rep_lines = ['　（代表社員氏名）']

    draw_article('8', '代表社員',
        ['当会社を代表する社員は、次のとおりとする。'] + rep_lines)

    draw_article('9', '業務執行の決定',
        ['当会社の業務執行は、社員の過半数をもって決定する。'])

    # ===== 第四章 計算 =====
    draw_chapter('第四章　計算')

    fiscal_start_month = data.get('fiscal_start_month', '3')
    fiscal_start_day = data.get('fiscal_start_day', '1')
    fiscal_end_month = data.get('fiscal_end_month', '2')
    fiscal_end_day = data.get('fiscal_end_day', '末日')

    if fiscal_end_day == '末日':
        fiscal_end_str = f'{fiscal_end_month}月末日'
    else:
        fiscal_end_str = f'{fiscal_end_month}月{fiscal_end_day}日'

    draw_article('10', '事業年度',
        [f'当会社の事業年度は、毎年{fiscal_start_month}月{fiscal_start_day}日から翌年{fiscal_end_str}までとする。'])

    draw_article('11', '利益の配当',
        ['当会社は、毎事業年度終了後、社員の出資の価額に応じて利益の配当を行う。'])

    # ===== 第五章 附則 =====
    draw_chapter('第五章　附則')

    established_date = data.get('established_date', '') or '令和　　年　　月　　日'

    draw_article('12', '設立に際して出資される財産の価額',
        [f'当会社の設立に際して出資される財産の価額は、金{capital_str}とする。'])

    draw_article('13', '最初の事業年度',
        [f'当会社の最初の事業年度は、当会社成立の日から{fiscal_end_str}までとする。'])

    draw_article('14', '設立時代表社員',
        ['当会社の設立時の代表社員は、次のとおりとする。'] + rep_lines)

    draw_article('15', '附則',
        [f'当会社の定款は、{established_date}に作成した。'])

    # ===== 署名欄 =====
    check_page_break(60)
    set_y(get_y() - 20)
    c.setFont(font_name, 10.5)
    c.drawString(margin_left, get_y(), '以上、合同会社設立のため、この定款を作成し、社員が記名押印する。')
    set_y(get_y() - 30)
    c.drawString(margin_left, get_y(), f'　　　　　　　　　　　　　　　　　　　　{established_date}')
    set_y(get_y() - 30)

    for m in members:
        check_page_break(20)
        c.setFont(font_name, 10.5)
        c.drawString(margin_left + 20 * mm, get_y(), f'社員　{m.get("name", "")}　　　　　　　印')
        set_y(get_y() - 25)

    c.save()
    buffer.seek(0)
    return buffer.read()

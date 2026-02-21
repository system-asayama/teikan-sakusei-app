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
# from app.utils.inkan_pdf import generate_inkan_pdf  # LibreOffice UNO版（スラグサイズ超過のため無効化）
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
        data['has_board_of_directors'] = request.form.get('has_board_of_directors', 'false')
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


@bp.route('/new_corporation')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def new_corporation():
    """新規法人設立：セッションをクリアして中間ページへ"""
    session.pop('teikan_data', None)
    session.pop('teikan_draft_id', None)
    session.modified = True
    return redirect(url_for('teikan.new_setup'))


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

    # 日本語フォントの設定（リポジトリ内 → システムの順に探索）
    font_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'ipag.ttf'),
        '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    ]
    jp_font_path = None
    for candidate in font_candidates:
        if os.path.exists(candidate):
            jp_font_path = candidate
            break

    if jp_font_path:
        try:
            if 'JapaneseGothic' not in pdfmetrics.getRegisteredFontNames():
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



@bp.route('/registration_docs/download/inkan_card')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def download_inkan_card():
    """印鑑カード交付申請書PDFダウンロード"""
    data = get_session_data()
    if not data.get('company_name'):
        flash('最初から入力してください', 'warning')
        return redirect(url_for('teikan.step1'))
    try:
        pdf_bytes = generate_inkan_card_pdf(data)
        company_type = data.get('company_type', '合同会社')
        company_name = data.get('company_name', '会社')
        filename = f"{company_type}{company_name}_印鑑カード交付申請書.pdf"
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

            # 印鑑カード交付申請書
            inkan_card_pdf = generate_inkan_card_pdf(data)
            zf.writestr(f"{full_name}_印鑑カード交付申請書.pdf", inkan_card_pdf)

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

    # フォントパスの候補（リポジトリ内 → システム）
    font_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'ipag.ttf'),
        '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    ]
    jp_font_path = None
    for candidate in font_candidates:
        if os.path.exists(candidate):
            jp_font_path = candidate
            break

    if jp_font_path:
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


def generate_registration_application_pdf(data):  # noqa: C901
    """設立登記申請書PDFを生成する（法務局公式雛形準拠）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import io
    import os

    buffer = io.BytesIO()
    width, height = A4

    # フォント設定
    fn = 'IPAGothic'
    font_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'fonts', 'ipag.ttf'),
        '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    ]
    for fp in font_paths:
        fp = os.path.normpath(fp)
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont(fn, fp))
            except Exception:
                pass
            break

    company_type = data.get('company_type', '合同会社')
    has_board = data.get('has_board_of_directors', 'false') == 'true'
    full_name = _get_full_company_name(data)
    company_name_kana = data.get('company_name_kana', '')
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    capital = data.get('capital', '0')
    phone = data.get('phone', '')
    try:
        capital_int = int(str(capital).replace(',', '').replace('円', ''))
    except Exception:
        capital_int = 0
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    rep = rep_members[0] if rep_members else {}
    established_date = data.get('established_date', '') or ''

    # 登録免許税計算
    if company_type == '株式会社':
        tax = max(150000, int(capital_int * 7 / 1000))
    elif company_type == '一般社団法人':
        tax = 60000
    else:
        tax = max(60000, int(capital_int * 7 / 1000))

    # ページ設定
    outer_left = 15 * mm
    outer_right = 15 * mm
    outer_top = 10 * mm

    def new_page(c):
        c.showPage()

    # ============================================================
    # ページ共通：テキスト描画ヘルパー
    # ============================================================
    def draw_text(c, x, y, text, size=10, bold=False):
        c.setFont(fn, size)
        c.drawString(x, y, text)

    def draw_text_center(c, y, text, size=10):
        c.setFont(fn, size)
        tw = c.stringWidth(text, fn, size)
        c.drawString((width - tw) / 2, y, text)

    def draw_multiline(c, x, y, text, size=9.5, max_width=None, line_height=14):
        """\u9577いテキストを折り返して描画する"""
        if max_width is None:
            max_width = width - outer_left - outer_right
        c.setFont(fn, size)
        line = ''
        lines = []
        for ch in text:
            test = line + ch
            if c.stringWidth(test, fn, size) <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = ch
        if line:
            lines.append(line)
        cur_y = y
        for ln in lines:
            c.drawString(x, cur_y, ln)
            cur_y -= line_height
        return cur_y

    # ============================================================
    # ページ 1: 受付番号票貼付欄 + 申請書本体
    # ============================================================
    c = pdfcanvas.Canvas(buffer, pagesize=A4)

    # --- 受付番号票貼付欄（枚枠） ---
    ticket_left = outer_left
    ticket_right = width - outer_right
    ticket_top = height - outer_top
    ticket_bottom = ticket_top - 28 * mm
    c.setLineWidth(1)
    c.rect(ticket_left, ticket_bottom, ticket_right - ticket_left, ticket_top - ticket_bottom)
    draw_text_center(c, ticket_bottom + (ticket_top - ticket_bottom) / 2 - 3 * mm, '受付番号票貼付欄', size=11)

    # --- タイトル ---
    if company_type == '合同会社':
        title = '合同会社設立登記申請書'
    elif company_type == '株式会社':
        title = '株式会社設立登記申請書'
    else:
        title = '一般社団法人設立登記申請書'

    title_y = ticket_bottom - 14 * mm
    draw_text_center(c, title_y, title, size=16)

    cur_y = title_y - 12 * mm
    left_indent = outer_left + 10 * mm
    label_x = outer_left + 5 * mm

    def draw_item(c, label, value, kana=None):
        """1項目を描画する"""
        nonlocal cur_y
        if kana:
            draw_text(c, left_indent, cur_y, 'フリガナ', size=8)
            cur_y -= 10
            draw_text(c, left_indent, cur_y, kana, size=9.5)
            cur_y -= 12
        draw_text(c, label_x, cur_y, label, size=10.5)
        if value:
            draw_multiline(c, left_indent, cur_y, value, size=10.5,
                           max_width=width - left_indent - outer_right - 5 * mm)
        cur_y -= 16

    # 商号
    draw_item(c, '1．商　号', full_name, kana=company_name_kana if company_name_kana else None)
    cur_y -= 2

    # 本店
    draw_item(c, '1．本　店', address)
    cur_y -= 2

    # 登記の事由
    if established_date:
        jiyuu_text = f'令和{established_date}発起設立の手続終了'
    else:
        jiyuu_text = '令和　　年　　月　　日発起設立の手続終了'
    draw_text(c, label_x, cur_y, '1．登記の事由', size=10.5)
    draw_text(c, left_indent + 20 * mm, cur_y, jiyuu_text, size=10.5)
    cur_y -= 16
    cur_y -= 2

    # 登記すべき事項
    draw_text(c, label_x, cur_y, '1．登記すべき事項', size=10.5)
    cur_y -= 16
    cur_y -= 2

    # 課税標準金額
    draw_text(c, label_x, cur_y, '1．課税標準金額', size=10.5)
    draw_text(c, label_x + 28 * mm, cur_y, '金', size=10.5)
    draw_text(c, label_x + 33 * mm, cur_y, f'{capital_int:,}', size=10.5)
    draw_text(c, label_x + 33 * mm + c.stringWidth(f'{capital_int:,}', fn, 10.5) + 2 * mm, cur_y, '円', size=10.5)
    cur_y -= 16
    cur_y -= 2

    # 登録免許税
    draw_text(c, label_x, cur_y, '1．登録免許税', size=10.5)
    draw_text(c, label_x + 28 * mm, cur_y, '金', size=10.5)
    draw_text(c, label_x + 33 * mm, cur_y, f'{tax:,}', size=10.5)
    draw_text(c, label_x + 33 * mm + c.stringWidth(f'{tax:,}', fn, 10.5) + 2 * mm, cur_y, '円', size=10.5)
    cur_y -= 16
    cur_y -= 4

    # 添付書類
    draw_text(c, label_x - 5 * mm, cur_y, '1．添付書類', size=10.5)
    cur_y -= 14

    doc_indent = outer_left + 15 * mm
    right_num_x = width - outer_right - 18 * mm

    def draw_doc_line(c, doc_name, count_str):
        nonlocal cur_y
        c.setFont(fn, 9.5)
        c.drawString(doc_indent, cur_y, doc_name)
        c.drawRightString(right_num_x + 12 * mm, cur_y, count_str)
        cur_y -= 13

    # 添付書類リスト（会社種別・取締役会設置の有無により分岐）
    if company_type == '株式会社':
        if has_board:
            # 取締役会設置版
            draw_doc_line(c, '定款', '1通')
            draw_doc_line(c, '発起人の同意書', '通')
            draw_doc_line(c, '設立時代表取締役を選定したことを証する書面', '1通')
            draw_doc_line(c, '設立時取締役、設立時代表取締役及び設立時監査役の就任承諾書', '通')
            draw_doc_line(c, '印鑑証明書', '通')
            draw_doc_line(c, '本人確認証明書', '通')
            draw_doc_line(c, '設立時取締役及び設立時監査役の調査報告書及びその附属書類', '1通')
            draw_doc_line(c, '払込みを証する書面', '1通')
            draw_doc_line(c, '資本金の額の計上に関する設立時代表取締役の証明書', '1通')
            draw_doc_line(c, '委任状', '1通')
        else:
            # 取締役会非設置版
            draw_doc_line(c, '定款', '1通')
            draw_doc_line(c, '発起人の同意書', '通')
            draw_doc_line(c, '設立時代表取締役を選定したことを証する書面', '1通')
            draw_doc_line(c, '設立時取締役（及び設立時監査役）の就任承諾書', '通')
            draw_doc_line(c, '印鑑証明書', '通')
            draw_doc_line(c, '本人確認証明書', '通')
            draw_doc_line(c, '設立時取締役（及び設立時監査役）の調査報告書及びその附属書類', '1通')
            draw_doc_line(c, '払込みを証する書面', '1通')
            draw_doc_line(c, '資本金の額の計上に関する設立時代表取締役の証明書', '1通')
            draw_doc_line(c, '委任状', '1通')
    elif company_type == '合同会社':
        draw_doc_line(c, '定款', '1通')
        draw_doc_line(c, '発起人の同意書', '通')
        draw_doc_line(c, '代表社員・業務執行社員の就任承諾書', '通')
        draw_doc_line(c, '印鑑証明書', '通')
        draw_doc_line(c, '本人確認証明書', '通')
        draw_doc_line(c, '払込みを証する書面', '1通')
        draw_doc_line(c, '資本金の額の計上に関する証明書', '1通')
        draw_doc_line(c, '委任状', '1通')
    else:  # 一般社団法人
        draw_doc_line(c, '定款', '1通')
        draw_doc_line(c, '設立時社員の決議書', '1通')
        draw_doc_line(c, '設立時理事・代表理事の就任承諾書', '通')
        draw_doc_line(c, '印鑑証明書', '通')
        draw_doc_line(c, '本人確認証明書', '通')
        draw_doc_line(c, '委任状', '1通')

    cur_y -= 6

    # 「上記のとおり、登記の申請をします。」
    draw_text(c, outer_left, cur_y,
              '上記のとおり、登記の申請をします。', size=10.5)
    cur_y -= 16
    cur_y -= 4

    # 申請日
    if established_date:
        date_text = f'令和{established_date}'
    else:
        date_text = '令和　　年　　月　　日'
    draw_text(c, outer_left + 15 * mm, cur_y, date_text, size=10.5)
    cur_y -= 16
    cur_y -= 4

    # 申請人・代表取締役（取締役会設置版は1ページ目に記載）
    if company_type != '株式会社' or has_board:
        draw_text(c, outer_left + 15 * mm, cur_y, '申請人', size=10.5)
        cur_y -= 16
        cur_y -= 4
        draw_text(c, outer_left + 15 * mm, cur_y, '代表取締役　' + rep.get('name', ''), size=10.5)
        # 印鑑押印欄（点線丸）
        seal_cx = width - outer_right - 20 * mm
        seal_cy = cur_y + 5 * mm
        seal_r = 12 * mm
        c.setDash(3, 3)
        c.setLineWidth(0.8)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.circle(seal_cx, seal_cy, seal_r, stroke=1, fill=0)
        c.setDash()
        c.setStrokeColorRGB(0, 0, 0)
        cur_y -= 16

    # 連絡先電話番号・法務局宛・封筒印鑑欄（取締役会設置版または株式会社以外のみ1ページ目に表示）
    if company_type != '株式会社' or has_board:
        cur_y -= 4
        draw_text(c, outer_left + 15 * mm, cur_y, '連絡先の電話番号　' + phone, size=10)
        cur_y -= 14

        draw_text(c, outer_left + 15 * mm, cur_y, '法務局　　　支　局　　御中', size=10.5)
        cur_y -= 12
        draw_text(c, outer_left + 15 * mm + 20 * mm, cur_y, '出張所', size=10.5)

        # 封筒印鑑押印欄（点線丸）
        seal2_cx = outer_left + 15 * mm
        seal2_cy = cur_y - 15 * mm
        seal2_r = 12 * mm
        c.setDash(3, 3)
        c.setLineWidth(0.8)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.circle(seal2_cx, seal2_cy, seal2_r, stroke=1, fill=0)
        c.setDash()
        c.setStrokeColorRGB(0, 0, 0)

    # ============================================================
    # ページ 2: 取締役会非設置版の申請人欄（非設置版のみ）
    # ============================================================
    if company_type == '株式会社' and not has_board:
        c.showPage()
        cur_y2 = height - outer_top - 10 * mm

        draw_text(c, outer_left + 15 * mm, cur_y2, '申請人', size=10.5)
        cur_y2 -= 16
        cur_y2 -= 4
        draw_text(c, outer_left + 15 * mm, cur_y2, '代表取締役　' + rep.get('name', ''), size=10.5)
        # 印鑑押印欄（点線丸）
        seal_cx2 = width - outer_right - 20 * mm
        seal_cy2 = cur_y2 + 5 * mm
        seal_r2 = 12 * mm
        c.setDash(3, 3)
        c.setLineWidth(0.8)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.circle(seal_cx2, seal_cy2, seal_r2, stroke=1, fill=0)
        c.setDash()
        c.setStrokeColorRGB(0, 0, 0)
        cur_y2 -= 16
        cur_y2 -= 4

        draw_text(c, outer_left + 15 * mm, cur_y2, '連絡先の電話番号　' + phone, size=10)
        cur_y2 -= 14

        draw_text(c, outer_left + 15 * mm, cur_y2, '法務局　　　支　局　　御中', size=10.5)
        cur_y2 -= 12
        draw_text(c, outer_left + 15 * mm + 20 * mm, cur_y2, '出張所', size=10.5)

        seal3_cx = outer_left + 15 * mm
        seal3_cy = cur_y2 - 15 * mm
        seal3_r = 12 * mm
        c.setDash(3, 3)
        c.setLineWidth(0.8)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.circle(seal3_cx, seal3_cy, seal3_r, stroke=1, fill=0)
        c.setDash()
        c.setStrokeColorRGB(0, 0, 0)

    # ============================================================
    # 最終ページ: 収入印紙貼付台紙
    # ============================================================
    c.showPage()
    cur_y3 = height - outer_top - 5 * mm
    draw_text(c, outer_left, cur_y3, '収入印紙貼付台紙', size=10)
    cur_y3 -= 10 * mm

    # 印鑑押印欄（点線丸）
    seal4_cx = outer_left + 15 * mm
    seal4_cy = cur_y3 - 20 * mm
    seal4_r = 12 * mm
    c.setDash(3, 3)
    c.setLineWidth(0.8)
    c.setStrokeColorRGB(0.8, 0, 0)
    c.circle(seal4_cx, seal4_cy, seal4_r, stroke=1, fill=0)
    c.setDash()
    c.setStrokeColorRGB(0, 0, 0)

    # 収入印紙貼付欄（ギザギザ枚枠）
    stamp_left = width - outer_right - 30 * mm
    stamp_bottom = cur_y3 - 35 * mm
    stamp_w = 25 * mm
    stamp_h = 30 * mm
    # ギザギザ枚枠を描画
    c.setLineWidth(0.5)
    seg = 2 * mm
    sx, sy = stamp_left, stamp_bottom
    sw, sh = stamp_w, stamp_h
    # 上辺
    x = sx
    while x < sx + sw:
        c.line(x, sy + sh, min(x + seg, sx + sw), sy + sh)
        x += seg * 2
    # 下辺
    x = sx
    while x < sx + sw:
        c.line(x, sy, min(x + seg, sx + sw), sy)
        x += seg * 2
    # 左辺
    y2 = sy
    while y2 < sy + sh:
        c.line(sx, y2, sx, min(y2 + seg, sy + sh))
        y2 += seg * 2
    # 右辺
    y2 = sy
    while y2 < sy + sh:
        c.line(sx + sw, y2, sx + sw, min(y2 + seg, sy + sh))
        y2 += seg * 2
    # 収入印紙テキスト
    draw_text(c, stamp_left + 3 * mm, stamp_bottom + stamp_h / 2 + 2 * mm, '収　入', size=9)
    draw_text(c, stamp_left + 3 * mm, stamp_bottom + stamp_h / 2 - 8 * mm, '印　紙', size=9)

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


def generate_seal_registration_pdf(data):  # noqa: C901
    """印鑑届出書PDFを生成する（法務局公式書式に準拠）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # フォント設定
    font_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'ipag.ttf'),
        '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    ]
    jp_font_path = None
    for candidate in font_candidates:
        if os.path.exists(candidate):
            jp_font_path = candidate
            break
    if jp_font_path:
        try:
            if 'JapaneseGothic' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('JapaneseGothic', jp_font_path))
            fn = 'JapaneseGothic'
        except Exception:
            fn = 'Helvetica'
    else:
        fn = 'Helvetica'

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    rep = rep_members[0] if rep_members else {}

    if company_type == '合同会社':
        role = '代表社員'
    elif company_type == '株式会社':
        role = '代表取締役'
    else:
        role = '代表理事'

    # ページ余白
    outer_left = 10 * mm
    outer_right = 10 * mm
    outer_top = 8 * mm
    outer_bottom = 8 * mm

    # ============================================================
    # タイトル
    # ============================================================
    title = '印　鑑　（　改　印　）　届　書'
    c.setFont(fn, 16)
    tw = c.stringWidth(title, fn, 16)
    c.drawString((width - tw) / 2, height - outer_top - 10 * mm, title)

    # 注意書き
    c.setFont(fn, 9)
    c.drawString(outer_left + 2 * mm, height - outer_top - 16 * mm, '※　太枠の中に書いてください。')

    # ============================================================
    # ヘッダー行（法務局・年月日）
    # ============================================================
    header_y = height - outer_top - 22 * mm
    c.setFont(fn, 8.5)
    c.drawString(outer_left + 2 * mm, header_y, '（地方）法務局')
    c.drawString(outer_left + 38 * mm, header_y, '支局・出張所')
    c.drawString(outer_left + 130 * mm, header_y, '年')
    c.drawString(outer_left + 148 * mm, header_y, '月')
    c.drawString(outer_left + 162 * mm, header_y, '日　届出')

    # ============================================================
    # レイアウト定義
    # ============================================================
    seal_col_w = 42 * mm      # 左側印鑑押印欄の幅
    label_col_w = 30 * mm     # ラベル列の幅（右側記入欄内）
    right_area_x = outer_left + seal_col_w  # 右側記入欄の開始X座標

    # 行の高さ定義
    row_company_h = 11 * mm
    row_address_h = 11 * mm
    row_shikaku_h = 32 * mm
    row_card_h = 22 * mm
    row_deliv_h = 9 * mm
    row_addr_h = 9 * mm
    row_furi_h = 5 * mm
    row_name_h = 9 * mm

    total_height = (row_company_h + row_address_h + row_shikaku_h +
                    row_card_h + row_deliv_h + row_addr_h + row_furi_h + row_name_h)

    # メイン枠の座標
    main_box_top = header_y - 3 * mm
    main_box_bottom = main_box_top - total_height
    main_box_left = outer_left
    main_box_right = width - outer_right
    main_box_width = main_box_right - main_box_left

    # ============================================================
    # メイン枠（太枠）
    # ============================================================
    c.setLineWidth(2)
    c.rect(main_box_left, main_box_bottom, main_box_width, total_height)
    c.setLineWidth(0.5)

    # ============================================================
    # 縦区切り線（印鑑欄と記入欄の境界）
    # ============================================================
    c.line(main_box_left + seal_col_w, main_box_bottom,
           main_box_left + seal_col_w, main_box_top)

    # ============================================================
    # 各行のY座標を計算（上から下へ）
    # ============================================================
    y_company_top = main_box_top
    y_company_bot = y_company_top - row_company_h

    y_address_top = y_company_bot
    y_address_bot = y_address_top - row_address_h

    y_shikaku_top = y_address_bot
    y_shikaku_bot = y_shikaku_top - row_shikaku_h

    y_card_top = y_shikaku_bot
    y_card_bot = y_card_top - row_card_h

    y_deliv_top = y_card_bot
    y_deliv_bot = y_deliv_top - row_deliv_h

    y_addr_top = y_deliv_bot
    y_addr_bot = y_addr_top - row_addr_h

    y_furi_top = y_addr_bot
    y_furi_bot = y_furi_top - row_furi_h

    y_name_top = y_furi_bot
    y_name_bot = y_name_top - row_name_h

    # ============================================================
    # 横線を描画
    # ============================================================
    for _y in [y_company_bot, y_address_bot, y_shikaku_bot, y_card_bot,
               y_deliv_bot, y_addr_bot, y_furi_bot]:
        c.line(main_box_left, _y, main_box_right, _y)

    # ============================================================
    # 左側：注1テキスト + 印鑑押印枠
    # ============================================================
    c.setFont(fn, 7)
    c.drawString(main_box_left + 1 * mm, main_box_top - 3 * mm,
                 '（注１）（届出印は鮮明に押印してください。）')

    seal_box_size = 30 * mm
    seal_box_x = main_box_left + (seal_col_w - seal_box_size) / 2
    seal_box_y = main_box_top - 5 * mm - seal_box_size

    c.setLineWidth(1)
    c.rect(seal_box_x, seal_box_y, seal_box_size, seal_box_size)
    c.setLineWidth(0.5)
    c.setFont(fn, 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(seal_box_x + 1 * mm, seal_box_y + seal_box_size / 2 - 2 * mm, '（代表印を押印）')
    c.setFillColorRGB(0, 0, 0)

    # ============================================================
    # 商号・名称行
    # ============================================================
    c.line(right_area_x + label_col_w, y_company_bot,
           right_area_x + label_col_w, y_company_top)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + 2 * mm,
                 y_company_bot + row_company_h / 2 - 2 * mm, '商号・名称')
    c.setFont(fn, 9)
    c.drawString(right_area_x + label_col_w + 3 * mm,
                 y_company_bot + row_company_h / 2 - 2 * mm, full_name)

    # ============================================================
    # 本店・主たる事務所行
    # ============================================================
    c.line(right_area_x + label_col_w, y_address_bot,
           right_area_x + label_col_w, y_address_top)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + 2 * mm,
                 y_address_bot + row_address_h / 2 - 2 * mm, '本店・主たる事務所')
    c.setFont(fn, 9)
    c.drawString(right_area_x + label_col_w + 3 * mm,
                 y_address_bot + row_address_h / 2 - 2 * mm, address)

    # ============================================================
    # 資格/氏名/生年月日複合行（印鑑提出者）
    # ============================================================
    c.line(right_area_x + label_col_w, y_shikaku_bot,
           right_area_x + label_col_w, y_shikaku_top)

    # 「印鑑提出者」縦書きラベル
    c.setFont(fn, 8)
    chars = ['印', '鑑', '提', '出', '者']
    char_spacing = row_shikaku_h / (len(chars) + 1)
    for i, ch in enumerate(chars):
        c.drawString(right_area_x + 3 * mm,
                     y_shikaku_top - (i + 1) * char_spacing, ch)

    # 資格行（上1/3）
    row1_h = row_shikaku_h / 3
    row1_bot = y_shikaku_top - row1_h
    c.line(right_area_x + label_col_w, row1_bot, main_box_right, row1_bot)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + label_col_w + 2 * mm, y_shikaku_top - 4 * mm, '資　格')
    c.setFont(fn, 7)
    c.drawString(right_area_x + label_col_w + 22 * mm, y_shikaku_top - 3.5 * mm,
                 '代表取締役・取締役・代表理事')
    c.drawString(right_area_x + label_col_w + 22 * mm, y_shikaku_top - 7.5 * mm,
                 f'理事・（　{role}　）')

    # 氏名行（中1/3）
    row2_bot = y_shikaku_top - row1_h * 2
    c.line(right_area_x + label_col_w, row2_bot, main_box_right, row2_bot)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + label_col_w + 2 * mm, row1_bot - 4 * mm, '氏　名')
    c.setFont(fn, 9)
    c.drawString(right_area_x + label_col_w + 20 * mm, row1_bot - 5 * mm, rep.get('name', ''))

    # 生年月日行（下1/3）
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + label_col_w + 2 * mm, row2_bot - 4 * mm, '生年月日')
    c.drawString(right_area_x + label_col_w + 20 * mm, row2_bot - 4 * mm,
                 '大・昭・平・西暦　　　年　　　月　　　日生')

    # ============================================================
    # 印鑑カード欄 + 会社法人等番号欄
    # ============================================================
    card_div_x = main_box_left + seal_col_w + label_col_w
    c.line(card_div_x, y_card_bot, card_div_x, y_card_top)

    c.setFont(fn, 7.5)
    c.drawString(main_box_left + 2 * mm, y_card_top - 5 * mm, '□　印鑑カードは引き継がない。')
    c.setFont(fn, 7)
    c.drawString(main_box_left + 1 * mm, y_card_top - 9 * mm, '（注')
    c.drawString(main_box_left + 1 * mm, y_card_top - 12.5 * mm, '２）')
    c.setFont(fn, 7.5)
    c.drawString(main_box_left + 7 * mm, y_card_top - 9 * mm, '□　印鑑カードを引き継ぐ。')
    c.drawString(main_box_left + 7 * mm, y_card_top - 14 * mm, '印鑑カード番号　＿＿＿＿＿＿＿＿')
    c.drawString(main_box_left + 7 * mm, y_card_top - 19 * mm, '前　任　者')

    c.setFont(fn, 7.5)
    c.drawString(card_div_x + 2 * mm, y_card_top - 5 * mm, '会社法人等番号')

    # ============================================================
    # 届出人行
    # ============================================================
    c.setFont(fn, 7.5)
    c.drawString(main_box_left + 2 * mm, y_deliv_top - 5.5 * mm,
                 '届出人（注３）　□　印鑑提出者本人　　□　代理人')

    # 注3の印の説明テキスト（届出人行の右側）
    c.setFont(fn, 6.5)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(main_box_right - 38 * mm, y_deliv_top - 2.5 * mm, '（注３）の印')
    c.drawString(main_box_right - 38 * mm, y_deliv_top - 5.5 * mm, '（市区町村に登録した印）')
    c.drawString(main_box_right - 38 * mm, y_deliv_top - 8.5 * mm, '※　代理人は押印不要')
    c.setFillColorRGB(0, 0, 0)

    # 注3の印欄（住所・フリガナ・氏名行の右側にまたがる枠）
    seal3_box_w = 22 * mm
    seal3_box_h = row_addr_h + row_furi_h + row_name_h
    seal3_x = main_box_right - seal3_box_w - 1 * mm
    seal3_y = y_name_bot
    c.setLineWidth(0.5)
    c.rect(seal3_x, seal3_y, seal3_box_w, seal3_box_h)

    # ============================================================
    # 住所行
    # ============================================================
    c.setFont(fn, 8)
    c.drawString(main_box_left + 2 * mm, y_addr_top - 5.5 * mm, '住　所')
    c.setFont(fn, 9)
    c.drawString(main_box_left + 18 * mm, y_addr_top - 5.5 * mm, rep.get('address', ''))

    # ============================================================
    # フリガナ行
    # ============================================================
    c.setFont(fn, 7)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(main_box_left + 2 * mm, y_furi_top - 3.5 * mm, 'フリガナ')
    c.setFillColorRGB(0, 0, 0)

    # ============================================================
    # 氏名行
    # ============================================================
    c.setFont(fn, 8)
    c.drawString(main_box_left + 2 * mm, y_name_top - 5.5 * mm, '氏　名')
    c.setFont(fn, 9)
    c.drawString(main_box_left + 18 * mm, y_name_top - 5.5 * mm, rep.get('name', ''))

    # ============================================================
    # 委任状欄
    # ============================================================
    # 委任状はメイン枠の直下（main_box_bottom - 3mmの位置から下方向に33mm）
    inin_top = main_box_bottom - 3 * mm
    inin_bottom = inin_top - 33 * mm
    inin_left = outer_left
    inin_right = width - outer_right

    c.setLineWidth(0.5)
    c.rect(inin_left, inin_bottom, inin_right - inin_left, inin_top - inin_bottom)

    c.setFont(fn, 10)
    inin_title = '委　　任　　状'
    tw = c.stringWidth(inin_title, fn, 10)
    c.drawString((width - tw) / 2, inin_top - 6 * mm, inin_title)

    c.setFont(fn, 8)
    inin_text_y = inin_top - 12 * mm
    c.drawString(inin_left + 10 * mm, inin_text_y, '私は、（住所）')
    c.drawString(inin_left + 20 * mm, inin_text_y - 5 * mm, '（氏名）')
    c.drawString(inin_left + 10 * mm, inin_text_y - 10 * mm,
                 'を代理人と定め、□印鑑（改印）の届出、□添付書面の原本還付請求及び受領')
    c.drawString(inin_left + 10 * mm, inin_text_y - 14 * mm, 'の権限を委任します。')
    c.drawString(inin_left + 50 * mm, inin_text_y - 19 * mm, '年　　　月　　　日')

    c.drawString(inin_left + 10 * mm, inin_text_y - 25 * mm, '住　所')
    c.drawString(inin_left + 10 * mm, inin_text_y - 30 * mm, '氏　名')
    c.drawString(inin_left + 130 * mm, inin_text_y - 30 * mm, '印')

    # 委任状の印欄
    c.setFont(fn, 7)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(inin_right - 32 * mm, inin_top - 14 * mm, '（注３）の印')
    c.drawString(inin_right - 32 * mm, inin_top - 18 * mm, '市区町村に')
    c.drawString(inin_right - 32 * mm, inin_top - 22 * mm, '登録した印')
    c.setFillColorRGB(0, 0, 0)
    c.rect(inin_right - 27 * mm, inin_bottom + 4 * mm, 20 * mm, 20 * mm)

    # ============================================================
    # 注意事項・援用チェック欄
    # ============================================================
    note_y = inin_bottom - 3 * mm
    c.setFont(fn, 7.5)
    c.drawString(outer_left, note_y,
                 '□　市区町村長作成の印鑑証明書は、登記申請書に添付のものを援用する。（注４）')

    c.setFont(fn, 6.5)
    notes = [
        '（注１）　印鑑の大きさは、辺の長さが１㎝を超え、３㎝以内の正方形の中に収まるものでなければなりません。',
        '（注２）　印鑑カードを前任者から引き継ぐことができます。該当する□にレ印をつけ、カードを引き継いだ場合には、その印鑑カードの番号・前任者の氏名を記載してください。',
        '（注３）　本人が届け出るときは、本人の住所・氏名を記載し、市区町村に登録済みの印鑑を押印してください。代理人が届け出るときは、代理人の住所・氏名を記載（押印不要）し、委任状に所要事',
        '　　　　　項を記載し（該当する□にはレ印をつける）、本人が市区町村に登録済みの印鑑を押印してください。なお、本人の住所・氏名が登記簿上の代表者の住所・氏名と一致しない場合には、',
        '　　　　　代表者の住所又は氏名の変更の登記をする必要があります。',
    ]
    for i, note in enumerate(notes):
        c.drawString(outer_left, note_y - 4 * mm - i * 3.5 * mm, note)

    # 注4（右下）
    note4_x = outer_left
    note4_y = note_y - 4 * mm - len(notes) * 3.5 * mm
    c.drawString(note4_x, note4_y,
                 '（注４）　この届書には作成後３か月以内の本人の印鑑証明書を添付してください。登記申請書に添付した印鑑証明書を援用する場合（登記の申請と同時に印鑑を届け出た場合に限る。）は、□にレ印をつけてください。')

    # 処理欄（右下）
    proc_box_x = width - outer_right - 55 * mm
    proc_box_y = outer_bottom
    proc_box_w = 55 * mm
    proc_box_h = 15 * mm
    c.setLineWidth(0.5)
    c.rect(proc_box_x, proc_box_y, proc_box_w, proc_box_h)
    c.setFont(fn, 7)
    c.drawString(proc_box_x + 1 * mm, proc_box_y + proc_box_h - 4 * mm, '印鑑処理年月日')
    c.line(proc_box_x, proc_box_y + proc_box_h / 2, proc_box_x + proc_box_w, proc_box_y + proc_box_h / 2)
    c.drawString(proc_box_x + 1 * mm, proc_box_y + proc_box_h / 2 - 4 * mm, '印鑑処理番号')
    # 処理欄の縦線（受付・調査・入力・校合）
    labels = ['受\n付', '調\n査', '入\n力', '校\n合']
    cell_w = proc_box_w / (len(labels) + 1)
    for i, lbl in enumerate(labels):
        lx = proc_box_x + cell_w * (i + 1)
        c.line(lx, proc_box_y, lx, proc_box_y + proc_box_h)
        c.drawString(lx + 1 * mm, proc_box_y + 2 * mm, lbl.replace('\n', ''))

    # 乙号番号
    c.setFont(fn, 7)
    c.drawString(outer_left, outer_bottom, '（乙号・８）')

    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_inkan_card_pdf(data):  # noqa: C901
    """印鑑カード交付申請書PDFを生成する（法務局公式書式に準拠）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # フォント設定
    font_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'ipag.ttf'),
        '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    ]
    jp_font_path = None
    for candidate in font_candidates:
        if os.path.exists(candidate):
            jp_font_path = candidate
            break
    if jp_font_path:
        try:
            if 'JapaneseGothic' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('JapaneseGothic', jp_font_path))
            fn = 'JapaneseGothic'
        except Exception:
            fn = 'Helvetica'
    else:
        fn = 'Helvetica'

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    company_type = data.get('company_type', '合同会社')
    full_name = _get_full_company_name(data)
    address = data.get('address', '') + ((' ' + data.get('address_detail', '')) if data.get('address_detail') else '')
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    rep = rep_members[0] if rep_members else {}

    if company_type == '合同会社':
        role = '代表社員'
    elif company_type == '株式会社':
        role = '代表取締役'
    else:
        role = '代表理事'

    # ページ余白
    outer_left = 10 * mm
    outer_right = 10 * mm
    outer_top = 8 * mm
    outer_bottom = 8 * mm

    # ============================================================
    # タイトル
    # ============================================================
    title = '印鑑カード交付申請書'
    c.setFont(fn, 16)
    tw = c.stringWidth(title, fn, 16)
    c.drawString((width - tw) / 2, height - outer_top - 10 * mm, title)

    # 注意書き
    c.setFont(fn, 9)
    c.drawString(outer_left + 2 * mm, height - outer_top - 16 * mm, '※　太枠の中に書いてください。')

    # 照合印欄（右上）
    shogouin_x = width - outer_right - 18 * mm
    shogouin_y = height - outer_top - 18 * mm
    shogouin_w = 18 * mm
    shogouin_h = 18 * mm
    c.setLineWidth(0.5)
    c.rect(shogouin_x, shogouin_y, shogouin_w, shogouin_h)
    c.setFont(fn, 7)
    chars_shogouin = ['照', '合', '印']
    for i, ch in enumerate(chars_shogouin):
        c.drawString(shogouin_x + 5 * mm, shogouin_y + shogouin_h - (i + 1) * 5 * mm, ch)

    # ============================================================
    # ヘッダー行（法務局・年月日）
    # ============================================================
    header_y = height - outer_top - 22 * mm
    c.setFont(fn, 8.5)
    c.drawString(outer_left + 2 * mm, header_y, '（地方）法務局')
    c.drawString(outer_left + 38 * mm, header_y, '支局・出張所')
    c.drawString(outer_left + 110 * mm, header_y, '年')
    c.drawString(outer_left + 128 * mm, header_y, '月')
    c.drawString(outer_left + 142 * mm, header_y, '日　申請')

    # ============================================================
    # レイアウト定義
    # ============================================================
    seal_col_w = 38 * mm
    label_col_w = 28 * mm
    right_area_x = outer_left + seal_col_w

    row_company_h = 11 * mm
    row_address_h = 11 * mm
    row_shikaku_h = 35 * mm
    row_houjin_h = 11 * mm
    row_shinsei_h = 9 * mm
    row_addr_h = 10 * mm
    row_furi_h = 5 * mm
    row_name_h = 10 * mm

    total_height = (row_company_h + row_address_h + row_shikaku_h +
                    row_houjin_h + row_shinsei_h + row_addr_h + row_furi_h + row_name_h)

    main_box_top = header_y - 3 * mm
    main_box_bottom = main_box_top - total_height
    main_box_left = outer_left
    main_box_right = width - outer_right
    main_box_width = main_box_right - main_box_left

    y_company_top = main_box_top
    y_company_bot = y_company_top - row_company_h
    y_address_top = y_company_bot
    y_address_bot = y_address_top - row_address_h
    y_shikaku_top = y_address_bot
    y_shikaku_bot = y_shikaku_top - row_shikaku_h
    y_houjin_top = y_shikaku_bot
    y_houjin_bot = y_houjin_top - row_houjin_h
    y_shinsei_top = y_houjin_bot
    y_shinsei_bot = y_shinsei_top - row_shinsei_h
    y_addr_top = y_shinsei_bot
    y_addr_bot = y_addr_top - row_addr_h
    y_furi_top = y_addr_bot
    y_furi_bot = y_furi_top - row_furi_h
    y_name_top = y_furi_bot
    y_name_bot = y_name_top - row_name_h

    # ============================================================
    # メイン枠（太枠）
    # ============================================================
    c.setLineWidth(1.5)
    c.rect(main_box_left, main_box_bottom, main_box_width, total_height)

    c.setLineWidth(0.5)
    for y_line in [y_company_bot, y_address_bot, y_shikaku_bot, y_houjin_bot,
                   y_shinsei_bot, y_addr_bot, y_furi_bot]:
        c.line(main_box_left, y_line, main_box_right, y_line)

    c.line(right_area_x, main_box_bottom, right_area_x, main_box_top)

    # ============================================================
    # 左側：印鑑押印欄
    # ============================================================
    c.setFont(fn, 7)
    c.drawString(main_box_left + 2 * mm, y_company_top - 4 * mm, '（注１）')
    c.drawString(main_box_left + 2 * mm, y_company_top - 8 * mm, '登記所に提出した')
    c.drawString(main_box_left + 2 * mm, y_company_top - 12 * mm, '印鑑の押印欄')

    seal_box_size = 28 * mm
    seal_box_x = main_box_left + (seal_col_w - seal_box_size) / 2
    seal_box_y = y_shikaku_bot - seal_box_size + 3 * mm
    c.setLineWidth(0.8)
    c.rect(seal_box_x, seal_box_y, seal_box_size, seal_box_size)
    c.setLineWidth(0.5)
    c.setFont(fn, 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(seal_box_x + 2 * mm, seal_box_y + seal_box_size / 2 - 2 * mm, '（印鑑は鮮明に押')
    c.drawString(seal_box_x + 2 * mm, seal_box_y + seal_box_size / 2 - 6 * mm, '印してください。）')
    c.setFillColorRGB(0, 0, 0)

    # ============================================================
    # 商号・名称行
    # ============================================================
    c.line(right_area_x + label_col_w, y_company_bot, right_area_x + label_col_w, y_company_top)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + 2 * mm, y_company_bot + row_company_h / 2 - 2 * mm, '商号・名称')
    c.setFont(fn, 9)
    c.drawString(right_area_x + label_col_w + 3 * mm, y_company_bot + row_company_h / 2 - 2 * mm, full_name)

    # ============================================================
    # 本店・主たる事務所行
    # ============================================================
    c.line(right_area_x + label_col_w, y_address_bot, right_area_x + label_col_w, y_address_top)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + 2 * mm, y_address_bot + row_address_h / 2 - 2 * mm, '本店・主たる事務所')
    c.setFont(fn, 9)
    c.drawString(right_area_x + label_col_w + 3 * mm, y_address_bot + row_address_h / 2 - 2 * mm, address)

    # ============================================================
    # 資格/氏名/生年月日複合行（印鑑提出者）
    # ============================================================
    c.line(right_area_x + label_col_w, y_shikaku_bot, right_area_x + label_col_w, y_shikaku_top)

    c.setFont(fn, 8)
    chars = ['印', '鑑', '提', '出', '者']
    char_spacing = row_shikaku_h / (len(chars) + 1)
    for i, ch in enumerate(chars):
        c.drawString(right_area_x + 3 * mm, y_shikaku_top - (i + 1) * char_spacing, ch)

    row1_h = row_shikaku_h / 3
    row1_bot = y_shikaku_top - row1_h
    c.line(right_area_x + label_col_w, row1_bot, main_box_right, row1_bot)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + label_col_w + 2 * mm, y_shikaku_top - 4 * mm, '資　格')
    c.setFont(fn, 7)
    c.drawString(right_area_x + label_col_w + 20 * mm, y_shikaku_top - 3.5 * mm,
                 '代表取締役・取締役・代表社員・代表理事・理事・支配人')
    c.drawString(right_area_x + label_col_w + 20 * mm, y_shikaku_top - 7.5 * mm,
                 f'（　{role}　）')

    row2_bot = y_shikaku_top - row1_h * 2
    c.line(right_area_x + label_col_w, row2_bot, main_box_right, row2_bot)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + label_col_w + 2 * mm, row1_bot - 4 * mm, '氏　名')
    c.setFont(fn, 9)
    c.drawString(right_area_x + label_col_w + 20 * mm, row1_bot - 5 * mm, rep.get('name', ''))

    c.setFont(fn, 7.5)
    c.drawString(right_area_x + label_col_w + 2 * mm, row2_bot - 4 * mm, '生年月日')
    c.drawString(right_area_x + label_col_w + 20 * mm, row2_bot - 4 * mm,
                 '大・昭・平・西暦　　　年　　　月　　　日生')

    # ============================================================
    # 会社法人等番号行
    # ============================================================
    c.line(right_area_x + label_col_w, y_houjin_bot, right_area_x + label_col_w, y_houjin_top)
    c.setFont(fn, 7.5)
    c.drawString(right_area_x + 2 * mm, y_houjin_bot + row_houjin_h / 2 - 2 * mm, '会社法人等番号')

    # ============================================================
    # 申請人行
    # ============================================================
    c.setFont(fn, 7.5)
    c.drawString(main_box_left + 2 * mm, y_shinsei_top - 5.5 * mm,
                 '申　請　人（注２）　□　印鑑提出者本人　　□　代理人')

    # 連絡先欄（右側）
    renraku_x = main_box_right - 45 * mm
    c.line(renraku_x, y_shinsei_bot, renraku_x, y_name_bot)
    c.setFont(fn, 7)
    c.drawString(renraku_x + 1 * mm, y_addr_top - 4 * mm, '連')
    c.drawString(renraku_x + 1 * mm, y_addr_top - 8 * mm, '絡')
    c.drawString(renraku_x + 1 * mm, y_addr_top - 12 * mm, '先')
    c.drawString(renraku_x + 5 * mm, y_addr_top - 3 * mm, '□　勤務先　□　自宅')
    c.drawString(renraku_x + 5 * mm, y_addr_top - 7 * mm, '□　携帯電話')
    c.drawString(renraku_x + 5 * mm, y_addr_top - 11 * mm, '電話番号')

    # ============================================================
    # 住所行
    # ============================================================
    c.setFont(fn, 8)
    c.drawString(main_box_left + 2 * mm, y_addr_top - 5.5 * mm, '住　所')
    c.setFont(fn, 9)
    c.drawString(main_box_left + 18 * mm, y_addr_top - 5.5 * mm, rep.get('address', ''))

    # ============================================================
    # フリガナ行
    # ============================================================
    c.setFont(fn, 7)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(main_box_left + 2 * mm, y_furi_top - 3.5 * mm, 'フリガナ')
    c.setFillColorRGB(0, 0, 0)

    # ============================================================
    # 氏名行
    # ============================================================
    c.setFont(fn, 8)
    c.drawString(main_box_left + 2 * mm, y_name_top - 5.5 * mm, '氏　名')
    c.setFont(fn, 9)
    c.drawString(main_box_left + 18 * mm, y_name_top - 5.5 * mm, rep.get('name', ''))

    # ============================================================
    # 委任状欄
    # ============================================================
    inin_top = main_box_bottom - 3 * mm
    inin_bottom = inin_top - 33 * mm
    inin_left = outer_left
    inin_right = width - outer_right

    c.setLineWidth(0.5)
    c.rect(inin_left, inin_bottom, inin_right - inin_left, inin_top - inin_bottom)

    c.setFont(fn, 10)
    inin_title = '委　　任　　状'
    tw = c.stringWidth(inin_title, fn, 10)
    c.drawString((width - tw) / 2, inin_top - 6 * mm, inin_title)

    c.setFont(fn, 8)
    inin_text_y = inin_top - 12 * mm
    c.drawString(inin_left + 10 * mm, inin_text_y, '私は，（住所）')
    c.drawString(inin_left + 20 * mm, inin_text_y - 5 * mm, '（氏名）')
    c.drawString(inin_left + 10 * mm, inin_text_y - 10 * mm,
                 'を代理人と定め、印鑑カードの交付申請及び受領の権限を委任します。')
    c.drawString(inin_left + 50 * mm, inin_text_y - 16 * mm, '年　　　月　　　日')
    c.drawString(inin_left + 10 * mm, inin_text_y - 22 * mm, '住　所')
    c.drawString(inin_left + 10 * mm, inin_text_y - 27 * mm, '氏　名')
    c.drawString(inin_left + 130 * mm, inin_text_y - 27 * mm, '印')

    c.setFont(fn, 7)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(inin_right - 30 * mm, inin_top - 14 * mm, '登記所に提')
    c.drawString(inin_right - 30 * mm, inin_top - 18 * mm, '出した印鑑')
    c.setFillColorRGB(0, 0, 0)
    c.rect(inin_right - 25 * mm, inin_bottom + 4 * mm, 20 * mm, 20 * mm)

    # ============================================================
    # 注意事項
    # ============================================================
    note_y = inin_bottom - 3 * mm
    c.setFont(fn, 6.5)
    notes = [
        '（注１）　押印欄には、登記所に提出した印鑑を押印してください。',
        '（注２）　該当する□にレ印をつけてください。代理人の場合は、代理人の住所・氏名を記載してください。その場合は、委任状に所要事項を記載し、',
        '　　　　　登記所に提出した印鑑を押印してください。',
    ]
    for i, note in enumerate(notes):
        c.drawString(outer_left, note_y - 4 * mm - i * 3.5 * mm, note)

    # ============================================================
    # 下部処理欄（交付年月日・印鑑カード番号・担当者印・受領印）
    # ============================================================
    proc_y = note_y - 4 * mm - len(notes) * 3.5 * mm - 5 * mm
    proc_left = outer_left
    proc_right = width - outer_right
    proc_h = 12 * mm

    c.setLineWidth(0.5)
    c.rect(proc_left, proc_y - proc_h, proc_right - proc_left, proc_h)

    div1_x = proc_left + 50 * mm
    div2_x = proc_left + 120 * mm
    div3_x = proc_left + 155 * mm
    c.line(div1_x, proc_y - proc_h, div1_x, proc_y)
    c.line(div2_x, proc_y - proc_h, div2_x, proc_y)
    c.line(div3_x, proc_y - proc_h, div3_x, proc_y)

    c.setFont(fn, 7.5)
    c.drawString(proc_left + 5 * mm, proc_y - 7 * mm, '交　付　年　月　日')
    c.drawString(div1_x + 5 * mm, proc_y - 7 * mm, '印鑑カード番号')
    c.drawString(div2_x + 5 * mm, proc_y - 7 * mm, '担当者印')
    c.drawString(div3_x + 5 * mm, proc_y - 7 * mm, '受領印又は署名')

    # 乙号番号
    c.setFont(fn, 7)
    c.drawString(outer_left, outer_bottom, '（乙号・９）')

    c.save()
    buffer.seek(0)
    return buffer.read()

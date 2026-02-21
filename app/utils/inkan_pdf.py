"""
印鑑届出書PDF生成ユーティリティ
LibreOffice UNO経由で公式Excelテンプレートにデータを書き込んでPDF変換する
"""
import os
import sys
import subprocess
import time
import tempfile
import threading
import logging

logger = logging.getLogger(__name__)

# UNOサーバーのポート
UNO_PORT = 2002

# テンプレートファイルのパス
TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates_excel', 'inkan_template.xlsx'
)

_uno_server_process = None
_uno_server_lock = threading.Lock()


def _start_uno_server():
    """UNOサーバーをバックグラウンドで起動する"""
    global _uno_server_process
    with _uno_server_lock:
        if _uno_server_process is not None:
            if _uno_server_process.poll() is None:
                return True  # 既に起動中

        try:
            # sofficeコマンドを探す
            soffice_candidates = ['soffice', 'libreoffice', '/usr/bin/soffice', '/usr/bin/libreoffice']
            soffice_cmd = None
            for candidate in soffice_candidates:
                try:
                    result = subprocess.run(['which', candidate], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        soffice_cmd = candidate
                        break
                except Exception:
                    pass
            
            if soffice_cmd is None:
                logger.error("soffice/libreofficeコマンドが見つかりません")
                return False

            cmd = [
                soffice_cmd, '--headless',
                f'--accept=socket,host=localhost,port={UNO_PORT};urp;StarOffice.ServiceManager',
                '--norestore', '--nofirststartwizard'
            ]
            _uno_server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # 起動を待つ
            time.sleep(8)
            logger.info(f"UNOサーバーを起動しました (PID: {_uno_server_process.pid})")
            return True
        except Exception as e:
            logger.error(f"UNOサーバー起動エラー: {e}")
            return False


def _ensure_uno_server():
    """UNOサーバーが起動していることを確認する"""
    global _uno_server_process
    if _uno_server_process is None or _uno_server_process.poll() is not None:
        return _start_uno_server()
    return True


def generate_inkan_pdf(data):
    """
    UNO経由で印鑑届出書PDFを生成する

    Args:
        data: セッションデータ（company_name, address, members等）

    Returns:
        bytes: PDFデータ
    """
    # UNOサーバーを確認・起動
    if not _ensure_uno_server():
        raise RuntimeError("UNOサーバーの起動に失敗しました")

    # データを準備
    company_type = data.get('company_type', '合同会社')

    # 会社名（フルネーム）
    company_name = data.get('company_name', '')
    company_type_position = data.get('company_type_position', 'prefix')
    if company_type_position == 'prefix':
        full_name = company_type + company_name
    else:
        full_name = company_name + company_type

    # 住所
    address = data.get('address', '')
    if data.get('address_detail'):
        address = address + ' ' + data.get('address_detail', '')

    # 代表者情報
    members = data.get('members', [])
    rep_members = [m for m in members if m.get('is_representative')]
    if not rep_members and members:
        rep_members = [members[0]]
    rep = rep_members[0] if rep_members else {}

    rep_name = rep.get('name', '')
    rep_address = rep.get('address', '')
    if rep.get('address_detail'):
        rep_address = rep_address + ' ' + rep.get('address_detail', '')

    # 役職
    if company_type == '合同会社':
        role = '代表社員'
    elif company_type == '株式会社':
        role = '代表取締役'
    else:
        role = '代表理事'

    # 生年月日
    birthday = ''
    if rep.get('birth_year') and rep.get('birth_month') and rep.get('birth_day'):
        era = rep.get('birth_era', '昭和')
        birthday = f"{era}{rep.get('birth_year')}年{rep.get('birth_month')}月{rep.get('birth_day')}日"

    # フリガナ（代表者）
    rep_kana = rep.get('name_kana', '')

    # 会社法人等番号
    corp_number = data.get('corporate_number', '')

    # 一時出力ファイルパス
    output_path = tempfile.mktemp(suffix='.pdf')

    # UNOスクリプトを生成
    script_content = f'''import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.awt import Size

def connect():
    localContext = uno.getComponentContext()
    resolver = localContext.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", localContext)
    ctx = resolver.resolve(
        "uno:socket,host=localhost,port={UNO_PORT};urp;StarOffice.ComponentContext")
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    return desktop

desktop = connect()
doc = desktop.loadComponentFromURL(
    "file://{TEMPLATE_PATH}", "_blank", 0, ())
sheet = doc.Sheets.getByIndex(0)
draw_page = sheet.DrawPage

full_name = {repr(full_name)}
address = {repr(address)}
role = {repr(role)}
rep_name = {repr(rep_name)}
birthday = {repr(birthday)}
corp_number = {repr(corp_number)}
rep_address = {repr(rep_address)}
rep_kana = {repr(rep_kana)}

def add_data_to_shape(shape, data_text, font_size=10):
    text = shape.getText()
    cursor = text.createTextCursor()
    cursor.gotoEnd(False)
    text.insertControlCharacter(
        cursor,
        uno.getConstantByName("com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK"),
        False
    )
    cursor.gotoEnd(False)
    cursor.setPropertyValue("CharFontName", "IPAGothic")
    cursor.setPropertyValue("CharFontNameAsian", "IPAGothic")
    cursor.setPropertyValue("CharHeight", font_size)
    text.insertString(cursor, data_text, False)

def replace_shape_text(shape, label_text, data_text, font_size=10):
    text = shape.getText()
    cursor = text.createTextCursor()
    cursor.gotoStart(False)
    cursor.gotoEnd(True)
    cursor.setPropertyValue("CharFontName", "IPAGothic")
    cursor.setPropertyValue("CharFontNameAsian", "IPAGothic")
    cursor.setPropertyValue("CharHeight", font_size)
    text.insertString(cursor, label_text + "\\u3000" + data_text, True)

# 全シェイプのフォントをIPAGothicに変更
for i in range(draw_page.Count):
    shape = draw_page.getByIndex(i)
    try:
        text = shape.getText()
        enum = text.createEnumeration()
        while enum.hasMoreElements():
            para = enum.nextElement()
            para_enum = para.createEnumeration()
            while para_enum.hasMoreElements():
                portion = para_enum.nextElement()
                portion.setPropertyValue("CharFontName", "IPAGothic")
                portion.setPropertyValue("CharFontNameAsian", "IPAGothic")
    except Exception:
        pass

# データを書き込む（テキストボックスのインデックスはtest_v13.pyで確認済み）
add_data_to_shape(draw_page.getByIndex(3), full_name)
add_data_to_shape(draw_page.getByIndex(4), address)
add_data_to_shape(draw_page.getByIndex(8), role)
add_data_to_shape(draw_page.getByIndex(9), rep_name)
if birthday:
    add_data_to_shape(draw_page.getByIndex(10), birthday)
if corp_number:
    add_data_to_shape(draw_page.getByIndex(11), corp_number)

# 住所・フリガナ・氏名（届出人）のテキストボックスを変更
for idx, label, val in [
    (15, "住\\u3000所", rep_address),
    (17, "フリガナ", rep_kana),
    (16, "氏\\u3000名", rep_name),
]:
    shape = draw_page.getByIndex(idx)
    pos = shape.Position
    new_size = Size()
    new_size.Width = int((180 - pos.X / 100) * 100)
    new_size.Height = shape.Size.Height
    shape.Size = new_size
    replace_shape_text(shape, label, val)

# PDF出力
pdf_prop = PropertyValue()
pdf_prop.Name = "FilterName"
pdf_prop.Value = "calc_pdf_Export"
doc.storeToURL("file://{output_path}", (pdf_prop,))
doc.close(True)
print("OK")
'''

    # 一時スクリプトファイルを作成
    script_fd, script_path = tempfile.mkstemp(suffix='.py')
    try:
        with os.fdopen(script_fd, 'w', encoding='utf-8') as f:
            f.write(script_content)

        # python3-unoを使ってスクリプトを実行
        python_candidates = ['/usr/bin/python3', 'python3']
        python_cmd = python_candidates[0]

        result = subprocess.run(
            [python_cmd, script_path],
            capture_output=True, text=True, timeout=90
        )

        if result.returncode != 0 or 'OK' not in result.stdout:
            logger.error(f"UNO変換エラー stdout: {result.stdout}")
            logger.error(f"UNO変換エラー stderr: {result.stderr}")
            raise RuntimeError(f"PDF変換に失敗しました: {result.stderr[:300]}")

        if not os.path.exists(output_path):
            raise RuntimeError("PDFファイルが生成されませんでした")

        with open(output_path, 'rb') as f:
            return f.read()

    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)
        if os.path.exists(output_path):
            os.unlink(output_path)

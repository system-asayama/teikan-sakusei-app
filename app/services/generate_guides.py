#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.lib.colors import black, red, gray, HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- Constants ---
WIDTH, HEIGHT = A4
FONT_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
FONT_MINCHO_PATH = os.path.join(FONT_DIR, 'ipam.ttf')
FONT_GOTHIC_PATH = os.path.join(FONT_DIR, 'ipag.ttf')
FONT_NAME_MINCHO = 'ipam'
FONT_NAME_GOTHIC = 'ipag'

# --- Initial Setup ---
def setup_canvas(buffer):
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    pdfmetrics.registerFont(TTFont(FONT_NAME_MINCHO, FONT_MINCHO_PATH))
    pdfmetrics.registerFont(TTFont(FONT_NAME_GOTHIC, FONT_GOTHIC_PATH))
    return c

def draw_header(c, title):
    c.setFont(FONT_NAME_GOTHIC, 16)
    c.drawString(20 * mm, HEIGHT - 20 * mm, title)

def draw_footer(c, page_num, total_pages):
    c.setFont(FONT_NAME_MINCHO, 10)
    c.drawCentredString(WIDTH / 2, 10 * mm, f"- {page_num} / {total_pages} -")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CustomNormal', parent=styles['Normal'], fontName=FONT_NAME_MINCHO, fontSize=9))

def draw_item(c, y_pos, number, title, description, desc_color=black):
    # Background box
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(25 * mm, y_pos - 2 * mm, 165 * mm, 17 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)

    # Number and Title
    c.setFont(FONT_NAME_GOTHIC, 10)
    c.drawString(30 * mm, y_pos + 8 * mm, f"{number} {title}")

    # Description
    p = Paragraph(description, styles['CustomNormal'])
    p.wrapOn(c, 100 * mm, 10 * mm)
    p.drawOn(c, 30 * mm, y_pos)

# --- Guide Generation Functions ---

def generate_kk_guide():
    buffer = io.BytesIO()
    c = setup_canvas(buffer)
    total_pages = 2

    # Page 1
    draw_header(c, "設立登記書類の綴じ方ガイド（株式会社版）")
    c.setFont(FONT_NAME_GOTHIC, 12)
    c.drawString(25 * mm, HEIGHT - 35 * mm, "1. 設立登記書類を印刷して、捺印しましょう")
    draw_item(c, HEIGHT - 55 * mm, "①", "株式会社設立登記申請書", "会社の実印を押します", red)
    draw_item(c, HEIGHT - 75 * mm, "②", "登録免許税納付用台紙", "指定された額の収入印紙を貼ります。消印は不要です。")
    draw_item(c, HEIGHT - 95 * mm, "③", "定款", "電子定款の場合はCD-Rに保存します。紙定款の場合は末尾に発起人全員の実印を押します。", red)
    draw_item(c, HEIGHT - 115 * mm, "④", "発起人の決定書", "発起人全員の個人の実印を押します", red)
    draw_item(c, HEIGHT - 135 * mm, "⑤", "就任承諾書", "取締役全員の個人の実印を押します", red)
    draw_item(c, HEIGHT - 155 * mm, "⑥", "印鑑証明書", "取締役全員のものを添付します。")
    draw_item(c, HEIGHT - 175 * mm, "⑦", "払込みを証する書面", "通帳コピーの各ページに会社の実印で契印します", red)
    draw_item(c, HEIGHT - 195 * mm, "⑧", "印鑑届出書", "会社の実印と代表取締役の個人の実印を押します", red)
    draw_footer(c, 1, total_pages)
    c.showPage()

    # Page 2
    draw_header(c, "設立登記書類の綴じ方ガイド（株式会社版）")
    c.setFont(FONT_NAME_GOTHIC, 12)
    c.drawString(25 * mm, HEIGHT - 35 * mm, "2. 書類をまとめて法務局へ提出しましょう")
    draw_item(c, HEIGHT - 55 * mm, "①", "書類の順番", "申請書→台紙→定款→決定書→承諾書→印鑑証明書→払込証明書の順に重ねます。")
    draw_item(c, HEIGHT - 75 * mm, "②", "ホチキス留めと契印", "①の束をホチキスで留め、全ページの継ぎ目に会社の実印で契印します。", red)
    draw_item(c, HEIGHT - 95 * mm, "③", "クリップでまとめる", "②の束、OCR用紙、印鑑届出書をクリップでまとめます。")
    draw_item(c, HEIGHT - 115 * mm, "④", "提出", "管轄の法務局に提出します。郵送も可能です。")
    draw_footer(c, 2, total_pages)
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

def generate_gk_guide():
    buffer = io.BytesIO()
    c = setup_canvas(buffer)
    total_pages = 2

    # Page 1
    draw_header(c, "設立登記書類の綴じ方ガイド（合同会社版）")
    c.setFont(FONT_NAME_GOTHIC, 12)
    c.drawString(25 * mm, HEIGHT - 35 * mm, "1. 設立登記書類を印刷して、捺印しましょう")
    draw_item(c, HEIGHT - 55 * mm, "①", "合同会社設立登記申請書", "会社の実印を押します", red)
    draw_item(c, HEIGHT - 75 * mm, "②", "登録免許税納付用台紙", "指定された額の収入印紙を貼ります。消印は不要です。")
    draw_item(c, HEIGHT - 95 * mm, "③", "定款", "電子定款の場合はCD-Rに保存します。紙定款の場合は末尾に社員全員の実印を押します。", red)
    draw_item(c, HEIGHT - 115 * mm, "④", "本店所在地及び資本金決定書", "社員全員の個人の実印を押します", red)
    draw_item(c, HEIGHT - 135 * mm, "⑤", "就任承諾書", "代表社員の個人の実印を押します", red)
    draw_item(c, HEIGHT - 155 * mm, "⑥", "印鑑証明書", "社員全員のものを添付します。")
    draw_item(c, HEIGHT - 175 * mm, "⑦", "払込みを証する書面", "通帳コピーの各ページに会社の実印で契印します", red)
    draw_item(c, HEIGHT - 195 * mm, "⑧", "印鑑届出書", "会社の実印と代表社員の個人の実印を押します", red)
    draw_footer(c, 1, total_pages)
    c.showPage()

    # Page 2
    draw_header(c, "設立登記書類の綴じ方ガイド（合同会社版）")
    c.setFont(FONT_NAME_GOTHIC, 12)
    c.drawString(25 * mm, HEIGHT - 35 * mm, "2. 書類をまとめて法務局へ提出しましょう")
    draw_item(c, HEIGHT - 55 * mm, "①", "書類の順番", "申請書→台紙→定款→決定書→承諾書→印鑑証明書→払込証明書の順に重ねます。")
    draw_item(c, HEIGHT - 75 * mm, "②", "ホチキス留めと契印", "①の束をホチキスで留め、全ページの継ぎ目に会社の実印で契印します。", red)
    draw_item(c, HEIGHT - 95 * mm, "③", "クリップでまとめる", "②の束、OCR用紙、印鑑届出書をクリップでまとめます。")
    draw_item(c, HEIGHT - 115 * mm, "④", "提出", "管轄の法務局に提出します。郵送も可能です。")
    draw_footer(c, 2, total_pages)
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

def generate_ippan_guide():
    buffer = io.BytesIO()
    c = setup_canvas(buffer)
    total_pages = 2

    # Page 1
    draw_header(c, "設立登記書類の綴じ方ガイド（一般社団法人版）")
    c.setFont(FONT_NAME_GOTHIC, 12)
    c.drawString(25 * mm, HEIGHT - 35 * mm, "1. 設立登記書類を印刷して、捺印しましょう")
    draw_item(c, HEIGHT - 55 * mm, "①", "一般社団法人設立登記申請書", "法人の実印を押します", red)
    draw_item(c, HEIGHT - 75 * mm, "②", "登録免許税納付用台紙", "6万円の収入印紙を貼ります。消印は不要です。")
    draw_item(c, HEIGHT - 95 * mm, "③", "定款", "公証役場で認証を受けたものを提出します。")
    draw_item(c, HEIGHT - 115 * mm, "④", "設立時社員の決議書", "設立時社員全員が記名押印します。実印である必要はありません。")
    draw_item(c, HEIGHT - 135 * mm, "⑤", "就任承諾書", "設立時理事全員が記名押印します。実印である必要はありません。")
    draw_item(c, HEIGHT - 155 * mm, "⑥", "印鑑証明書", "代表理事のものを添付します。")
    draw_item(c, HEIGHT - 175 * mm, "⑦", "印鑑届出書", "法人の実印と代表理事の個人の実印を押します", red)
    draw_footer(c, 1, total_pages)
    c.showPage()

    # Page 2
    draw_header(c, "設立登記書類の綴じ方ガイド（一般社団法人版）")
    c.setFont(FONT_NAME_GOTHIC, 12)
    c.drawString(25 * mm, HEIGHT - 35 * mm, "2. 書類をまとめて法務局へ提出しましょう")
    draw_item(c, HEIGHT - 55 * mm, "①", "書類の順番", "申請書→台紙→定款→決議書→承諾書→印鑑証明書の順に重ねます。")
    draw_item(c, HEIGHT - 75 * mm, "②", "ホチキス留めと契印", "①の束をホチキスで留め、全ページの継ぎ目に法人の実印で契印します。", red)
    draw_item(c, HEIGHT - 95 * mm, "③", "クリップでまとめる", "②の束、OCR用紙、印鑑届出書をクリップでまとめます。")
    draw_item(c, HEIGHT - 115 * mm, "④", "提出", "管轄の法務局に提出します。郵送も可能です。")
    draw_footer(c, 2, total_pages)
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

if __name__ == '__main__':
    with open("guide_kk.pdf", "wb") as f:
        f.write(generate_kk_guide().read())
    with open("guide_gk.pdf", "wb") as f:
        f.write(generate_gk_guide().read())
    with open("guide_ippan.pdf", "wb") as f:
        f.write(generate_ippan_guide().read())
    print("Generated all guides.")

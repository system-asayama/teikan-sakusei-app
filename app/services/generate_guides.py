#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.lib.colors import black, red, gray
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.colors import HexColor

# --- 定数 ---
WIDTH, HEIGHT = A4
FONT_NAME = "HeiseiMin-W3"
FONT_NAME_B = "HeiseiKakuGo-W5"

# フォントパス（アプリ同梱フォントを使用）
import os as _os
_FONT_DIR = _os.path.join(_os.path.dirname(__file__), 'fonts')
_FONT_MINCHO = _os.path.join(_FONT_DIR, 'ipam.ttf')
_FONT_GOTHIC = _os.path.join(_FONT_DIR, 'ipag.ttf')

# --- 初期設定 ---
def setup_canvas(buffer):
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    pdfmetrics.registerFont(TTFont(FONT_NAME, _FONT_MINCHO))
    pdfmetrics.registerFont(TTFont(FONT_NAME_B, _FONT_GOTHIC))
    return c

def draw_header(c, title):
    c.setFont(FONT_NAME_B, 16)
    c.drawString(20 * mm, HEIGHT - 20 * mm, title)

def draw_footer(c, page_num, total_pages):
    c.setFont(FONT_NAME, 10)
    c.drawCentredString(WIDTH / 2, 10 * mm, f"- {page_num} / {total_pages} -")

# --- 各会社形態のガイド生成関数 ---
def generate_kk_guide():
    buffer = io.BytesIO()
    c = setup_canvas(buffer)
    
    # 1ページ目
    draw_header(c, "設立登記書類の綴じ方ガイド（株式会社版）")
    # --- 1. 書類と捺印 ---
    c.setFont(FONT_NAME_B, 12)
    c.drawString(25 * mm, HEIGHT - 30 * mm, "１ 設立登記書類を印刷して、捺印しましょう")

    # ① 設立登記申請書
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 50 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 50 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 47 * mm, "① 株式会社設立登記申請書")
    c.setFont(FONT_NAME, 9)
    c.setFillColor(red)
    c.drawString(100 * mm, HEIGHT - 47 * mm, "会社の実印 を押します")
    c.setFillColor(black)

    # ② 登録免許税納付用台紙
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 70 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 70 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 67 * mm, "② 登録免許税納付用台紙")
    c.setFont(FONT_NAME, 9)
    c.drawString(100 * mm, HEIGHT - 67 * mm, "指定された額の収入印紙を貼ります。")

    # ③ 発起人の決定書
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 90 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 90 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 87 * mm, "③ 発起人の決定書")
    c.setFont(FONT_NAME, 9)
    c.setFillColor(red)
    c.drawString(100 * mm, HEIGHT - 87 * mm, "発起人それぞれの 個人の実印 を押します")
    c.setFillColor(black)

    draw_footer(c, 1, 5)
    c.showPage()
    
    # ... 2ページ目以降 ...

    c.save()
    buffer.seek(0)
    return buffer

def generate_gk_guide():
    buffer = io.BytesIO()
    c = setup_canvas(buffer)

    # 1ページ目
    draw_header(c, "設立登記書類の綴じ方ガイド（合同会社版）")
        # --- 1. 書類と捺印 ---
    c.setFont(FONT_NAME_B, 12)
    c.drawString(25 * mm, HEIGHT - 30 * mm, "１ 設立登記書類を印刷して、捺印しましょう")

    # ① 設立登記申請書
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 50 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 50 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 47 * mm, "① 合同会社設立登記申請書")
    c.setFont(FONT_NAME, 9)
    c.setFillColor(red)
    c.drawString(100 * mm, HEIGHT - 47 * mm, "会社の実印 を押します")
    c.setFillColor(black)

    # ② 登録免許税納付用台紙
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 70 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 70 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 67 * mm, "② 登録免許税納付用台紙")
    c.setFont(FONT_NAME, 9)
    c.drawString(100 * mm, HEIGHT - 67 * mm, "指定された額の収入印紙を貼ります。")

    # ③ 本店所在地及び資本金決定書
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 90 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 90 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 87 * mm, "③ 本店所在地及び資本金決定書")
    c.setFont(FONT_NAME, 9)
    c.setFillColor(red)
    c.drawString(100 * mm, HEIGHT - 87 * mm, "社員それぞれの 個人の実印 を押します")
    c.setFillColor(black)

    draw_footer(c, 1, 5)
    c.showPage()

    # ... 2ページ目以降 ...

    c.save()
    buffer.seek(0)
    return buffer

def generate_ippan_guide():
    buffer = io.BytesIO()
    c = setup_canvas(buffer)

    # 1ページ目
    draw_header(c, "設立登記書類の綴じ方ガイド（一般社団法人版）")
        # --- 1. 書類と捺印 ---
    c.setFont(FONT_NAME_B, 12)
    c.drawString(25 * mm, HEIGHT - 30 * mm, "１ 設立登記書類を印刷して、捺印しましょう")

    # ① 設立登記申請書
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 50 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 50 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 47 * mm, "① 一般社団法人設立登記申請書")
    c.setFont(FONT_NAME, 9)
    c.setFillColor(red)
    c.drawString(100 * mm, HEIGHT - 47 * mm, "法人の実印 を押します")
    c.setFillColor(black)

    # ② 登録免許税納付用台紙 (非課税)
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 70 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 70 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 67 * mm, "② 登録免許税納付用台紙")
    c.setFont(FONT_NAME, 9)
    c.drawString(100 * mm, HEIGHT - 67 * mm, "登録免許税は非課税です。収入印紙は不要です。")

    # ③ 設立時社員の決定書
    c.setFont(FONT_NAME_B, 10)
    c.roundRect(28 * mm, HEIGHT - 90 * mm, 160 * mm, 15 * mm, 5, stroke=1, fill=0)
    c.setFillColor(HexColor('#f0f0f0'))
    c.roundRect(28 * mm, HEIGHT - 90 * mm, 160 * mm, 15 * mm, 5, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_NAME_B, 10)
    c.drawString(30 * mm, HEIGHT - 87 * mm, "③ 設立時社員の決定書")
    c.setFont(FONT_NAME, 9)
    c.setFillColor(red)
    c.drawString(100 * mm, HEIGHT - 87 * mm, "設立時社員それぞれの 個人の実印 を押します")
    c.setFillColor(black)

    draw_footer(c, 1, 5)
    c.showPage()

    # ... 2ページ目以降 ...

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

"""Dagli Leather Studio ev stili: başlık + logo, filigran, alt bilgi, rozet, kart, kontrol karesi, zengin metin."""
from __future__ import annotations

import os

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
BRAND = "DAGLI LEATHER STUDIO"
INK = HexColor("#1d1d1b")
GREY = HexColor("#6b6b6b")
LIGHT = HexColor("#f4efe8")  # yardım kutuları
CARD_LINE = HexColor("#3a3a3a")
RED = HexColor("#d8262c")
BLUE = HexColor("#1f63c6")
ACCENT = HexColor("#8a4b22")

_fonts_done = False


def fonts():
    global _fonts_done
    if not _fonts_done:
        pdfmetrics.registerFont(TTFont("Dagli", os.path.join(ASSETS, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("Dagli-Bold", os.path.join(ASSETS, "DejaVuSans-Bold.ttf")))
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily("Dagli", normal="Dagli", bold="Dagli-Bold", italic="Dagli", boldItalic="Dagli-Bold")
        _fonts_done = True
    return "Dagli", "Dagli-Bold"


_img_cache: dict[str, ImageReader] = {}


def asset_img(name: str) -> ImageReader:
    if name not in _img_cache:
        _img_cache[name] = ImageReader(os.path.join(ASSETS, name))
    return _img_cache[name]


def style(size=8.0, bold=False, color=INK, leading=None, align=TA_LEFT) -> ParagraphStyle:
    f, fb = fonts()
    return ParagraphStyle("s", fontName=fb if bold else f, fontSize=size, leading=leading or size * 1.28,
                          textColor=color, alignment=align)


def esc(s: str) -> str:
    """'**kalın**' biçimini Paragraph XML'ine çevirir."""
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    parts = s.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))


def para(c, text, x, y_top, w, size=8.0, bold=False, color=INK, min_size=5.5, max_h=None) -> float:
    """Metni (x, y_top)'tan aşağı yazar; sığmazsa küçültür. Kullanılan yüksekliği döndürür."""
    while True:
        p = Paragraph(esc(text), style(size, bold, color))
        _, h = p.wrap(w, 10_000)
        if max_h is None or h <= max_h or size <= min_size:
            p.drawOn(c, x, y_top - h)
            return h
        size -= 0.3


def para_h(text, w, size=8.0, bold=False) -> float:
    p = Paragraph(esc(text), style(size, bold))
    return p.wrap(w, 10_000)[1]


class Doc:
    """Sayfa iskeleti. Sayfa sayısı önceden bilinmeli (iki geçişli üretim, bkz. booklet.py)."""

    def __init__(self, c, title: str, version: str, total_pages: int):
        self.c = c
        self.title = title.upper()
        self.version = version
        self.total = total_pages
        self.page = 0
        fonts()

    @property
    def size(self):
        return self.c._pagesize

    def new_page(self, size, watermark=True):
        if self.page:
            self.c.showPage()
        self.page += 1
        self.c.setPageSize(size)
        if watermark:
            self.watermark()

    def watermark(self):
        w, h = self.size
        ww = min(w, h) * 0.62
        hh = ww * 1725 / 1308
        self.c.drawImage(asset_img("watermark.png"), (w - ww) / 2, (h - hh) / 2, ww, hh, mask="auto")

    def header(self, line2: str, line3: str = "", small=False):
        c = self.c
        f, fb = fonts()
        w, h = self.size
        lh = (11 if small else 15) * mm
        lw = lh * 1308 / 1725
        x0, top = 10 * mm, h - 8 * mm
        c.drawImage(asset_img("logo.png"), x0, top - lh, lw, lh, mask="auto")
        tx = x0 + lw + 4 * mm
        c.setFillColor(INK)
        c.setFont(fb, 9 if small else 13)
        c.drawString(tx, top - (4 if small else 5.5) * mm, self.title)
        c.setFont(fb, 6.5 if small else 8.5)
        c.drawString(tx, top - (7.5 if small else 10.5) * mm, line2.upper())
        if line3:
            c.setFont(f, 5.5 if small else 7)
            c.setFillColor(GREY)
            c.drawString(tx, top - (10.5 if small else 14.5) * mm, line3)
        return top - lh - 3 * mm  # içerik buradan başlar

    def footer(self):
        c = self.c
        f, fb = fonts()
        w, _ = self.size
        c.setFillColor(GREY)
        c.setFont(f, 5.5)
        c.drawString(10 * mm, 6 * mm, f"© {BRAND} · All rights reserved · For personal and small-scale crafting use · "
                                      f"Pattern v{self.version}")
        c.setFillColor(INK)
        c.setFont(fb, 6.5)
        c.drawRightString(w - 10 * mm, 6 * mm, f"Page {self.page} of {self.total}")


def badge(c, x, y, n, s=4.6 * mm):
    """Siyah kare içinde beyaz adım numarası (sol-alt köşe x,y)."""
    _, fb = fonts()
    c.setFillColor(INK)
    c.rect(x, y, s, s, stroke=0, fill=1)
    c.setFillColor(Color(1, 1, 1))
    c.setFont(fb, s * 0.62)
    c.drawCentredString(x + s / 2, y + s * 0.27, str(n))


def card(c, x, y, w, h, fill=None, r=2.2 * mm, line=CARD_LINE, lw=0.6):
    c.setStrokeColor(line)
    c.setLineWidth(lw)
    if fill is not None:
        c.setFillColor(fill)
    c.roundRect(x, y, w, h, r, stroke=1, fill=1 if fill is not None else 0)


def box_title(c, x, y, text, size=7.5):
    _, fb = fonts()
    c.setFillColor(INK)
    c.setFont(fb, size)
    c.drawString(x, y, text.upper())


def check_square(c, x, y, size=50.0, label=True):
    """50 mm kontrol karesi (sol-alt köşe, pt)."""
    f, _ = fonts()
    s = size * mm
    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.rect(x, y, s, s, stroke=1, fill=0)
    if label:
        c.setFillColor(INK)
        c.setFont(f, 6)
        inch = size / 25.4
        c.drawCentredString(x + s / 2, y - 3.2 * mm, f"{size:g} mm ({inch:.2g} in)")
        c.saveState()
        c.translate(x - 2 * mm, y + s / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, f"{size:g} mm ({inch:.2g} in)")
        c.restoreState()


def ref_frame(c, x, y, w, h, text="REFERENCE ONLY · SHOWN SMALLER THAN REAL SIZE · DO NOT CUT"):
    _, fb = fonts()
    c.setStrokeColor(RED)
    c.setLineWidth(1.0)
    c.setDash(4, 2)
    c.roundRect(x, y, w, h, 2 * mm, stroke=1, fill=0)
    c.setDash()
    c.setFillColor(RED)
    c.setFont(fb, 7.5)
    c.drawCentredString(x + w / 2, y - 4 * mm, text)


def arrow(c, x0, y0, x1, y1, color=RED, lw=1.1, head=2.4 * mm):
    import math
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(lw)
    c.line(x0, y0, x1, y1)
    a = math.atan2(y1 - y0, x1 - x0)
    p = c.beginPath()
    p.moveTo(x1, y1)
    p.lineTo(x1 - head * math.cos(a - 0.4), y1 - head * math.sin(a - 0.4))
    p.lineTo(x1 - head * math.cos(a + 0.4), y1 - head * math.sin(a + 0.4))
    p.close()
    c.drawPath(p, stroke=0, fill=1)

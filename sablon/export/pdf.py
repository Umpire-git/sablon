"""Gerçek ölçekli (1:1) PDF çıktısı.

Üç biçim:
  * "A4" / "Letter": kapak + uyarılar + parçalı (döşemeli) kalıp sayfaları.
    Ev yazıcısında %100 ölçekle basılır, sayfalar hizalama işaretleriyle birleştirilir.
  * "full": tek sayfa, kalıbın tamamı (A0 plotter / matbaa / lazer kesim için).

Koordinatlar mm'den pt'ye 72/25.4 katsayısıyla birebir dönüştürülür.
"""
from __future__ import annotations

import math
import string

from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen.canvas import Canvas

from ..geometry import Arc, Circle, Line
from ..pattern import KIND_LABEL_TR, Kind, Pattern, Piece
from .fonts import pdf_fonts

MM = 72.0 / 25.4
PAPERS = {"A4": (210.0, 297.0), "Letter": (215.9, 279.4)}
MARGIN = 10.0  # yazıcıların basamadığı kenar (mm)

STYLE = {
    Kind.CUT: dict(color=HexColor("#000000"), width=0.35, dash=None),
    Kind.SLIT: dict(color=HexColor("#000000"), width=0.35, dash=None),
    Kind.HOLE: dict(color=HexColor("#000000"), width=0.25, dash=None),
    Kind.FOLD: dict(color=HexColor("#1f5fbf"), width=0.3, dash=(3.0, 1.5)),
    Kind.STITCH: dict(color=HexColor("#c0392b"), width=0.2, dash=None),
    Kind.GUIDE: dict(color=HexColor("#c0392b"), width=0.15, dash=(1.0, 1.0)),
    Kind.GRAIN: dict(color=HexColor("#555555"), width=0.25, dash=None),
}


def _draw_prim(c: Canvas, prim, kind: Kind):
    st = STYLE[kind]
    c.setStrokeColor(st["color"])
    c.setLineWidth(st["width"] * MM)
    c.setDash([d * MM for d in st["dash"]] if st["dash"] else [])
    if isinstance(prim, Line):
        c.line(prim.x0 * MM, prim.y0 * MM, prim.x1 * MM, prim.y1 * MM)
        if kind == Kind.GRAIN:
            _arrow_heads(c, prim)
    elif isinstance(prim, Arc):
        r = prim.r
        c.arc((prim.cx - r) * MM, (prim.cy - r) * MM, (prim.cx + r) * MM, (prim.cy + r) * MM,
              prim.a0, prim.a1 - prim.a0)
    elif isinstance(prim, Circle):
        fill = 1 if kind == Kind.STITCH else 0
        if fill:
            c.setFillColor(st["color"])
        c.circle(prim.cx * MM, prim.cy * MM, prim.r * MM, stroke=1, fill=fill)
        if kind == Kind.HOLE:  # artı işareti: zımba merkezi
            k = prim.r * 0.7
            c.line((prim.cx - k) * MM, prim.cy * MM, (prim.cx + k) * MM, prim.cy * MM)
            c.line(prim.cx * MM, (prim.cy - k) * MM, prim.cx * MM, (prim.cy + k) * MM)


def _arrow_heads(c: Canvas, ln: Line):
    ang = math.atan2(ln.y1 - ln.y0, ln.x1 - ln.x0)
    for (x, y, a) in ((ln.x1, ln.y1, ang), (ln.x0, ln.y0, ang + math.pi)):
        for s in (+1, -1):
            b = a + math.pi - s * math.radians(25)
            c.line(x * MM, y * MM, (x + 3 * math.cos(b)) * MM, (y + 3 * math.sin(b)) * MM)


def draw_pieces(c: Canvas, pieces: list[Piece]):
    font, bold = pdf_fonts()
    for p in pieces:
        for kind, prim in p.items:
            _draw_prim(c, prim, kind)
        c.setFillColor(HexColor("#444444"))
        for t in p.texts:
            c.saveState()
            c.translate(t.x * MM, t.y * MM)
            c.rotate(t.angle)
            c.setFont(font, t.size * MM)
            {"start": c.drawString, "end": c.drawRightString}.get(t.anchor, c.drawCentredString)(0, 0, t.text)
            c.restoreState()
        # parça adı + adet (kesim sınırının altına)
        x0, y0, x1, y1 = p.cut_bounds()
        c.setFont(bold, 3.0 * MM)
        c.setFillColor(HexColor("#000000"))
        c.drawString(x0 * MM, (y0 - 5) * MM, f"{p.name}  ×{p.quantity}  ({x1 - x0:.1f} × {y1 - y0:.1f} mm)")


def _test_square(c: Canvas, x: float, y: float, size: float = 50.0, inch: bool = True):
    font, bold = pdf_fonts()
    c.setDash([])
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(0.3 * MM)
    c.rect(x * MM, y * MM, size * MM, size * MM)
    c.setFont(bold, 3.2 * MM)
    c.drawCentredString((x + size / 2) * MM, (y + size / 2 + 1) * MM, f"{size:.0f} mm")
    c.setFont(font, 2.4 * MM)
    c.drawCentredString((x + size / 2) * MM, (y + size / 2 - 4) * MM, "ölçek testi")
    if inch:
        s = 50.8
        xx = x + size + 8
        c.rect(xx * MM, y * MM, s * MM, s * MM)
        c.setFont(bold, 3.2 * MM)
        c.drawCentredString((xx + s / 2) * MM, (y + s / 2 + 1) * MM, '2 inch')
        c.setFont(font, 2.4 * MM)
        c.drawCentredString((xx + s / 2) * MM, (y + s / 2 - 4) * MM, "scale check")


def _wrap(text: str, font: str, size: float, width_mm: float, c: Canvas) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if c.stringWidth(trial, font, size * MM) / MM > width_mm and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class _Writer:
    """Sayfa taşmasını yöneten basit metin yazıcı."""

    def __init__(self, c: Canvas, pw: float, ph: float):
        self.c, self.pw, self.ph = c, pw, ph
        self.font, self.bold = pdf_fonts()
        self.y = ph - 18

    def need(self, h: float):
        if self.y - h < 15:
            self.c.showPage()
            self.y = self.ph - 18

    def heading(self, s: str, size: float = 5.0):
        self.need(size + 6)
        self.c.setFillColor(HexColor("#000000"))
        self.c.setFont(self.bold, size * MM)
        self.c.drawString(15 * MM, self.y * MM, s)
        self.y -= size + 3

    def para(self, s: str, size: float = 3.4, indent: float = 0.0, color: str = "#222222"):
        for ln in _wrap(s, self.font, size, self.pw - 30 - indent, self.c):
            self.need(size + 1.6)
            self.c.setFillColor(HexColor(color))
            self.c.setFont(self.font, size * MM)
            self.c.drawString((15 + indent) * MM, self.y * MM, ln)
            self.y -= size + 1.6
        self.y -= 1


def _info_pages(c: Canvas, tpl, pw: float, ph: float, tiles: list[list[str]] | None, edition: str):
    w = _Writer(c, pw, ph)
    w.heading(tpl.title, 7.0)
    w.para(tpl.description, 3.6)
    w.para(f"Malzeme: {tpl.material}", 3.6)
    w.para(f"Baskı: {edition}. Yazıcıda 'Gerçek boyut / %100 / Actual size' seçin, 'Sayfaya sığdır' KAPALI olsun. "
           "Basınca aşağıdaki kareleri cetvelle ölçün; 50 mm değilse kalıbı kullanmayın.", 3.4)
    w.y -= 2
    w.need(60)
    _test_square(c, 15, w.y - 52)
    w.y -= 60

    w.heading("Ana ölçüler", 4.6)
    for m in tpl.measures().values():
        w.para(f"• {m.label}: {m.value:.1f} {m.unit}" if m.unit != "adet" else f"• {m.label}: {m.value:.0f}", 3.3, 2)

    w.heading("Çizgi türleri", 4.6)
    for kind in (Kind.CUT, Kind.SLIT, Kind.FOLD, Kind.STITCH, Kind.HOLE, Kind.GUIDE):
        w.need(6)
        st = STYLE[kind]
        c.setStrokeColor(st["color"])
        c.setLineWidth(st["width"] * MM * 1.5)
        c.setDash([d * MM for d in st["dash"]] if st["dash"] else [])
        c.line(17 * MM, (w.y + 1) * MM, 32 * MM, (w.y + 1) * MM)
        c.setDash([])
        c.setFillColor(HexColor("#222222"))
        c.setFont(w.font, 3.3 * MM)
        c.drawString(36 * MM, w.y * MM, KIND_LABEL_TR[kind])
        w.y -= 5.5

    if tiles:
        w.heading("Sayfa birleştirme haritası", 4.6)
        w.para("Her sayfayı çerçeve çizgisinden kesin (veya kenarı katlayın), ◆ işaretlerini üst üste getirip bantlayın. "
               "Sayfa kodları sütun harfi + satır numarasıdır.", 3.3)
        rows, cols = len(tiles), len(tiles[0])
        cell = min(14.0, (pw - 40) / cols)
        w.need(rows * cell * 0.8 + 6)
        for r in range(rows):
            for col in range(cols):
                x = 15 + col * cell
                y = w.y - (r + 1) * cell * 0.8
                c.setStrokeColor(HexColor("#888888"))
                c.setLineWidth(0.2 * MM)
                c.rect(x * MM, y * MM, cell * MM, cell * 0.8 * MM)
                c.setFont(w.bold, 3 * MM)
                c.drawCentredString((x + cell / 2) * MM, (y + cell * 0.3) * MM, tiles[r][col])
        w.y -= rows * cell * 0.8 + 6

    c.showPage()
    w = _Writer(c, pw, ph)
    w.heading("Tasarım kontrolleri", 5.0)
    colors = {"hata": "#c0392b", "uyari": "#b9770e", "bilgi": "#1e6b3a"}
    tags = {"hata": "HATA", "uyari": "UYARI", "bilgi": "BİLGİ"}
    for f in tpl.checks():
        w.para(f"[{tags[f.level]}] {f.message}", 3.4, 0, colors[f.level])
    w.heading("Montaj adımları", 5.0)
    for i, s in enumerate(tpl.assembly(), 1):
        w.para(f"{i}. {s}", 3.4)
    c.showPage()


def _tile_labels(rows: int, cols: int) -> list[list[str]]:
    letters = string.ascii_uppercase
    # satır 1 en üstte olsun
    return [[f"{letters[col % 26]}{r + 1}" for col in range(cols)] for r in range(rows)]


def write_pdf(tpl, path: str, paper: str = "A4", include_info: bool = True) -> dict:
    pattern: Pattern = tpl.build()
    font, bold = pdf_fonts()
    placed = pattern.layout(max_width=600.0 if paper == "full" else 380.0)
    ex0, ey0, ex1, ey1 = Pattern.extent(placed)
    ey0 -= 8  # parça adı yazısı için
    W, H = ex1 - ex0, ey1 - ey0

    if paper == "full":
        m = 15.0
        pw, ph = W + 2 * m, H + 2 * m + 12
        c = Canvas(path, pagesize=(210 * MM, 297 * MM))
        c.setTitle(tpl.title)
        if include_info:
            _info_pages(c, tpl, 210, 297, None, "Tek sayfa tam boy (plotter / matbaa / lazer)")
        c.setPageSize((pw * MM, ph * MM))
        c.saveState()
        c.translate((m - ex0) * MM, (m - ey0) * MM)
        draw_pieces(c, placed)
        c.restoreState()
        c.setFont(font, 3 * MM)
        c.setFillColor(HexColor("#000000"))
        c.drawString(m * MM, (ph - 9) * MM, f"{tpl.title} — 1:1 ölçek — 10 mm:")
        sx = m + c.stringWidth(f"{tpl.title} — 1:1 ölçek — 10 mm:", font, 3 * MM) / MM + 3
        c.setLineWidth(0.4 * MM)
        c.line(sx * MM, (ph - 8.5) * MM, (sx + 10) * MM, (ph - 8.5) * MM)
        c.showPage()
        c.save()
        return {"pages": "1 (+bilgi)" if include_info else 1, "size_mm": (round(pw, 1), round(ph, 1))}

    pw, ph = PAPERS[paper]
    tw, th = pw - 2 * MARGIN, ph - 2 * MARGIN - 8  # üstte başlık şeridi
    cols, rows = max(1, math.ceil(W / tw)), max(1, math.ceil(H / th))
    # kalıbı döşeme ızgarasında ortala
    ox = ex0 - (cols * tw - W) / 2
    oy = ey0 - (rows * th - H) / 2
    labels = _tile_labels(rows, cols)
    c = Canvas(path, pagesize=(pw * MM, ph * MM))
    c.setTitle(tpl.title)
    if include_info:
        _info_pages(c, tpl, pw, ph, labels, f"{paper}, {rows * cols} kalıp sayfası")

    for r in range(rows):
        for col in range(cols):
            # r=0 üst satır
            tx0 = ox + col * tw
            ty0 = oy + (rows - 1 - r) * th
            c.saveState()
            p = c.beginPath()
            p.rect(MARGIN * MM, MARGIN * MM, tw * MM, th * MM)
            c.clipPath(p, stroke=0, fill=0)
            c.translate((MARGIN - tx0) * MM, (MARGIN - ty0) * MM)
            draw_pieces(c, placed)
            c.restoreState()
            # çerçeve + hizalama elmasları
            c.setDash([])
            c.setStrokeColor(Color(0.6, 0.6, 0.6))
            c.setLineWidth(0.15 * MM)
            c.rect(MARGIN * MM, MARGIN * MM, tw * MM, th * MM)
            c.setFillColor(Color(0.55, 0.55, 0.55))
            for (x, y) in _diamond_points(tw, th):
                _diamond(c, MARGIN + x, MARGIN + y)
            # başlık şeridi
            c.setFillColor(HexColor("#000000"))
            c.setFont(bold, 4 * MM)
            c.drawString(MARGIN * MM, (ph - MARGIN - 4.5) * MM, labels[r][col])
            c.setFont(font, 2.8 * MM)
            nb = []
            if r > 0: nb.append(f"↑ {labels[r - 1][col]}")
            if r < rows - 1: nb.append(f"↓ {labels[r + 1][col]}")
            if col > 0: nb.append(f"← {labels[r][col - 1]}")
            if col < cols - 1: nb.append(f"→ {labels[r][col + 1]}")
            c.drawString((MARGIN + 12) * MM, (ph - MARGIN - 4.5) * MM,
                         f"{tpl.title} · sayfa {r * cols + col + 1}/{rows * cols}" + (f" · komşular: {'  '.join(nb)}" if nb else ""))
            # 10 mm ölçek çubuğu
            c.setLineWidth(0.4 * MM)
            c.line((pw - MARGIN - 10) * MM, (ph - MARGIN - 4) * MM, (pw - MARGIN) * MM, (ph - MARGIN - 4) * MM)
            c.setFont(font, 2.2 * MM)
            c.drawRightString((pw - MARGIN - 11) * MM, (ph - MARGIN - 4.6) * MM, "10 mm")
            c.showPage()
    c.save()
    return {"pages": rows * cols, "grid": (rows, cols)}


def _diamond_points(tw: float, th: float):
    pts = []
    for fx in (0.25, 0.75):
        pts += [(tw * fx, 0), (tw * fx, th)]
    for fy in (0.25, 0.75):
        pts += [(0, th * fy), (tw, th * fy)]
    return pts


def _diamond(c: Canvas, x: float, y: float, s: float = 2.5):
    p = c.beginPath()
    p.moveTo((x) * MM, (y + s) * MM)
    p.lineTo((x + s) * MM, y * MM)
    p.lineTo(x * MM, (y - s) * MM)
    p.lineTo((x - s) * MM, y * MM)
    p.close()
    c.drawPath(p, stroke=0, fill=1)

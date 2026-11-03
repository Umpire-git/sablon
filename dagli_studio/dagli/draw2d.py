"""Düz parçaları ReportLab tuvaline çizer (1:1 şablon, küçültülmüş genel bakış, adım çizimleri)."""
from __future__ import annotations

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.units import mm

from .geom import Part, bounds_of, rings
from .house import BLUE, GREY, INK, RED, fonts

# vurgu modları: hangi öğe kırmızı (o adımda yapılacak iş)
MODES = {"template", "overview", "trace", "punch", "slits", "outline", "cuts", "edges", "crease", "plain"}


def fit(parts: list[Part], w: float, h: float, pad: float = 0.06):
    """Parçaları (w×h pt) kutuya sığdıran ölçek (pt/mm) ve ofset."""
    x0, y0, x1, y1 = bounds_of(parts)
    bw, bh = x1 - x0, y1 - y0
    s = min(w * (1 - 2 * pad) / bw, h * (1 - 2 * pad) / bh)
    return s, (w - bw * s) / 2 - x0 * s, (h - bh * s) / 2 - y0 * s


def _path(c, pts, X, Y, close=True):
    p = c.beginPath()
    p.moveTo(X(pts[0][0]), Y(pts[0][1]))
    for x, y in pts[1:]:
        p.lineTo(X(x), Y(y))
    if close:
        p.close()
    return p


def draw_parts(c, parts: list[Part], ox: float, oy: float, s: float, mode: str = "template",
               leather: str | None = None, labels: bool = True, punch_d: float | None = None):
    """s: pt/mm (1:1 için s = mm). ox, oy: mm 0 noktasının sayfa konumu (pt)."""
    f, fb = fonts()
    X = lambda x: ox + x * s
    Y = lambda y: oy + y * s
    full = mode in ("template", "plain")
    lw_cut = 0.5 if full else max(0.35, 0.25 * s)
    hi = RED
    for p in parts:
        rs = rings(p.outline)
        # dolgu
        if mode == "overview":
            fill = HexColor(p.color)
        elif mode in ("trace",) or leather:
            fill = HexColor(leather or "#8a5230")
        elif mode == "edges":
            fill = HexColor("#efe6d8")
        else:
            fill = None
        path = c.beginPath()
        for r in rs:
            sub = _path(c, r, X, Y)
            path._code.extend(sub._code)  # birden çok halka, çift-tek dolgu
        c.setLineWidth(lw_cut * (2.2 if mode == "edges" else 1.0))
        c.setStrokeColor(hi if mode == "outline" else (HexColor("#3b2414") if mode == "edges" else INK))
        if fill is not None:
            c.setFillColor(fill)
        c.drawPath(path, stroke=1, fill=1 if fill is not None else 0, fillMode=0)
        # kat çizgileri
        c.setStrokeColor(BLUE)
        c.setLineWidth((1.0 if mode == "crease" else 0.6) * (1 if full else max(0.5, s / 2.8)))
        c.setDash(3, 2)
        for fl in p.folds:
            c.drawPath(_path(c, fl, X, Y, close=False), stroke=1, fill=0)
        c.setDash()
        # kesikler (dil çifti orta kesikleri, boyun kesikleri)
        c.setStrokeColor(hi if mode == "cuts" else INK)
        c.setLineWidth(lw_cut * (1.6 if mode == "cuts" else 1))
        for cu in p.cuts:
            c.drawPath(_path(c, cu, X, Y, close=False), stroke=1, fill=0)
        # yarıklar
        for sl in p.slits:
            a, b = sl.ends(punch_d)
            c.setStrokeColor(hi if mode in ("slits", "template", "overview") else INK)
            c.setLineWidth(lw_cut * (1.6 if mode == "slits" else 1))
            c.line(X(a[0]), Y(a[1]), X(b[0]), Y(b[1]))
        # delikler
        for h in p.stop_holes(punch_d) + [hh for hh in p.holes if not hh.stop]:
            red = (mode == "punch" and h.stop) or (mode in ("template", "overview") and h.stop)
            c.setStrokeColor(hi if red else INK)
            c.setFillColor(hi if mode == "punch" and h.stop else Color(1, 1, 1))
            c.setLineWidth(0.35 if full else 0.3)
            c.circle(X(h.center[0]), Y(h.center[1]), h.d / 2 * s, stroke=1, fill=1 if mode == "punch" and h.stop else 0)
        # yazılar
        if labels and mode in ("template", "overview", "plain"):
            for lb in p.labels:
                size_pt = lb.size * s if mode == "template" or s < mm else lb.size * mm
                size_pt = max(4.0, min(size_pt, 14.0))
                c.saveState()
                c.translate(X(lb.pos[0]), Y(lb.pos[1]))
                c.rotate(lb.angle)
                c.setFillColor(HexColor(lb.color))
                c.setFont(fb if lb.size >= 4 else f, size_pt)
                c.drawCentredString(0, -size_pt / 3, lb.text)
                c.restoreState()
            if p.note and mode == "template":
                x0, y0, x1, y1 = p.bounds()
                c.setFillColor(GREY)
                c.setFont(f, 7)
                c.drawCentredString(X((x0 + x1) / 2), Y((y0 + y1) / 2) - 10, p.note)


def draw_fit(c, parts, x, y, w, h, mode="plain", pad=0.06, **kw):
    s, ox, oy = fit(parts, w, h, pad)
    draw_parts(c, parts, x + ox, y + oy, s, mode, **kw)
    return s, x + ox, y + oy


def legend(c, x, y, punch_d=2.0):
    """Çizgi lejantı (sol üst köşe x,y)."""
    f, fb = fonts()
    c.setFont(fb, 7)
    c.setFillColor(INK)
    c.drawString(x, y, "LEGEND")
    rows = [("cut", INK, False), ("fold – do not cut", BLUE, True),
            (f"slit: punch Ø {punch_d:g} mm holes, cut between", RED, False)]
    yy = y - 4.5 * mm
    for text, col, dash in rows:
        c.setStrokeColor(col)
        c.setLineWidth(0.8)
        if dash:
            c.setDash(3, 2)
        c.line(x, yy + 1, x + 9 * mm, yy + 1)
        c.setDash()
        if text.startswith("slit"):
            c.setFillColor(Color(1, 1, 1))
            c.circle(x, yy + 1, 1 * mm, fill=1)
            c.circle(x + 9 * mm, yy + 1, 1 * mm, fill=1)
        c.setFillColor(INK)
        c.setFont(f, 6.5)
        c.drawString(x + 11 * mm, yy - 1, text)
        yy -= 4 * mm
    return yy

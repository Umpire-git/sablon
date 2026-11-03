"""Satış PDF'i (A4 / US Letter / tam boy fotokopici) — Dagli ev formatı.

Tek sayfaya sığan ürün:   1 şablon 1:1 + kontrol karesi → 2 genel bakış → adımlar → yakın plan → yardım
Sığmayan ürün:            1 genel bakış → 2 baskı & sayfa haritası → şablon sayfaları → adımlar → yakın plan → yardım
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from . import draw2d as D
from . import house as Hs
from .geom import bounds_of
from .product import Product, Step

PAPER = {"A4": A4, "Letter": letter}
TOP_RESERVE = 24 * mm  # küçük başlık
BOTTOM_RESERVE = 12 * mm
M = 8 * mm  # şablon kenar boşluğu
SIDE_COL = 64 * mm
OVERLAP = 20.0  # mm, parçalı baskıda bindirme


@dataclass
class TemplatePlan:
    single: bool
    orient: str = "portrait"  # tek sayfa için
    side: bool = True  # lejant/kare yanda (True) veya altta
    pages: list = None  # parçalı: [(parça_adı, sayfa_boyutu, [döşeme])]


def _sizes(paper):
    p = PAPER[paper]
    return {"portrait": p, "landscape": landscape(p)}


def plan_template(prod: Product, paper: str) -> TemplatePlan:
    parts = prod.layout()
    x0, y0, x1, y1 = bounds_of(parts)
    w, h = (x1 - x0) * mm, (y1 - y0) * mm
    for orient, (W, H) in _sizes(paper).items():
        avail_h = H - TOP_RESERVE - BOTTOM_RESERVE
        if w <= W - 2 * M - SIDE_COL and h <= avail_h:
            return TemplatePlan(True, orient, True)
        if w <= W - 2 * M and h <= avail_h - 64 * mm:
            return TemplatePlan(True, orient, False)
    # parçalı: her parça kendi sayfası/sayfaları
    pages = []
    for p in prod.parts():
        pw, ph = (v * mm for v in p.size())
        done = False
        for orient, (W, H) in _sizes(paper).items():
            if pw <= W - 2 * M and ph <= H - TOP_RESERVE - BOTTOM_RESERVE:
                pages.append((p.name, (W, H), [None]))
                done = True
                break
        if not done:
            W, H = _sizes(paper)["landscape"]
            cw, ch = W - 2 * M, H - TOP_RESERVE - BOTTOM_RESERVE
            step_w, step_h = cw - OVERLAP * mm, ch - OVERLAP * mm
            nx = max(1, math.ceil((pw - OVERLAP * mm) / step_w))
            ny = max(1, math.ceil((ph - OVERLAP * mm) / step_h))
            tiles = [(ix, iy, nx, ny) for iy in range(ny - 1, -1, -1) for ix in range(nx)]
            pages.append((p.name, (W, H), tiles))
    return TemplatePlan(False, pages=pages)


class Booklet:
    def __init__(self, prod: Product, paper: str = "A4", images: dict | None = None):
        self.p = prod
        self.paper = paper
        self.tp = plan_template(prod, paper)
        self.steps = prod.steps()
        self.closeups = prod.closeups()
        self.images = images or {}
        self.info_size = landscape(PAPER[paper])
        self._scene = None

    @property
    def scene(self):
        if self._scene is None:
            self._scene = self.p.scene(self.p.meta.t_draw)
        return self._scene

    # ---------------------------------------------------------------- sayfa planı
    def page_plan(self):
        pl = []
        if self.tp.single:
            pl.append(("template", None))
            pl.append(("overview", None))
        else:
            pl.append(("overview", None))
            pl.append(("printmap", None))
            for name, size, tiles in self.tp.pages:
                for t in tiles:
                    pl.append(("tile", (name, size, t)))
        for i in range(0, len(self.steps), 9):
            pl.append(("steps", i))
        for i in range(0, len(self.closeups), 2):
            pl.append(("closeups", i))
        pl.append(("help", None))
        return pl

    def contents_lines(self, plan) -> list[str]:
        def pages_of(kind):
            idx = [i + 1 for i, (k, _) in enumerate(plan) if k == kind]
            if not idx:
                return ""
            return f"Page {idx[0]}" if len(idx) == 1 else f"Pages {idx[0]}–{idx[-1]}"

        n = len(self.steps)
        out = []
        if self.tp.single:
            out.append(f"{pages_of('template')}  Template 1:1 + 50 mm check square (print first)")
            out.append(f"{pages_of('overview')}  Overview (this page)")
        else:
            out.append(f"{pages_of('overview')}  Overview (this page)")
            out.append(f"{pages_of('printmap')}  How to print and join the template pages · page map · 50 mm check square")
            out.append(f"{pages_of('tile')}  Templates 1:1 · " + ", ".join(n_ for n_, _, _ in self.tp.pages))
        out.append(f"{pages_of('steps')}  {n} illustrated steps, one drawing per step")
        if self.closeups:
            out.append(f"{pages_of('closeups')}  Close-ups of the locks")
        out.append(f"{pages_of('help')}  Troubleshooting · care · words used")
        out.append("Extra files  SVG / Cricut SVG / DXF cut files (ZIP) · full-size copy-shop PDF")
        return out

    # ---------------------------------------------------------------- üretim
    def write(self, path: str):
        plan = self.page_plan()
        c = Canvas(path, pagesize=self.info_size)
        m = self.p.meta
        c.setTitle(f"Dagli Leather Studio – {m.name}")
        c.setAuthor("Dagli Leather Studio")
        c.setSubject("Printable leathercraft pattern and illustrated instructions")
        c.setKeywords(", ".join([self.p.seo.primary] + self.p.seo.keywords[:6]))
        d = Hs.Doc(c, m.name, m.version, len(plan))
        self.d = d
        for kind, arg in plan:
            getattr(self, f"_pg_{kind}")(arg, plan)
            d.footer()
        c.save()
        return len(plan)

    # ---------------------------------------------------------------- sayfalar
    def _pg_template(self, _, plan):
        d, c, p = self.d, self.d.c, self.p
        W, H = _sizes(self.paper)[self.tp.orient]
        d.new_page((W, H), watermark=False)
        top = d.header(f"PAGE {d.page} · TEMPLATE 1:1 · PRINT THIS PAGE FIRST",
                       "Print at 100% / Actual Size (“Fit to page” OFF) · check the 50 mm square before cutting",
                       small=True)
        parts = p.layout()
        x0, y0, x1, y1 = bounds_of(parts)
        if self.tp.side:
            area = (M, BOTTOM_RESERVE, W - 2 * M - SIDE_COL, top - BOTTOM_RESERVE)
            colx, coly = W - M - SIDE_COL + 4 * mm, top - 4 * mm
        else:
            area = (M, BOTTOM_RESERVE + 64 * mm, W - 2 * M, top - BOTTOM_RESERVE - 64 * mm)
            colx, coly = M + 2 * mm, BOTTOM_RESERVE + 60 * mm
        ax, ay, aw, ah = area
        ox = ax + (aw - (x1 - x0) * mm) / 2 - x0 * mm
        oy = ay + (ah - (y1 - y0) * mm) / 2 - y0 * mm
        D.draw_parts(c, parts, ox, oy, mm, "template")
        f, fb = Hs.fonts()
        c.setFillColor(Hs.INK)
        c.setFont(fb, 9)
        c.drawString(colx, coly, "TEMPLATE 1:1")
        c.setFont(f, 6.5)
        c.drawString(colx, coly - 4 * mm, f"{len(parts)} piece{'s' if len(parts) > 1 else ''} · leather {p.meta.leather.split('(')[0].strip()}")
        D.legend(c, colx, coly - 11 * mm)
        if self.tp.side:
            Hs.check_square(c, colx + 4 * mm, BOTTOM_RESERVE + 8 * mm)
            Hs.para(c, "Check the square first. If it is not exactly 50 mm, check the print scale and print again.",
                    colx, BOTTOM_RESERVE + 8 * mm + 50 * mm + 12 * mm, SIDE_COL - 8 * mm, 6.5)
        else:
            Hs.check_square(c, W - M - 56 * mm, BOTTOM_RESERVE + 8 * mm)

    def _pg_overview(self, _, plan):
        d, c, p = self.d, self.d.c, self.p
        W, H = self.info_size
        d.new_page((W, H))
        top = d.header(f"PAGE {d.page} · OVERVIEW · WHAT YOU WILL MAKE", "Digital pattern · read this page first")
        f, fb = Hs.fonts()
        left_w = W * 0.47
        # 3B kahraman görseli
        hero_h = (top - BOTTOM_RESERVE) * 0.52
        self.scene.draw(c, M, top - hero_h, left_w - M, hero_h, fold=1.0, az=-35, el=28)
        # küçültülmüş renkli açınım
        fy0 = BOTTOM_RESERVE + 8 * mm
        fh = top - hero_h - fy0 - 6 * mm
        Hs.ref_frame(c, M, fy0, left_w - M, fh)
        s, ox, oy = D.draw_fit(c, p.layout(), M, fy0, left_w - M, fh, mode="overview", pad=0.08)
        # sağ sütun metin
        x = left_w + 8 * mm
        w = W - x - M
        blocks = [("AT A GLANCE", [f"**{k}:** {v}" for k, v in p.at_a_glance()])]
        before = []
        if p.meta.tested:
            before.append(f"**Real test:** {p.meta.tested}")
        before += [f"**Tools:** {p.meta.tools}.",
                   f"**Tolerant by design:** every lock is computer-checked for leather {p.meta.t_test[0]:g}–"
                   f"{p.meta.t_test[1]:g} mm, folds 1 mm off, slits 0.7 mm off and 1.5–3 mm punches.",
                   "**Card first:** one test in thin card (or the paper pages) takes 15 minutes and shows you every step."]
        blocks.append(("BEFORE YOU START", before))
        blocks.append(("WHAT IS IN THIS PDF", self.contents_lines(plan)))
        avail = top - BOTTOM_RESERVE - 4 * mm
        size = 8.0
        while size > 5.5:
            tot = sum(5 * mm + sum(Hs.para_h(t, w, size) + 1.2 for t in ts) for _, ts in blocks)
            if tot <= avail:
                break
            size -= 0.25
        y = top - 2 * mm
        for title, ts in blocks:
            Hs.box_title(c, x, y - 3 * mm, title, 8.5)
            y -= 5.5 * mm
            for t in ts:
                y -= Hs.para(c, t, x, y, w, size) + 1.2

    def _pg_printmap(self, _, plan):
        d, c = self.d, self.d.c
        W, H = self.info_size
        d.new_page((W, H))
        top = d.header(f"PAGE {d.page} · HOW TO PRINT AND JOIN THE TEMPLATE PAGES",
                       "Print every template page at 100% / Actual Size (“Fit to page” off) · the square must measure 50 mm")
        x, w = 12 * mm, W * 0.55
        txt = [
            "**1  Print:** 100 % / Actual Size, “Fit to page” OFF. Measure the 50 mm square below. Wrong size? "
            "Check the print settings and print again.",
            f"**2  Join:** lay the pages out as the map shows. Neighbouring pages overlap by {OVERLAP:g} mm: put the "
            "cross marks exactly on top of each other and tape.",
            "**3  Trace:** cut out the paper template along the outer line, lay it on the grain side of the leather and "
            "trace the outline, slits, holes and the ends of the fold lines.",
            "**Tip:** one full sheet instead of tiles? Print the “FullSize_CopyShop” PDF at a copy shop or on a plotter, 100 %.",
        ]
        y = top - 2 * mm
        for t in txt:
            y -= Hs.para(c, t, x, y, w, 8) + 2 * mm
        D.legend(c, W - 75 * mm, top - 2 * mm)
        Hs.check_square(c, x + 4 * mm, BOTTOM_RESERVE + 10 * mm)
        # sayfa haritası
        f, fb = Hs.fonts()
        mx = x + 70 * mm
        pg = 1 + next(i for i, (k, _) in enumerate(plan) if k == "tile")
        for name, size, tiles in self.tp.pages:
            nx = tiles[0][2] if tiles[0] else 1
            ny = tiles[0][3] if tiles[0] else 1
            cw = 14 * mm
            for t in tiles:
                ix, iy = (t[0], t[1]) if t else (0, 0)
                bx, by = mx + ix * cw, BOTTOM_RESERVE + 18 * mm + iy * cw
                c.setStrokeColor(Hs.INK)
                c.setLineWidth(0.5)
                c.rect(bx, by, cw - 1 * mm, cw - 1 * mm)
                c.setFont(fb, 7)
                c.drawCentredString(bx + cw / 2, by + cw / 2 - 2, str(pg))
                pg += 1
            c.setFont(fb, 7)
            c.drawString(mx, BOTTOM_RESERVE + 18 * mm + ny * cw + 2 * mm, name.upper())
            mx += nx * cw + 10 * mm
        c.setFont(f, 6)
        c.setFillColor(Hs.GREY)
        c.drawString(x + 70 * mm, BOTTOM_RESERVE + 12 * mm, "PAGE MAP · numbers = PDF page numbers")

    def _pg_tile(self, arg, plan):
        name, (W, H), t = arg
        d, c, p = self.d, self.d.c, self.p
        part = next(pp for pp in p.parts() if pp.name == name)
        d.new_page((W, H), watermark=False)
        lab = f" · SHEET {chr(65 + t[1])}{t[0] + 1}" if t else ""
        top = d.header(f"PAGE {d.page} · TEMPLATE 1:1 · {name.upper()}{lab}", "print at 100% / Actual Size", small=True)
        x0, y0, x1, y1 = part.bounds()
        cw, ch = W - 2 * M, top - BOTTOM_RESERVE
        if t is None:
            ox = M + (cw - (x1 - x0) * mm) / 2 - x0 * mm
            oy = BOTTOM_RESERVE + (ch - (y1 - y0) * mm) / 2 - y0 * mm
            D.draw_parts(c, [part], ox, oy, mm, "template")
            return
        ix, iy, nx, ny = t
        step_w, step_h = cw - OVERLAP * mm, ch - OVERLAP * mm
        ox = M - x0 * mm - ix * step_w
        oy = BOTTOM_RESERVE - y0 * mm - iy * step_h
        c.saveState()
        pth = c.beginPath()
        pth.rect(M, BOTTOM_RESERVE, cw, ch)
        c.clipPath(pth, stroke=0, fill=0)
        D.draw_parts(c, [part], ox, oy, mm, "template")
        c.restoreState()
        c.setStrokeColor(Hs.GREY)
        c.setLineWidth(0.3)
        c.setDash(1, 2)
        c.rect(M, BOTTOM_RESERVE, cw, ch)
        c.setDash()
        # bindirme artıları
        for bx in (M + OVERLAP * mm / 2, M + cw - OVERLAP * mm / 2):
            for by in (BOTTOM_RESERVE + OVERLAP * mm / 2, BOTTOM_RESERVE + ch - OVERLAP * mm / 2):
                c.setStrokeColor(Hs.INK)
                c.line(bx - 3 * mm, by, bx + 3 * mm, by)
                c.line(bx, by - 3 * mm, bx, by + 3 * mm)
        if ix == 0 and iy == 0:
            Hs.check_square(c, M + cw - 56 * mm, BOTTOM_RESERVE + 26 * mm, label=True)

    def _draw_step(self, st: Step, x, y, w, h, n):
        c, p = self.d.c, self.p
        parts = p.layout()
        k = st.kind
        if k == "print":
            pw, ph = w * 0.42, h * 0.8
            px, py = x + w * 0.08, y + (h - ph) / 2
            c.setStrokeColor(Hs.GREY)
            c.setLineWidth(0.4)
            c.rect(px, py, pw, ph)
            D.draw_fit(c, parts, px, py + ph * 0.25, pw, ph * 0.72, mode="template", labels=False)
            c.rect(px + pw * 0.65, py + 2, pw * 0.25, pw * 0.25)
            c.setFont(Hs.fonts()[0], 5)
            c.drawCentredString(px + pw * 0.78, py + pw * 0.27 + 3, "50 mm")
            c.setFont(Hs.fonts()[1], 7)
            c.setFillColor(Hs.RED)
            c.drawString(px + pw + 4 * mm, py + ph / 2, "100 %")
        elif k in ("trace", "punch", "slits", "outline", "cuts", "edges", "crease"):
            D.draw_fit(c, parts, x, y + 3 * mm, w, h - 3 * mm, mode=k,
                       leather=p.meta.grain_color if k == "trace" else None, labels=False)
        elif k in ("fold", "done"):
            self.scene.draw(c, x, y + 3 * mm, w, h - 3 * mm, fold=st.fold, az=st.az, el=st.el)
        elif k == "custom" and st.draw:
            st.draw(c, x, y, w, h, p)
        for (a, b) in st.arrows:
            Hs.arrow(c, x + a[0] * w, y + a[1] * h, x + b[0] * w, y + b[1] * h)
        if st.caption:
            c.setFont(Hs.fonts()[0], 5.5)
            c.setFillColor(Hs.INK)
            c.drawCentredString(x + w / 2, y + 0.8 * mm, st.caption)

    def _pg_steps(self, i0, plan):
        d, c = self.d, self.d.c
        W, H = self.info_size
        d.new_page((W, H))
        sts = self.steps[i0:i0 + 9]
        top = d.header(f"PAGE {d.page} · STEPS {i0 + 1}–{i0 + len(sts)}", f"Pattern v{self.p.meta.version} · one drawing per step")
        gx, gy = 10 * mm, BOTTOM_RESERVE + 2 * mm
        gw, gh = W - 20 * mm, top - gy - 2 * mm
        cw, ch = (gw - 2 * 5 * mm) / 3, (gh - 2 * 5 * mm) / 3
        for j, st in enumerate(sts):
            col, row = j % 3, j // 3
            x = gx + col * (cw + 5 * mm)
            y = gy + gh - (row + 1) * ch - row * 5 * mm
            c.setFillColor(HexColor("#ffffff"))
            Hs.card(c, x, y, cw, ch, fill=HexColor("#ffffff"))
            self._draw_step(st, x + 2 * mm, y + 2 * mm, cw * 0.5 - 2 * mm, ch - 4 * mm, i0 + j + 1)
            tx = x + cw * 0.52
            Hs.badge(c, tx, y + ch - 8 * mm, i0 + j + 1)
            Hs.para(c, st.text, tx, y + ch - 10 * mm, cw * 0.46, 7.2, max_h=ch - 13 * mm)

    def _pg_closeups(self, i0, plan):
        d, c, p = self.d, self.d.c, self.p
        W, H = self.info_size
        d.new_page((W, H))
        top = d.header(f"PAGE {d.page} · CLOSE-UPS", "How the locks work")
        cls = self.closeups[i0:i0 + 2]
        bw = (W - 20 * mm - 6 * mm) / 2
        for j, cl in enumerate(cls):
            x = 10 * mm + j * (bw + 6 * mm)
            y, h = BOTTOM_RESERVE + 4 * mm, top - BOTTOM_RESERVE - 6 * mm
            Hs.card(c, x, y, bw, h, fill=HexColor("#ffffff"))
            Hs.box_title(c, x + 4 * mm, y + h - 7 * mm, cl.title, 8)
            th = Hs.para(c, cl.text, x + 4 * mm, y + h - 9 * mm, bw - 8 * mm, 7.5)
            dy = y + 10 * mm
            dh = h - 9 * mm - th - 14 * mm
            if cl.draw:
                cl.draw(c, x + 4 * mm, dy, bw - 8 * mm, dh, p)
            else:
                sc = zoom_scene(self.scene, cl)
                sc.draw(c, x + 4 * mm, dy, bw - 8 * mm, dh, fold=cl.fold, az=cl.az, el=cl.el)
            if cl.caption:
                c.setFont(Hs.fonts()[0], 8)
                c.setFillColor(Hs.INK)
                c.drawCentredString(x + bw / 2, y + 4 * mm, cl.caption)

    def _pg_help(self, _, plan):
        d, c, p = self.d, self.d.c, self.p
        W, H = self.info_size
        d.new_page((W, H))
        top = d.header(f"PAGE {d.page} · TROUBLESHOOTING, CARE, WORDS USED", "Read this if something does not close or hold")
        f, fb = Hs.fonts()
        ts = list(p.troubleshooting) + [("Template wrong size", "The 50 mm square must measure 50 mm. Print at 100 % / "
                                                                 "Actual Size, “Fit to page” off.")]
        box_h = 62 * mm
        colw = (W - 30 * mm) / 2
        Hs.box_title(c, 10 * mm, top - 4 * mm, "TROUBLESHOOTING", 8.5)
        avail = top - 8 * mm - (BOTTOM_RESERVE + box_h + 6 * mm)
        size = 7.8
        while size > 5.6:
            hs = [Hs.para_h(f"**{a}**", colw, size) + Hs.para_h(b, colw, size) + 2 * mm for a, b in ts]
            half = (len(hs) + 1) // 2
            if max(sum(hs[:half]), sum(hs[half:])) <= avail:
                break
            size -= 0.25
        half = (len(ts) + 1) // 2
        for col, chunk in enumerate((ts[:half], ts[half:])):
            x = 10 * mm + col * (colw + 10 * mm)
            y = top - 8 * mm
            for a, b in chunk:
                y -= Hs.para(c, f"**{a}**", x, y, colw, size)
                y -= Hs.para(c, b, x, y, colw, size) + 2 * mm
        # alt kutular
        bw = (W - 26 * mm) / 2
        for j, (title, rows) in enumerate((("CARE AND USE", p.care), ("WORDS USED IN THIS PATTERN", p.words))):
            x = 10 * mm + j * (bw + 6 * mm)
            y = BOTTOM_RESERVE + 2 * mm
            Hs.card(c, x, y, bw, box_h, fill=Hs.LIGHT, line=Hs.LIGHT)
            Hs.box_title(c, x + 4 * mm, y + box_h - 7 * mm, title, 7.5)
            yy = y + box_h - 10 * mm
            sz = 7.0
            while sz > 5.2 and sum(Hs.para_h(f"**{a}** – {b}", bw - 8 * mm, sz) + 1 for a, b in rows) > box_h - 14 * mm:
                sz -= 0.25
            for a, b in rows:
                yy -= Hs.para(c, f"**{a}** – {b}", x + 4 * mm, yy, bw - 8 * mm, sz) + 1


def write_fullsize(prod: Product, path: str):
    """Tek sayfa, gerçek boy (fotokopici / plotter)."""
    parts = prod.layout()
    x0, y0, x1, y1 = bounds_of(parts)
    W = (x1 - x0) * mm + 2 * 15 * mm
    H = (y1 - y0) * mm + 2 * 15 * mm + 70 * mm
    c = Canvas(path, pagesize=(W, H))
    c.setTitle(f"Dagli Leather Studio – {prod.meta.name} – full size")
    Hs.fonts()
    D.draw_parts(c, parts, 15 * mm - x0 * mm, 85 * mm - y0 * mm, mm, "template")
    Hs.check_square(c, 15 * mm, 15 * mm)
    f, fb = Hs.fonts()
    c.setFont(fb, 9)
    c.drawString(75 * mm, 55 * mm, f"{prod.meta.name.upper()} · FULL SIZE 1:1 · v{prod.meta.version}")
    c.setFont(f, 7)
    c.drawString(75 * mm, 50 * mm, "Print at 100 % on one large sheet (copy shop / plotter). The square must measure 50 mm.")
    c.drawString(75 * mm, 45 * mm, f"© {Hs.BRAND} · All rights reserved · For personal and small-scale crafting use")
    D.legend(c, 75 * mm, 38 * mm)
    c.save()


def zoom_scene(scene, cl):
    """Yakın plan için sahnenin bir bölümü (panel listesi veya bir panelin çevresi)."""
    import numpy as np
    from copy import copy
    if not (cl.zoom_panels or cl.zoom_near):
        return scene
    sc = copy(scene)
    sc.props = []

    def ctr(pp):
        q = np.array(pp.poly.centroid.coords[0])
        return (pp.world(cl.fold) @ np.array([q[0], q[1], 0, 1.0]))[:3]

    keep = set(cl.zoom_panels or [])
    if cl.zoom_near:
        name, r = cl.zoom_near
        c0 = ctr(next(pp for pp in scene.panels if pp.name == name))
        keep |= {pp.name for pp in scene.panels if np.linalg.norm(ctr(pp) - c0) <= r}
    sc.panels = [pp for pp in scene.panels if pp.name in keep]
    return sc

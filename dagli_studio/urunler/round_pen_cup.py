"""No-Stitch Round Pen Cup — Round Pen Cup v1.1'in parametrik yeniden kurulumu (motor örneği).

İki parça: duvar şeridi (tüp olur) + yuvarlak taban (4 tırnak). Dikiş, yapıştırıcı, metal yok.
Dikiş yeri: dil ucu, yarık ucunun ÜSTÜNDEN geçer; 3 dil çifti yarıklardan içeri girer (başlar içte).
Taban: 4 tırnak duvarın DIŞINDAN yukarı katlanır, dil çiftleri alçak yarıklardan içeri girer.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Polygon, box

from dagli.fold3d import Scene, rot, tr
from dagli.geom import Label, Part, Slit, circle, fillet_inner, union
from dagli.locks import LockCase, Tongue, check_tongue_slit
from dagli.product import Closeup, Meta, Product, Seo, Step

# ---- ana ölçüler (mm) ----
T_NOM = 2.0  # tasarım kalınlığı
DF = 39.6  # tırnak katı merkezden (duvar dış yüzü)
RB = 40.8  # taban yarıçapı (alttan ince şerit görünür)
HW = 100.0  # duvar yüksekliği
SLIT_X = 10.0  # dikiş yarıklarının sol uçtan uzaklığı
SEAM_Y = (20.0, 50.0, 80.0)  # dikiş dil çiftleri
LOW_Y = 8.5  # alçak (taban) yarık merkez yüksekliği
OPEN = 16.0  # yarık açıklığı
NECK_W, HEAD_W, HEAD_L = 12.0, 23.0, 9.0
SEAM_R0 = 2.5  # nominal: dil kökü yarığa bu kadar uzak
SEAM_NECK = 10.6
TAB_W = 20.0
TAB_L = 6.5  # tırnak gövdesi (kat çizgisinden dil köküne)
TAB_NECK = 11.0

C_IN = 2 * math.pi * (DF - T_NOM / 2)  # iç kat orta çevresi
L_BODY = C_IN + SLIT_X - SEAM_R0  # şerit gövde boyu (dilsiz)
LOW_X = [SLIT_X + C_IN / 8 + k * C_IN / 4 for k in range(4)]


def seam_tongues():
    return [Tongue((L_BODY, y), 0.0, NECK_W, SEAM_NECK, HEAD_W, HEAD_L, pair=True, label=f"T{i + 1}")
            for i, y in enumerate(SEAM_Y)]


def seam_slits():
    return [Slit((SLIT_X, y), 90.0, OPEN, f"S{i + 1}") for i, y in enumerate(SEAM_Y)]


def low_slits():
    return [Slit((x, LOW_Y), 0.0, OPEN, f"B{i + 1}") for i, x in enumerate(LOW_X)]


def tab_angles():
    return [45.0 + 90.0 * k for k in range(4)]


def tab_tongues():
    out = []
    for i, a in enumerate(tab_angles()):
        r = math.radians(a)
        bx, by = (DF + TAB_L) * math.cos(r), (DF + TAB_L) * math.sin(r)
        out.append(Tongue((bx, by), a, NECK_W, TAB_NECK, HEAD_W, HEAD_L, pair=True, label=f"P{i + 1}"))
    return out


def _tab_poly(a_deg, inner=DF - 3.0):
    r = math.radians(a_deg)
    pts = [(inner, -TAB_W / 2), (DF + TAB_L, -TAB_W / 2), (DF + TAB_L, TAB_W / 2), (inner, TAB_W / 2)]
    return Polygon([(u * math.cos(r) - v * math.sin(r), u * math.sin(r) + v * math.cos(r)) for u, v in pts])


def _fold_line(a_deg):
    r = math.radians(a_deg)
    h = math.sqrt(RB ** 2 - DF ** 2)
    return [(DF * math.cos(r) - v * math.sin(r), DF * math.sin(r) + v * math.cos(r)) for v in (-h, h)]


class RoundPenCup(Product):
    meta = Meta(
        name="No-Stitch Round Pen Cup", slug="Dagli_Round_Pen_Cup", sku="DLS-PENCUP-V2", version="2.0",
        finished_size="round, inside Ø 7.4–7.7 cm, 10 cm high (Ø 3 × 3.9 in)",
        leather="1.4–2.4 mm (3.5–6 oz); even soft leather that does not hold a fold makes a firm cup",
        t_range=(1.4, 2.4), t_test=(0.2, 2.4),
        tested="made and tested in 2.0 mm oiled pull-up leather. The tongues are snug by design – press them "
               "through with the tip of a bone folder.",
        lock_summary="3 tongue pairs close the seam, 4 base tabs fold up outside and lock in – all heads inside",
        matching="square pen holder, desk organizer, document tray",
        build_time="about 1 hour", skill="Beginner – no sewing, no glue",
        grain_color="#6e3b1f", flesh_color="#d8b48a", t_draw=2.0,
    )
    seo = Seo(
        primary="leather pen holder pattern",
        keywords=["no sew pen cup", "pen cup pattern", "desk organizer pattern", "leather pdf pattern",
                  "stitchless leather", "makeup brush holder", "pencil cup template", "svg leather pattern",
                  "cricut leather", "dxf laser pattern", "teacher gift diy", "veg tan pattern", "leathercraft pattern"],
        occasion="Back to school", holidays=["Christmas", "Teacher Appreciation", "Father's Day"],
        section="PDF Patterns", price_usd=(9.0, 12.0),
        what_it_does="A round leather pen cup that locks itself together with tongue-and-slit locks. "
                     "No stitching, no glue, no hardware – unlock it and it lies flat again.",
        use_cases=["pens and pencils", "make-up brushes", "paint brushes", "small tools"],
        cross_links=["Square Pen Holder pattern", "Desk Organizer pattern", "Origami AirTag Keyring pattern"],
    )
    troubleshooting = [
        ("Tube is not round", "Roll the wall round a bottle or a can before you close it; veg-tan: dampen slightly and "
                              "let it dry on the can."),
        ("Base sits off-centre", "Centre the tube on the disc before you lock the first tab; then lock the opposite "
                                 "tab, then the other two."),
        ("Seam gapes", "All three pairs must be through; close the middle pair first."),
        ("A tongue will not go in", "Push one tongue of the pair at a time, tip first. Use the flat tip of a bone folder "
                                    "to press it through. Thick leather: skive the head on the flesh side."),
        ("A tongue pops out", "Both tongues must be fully through. Check the slit ends exactly at its holes and the "
                              "centre cut reaches its hole."),
    ]
    care = [("Use", "pens, brushes, make-up brushes, tools."), ("Flat-pack", "unlock base and seam."),
            ("Care", "a little leather balm now and then.")]
    words = [
        ("Grain / flesh side", "smooth outer face / rougher inner face."),
        ("Tongue pair", "two tongues side by side, split by a centre cut; they go through one slit one at a time."),
        ("Neck / head", "the narrow part goes through the slit; the wide head stays behind it."),
        ("Stop hole", "Ø 2 mm hole at each slit end and at the root of each centre cut; stops tearing."),
        ("Fold line", "dashed line: crease it on the flesh side, never cut it."),
    ]
    product_block = (
        "A round, open-top pen cup made from ONE strip of thick leather rolled into a tube (about 7.5 cm across, "
        "10 cm high) standing on a separate round leather disc base that is slightly wider than the tube, so a thin "
        "rim of the base shows at the bottom. The vertical seam is closed by three small tongue-and-slit locks: from "
        "outside you only see three short neat slits with the edge of the overlapping end – the tongue heads are "
        "INSIDE the cup. Four short tabs of the base fold up on the OUTSIDE of the wall at 90° spacing and tuck in "
        "through low slits about 1 cm above the bottom. Grain side (smooth, slightly waxy) faces out everywhere; the "
        "rough flesh side is never visible from outside. All edges are burnished and slightly rounded.")
    product_block_tr = (
        "Tek şerit kalın deriden yuvarlanmış, üstü açık yuvarlak kalemlik (≈7,5 cm çap, 10 cm boy); tüpten biraz geniş "
        "ayrı yuvarlak taban, alttan ince bir şerit görünür. Dikey dikiş yeri üç küçük dil-yarık kilidiyle kapanır; "
        "dışarıdan yalnızca üç kısa düzgün yarık ve bindirme kenarı görünür, dil başları İÇTEDİR. Tabanın dört kısa "
        "tırnağı duvarın DIŞINDAN 90° arayla yukarı katlanır ve alttan ≈1 cm yukarıdaki alçak yarıklardan içeri girer. "
        "Her yerde deri yüzü (düz, hafif mumlu) dışta; et yüzü dışarıdan hiç görünmez. Tüm kenarlar perdahlı ve hafif yuvarlak.")
    must_not = ["stitching or thread", "glue lines", "rivets, snaps or any metal", "logos or text on the leather",
                "a lid or handle", "visible tongue heads on the outside", "rough flesh side on the outside"]
    shots = [
        ("hero", "Hero: three-quarter view on a warm oak desk, a few pens inside, soft window light, shallow depth of field.",
         "Ana görsel: meşe masada 3/4 açı, içinde birkaç kalem, yumuşak pencere ışığı, sığ alan derinliği."),
        ("lock", "Close-up of the seam from outside showing the three neat slits and the burnished overlapping edge.",
         "Dikiş yerinin dışarıdan yakın çekimi: üç düzgün yarık ve perdahlı bindirme kenarı."),
        ("hand", "In hand: a hand (no face) placing a fountain pen into the cup, neutral linen background.",
         "Elde: bir el (yüz yok) kalemliğe dolma kalem koyuyor, nötr keten fon."),
        ("lifestyle", "Lifestyle: on a tidy home-office desk next to a notebook and a plant, make-up brushes variant optional.",
         "Yaşam tarzı: düzenli ev ofisi masasında defter ve bitkinin yanında."),
        ("workshop", "Workshop: the flat cut pieces and the finished cup on a cutting mat with a bone folder and a 2 mm "
                     "punch; the paper pattern is NOT visible.",
         "Atölye: kesim matında düz kesilmiş parçalar ve bitmiş kalemlik, perdah kemiği ve 2 mm zımba; kâğıt kalıp GÖRÜNMEZ."),
    ]

    # ------------------------------------------------------------ geometri
    def parts(self):
        body = box(0, 0, L_BODY, HW)
        tg = seam_tongues()
        wall = fillet_inner(union(body, *[t.polygon() for t in tg]), 1.0)
        wall_p = Part("Wall", wall, "#e8b28a", note="WALL · rolls into a tube, grain side out")
        for t in tg:
            wall_p.cuts += t.cuts()
            wall_p.holes += t.holes()
        wall_p.slits = seam_slits() + low_slits()
        wall_p.labels = [Label((L_BODY - 60, HW - 8), "tongue end goes OVER the slit end", 3.0),
                         *[Label((s.center[0] + 7, s.center[1]), s.label, 3.0) for s in seam_slits()],
                         *[Label((s.center[0], s.center[1] + 6), s.label, 3.0) for s in low_slits()],
                         *[Label((t.base[0] + 3, t.base[1] + 9), t.label, 3.0) for t in tg]]
        tt = tab_tongues()
        base = fillet_inner(union(circle(0, 0, RB), *[_tab_poly(a) for a in tab_angles()], *[t.polygon() for t in tt]), 1.0)
        base_p = Part("Base", base, "#9fc6a8", note="BASE · fold the 4 tabs up")
        for t in tt:
            base_p.cuts += t.cuts()
            base_p.holes += t.holes()
        base_p.folds = [_fold_line(a) for a in tab_angles()]
        base_p.labels = [Label((0, 6), "BASE", 5.0)] + [
            Label(((DF - 9) * math.cos(math.radians(a)), (DF - 9) * math.sin(math.radians(a))), t.label, 3.0)
            for a, t in zip(tab_angles(), tt)]
        return [wall_p, base_p]

    def layout(self):
        w, b = self.parts()
        x0, y0, x1, y1 = w.bounds()
        bx0, by0, bx1, by1 = b.bounds()
        # taban şeridin altına ortalanır (yatay A4'e sığar mı? değilse booklet sayfalara böler)
        return [w.transformed(dx=-x0, dy=-y0 + (by1 - by0) + 8),
                b.transformed(dx=-bx0 + (x1 - x0 - (bx1 - bx0)) / 2, dy=-by0)]

    # ------------------------------------------------------------ kilit kontrolü
    def lock_check(self, case: LockCase):
        errs = []
        # dikiş: çevre, kalınlıkla değişir (π·Δt); gevşek sarım ve yarık kayması doğrudan eklenir
        reach = SEAM_R0 + math.pi * (T_NOM - case.t) + case.wrap + case.slit_off
        for tg, sl in zip(seam_tongues(), seam_slits()):
            errs += check_tongue_slit(tg, sl, case, reach)
        # taban: kat ekseninden alçak yarığa (taban kalınlığı + kıvrım ~1.3·t + kat/yarık hatası)
        s_d = LOW_Y + 1.3 * case.t + case.fold + case.slit_off + case.wrap
        for tg, sl in zip(tab_tongues(), low_slits()):
            errs += check_tongue_slit(tg, sl, case, s_d - TAB_L)
        return errs

    def extra_checks(self):
        e = []
        if RB - DF < 0.8:
            e.append("Taban kenarı duvarın dışına taşmıyor (RB − DF < 0.8 mm)")
        return e

    # ------------------------------------------------------------ 3B
    def scene(self, t=None):
        t = t or T_NOM
        m = self.meta
        sc = Scene(t, grain=m.grain_color, flesh=m.flesh_color, edge="#3d2010")
        w_part, b_part = self.parts()
        N = 40
        c_in = 2 * math.pi * (DF - t / 2)
        seg = c_in / N
        Rc = (seg / 2) / math.tan(math.pi / N)
        # duvar: x ekseni çevre, y yükseklik → dik durması için x ekseni etrafında 90°
        place = tr((0, 0, t)) @ rot((1, 0, 0), math.radians(90)) @ tr((-seg / 2, 0, Rc))
        prev = None
        xs = [i * seg for i in range(N + 1)] + [L_BODY]
        wall = w_part.outline
        panels = []
        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            piece = wall.intersection(box(x0, -1, x1, HW + 1))
            if piece.geom_type != "Polygon":
                piece = max(piece.geoms, key=lambda g: g.area)
            if prev is None:
                p = sc.panel(f"wall{i}", piece, place=place, smooth=True)
            else:
                last = i == N
                p = sc.panel("overlap" if last else f"wall{i}", piece, parent=prev, hinge=((x0, 0), (x0, HW)),
                             angle=0.0 if last else 360.0 / N, stage=(0.0, 0.45), lift=t if last else 0.0, smooth=True)
            for s in w_part.slits:  # yarıklar → çıkartma
                if x0 <= s.center[0] < x1:
                    p.decals.append((list(s.ends()), "#1a0d05", 0.9))
            panels.append(p)
            prev = p
        # dikiş dilleri: bindirme ucundan içeri (yarıklardan) kıvrılır
        tongues = wall.intersection(box(L_BODY, -1, L_BODY + 40, HW + 1))
        tongues = [g for g in getattr(tongues, "geoms", [tongues]) if g.geom_type == "Polygon" and g.area > 1]
        for j, g in enumerate(tongues):
            sc.panel(f"seamT{j + 1}", g, parent=prev, hinge=((L_BODY, 0), (L_BODY, HW)), angle=88.0,
                     stage=(0.45, 0.6))
        # tüpü tabanın merkezine al
        pts = np.vstack([(pp.world(1.0) @ np.c_[np.array(pp.poly.exterior.coords), np.zeros(len(pp.poly.exterior.coords)),
                                               np.ones(len(pp.poly.exterior.coords))].T).T[:, :3] for pp in panels[:N]])
        ctr = (pts.min(0) + pts.max(0)) / 2
        place = tr((-ctr[0], -ctr[1], 0)) @ place
        panels[0].place = place
        # taban (deri yüzü altta)
        flip = rot((1, 0, 0), math.pi)
        base_full = b_part.outline
        core = base_full
        for a in tab_angles():
            core = core.difference(_tab_far(a))
        base = sc.panel("base", core, place=tr((0, 0, t / 2)) @ flip)
        for k, a in enumerate(tab_angles()):
            r = math.radians(a)
            fl = _fold_line(a)
            far = base_full.intersection(_tab_far(a))
            tab_poly = far.difference(_tab_far(a, DF + TAB_L))
            tab_poly = max(getattr(tab_poly, "geoms", [tab_poly]), key=lambda g: g.area)
            tab = sc.panel(f"tab{k + 1}", tab_poly, parent=base, hinge=(fl[1], fl[0]), angle=-90.0, stage=(0.6, 0.85))
            tip = far.intersection(_tab_far(a, DF + TAB_L))
            tip = max(getattr(tip, "geoms", [tip]), key=lambda g: g.area)
            e = [(DF + TAB_L) * math.cos(r) - v * math.sin(r) for v in (TAB_W / 2, -TAB_W / 2)]
            f_ = [(DF + TAB_L) * math.sin(r) + v * math.cos(r) for v in (TAB_W / 2, -TAB_W / 2)]
            sc.panel(f"tabT{k + 1}", tip, parent=tab, hinge=((e[0], f_[0]), (e[1], f_[1])), angle=-80.0,
                     stage=(0.85, 1.0))
        # alçak yarık B1 tırnak 1'e (45°) gelsin
        b1 = next(p for p in panels if any(abs(d[0][0][1] - LOW_Y) < 1e-6 and d[0][0][0] <= LOW_X[0] + 8 for d in p.decals))
        P = b1.world(1.0) @ np.array([LOW_X[0], LOW_Y, 0, 1.0])
        cur = math.degrees(math.atan2(P[1], P[0]))
        panels[0].place = rot((0, 0, 1), math.radians(45.0 - cur)) @ place
        return sc

    def steps(self):
        return [
            Step("Print the template page(s) at 100 % and check the 50 mm square. Tiled pages: join them with the "
                 "cross marks.", "print"),
            Step("Cut the paper templates out, lay them on the grain side and trace the outlines, slits, hole marks and "
                 "the ends of the fold lines.", "trace", caption="trace on the grain side", reveals_pattern=True),
            Step("Punch Ø 2 mm holes: both ends of every slit and the root of every centre line.", "punch",
                 reveals_pattern=True),
            Step("Cut each slit straight from hole to hole – never past a hole.", "slits", reveals_pattern=True),
            Step("Cut the outlines.", "outline", reveals_pattern=True),
            Step("Cut the centre line of every tongue pair, from the tip to its hole.", "cuts", reveals_pattern=True),
            Step("Finish the edges now, while the pieces are flat: burnish firm leather, edge paint on oiled leather.",
                 "edges", caption="edges: burnish or paint now, while flat", reveals_pattern=True),
            Step("Base: crease the 4 tab lines (dashed) on the flesh side.", "crease", reveals_pattern=True),
            Step("Wall: roll the strip into a tube, grain side out. Warm, slightly damp veg-tan rolls more easily.",
                 "fold", fold=0.25, az=-30, el=25),
            Step("Lay the tongue end OVER the slit end. Push one tongue of each pair into its slit, then the other – "
                 "start at the middle pair. Press each tongue through with the tip of a bone folder.",
                 "fold", fold=0.45, az=150, el=20, caption="one tongue into the slit, then the other"),
            Step("Stand the tube on the base, centred: each tab under a low slit, tabs on the OUTSIDE.",
                 "fold", fold=0.6, az=-30, el=35),
            Step("Fold each tab up the outside of the wall and press its tongue pair IN through the low slit, one tongue "
                 "at a time. Heads end up inside.", "fold", fold=0.9, az=-30, el=25),
            Step("Done. Unlock the base and the seam and it lies flat again.", "done", fold=1.0, az=-35, el=28),
        ]

    def closeups(self):
        return [
            Closeup("Seam lock · inside", "The tongue end lies over the slit end. The necks pass the slits; the heads stay "
                    "inside the cup, flat against the wall.", fold=1.0, az=80, el=20, zoom_near=("overlap", 35),
                    caption="heads inside the cup"),
            Closeup("Seam lock · outside", "From outside you see only the clean overlapping edge – no heads, no "
                    "hardware.", fold=1.0, az=-100, el=15, zoom_near=("overlap", 35), caption="clean outside"),
            Closeup("Base lock · outside", "The wall stands on the base. Each tab folds up the outside of the wall and its "
                    "tongue pair goes in through a low slit; the heads stay inside.", fold=1.0, az=-45, el=12,
                    zoom_near=("tab1", 50), caption="tab up the OUTSIDE, tongue pair IN through the low slit"),
        ]


def _tab_far(a_deg, start=DF):
    """Kat çizgisinin (veya `start` mesafesinin) dış tarafı."""
    r = math.radians(a_deg)
    pts = [(start, -40), (start + 60, -40), (start + 60, 40), (start, 40)]
    return Polygon([(u * math.cos(r) - v * math.sin(r), u * math.sin(r) + v * math.cos(r)) for u, v in pts])


PRODUCT = RoundPenCup()

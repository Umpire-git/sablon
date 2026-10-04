"""Ters kilitli (reverse tuck end) karton kutu açınımı.

Paneller tek tek kapalı çokgen olarak tanımlanır; iki panelin ortak kenarı
otomatik olarak bigi (katlama), tek kalan kenarlar kesim çizgisi olur.
Ölçüler İÇ ölçüdür; panel ölçülerine karton kalınlığı payı eklenir.
"""
from __future__ import annotations

from ..geometry import Arc, Line, polyline
from ..pattern import Kind, Pattern, Piece
from ..svgdraw import Svg
from .base import Finding, Measure, Param, Template

SHEETS = [("A4", 297, 210), ("Letter", 279.4, 215.9), ("A3", 420, 297), ("Tabloid", 431.8, 279.4), ("A2", 594, 420)]


def _key(a, b):
    r = lambda p: (round(p[0], 4), round(p[1], 4))  # noqa: E731
    a, b = r(a), r(b)
    return (a, b) if a <= b else (b, a)


def classify(panels: list[list]) -> tuple[list, list]:
    """Panel kenarlarından (kesim, katlama) listeleri üretir."""
    count: dict = {}
    for segs in panels:
        for s in segs:
            if isinstance(s, Line):
                k = _key((s.x0, s.y0), (s.x1, s.y1))
                count[k] = count.get(k, 0) + 1
    cut, fold, seen = [], [], set()
    for segs in panels:
        for s in segs:
            if isinstance(s, Line):
                k = _key((s.x0, s.y0), (s.x1, s.y1))
                if count[k] > 1:
                    if k not in seen:
                        fold.append(s)
                        seen.add(k)
                else:
                    cut.append(s)
            else:
                cut.append(s)
    return cut, fold


class TuckKutu(Template):
    key = "kutu"
    title = "Ters Kilitli Karton Kutu"
    description = (
        "Klasik ürün/hediye kutusu: üst kapak arka panelden, alt kapak ön panelden açılır (ters kilit). "
        "Yan toz kapakları ve yapıştırma payı içerir. Bristol / Amerikan bristol / Kraft karton için."
    )
    material = "Karton 300–400 g/m² (0.3–0.6 mm)"
    relations = (
        "Lp = uzunluk + karton_kalinligi ; Wp = genislik + karton_kalinligi ; Hp = yukseklik + 2*karton_kalinligi\n"
        "Panel sırası: yapıştırma | ön (Lp) | yan (Wp) | arka (Lp) | yan (Wp)\n"
        "Üst kapak arka panelin üstünde (Wp) + dil (dil_boyu); alt kapak ön panelin altında\n"
        "toz_kapak = yan panellerdeki toz kapaklarının içeri uzanma boyu"
    )
    params = [
        Param("uzunluk", "İç uzunluk (ön yüz genişliği)", 80, 20, 400),
        Param("genislik", "İç genişlik (derinlik)", 40, 10, 300),
        Param("yukseklik", "İç yükseklik", 120, 10, 500),
        Param("karton_kalinligi", "Karton kalınlığı", 0.4, 0.15, 3.0),
        Param("yapistirma", "Yapıştırma payı genişliği", 14, 5, 30),
        Param("dil_boyu", "Kapak dili boyu", 15, 5, 60),
        Param("toz_kapak", "Toz kapağı boyu", 25, 5, 150),
        Param("dil_payi", "Kapak dilinin yanlardan daralması", 1.5, 0.0, 5.0),
    ]

    def dims(self) -> dict[str, float]:
        v = self.v
        t = v["karton_kalinligi"]
        return dict(t=t, L=v["uzunluk"] + t, W=v["genislik"] + t, H=v["yukseklik"] + 2 * t,
                    gl=v["yapistirma"], tf=v["dil_boyu"], d=v["toz_kapak"], c=v["dil_payi"])

    def panels(self) -> list[list]:
        k = self.dims()
        L, W, H, gl, tf, d, c = k["L"], k["W"], k["H"], k["gl"], k["tf"], k["d"], k["c"]
        x1, x2, x3, x4 = L, L + W, 2 * L + W, 2 * L + 2 * W
        taper = min(gl * 0.27, H / 4)  # ~15°
        rel = 1.0  # toz kapağı ile kapak arasındaki boşaltma
        ch = min(6.0, d / 2)
        r = min(tf * 0.6, (L - 2 * c) / 4, 10.0)

        def dust(xa, xb, up: bool, gap_left: bool):
            y0, s = (H, 1) if up else (0, -1)
            xa2 = xa + (rel if gap_left else 0)
            xb2 = xb - (0 if gap_left else rel)
            # gövde kenarı tam (xa..xb) olmalı ki katlama olarak eşleşsin
            pts = [(xa, y0), (xa2, y0), (xa2, y0 + s * (d - ch)), (xa2 + ch, y0 + s * d),
                   (xb2 - ch, y0 + s * d), (xb2, y0 + s * (d - ch)), (xb2, y0), (xb, y0)]
            segs = polyline(pts)
            segs.append(Line(xb, y0, xa, y0))
            return segs

        def lid(xa, xb, up: bool):
            y0, s = (H, 1) if up else (0, -1)
            y1 = y0 + s * W
            return polyline([(xa, y0), (xb, y0), (xb, y1), (xa, y1)], closed=True)

        def tuck(xa, xb, up: bool):
            y0, s = (H + W, 1) if up else (-W, -1)
            a, b = xa + c, xb - c
            y1 = y0 + s * tf
            segs = [Line(xa, y0, xb, y0), Line(xb, y0, b, y0 + s * (tf - r))]
            if up:
                segs += [Arc(b - r, y1 - r, r, 0, 90), Line(b - r, y1, a + r, y1), Arc(a + r, y1 - r, r, 90, 180)]
            else:
                segs += [Arc(b - r, y1 + r, r, 270, 360), Line(b - r, y1, a + r, y1), Arc(a + r, y1 + r, r, 180, 270)]
            segs.append(Line(a, y0 + s * (tf - r), xa, y0))
            return segs

        body = [polyline([(xa, 0), (xb, 0), (xb, H), (xa, H)], closed=True)
                for xa, xb in ((0, x1), (x1, x2), (x2, x3), (x3, x4))]
        glue = polyline([(0, 0), (-gl, taper), (-gl, H - taper), (0, H)], closed=True)
        return body + [
            glue,
            lid(x2, x3, True), tuck(x2, x3, True),            # üst kapak: arka panelden
            lid(0, x1, False), tuck(0, x1, False),            # alt kapak: ön panelden
            dust(x1, x2, True, False), dust(x3, x4, True, True),
            dust(x1, x2, False, True), dust(x3, x4, False, False),
        ]

    def build(self) -> Pattern:
        k = self.dims()
        cut, fold = classify(self.panels())
        p = Piece("Kutu açınımı", 1, "Kesintisiz çizgiler kesim, kesikli çizgiler bigi (katlama).")
        p.add_all(Kind.CUT, cut)
        p.add_all(Kind.FOLD, fold)
        L, W, H = k["L"], k["W"], k["H"]
        for x, name in ((L / 2, "ÖN"), (L + W / 2, "YAN"), (1.5 * L + W, "ARKA"), (2 * L + 1.5 * W, "YAN")):
            p.label(x, H / 2, name, 5.0)
        p.label(-k["gl"] / 2, H / 2, "yapıştır", 3.0, 90)
        p.label(1.5 * L + W, H + W / 2, "üst kapak", 3.5)
        p.label(L / 2, -W / 2, "alt kapak", 3.5)
        p.add(Kind.GRAIN, Line(L / 2, H * 0.6, L / 2, H * 0.85))
        p.label(L / 2 + 4, H * 0.725, "elyaf", 2.6, 90)
        return Pattern(self.title, [p])

    def flat_size(self) -> tuple[float, float]:
        k = self.dims()
        w = k["gl"] + 2 * k["L"] + 2 * k["W"]
        h = k["H"] + 2 * max(k["W"] + k["tf"], k["d"])
        return w, h

    def measures(self) -> dict[str, Measure]:
        k = self.dims()
        w, h = self.flat_size()
        return {
            "on_panel": Measure("Ön/arka panel genişliği", k["L"]),
            "yan_panel": Measure("Yan panel genişliği", k["W"]),
            "panel_yukseklik": Measure("Panel yüksekliği", k["H"]),
            "acik_genislik": Measure("Açınım genişliği", w),
            "acik_yukseklik": Measure("Açınım yüksekliği", h),
            "dis_olcu_u": Measure("Dış ölçü uzunluk", k["L"] + k["t"]),
            "dis_olcu_g": Measure("Dış ölçü genişlik", k["W"] + k["t"]),
            "dis_olcu_y": Measure("Dış ölçü yükseklik", k["H"] + 2 * k["t"]),
        }

    def checks(self) -> list[Finding]:
        v, k = self.v, self.dims()
        out: list[Finding] = []
        t = k["t"]
        if t > 0.8:
            out.append(Finding("uyari", "kalin_karton",
                               f"{t} mm karton bu kutu tipi için kalın; bigiler çatlar. 0.8 mm üzeri için oluklu "
                               "mukavva kutu şablonu (FEFCO) gerekir.", {"karton_kalinligi": 0.5}))
        if k["gl"] < 10:
            out.append(Finding("hata", "yapistirma_dar", f"Yapıştırma payı {k['gl']} mm; tutmaz, en az 10–12 mm olmalı.",
                               {"yapistirma": 14.0}))
        if k["gl"] > k["W"] - 2:
            out.append(Finding("hata", "yapistirma_genis",
                               "Yapıştırma payı yan panelden geniş; kapak/toz kapağı ile çakışır.",
                               {"yapistirma": round(max(5.0, k["W"] - 4), 1)}))
        if k["d"] > k["L"] / 2 - t:
            out.append(Finding("hata", "toz_cakisma",
                               f"Toz kapakları ({k['d']} mm) içeride birbirine çarpar; en fazla {k['L'] / 2 - t:.1f} mm.",
                               {"toz_kapak": round(k["L"] / 2 - t - 1, 1)}))
        if k["d"] > k["H"] / 2:
            out.append(Finding("hata", "toz_derin", "Toz kapağı kutu yüksekliğinin yarısını aşıyor.",
                               {"toz_kapak": round(k["H"] / 2 - 2, 1)}))
        if k["tf"] < max(10.0, k["W"] * 0.25):
            out.append(Finding("uyari", "dil_kisa",
                               f"Kapak dili {k['tf']} mm; kapak kendiliğinden açılabilir. ≥ {max(10.0, k['W'] * 0.3):.0f} mm önerilir.",
                               {"dil_boyu": round(max(12.0, k["W"] * 0.35), 1)}))
        if k["tf"] > k["H"] / 3:
            out.append(Finding("uyari", "dil_uzun", "Kapak dili çok uzun; kutu içindeki ürüne çarpar.",
                               {"dil_boyu": round(k["H"] / 4, 1)}))
        if k["c"] < t:
            out.append(Finding("uyari", "dil_sikisik", "Kapak dili yanlardan yeterince daralmamış; takarken sürter.",
                               {"dil_payi": round(max(1.0, 2 * t), 1)}))
        if max(v["uzunluk"], v["yukseklik"]) > 250 and t < 0.5:
            out.append(Finding("uyari", "zayif", "Bu boyutta ince karton ürünü taşımaz; 0.5 mm+ veya oluklu mukavva kullanın.",
                               {"karton_kalinligi": 0.6}))
        w, h = self.flat_size()
        fits = [n for n, a, b in SHEETS if (w + 10 <= a and h + 10 <= b) or (w + 10 <= b and h + 10 <= a)]
        if fits:
            out.append(Finding("bilgi", "kagit", f"Açınım {w:.0f} × {h:.0f} mm; tek parça basılabilir: {', '.join(fits)}."))
        else:
            out.append(Finding("uyari", "kagit_buyuk",
                               f"Açınım {w:.0f} × {h:.0f} mm, A2'ye bile sığmıyor; parçalı basılır, kartona aktarılmalı."))
        return out

    def assembly(self) -> list[str]:
        return [
            "Kalıbı kartona aktarın; elyaf yönü panel yüksekliğine paralel olsun (bigiler daha temiz katlanır).",
            "Önce bigileri boş tükenmez kalem veya kemik bıçakla cetvel boyunca bastırın, sonra dış hattı kesin.",
            "Tüm bigileri bir kez ileri bir kez geri katlayarak 'kırın'.",
            "Yapıştırma payına tutkal/çift taraflı bant sürün, son yan paneli üzerine bastırın; düz zeminde kurutun.",
            "Alt toz kapaklarını içe, alt kapağı kapatıp dilini içeri sokun.",
            "Ürünü yerleştirin; üst toz kapakları ve üst kapakla kapatın.",
        ]

    def preview_svg(self) -> str:
        k = self.dims()
        L, W, H = k["L"], k["W"], k["H"]
        # basit izometrik çizim
        import math
        cs, sn = math.cos(math.radians(30)), math.sin(math.radians(30))
        def iso(x, y, z):
            return (x * cs - y * cs, -(x * sn + y * sn) - z)
        pts = [iso(x, y, z) for x in (0, L) for y in (0, W) for z in (0, H)]
        minx = min(p[0] for p in pts); miny = min(p[1] for p in pts)
        maxx = max(p[0] for p in pts); maxy = max(p[1] for p in pts)
        m = 15
        s = Svg(maxx - minx + 2 * m, maxy - miny + 2 * m + 8, 2.5)
        def P(x, y, z):
            px, py = iso(x, y, z)
            return (px - minx + m, py - miny + m)
        def face(a, fill):
            cmds = [("M", *P(*a[0]))] + [("L", *P(*q)) for q in a[1:]]
            s.path(cmds, fill=fill, stroke="#5a4630", sw=0.35)
        face([(0, 0, 0), (L, 0, 0), (L, 0, H), (0, 0, H)], "#d9b98c")
        face([(0, 0, 0), (0, W, 0), (0, W, H), (0, 0, H)], "#c8a676")
        face([(0, 0, H), (L, 0, H), (L, W, H), (0, W, H)], "#e8cfa8")
        bx, by = P(L / 2, 0, H / 2)
        s.text(bx + 4, by, f"{L - k['t']:.0f} × {W - k['t']:.0f} × {H - 2 * k['t']:.0f} mm (iç)", 3.0)
        return s.render()

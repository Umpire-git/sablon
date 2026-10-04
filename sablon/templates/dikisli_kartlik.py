"""Dikişli, iki kademeli cepli ince kartlık (saraç dikişi).

Parçalar: gövde + arka cep + ön cep. Dikiş delikleri her parçada AYNI
koordinatlarda üretilir; parçalar alttan hizalanınca delikler birebir örtüşür.
Delik aralığı, seçilen zımba (pricking iron) adımına en yakın ve dikiş hattını
tam bölen değere ayarlanır: ilk ve son delik tam uçlara düşer.
"""
from __future__ import annotations

import math

from ..geometry import Arc, Circle, Line, path_length, points_along, rounded_rect
from ..pattern import Kind, Pattern, Piece
from ..svgdraw import Svg
from .base import Finding, Measure, Param, Template

STANDARD_IRONS = [2.0, 2.7, 3.0, 3.38, 3.85, 4.0, 5.0, 6.0]


class DikisliKartlik(Template):
    key = "dikisli_kartlik"
    title = "Dikişli Deri Kartlık (2 kademeli cep)"
    description = (
        "Gövde ve iki kademeli cepten oluşan ince kartlık. U şeklinde saraç dikişi; tüm parçalarda dikiş "
        "delikleri birebir örtüşür."
    )
    material = "Bitkisel/krom tabaklı deri, 0.8–1.2 mm (3 kat toplam ≤ 3.6 mm)"
    relations = (
        "govde_genislik = kart_genislik + 2*(bosluk + kenar_payi) + deri_kalinligi\n"
        "govde_yukseklik = kart_yukseklik + kenar_payi + ust_pay\n"
        "arka_cep_yukseklik = govde_yukseklik - ust_pay - cep_dusuklugu\n"
        "on_cep_yukseklik = arka_cep_yukseklik - kademe\n"
        "dikiş hattı kenardan kenar_payi içeride, arka cep üst kenarına kadar U şeklinde"
    )
    params = [
        Param("kart_genislik", "Kart genişliği", 85.6, 40, 130),
        Param("kart_yukseklik", "Kart yüksekliği", 53.98, 30, 100),
        Param("deri_kalinligi", "Deri kalınlığı (tek kat)", 1.0, 0.5, 2.5),
        Param("bosluk", "Yan boşluk (her bir yan)", 1.5, 0.0, 6.0),
        Param("kenar_payi", "Dikişin kenara uzaklığı", 3.5, 2.0, 8.0),
        Param("dikis_araligi", "Zımba adımı (delik aralığı)", 3.85, 2.0, 7.0),
        Param("delik_cap", "Dikiş deliği çapı (çizim)", 1.0, 0.5, 2.0),
        Param("ust_pay", "Gövdenin kartın üstünde kalan payı", 2.0, 0.0, 30.0),
        Param("cep_dusuklugu", "Arka cebin gövde üstünden aşağıda kalışı", 10.0, 0.0, 40.0),
        Param("kademe", "Ön cebin arka cepten alçaklığı", 12.0, 0.0, 40.0),
        Param("kose_radyus", "Köşe yarıçapı", 6.0, 0.0, 20.0),
    ]

    def dims(self) -> dict[str, float]:
        v = self.v
        e, t = v["kenar_payi"], v["deri_kalinligi"]
        W = v["kart_genislik"] + 2 * (v["bosluk"] + e) + t
        H = v["kart_yukseklik"] + e + v["ust_pay"]
        p1 = H - v["ust_pay"] - v["cep_dusuklugu"]
        p2 = p1 - v["kademe"]
        R = min(v["kose_radyus"], W / 2, p2 / 2 if p2 > 0 else 0)
        return dict(e=e, t=t, W=W, H=H, p1=p1, p2=p2, R=R)

    def stitch_path(self) -> list:
        """Sol üstten (arka cep üst kenarı hizası) aşağı, alttan sağa, sağdan yukarı."""
        d = self.dims()
        e, W, p1, R = d["e"], d["W"], d["p1"], d["R"]
        r = max(0.0, R - e)
        y_top = p1 - e
        segs = [Line(e, y_top, e, e + r)]
        if r > 0:
            segs.append(Arc(e + r, e + r, r, 180, 270))
        segs.append(Line(e + r, e, W - e - r, e))
        if r > 0:
            segs.append(Arc(W - e - r, e + r, r, 270, 360))
        segs.append(Line(W - e, e + r, W - e, y_top))
        return segs

    def holes(self) -> tuple[list[tuple[float, float]], float]:
        return points_along(self.stitch_path(), self.v["dikis_araligi"])

    def measures(self) -> dict[str, Measure]:
        d = self.dims()
        L = path_length(self.stitch_path())
        holes, step = self.holes()
        return {
            "govde_genislik": Measure("Gövde genişliği", d["W"]),
            "govde_yukseklik": Measure("Gövde yüksekliği", d["H"]),
            "arka_cep_yukseklik": Measure("Arka cep yüksekliği", d["p1"]),
            "on_cep_yukseklik": Measure("Ön cep yüksekliği", d["p2"]),
            "ic_genislik": Measure("Dikişler arası iç genişlik", d["W"] - 2 * d["e"]),
            "dikis_boyu": Measure("Dikiş hattı uzunluğu", L),
            "delik_sayisi": Measure("Delik sayısı (gövde)", len(holes), "adet"),
            "gercek_adim": Measure("Gerçek delik aralığı", step),
            "iplik": Measure("Gereken iplik (saraç dikişi, 4×hat + 30 cm)", (4 * L + 300) / 10, "cm"),
            "kapali_kalinlik": Measure("Toplam kat kalınlığı (dikiş hattında)", 3 * d["t"]),
        }

    def build(self) -> Pattern:
        d = self.dims()
        W, H, p1, p2, R = d["W"], d["H"], d["p1"], d["p2"], d["R"]
        holes, _ = self.holes()
        hr = self.v["delik_cap"] / 2

        def piece(name: str, h: float, note: str, top_round: bool) -> Piece:
            p = Piece(name, 1, note)
            if top_round:
                p.add_all(Kind.CUT, rounded_rect(0, 0, W, h, R))
            else:  # alt köşeler yuvarlak, üst kenar düz
                r = R
                p.add(Kind.CUT, Line(r, 0, W - r, 0))
                if r:
                    p.add(Kind.CUT, Arc(W - r, r, r, 270, 360))
                p.add(Kind.CUT, Line(W, r, W, h), Line(W, h, 0, h), Line(0, h, 0, r))
                if r:
                    p.add(Kind.CUT, Arc(r, r, r, 180, 270))
            p.add_all(Kind.GUIDE, _clip(self.stitch_path(), h - d["e"]))
            for (x, y) in holes:
                if y <= h - d["e"] * 0.5:
                    p.add(Kind.STITCH, Circle(x, y, hr))
            p.add(Kind.GRAIN, Line(W / 2, h * 0.3, W / 2, h * 0.7))
            p.label(W / 2 - 3, h * 0.5, name.upper(), 4.0, 90)
            return p

        body = piece("Gövde", H, "Damar yüz dışarıda.", True)
        back = piece("Arka cep", p1, "Gövdenin damar yüzü üzerine, alttan hizalı.", False)
        front = piece("Ön cep", p2, "Arka cebin üzerine, alttan hizalı.", False)
        return Pattern(self.title, [body, back, front])

    def checks(self) -> list[Finding]:
        v, d = self.v, self.dims()
        out: list[Finding] = []
        pitch = v["dikis_araligi"]
        nearest = min(STANDARD_IRONS, key=lambda s: abs(s - pitch))
        if abs(nearest - pitch) > 0.05:
            out.append(Finding("uyari", "standart_disi_zimba",
                               f"{pitch} mm adımlı zımba yaygın değil; en yakın standart {nearest} mm.",
                               {"dikis_araligi": nearest}))
        _, step = self.holes()
        if abs(step - pitch) / pitch > 0.03:
            out.append(Finding("uyari", "adim_sapmasi",
                               f"Hattın tam bölünmesi için gerçek aralık {step:.2f} mm (zımba {pitch} mm). "
                               "Zımbayı tek dişle 'yürüterek' kullanın veya ölçüyü ayarlayın."))
        if d["e"] < 3.0:
            out.append(Finding("uyari", "kenar_yakin", f"Dikiş kenara {d['e']} mm; deri kenardan yırtılabilir.",
                               {"kenar_payi": 3.5}))
        if v["bosluk"] < 1.0:
            out.append(Finding("hata", "sikisik_kart", "Kartın iki yanında 1 mm'den az pay var; cep dolunca kart girmez.",
                               {"bosluk": 1.5}))
        if d["p2"] <= 15:
            out.append(Finding("hata", "on_cep_kisa", f"Ön cep {d['p2']:.1f} mm; kartı tutamaz.", {"kademe": 10.0}))
        if v["kademe"] < 8:
            out.append(Finding("uyari", "kademe_az",
                               f"Cepler arası kademe {v['kademe']} mm; arka cepteki karta parmak ulaşmaz.",
                               {"kademe": 12.0}))
        if d["p1"] < v["kart_yukseklik"] * 0.55:
            out.append(Finding("uyari", "kart_dusme", "Arka cep kartın yarısını bile örtmüyor; kart kolay düşer.",
                               {"cep_dusuklugu": 8.0}))
        if d["R"] and d["R"] - d["e"] < 1.5:
            out.append(Finding("uyari", "kose_dikis",
                               "Köşe yarıçapı dikiş payına çok yakın; köşede dikiş sivri döner, delikler sıkışır.",
                               {"kose_radyus": round(d["e"] + 3, 1)}))
        if 3 * d["t"] > 3.6:
            out.append(Finding("uyari", "kalin_kat",
                               f"Dikiş hattında 3 kat = {3 * d['t']:.1f} mm; zımba geçmekte zorlanır, kenar hantal olur. "
                               "Cep kenarlarını inceltin (skiving) veya 0.8–1.0 mm deri kullanın.",
                               {"deri_kalinligi": 1.0}))
        if not any(f.level == "hata" for f in out):
            m = self.measures()
            out.append(Finding("bilgi", "ozet",
                               f"{int(m['delik_sayisi'].value)} delik, ~{m['iplik'].value:.0f} cm iplik; "
                               f"ürün {d['W']:.1f} × {d['H']:.1f} mm."))
        return out

    def assembly(self) -> list[str]:
        m = self.measures()
        return [
            "Üç parçayı kesin; cep üst kenarlarını kesimden hemen sonra zımparalayıp boyayın (sonra ulaşılamaz).",
            "Ön cebi arka cebin, arka cebi gövdenin üzerine alttan ve yanlardan hizalayıp çift taraflı bantla yapıştırın.",
            f"Dikiş delikleri kalıpta işaretli: {int(m['delik_sayisi'].value)} delik, aralık {m['gercek_adim'].value:.2f} mm. "
            "Kalıbı üstte tutup zımbayı noktalara oturtarak üç katı birlikte delin.",
            f"~{m['iplik'].value:.0f} cm iplik keserek iki iğneyle saraç dikişi yapın; ilk ve son 2 deliği geri dikin.",
            "Dış kenarları birlikte zımparalayın, kenar boyası ve cila sürün.",
        ]

    def preview_svg(self) -> str:
        d = self.dims()
        v = self.v
        W, H, p1, p2, R = d["W"], d["H"], d["p1"], d["p2"], d["R"]
        m = 16.0
        s = Svg(W + 2 * m + 10, H + 2 * m + 10, 3.0)
        base = m + H + 2
        x0 = m
        s.text(x0 + W / 2, 9, "ÖNDEN", 3.5, weight="bold")
        s.rect(x0, base - H, W, H, fill="#7a4f27", stroke="#3d2814", rx=R)
        s.rect(x0 + (W - v["kart_genislik"]) / 2, base - d["e"] - v["kart_yukseklik"], v["kart_genislik"],
               v["kart_yukseklik"], fill="#e8eef5", stroke="#7f8c9d", sw=0.25, rx=3.18)
        s.path([("M", x0, base - p1), ("L", x0 + W, base - p1), ("L", x0 + W, base - R),
                ("A", R, 0, 1, x0 + W - R, base), ("L", x0 + R, base), ("A", R, 0, 1, x0, base - R)],
               fill="#94653a", stroke="#3d2814")
        s.path([("M", x0, base - p2), ("L", x0 + W, base - p2), ("L", x0 + W, base - R),
                ("A", R, 0, 1, x0 + W - R, base), ("L", x0 + R, base), ("A", R, 0, 1, x0, base - R)],
               fill="#b07a45", stroke="#3d2814")
        for (x, y) in self.holes()[0]:
            s.circle(x0 + x, base - y, 0.45, fill="#f4e7d7", stroke="none")
        s.dim_h(x0, x0 + W, base, f"{W:.1f}")
        s.dim_v(x0, base - H, base, f"{H:.1f}", off=-6)
        return s.render()


def _clip(segs: list, ymax: float) -> list:
    """Dikiş hattını parçanın yüksekliğine göre kırpar (dikey doğrular kısalır)."""
    out = []
    for s in segs:
        if s.bounds()[3] <= ymax + 1e-6:
            out.append(s)
        elif isinstance(s, Line) and s.x0 == s.x1 and min(s.y0, s.y1) < ymax:
            out.append(Line(s.x0, min(s.y0, ymax), s.x1, min(s.y1, ymax)))
    return out

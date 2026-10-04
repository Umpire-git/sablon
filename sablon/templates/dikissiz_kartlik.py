"""Dikişsiz (dil-yarık kilitli) deri kartlık.

Tek parça. Düz yerleşim (alttan üste):
    ön panel  |  alt körük  |  arka panel
Ön panelin iki yanında yan duvarlar (körük) ve onların ucunda kilit dilleri
vardır. Diller arka panelin dış yüzüne sarılır ve yarıklardan içeri itilerek
kafa kısmıyla kilitlenir. Hiç dikiş yoktur.
"""
from __future__ import annotations

from ..geometry import Arc, Circle, Line, polyline
from ..pattern import Kind, Pattern, Piece, relief_holes
from ..svgdraw import Svg
from .base import Finding, Measure, Param, Template


class DikissizKartlik(Template):
    key = "dikissiz_kartlik"
    title = "Dikişsiz Deri Kartlık"
    description = (
        "Tek parça, dikişsiz, dil-yarık kilitli kartlık. Ön panel, alt körük ve arka panelden "
        "oluşur; yan duvarların ucundaki diller arka paneldeki yarıklara geçerek kilitlenir."
    )
    material = "Bitkisel tabaklanmış sert deri (1.2–1.8 mm önerilir)"
    relations = (
        "kalinlik_payi = kart_sayisi*kart_kalinligi + 0.5\n"
        "yan_duvar (körük genişliği) = kalinlik_payi + deri_kalinligi\n"
        "panel_genislik = kart_genislik + 2*bosluk + deri_kalinligi\n"
        "arka_yukseklik = kart_yukseklik - kart_tasma\n"
        "on_yukseklik = arka_yukseklik * on_panel_orani\n"
        "kilit_kafa_yuksekligi = dil_genislik + 2*kilit_payi ; yarik_boyu = dil_genislik + deri_kalinligi\n"
        "diller ön panelin dikey ortasından çıkar; yarıklar arka panelde kenardan dil_uzunluk kadar içeridedir."
    )
    params = [
        Param("kart_genislik", "Kart genişliği", 85.6, 40, 130, help="ISO/IEC 7810 ID-1: 85.60 mm"),
        Param("kart_yukseklik", "Kart yüksekliği", 53.98, 30, 100, help="ISO/IEC 7810 ID-1: 53.98 mm"),
        Param("kart_sayisi", "Kart kapasitesi", 4, 1, 12, unit="adet", integer=True),
        Param("kart_kalinligi", "Tek kart kalınlığı", 0.76, 0.3, 2.0),
        Param("deri_kalinligi", "Deri kalınlığı", 1.4, 0.6, 3.0),
        Param("bosluk", "Yan boşluk (her bir yan)", 1.5, 0.0, 6.0, help="Kartın panel içinde yanlara doğru oynama payı"),
        Param("kart_tasma", "Kartın arka panelden taşması", 6.0, 0.0, 25.0, help="Kartı tutup çekmek için"),
        Param("on_panel_orani", "Ön panel / arka panel yükseklik oranı", 0.72, 0.4, 1.0, unit="oran"),
        Param("basparmak_cap", "Başparmak oyuğu çapı (0 = yok)", 22.0, 0.0, 40.0),
        Param("dil_genislik", "Kilit dili boyun genişliği", 14.0, 6.0, 40.0),
        Param("dil_uzunluk", "Dilin arka yüzde kalan boyu (yarığa uzaklık)", 16.0, 6.0, 40.0),
        Param("kilit_payi", "Kilit kafası taşma payı (her bir yan)", 2.5, 0.5, 8.0),
        Param("kilit_boyu", "Kilit kafası boyu", 9.0, 4.0, 20.0),
        Param("kose_radyus", "Arka panel üst köşe yarıçapı", 5.0, 0.0, 15.0),
        Param("delik_cap", "Yarık ucu yırtılma önleyici delik çapı", 1.5, 0.8, 4.0),
    ]

    # ---- türetilmiş ölçüler -------------------------------------------------
    def dims(self) -> dict[str, float]:
        v = self.v
        t = v["deri_kalinligi"]
        stack = v["kart_sayisi"] * v["kart_kalinligi"] + 0.5
        g = stack + t
        W = v["kart_genislik"] + 2 * v["bosluk"] + t
        Hb = v["kart_yukseklik"] - v["kart_tasma"]
        Hf = Hb * v["on_panel_orani"]
        hn = v["dil_genislik"]
        hh = hn + 2 * v["kilit_payi"]
        slit = hn + t
        return dict(t=t, stack=stack, g=g, W=W, Hb=Hb, Hf=Hf, hn=hn, hh=hh, slit=slit,
                    Ln=v["dil_uzunluk"], Lh=v["kilit_boyu"], rn=v["basparmak_cap"] / 2,
                    r=v["kose_radyus"], yc=Hf / 2)

    def measures(self) -> dict[str, Measure]:
        d = self.dims()
        total_w = d["W"] + 2 * (d["g"] + d["Ln"] + d["Lh"])
        total_h = d["Hf"] + d["g"] + d["Hb"]
        return {
            "panel_genislik": Measure("Panel genişliği (ön/arka)", d["W"]),
            "ic_genislik": Measure("Kart cebi iç genişliği", d["W"] - d["t"]),
            "arka_yukseklik": Measure("Arka panel yüksekliği", d["Hb"]),
            "on_yukseklik": Measure("Ön panel yüksekliği", d["Hf"]),
            "yan_duvar": Measure("Yan duvar / alt körük genişliği", d["g"]),
            "dil_toplam": Measure("Kilit dili toplam boyu (körük hariç)", d["Ln"] + d["Lh"]),
            "kilit_kafa": Measure("Kilit kafası yüksekliği", d["hh"]),
            "yarik_boyu": Measure("Yarık boyu", d["slit"]),
            "kilit_sikilik": Measure("Kafa ile yarık farkı (kilit sıkılığı)", d["hh"] - d["slit"]),
            "acik_genislik": Measure("Açık kalıp genişliği", total_w),
            "acik_yukseklik": Measure("Açık kalıp yüksekliği", total_h),
            "kapali_genislik": Measure("Kapalı ürün genişliği", d["W"] + 2 * d["t"]),
            "kapali_yukseklik": Measure("Kapalı ürün yüksekliği (arka panel)", d["Hb"]),
            "kapali_kalinlik": Measure("Kapalı ürün kalınlığı (dolu)", d["g"] + d["t"]),
            "deri_alani": Measure("Gereken deri (fire %15 dahil)", total_w * total_h * 1.15 / 100, "cm²"),
        }

    # ---- geometri ---------------------------------------------------------
    def build(self) -> Pattern:
        d = self.dims()
        t, g, W, Hb, Hf = d["t"], d["g"], d["W"], d["Hb"], d["Hf"]
        hn, hh, Ln, Lh, yc, rn, r = d["hn"], d["hh"], d["Ln"], d["Lh"], d["yc"], d["rn"], d["r"]
        rt = min(3.0, hh / 4, Lh / 2)  # kafa ucu yuvarlatma (kolay takma)
        yb = Hf + g  # arka panel alt kenarı
        top = yb + Hb

        p = Piece("Gövde", 1, "Tek parça. Çizimde görünen yüz derinin iç (süet) yüzüdür.")
        cut = p.items

        def tab(sign: int) -> list:
            """sign=+1 sağ dil, -1 sol dil (dış kenar x0'dan dışarı)."""
            x0 = W + g if sign > 0 else -g
            xs = lambda dx: x0 + sign * dx  # noqa: E731
            segs = []
            yA, yB = yc - hn / 2, yc + hn / 2
            hA, hB = yc - hh / 2, yc + hh / 2
            tip = xs(Ln + Lh)
            segs += polyline([(x0, yA), (xs(Ln), yA), (xs(Ln), hA), (tip - sign * rt, hA)])
            if sign > 0:
                segs.append(Arc(tip - rt, hA + rt, rt, 270, 360))
                segs.append(Line(tip, hA + rt, tip, hB - rt))
                segs.append(Arc(tip - rt, hB - rt, rt, 0, 90))
            else:
                segs.append(Arc(tip + rt, hA + rt, rt, 180, 270))
                segs.append(Line(tip, hA + rt, tip, hB - rt))
                segs.append(Arc(tip + rt, hB - rt, rt, 90, 180))
            segs += polyline([(tip - sign * rt, hB), (xs(Ln), hB), (xs(Ln), yB), (x0, yB)])
            return segs

        # Ön üst kenar (serbest kenar) + başparmak oyuğu
        if rn > 0:
            cut += [(Kind.CUT, s) for s in polyline([(-g, 0), (W / 2 - rn, 0)])]
            cut.append((Kind.CUT, Arc(W / 2, 0, rn, 0, 180)))
            cut += [(Kind.CUT, s) for s in polyline([(W / 2 + rn, 0), (W + g, 0)])]
        else:
            cut += [(Kind.CUT, s) for s in polyline([(-g, 0), (W + g, 0)])]
        # Sağ yan duvar + dil
        p.add_all(Kind.CUT, polyline([(W + g, 0), (W + g, yc - hn / 2)]))
        p.add_all(Kind.CUT, tab(+1))
        p.add_all(Kind.CUT, polyline([(W + g, yc + hn / 2), (W + g, Hf), (W, Hf), (W, top - r)]))
        # Arka panel üst kenar
        if r > 0:
            p.add(Kind.CUT, Arc(W - r, top - r, r, 0, 90), Line(W - r, top, r, top), Arc(r, top - r, r, 90, 180))
        else:
            p.add(Kind.CUT, Line(W, top, 0, top))
        p.add_all(Kind.CUT, polyline([(0, top - r), (0, Hf), (-g, Hf), (-g, yc + hn / 2)]))
        p.add_all(Kind.CUT, tab(-1))
        p.add_all(Kind.CUT, polyline([(-g, yc - hn / 2), (-g, 0)]))

        # Katlama çizgileri
        p.add(Kind.FOLD, Line(0, 0, 0, Hf), Line(W, 0, W, Hf))
        p.add(Kind.FOLD, Line(-g, yc - hn / 2, -g, yc + hn / 2), Line(W + g, yc - hn / 2, W + g, yc + hn / 2))
        p.add(Kind.FOLD, Line(0, Hf, W, Hf), Line(0, yb, W, yb))

        # Arka paneldeki yarıklar: katlanınca dil merkezine denk gelir
        ys = yb + (Hf - yc)
        for xslit in (Ln, W - Ln):
            y0, y1 = ys - d["slit"] / 2, ys + d["slit"] / 2
            p.add(Kind.SLIT, Line(xslit, y0, xslit, y1))
            p.add(Kind.HOLE, *relief_holes(xslit, y0, xslit, y1, self.v["delik_cap"]))

        # Elyaf yönü: omurga, katlama çizgilerine paralel/dikey seçimi
        gx = W / 2
        p.add(Kind.GRAIN, Line(gx, yb + Hb * 0.35, gx, yb + Hb * 0.8))
        p.label(gx + 4, yb + Hb * 0.575, "omurga yönü", 2.6, 90)
        # Etiketler
        p.label(W / 2, Hf * 0.55, "ÖN PANEL", 4.5)
        p.label(W / 2, Hf + g / 2 - 1.2, "alt körük", 2.6)
        p.label(W / 2, yb + Hb * 0.25, "ARKA PANEL", 4.5)
        p.label(W / 2, yb + Hb * 0.25 - 6, "(iç yüz)", 2.8)
        return Pattern(self.title, [p])

    # ---- kontroller -------------------------------------------------------
    def checks(self) -> list[Finding]:
        v, d = self.v, self.dims()
        out: list[Finding] = []
        t = d["t"]
        b = v["bosluk"]
        if b < 0.75:
            out.append(Finding("hata", "sikisik_kart",
                               f"Yan boşluk {b} mm: kartlar dolu ceple sıkışır, deri esnemeden giremez.",
                               {"bosluk": 1.5}))
        elif b > 3.0:
            out.append(Finding("uyari", "gevsek_kart",
                               f"Yan boşluk {b} mm: tek kart kaldığında cebin içinde kayar ve düşebilir.",
                               {"bosluk": 1.5}))
        if t < 1.0:
            out.append(Finding("uyari", "ince_deri",
                               f"{t} mm deri dikişsiz kilit için ince; diller yarıktan çıkabilir veya yırtılabilir. "
                               "1.2–1.6 mm bitkisel tabaklı deri önerilir.", {"deri_kalinligi": 1.4}))
        elif t > 2.2:
            out.append(Finding("uyari", "kalin_deri",
                               f"{t} mm deri kat yerlerinde çatlayabilir ve ürün hantal olur. Kat yerlerini iç "
                               "yüzden kanal açarak inceltin veya 1.6 mm'ye inin.", {"deri_kalinligi": 1.6}))
        if t >= 1.6:
            out.append(Finding("bilgi", "kanal",
                               "Kat yerlerini iç yüzden V-kanal ile ~%40 inceltmek ve hafif nemlendirerek katlamak "
                               "çatlamayı önler."))
        lock = d["hh"] - d["slit"]
        if lock < 1.5:
            out.append(Finding("hata", "kilit_tutmaz",
                               f"Kilit kafası yarıktan yalnızca {lock:.1f} mm büyük; kullanımda kendiliğinden çıkar.",
                               {"kilit_payi": round((d["slit"] - d["hn"] + 3.0) / 2, 1)}))
        elif lock > 6.0:
            out.append(Finding("uyari", "kilit_zor",
                               f"Kilit kafası yarıktan {lock:.1f} mm büyük; takmak çok zor olur, yarık uçlarını yırtabilir.",
                               {"kilit_payi": round((d["slit"] - d["hn"] + 4.0) / 2, 1)}))
        min_neck = max(8.0, 5 * t)
        if d["hn"] < min_neck:
            out.append(Finding("hata", "dar_dil",
                               f"Dil boynu {d['hn']} mm; bu kalınlıkta en az {min_neck:.0f} mm olmalı, yoksa boyundan kopar.",
                               {"dil_genislik": round(min_neck, 1)}))
        if d["hh"] > d["Hf"] - 4:
            out.append(Finding("hata", "kafa_buyuk",
                               f"Kilit kafası ({d['hh']:.1f} mm) yan duvardan ({d['Hf']:.1f} mm) taşıyor.",
                               {"dil_genislik": round(max(6.0, d["Hf"] - 4 - 2 * v["kilit_payi"]), 1)}))
        free = d["W"] / 2 - (d["Ln"] + d["Lh"])
        if free < 3:
            out.append(Finding("hata", "kafa_cakisma",
                               f"Sağ ve sol kilit kafaları arka panelin içinde çakışıyor ({free:.1f} mm pay).",
                               {"dil_uzunluk": round(max(6.0, d["W"] / 2 - d["Lh"] - 6), 1)}))
        if d["Ln"] < max(8.0, 5 * t):
            out.append(Finding("uyari", "yarik_kenara_yakin",
                               f"Yarık arka panel kenarına {d['Ln']} mm uzakta; kenar ile yarık arası köprü yırtılabilir.",
                               {"dil_uzunluk": round(max(8.0, 5 * t), 1)}))
        if v["delik_cap"] < 1.2:
            out.append(Finding("uyari", "kucuk_delik",
                               "Yarık ucu deliği 1.2 mm'den küçük; yırtılmayı durdurmakta yetersiz kalabilir.",
                               {"delik_cap": 1.5}))
        if d["Hb"] < v["kart_yukseklik"] * 0.7:
            out.append(Finding("uyari", "kart_dusme",
                               f"Kart, arka panelden {v['kart_tasma']} mm taşıyor; kartların %30'dan fazlası dışarıda kalır, "
                               "cep kartı güvenle tutmaz.", {"kart_tasma": 6.0}))
        notch = v["basparmak_cap"]
        if notch == 0 and v["kart_tasma"] < 4 and v["on_panel_orani"] > 0.6:
            out.append(Finding("uyari", "kart_cikmiyor",
                               "Başparmak oyuğu yok ve kart neredeyse hiç taşmıyor: öndeki kartı çıkarmak zor olur.",
                               {"basparmak_cap": 22.0}))
        elif 0 < notch < 16:
            out.append(Finding("uyari", "dar_oyuk",
                               f"Başparmak oyuğu {notch} mm; yetişkin başparmağı için en az 18–20 mm önerilir.",
                               {"basparmak_cap": 22.0}))
        if notch / 2 > d["Hf"] * 0.6:
            out.append(Finding("uyari", "derin_oyuk",
                               "Başparmak oyuğu ön panelin yarısından derin; ön panel zayıflar ve kartlar görünür kalır.",
                               {"basparmak_cap": round(d["Hf"] * 0.8, 1)}))
        if v["kart_sayisi"] > 8:
            out.append(Finding("uyari", "fazla_kart",
                               f"{int(v['kart_sayisi'])} kart için körük {d['g']:.1f} mm; dikişsiz kilit bu kalınlıkta "
                               "zorlanır, yan duvarlar dışa bombe yapar."))
        if not any(f.level == "hata" for f in out):
            out.append(Finding("bilgi", "kapasite",
                               f"Kapalı ölçü ≈ {d['W'] + 2 * t:.1f} × {d['Hb']:.1f} × {d['g'] + t:.1f} mm, "
                               f"{int(v['kart_sayisi'])} kart kapasiteli."))
        return out

    def assembly(self) -> list[str]:
        d = self.dims()
        steps = [
            "Kalıbı deri arka (süet) yüzüne yerleştirin; omurga okunu derinin sırt çizgisine paralel tutun.",
            f"Önce yarık uçlarındaki Ø{self.v['delik_cap']} mm delikleri zımbalayın, sonra yarıkları delikten deliğe kesin.",
            "Dış kesimi keskin bıçakla tek seferde yapın; köşe ve kavislerde bıçağı kaldırmayın.",
            "Kenarları zımparalayıp kenar boyası/cilası uygulayın — katlamadan ÖNCE yapmak çok daha kolaydır.",
            "Kesikli çizgileri cetvel ve kemik bıçakla bastırarak çizin; deri hafif nemliyken katlamak çatlamayı önler.",
            "Alt körüğü iki kat çizgisinden VADİ katla (süet yüz içe) katlayarak ön paneli arka panelin önüne kaldırın.",
            "Yan duvarları da vadi katla içeri katlayın; dil boyun çizgileri ise DAĞ katlanır, diller arka panelin "
            "dış yüzüne sarılır.",
            f"Kilit kafasını hafifçe bükerek yarıktan içeri itin; kafa, yarıktan {d['hh'] - d['slit']:.1f} mm büyük olduğu için kilitlenir.",
            f"Ürün içine {int(self.v['kart_sayisi'])} kart (veya aynı kalınlıkta karton) koyup kuruyana kadar şekil verin.",
        ]
        if d["t"] >= 1.6:
            steps.insert(4, "Kat yerlerini iç yüzden V-kanal ile inceltin (kalınlığın ~%40'ı).")
        return steps

    # ---- montajlı görünüm --------------------------------------------------
    def preview_svg(self) -> str:
        d = self.dims()
        v = self.v
        W, Hb, Hf, g, t = d["W"], d["Hb"], d["Hf"], d["g"], d["t"]
        ch, cw = v["kart_yukseklik"], v["kart_genislik"]
        m = 18.0
        gapx = 30.0
        total_w = m + W + gapx + W + gapx + g + 2 * t + m
        total_h = m + ch + 30 + m
        s = Svg(total_w, total_h, 3.0)
        base = m + ch + 6  # alt çizgi (zemin)
        leather, dark, card = "#b07a45", "#7a4f27", "#e8eef5"

        # --- Önden görünüm
        x0 = m
        s.text(x0 + W / 2, 9, "ÖNDEN", 3.5, weight="bold")
        s.path([("M", x0, base), ("L", x0, base - Hb + d["r"]), ("A", d["r"], 0, 1, x0 + d["r"], base - Hb),
                ("L", x0 + W - d["r"], base - Hb), ("A", d["r"], 0, 1, x0 + W, base - Hb + d["r"]), ("L", x0 + W, base)],
               fill=dark, stroke="#3d2814")
        cx = x0 + (W - cw) / 2
        n = int(v["kart_sayisi"])
        for i in range(min(n, 4)):
            s.rect(cx + i * 0.8, base - t - ch - i * 1.2, cw, ch, fill=card, stroke="#7f8c9d", sw=0.25, rx=3.18)
        rn = d["rn"]
        top = base - Hf
        if rn > 0:
            s.path([("M", x0, base), ("L", x0, top), ("L", x0 + W / 2 - rn, top),
                    ("A", rn, 0, 0, x0 + W / 2 + rn, top), ("L", x0 + W, top), ("L", x0 + W, base)],
                   fill=leather, stroke="#3d2814")
        else:
            s.rect(x0, top, W, Hf, fill=leather, stroke="#3d2814")
        s.dim_h(x0, x0 + W, base, f"{W + 2 * t:.1f}")
        s.dim_v(x0, base - Hb, base, f"{Hb:.1f}", off=-6)
        s.dim_v(x0 + W, top, base, f"{Hf:.1f}", off=5)

        # --- Arkadan görünüm (diller ve kilitler)
        x1 = x0 + W + gapx
        s.text(x1 + W / 2, 9, "ARKADAN", 3.5, weight="bold")
        s.path([("M", x1, base), ("L", x1, base - Hb + d["r"]), ("A", d["r"], 0, 1, x1 + d["r"], base - Hb),
                ("L", x1 + W - d["r"], base - Hb), ("A", d["r"], 0, 1, x1 + W, base - Hb + d["r"]), ("L", x1 + W, base)],
               fill=dark, stroke="#3d2814")
        ytab = base - (Hf - d["yc"])
        for side in (0, 1):
            xa = x1 if side == 0 else x1 + W - d["Ln"]
            s.rect(xa, ytab - d["hn"] / 2, d["Ln"], d["hn"], fill=leather, stroke="#3d2814")
            xs = x1 + d["Ln"] if side == 0 else x1 + W - d["Ln"]
            s.line(xs, ytab - d["slit"] / 2, xs, ytab + d["slit"] / 2, stroke="#111", sw=0.6)
        s.text(x1 + W / 2, ytab + 1, "kilit dilleri", 2.8, fill="#f4e7d7")

        # --- Yandan kesit (kalınlık)
        x2 = x1 + W + gapx
        s.text(x2 + (g + 2 * t) / 2, 9, "YAN", 3.5, weight="bold")
        s.rect(x2, base - Hb, t, Hb, fill=dark, stroke="#3d2814", sw=0.2)
        s.rect(x2 + t, base - t - ch, g - t, ch, fill=card, stroke="#7f8c9d", sw=0.2)
        s.rect(x2 + g, base - Hf, t, Hf, fill=leather, stroke="#3d2814", sw=0.2)
        s.rect(x2, base - t, g + t, t, fill=leather, stroke="#3d2814", sw=0.2)
        s.dim_h(x2, x2 + g + t, base, f"{g + t:.1f}")
        s.text(total_w / 2, total_h - 4, f"{n} kart · kırmızı ölçüler mm · temsili görünüm", 3.0, fill="#555")
        return s.render()

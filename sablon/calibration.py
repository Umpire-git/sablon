"""Malzeme kalibrasyonu: kalıplar SENİN derine göre hesaplansın.

Deri tabakhaneye, partiye ve kalınlığa göre farklı katlanır. Kalibrasyon deneme parçası
(`sablon kalibrasyon`) kesilip katlanır, iki ölçüm girilir (`sablon kalibre`):

* Katlama testi: L uzunluğundaki şerit ortadan 180° katlanıp bastırılır; kat dış kenarından
  uçlara kadar olan boy F ölçülür. Motorun kıvrım modeli (iç yarıçap r, kat payı π(r + t/2))
  ile:  L = 2F − 2t − π t/2 + r(π − 2)  →  r = (L − 2F + 2t − π t/2) / (π − 2).
* Kilit testi: kafası yarıktan 2, 3, 4 mm geniş üç dilden hem takılabilen hem tutan en dar
  olanı kilit payıdır.

Değerler `kalibrasyon.json` dosyasına yazılır (çalışma klasörü, yoksa ~/.sablon/).
"""
from __future__ import annotations

import json
import math
import os

DEFAULTS = {
    "vaketa": {"kivrim_orani": 0.8, "kilit_payi": 2.0},
    "crazy_horse": {"kivrim_orani": 0.7, "kilit_payi": 3.0},
}
STRIP_L = 120.0


def _paths() -> list[str]:
    env = os.environ.get("SABLON_KALIBRASYON")
    if env:
        return [env]
    return [os.path.join(os.getcwd(), "kalibrasyon.json"), os.path.join(os.path.expanduser("~"), ".sablon", "kalibrasyon.json")]


def path_for_write() -> str:
    env = os.environ.get("SABLON_KALIBRASYON")
    if env:
        return env
    local = os.path.join(os.getcwd(), "kalibrasyon.json")
    if os.path.exists(local):
        return local
    return os.path.join(os.path.expanduser("~"), ".sablon", "kalibrasyon.json")


def load() -> dict:
    data = {k: dict(v) for k, v in DEFAULTS.items()}
    for p in _paths():
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    user = json.load(f)
                for mat, vals in user.items():
                    data.setdefault(mat, {}).update(vals)
                data["_kaynak"] = p
            except (OSError, ValueError):
                pass
            break
    return data


def bend_k(material: str) -> float:
    return float(load().get(material, {}).get("kivrim_orani", 0.8))


def lock_margin(material: str) -> float:
    return float(load().get(material, {}).get("kilit_payi", 2.0))


def bend_from_measure(F: float, t: float, L: float = STRIP_L) -> float:
    """Katlama testinden kıvrım iç yarıçapı / kalınlık oranı."""
    r = (L - 2 * F + 2 * t - math.pi * t / 2) / (math.pi - 2)
    return max(0.1, min(3.0, r / t))


def save(material: str, **values) -> str:
    path = path_for_write()
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault(material, {}).update(values)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def test_pieces(t: float):
    """Kalibrasyon kalıbı: katlama şeridi + kilit kuponu + üç farklı kafalı dil."""
    from .geometry import Circle, Line, rounded_rect, polyline
    from .pattern import Kind, Piece, Text

    pieces = []
    strip = Piece("Katlama şeridi", 1, f"{STRIP_L:g} × 25 mm; ortadan 180° katlayın")
    strip.add_all(Kind.CUT, polyline([(0, 0), (STRIP_L, 0), (STRIP_L, 25), (0, 25)], closed=True))
    strip.add(Kind.FOLD, Line(STRIP_L / 2, 0, STRIP_L / 2, 25))
    strip.texts.append(Text(STRIP_L / 2, 12, "kat (vadi 180°)", 2.6, 90))
    strip.texts.append(Text(STRIP_L / 4, 10, "A", 5))
    strip.texts.append(Text(3 * STRIP_L / 4, 10, "B", 5))
    pieces.append(strip)

    neck = 12.0
    slit = neck + t
    base = Piece("Kilit kuponu", 1, f"üç yarık: {slit:.1f} mm (boyun {neck:g} + t)")
    base.add_all(Kind.CUT, rounded_rect(0, 0, 90, 40, 3))
    for i, x in enumerate((15, 45, 75)):
        y0, y1 = 20 - slit / 2, 20 + slit / 2
        base.add(Kind.SLIT, Line(x, y0, x, y1))
        base.add(Kind.HOLE, Circle(x, y0, 0.75), Circle(x, y1, 0.75))
        base.texts.append(Text(x, 5, f"+{i + 2} mm", 3))
    pieces.append(base)
    for extra in (2, 3, 4):
        head = slit + extra
        tab = Piece(f"Dil +{extra} mm", 1, f"kafa {head:.1f} mm")
        # boyun (30 × 12 mm) + kafa (8 mm × head)
        nb = (head - neck) / 2
        pts = [(0, nb), (30, nb), (30, 0), (38, 0), (38, head), (30, head), (30, nb + neck), (0, nb + neck)]
        tab.add_all(Kind.CUT, polyline(pts, closed=True))
        tab.texts.append(Text(14, nb + neck / 2 - 1, f"+{extra}", 3.2))
        pieces.append(tab)
    return pieces


def write_pdf(path: str, material: str, t: float) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen.canvas import Canvas

    from .export.fonts import pdf_fonts
    from .export.pdf import MM, _Writer, _test_square, draw_pieces
    from .pattern import Pattern

    font, bold = pdf_fonts()
    c = Canvas(path, pagesize=(210 * MM, 297 * MM))
    c.setTitle("Kalibrasyon")
    w = _Writer(c, 210, 297)
    w.heading(f"Deri kalibrasyonu — {material}, {t:g} mm", 6)
    w.para("Bu sayfayı %100 ölçekle basın, kareyi ölçün. Parçaları KENDİ derinizden (satacağınız kalıplarda "
           "kullanacağınız deri ve kalınlıkta) kesin. İki ölçüm, bütün kalıplarınızın kat payını ve kilit sıkılığını "
           "bu deriye göre ayarlar.", 3.4)
    w.need(56)
    _test_square(c, 15, w.y - 52, 50, inch=False)
    w.y -= 58
    w.heading("1. Katlama testi", 4.6)
    w.para(f"Şeridi kesin, kat çizgisini süet yüzden kemik bıçakla çizin ve normal ürünlerinizdeki gibi katlayın "
           f"({'hafif nemlendirip' if material == 'vaketa' else 'ılıtıp'}) 180° kapatıp bastırın, kurumasını bekleyin. "
           "Kat dış kenarından A ve B uçlarına kadar olan boyları KUMPASLA ölçün, ortalamasını F olarak yazın "
           "(0.5 mm hata, kıvrım hesabını belirgin değiştirir; şüphedeyseniz iki şerit katlayıp ortalayın).", 3.3)
    w.heading("2. Kilit testi", 4.6)
    w.para("Üç dili kupondaki aynı etiketli yarıklara itin. Hem takılabilen hem de çekince çıkmayan EN DAR dilin "
           "numarası (2, 3 veya 4) kilit payıdır.", 3.3)
    w.heading("3. Sonuçları girin", 4.6)
    w.para(f"sablon kalibre {material} --kalinlik {t:g} --katlama F --kilit N", 3.6, color="#5a3a1e")
    w.para("Örnek: sablon kalibre vaketa --kalinlik 1.6 --katlama 59.1 --kilit 3", 3.2, color="#666666")
    c.showPage()
    placed = Pattern("kalibrasyon", test_pieces(t), gap=28).layout(max_width=180)
    x0, y0, x1, y1 = Pattern.extent(placed)
    c.saveState()
    c.translate((15 - x0) * MM, (297 - 30 - y1) * MM)
    draw_pieces(c, placed)
    c.restoreState()
    c.setFont(bold, 4 * MM)
    c.setFillColor(HexColor("#000000"))
    c.drawString(15 * MM, (297 - 15) * MM, "Kalibrasyon parçaları (1:1)")
    c.showPage()
    c.save()

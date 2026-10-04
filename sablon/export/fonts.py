"""Türkçe karakterleri (ç ğ ı İ ö ş ü) destekleyen TTF yazı tipi bulucu."""
from __future__ import annotations

import os

CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]

_registered: tuple[str, str] | None = None


def pdf_fonts() -> tuple[str, str]:
    """reportlab'a kayıtlı (normal, kalın) yazı tipi adlarını döndürür."""
    global _registered
    if _registered:
        return _registered
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    env = os.environ.get("SABLON_FONT")
    cands = [(env, os.environ.get("SABLON_FONT_BOLD", env))] if env else []
    for reg, bold in cands + CANDIDATES:
        if reg and os.path.exists(reg):
            pdfmetrics.registerFont(TTFont("SablonSans", reg))
            pdfmetrics.registerFont(TTFont("SablonSans-Bold", bold if bold and os.path.exists(bold) else reg))
            _registered = ("SablonSans", "SablonSans-Bold")
            return _registered
    # Son çare: reportlab ile gelen Vera (bazı Türkçe harfler eksik olabilir)
    import reportlab
    vera = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    pdfmetrics.registerFont(TTFont("SablonSans", os.path.join(vera, "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("SablonSans-Bold", os.path.join(vera, "VeraBd.ttf")))
    _registered = ("SablonSans", "SablonSans-Bold")
    return _registered

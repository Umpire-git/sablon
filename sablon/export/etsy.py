"""Etsy ilan metni (İngilizce başlık/açıklama/etiketler + Türkçe özet), yapay zekâ gerekmeden tasarımdan üretilir."""
from __future__ import annotations

from ..checks import pull_strip_data
from .document import Document

MAT_EN = {"vaketa": "vegetable-tanned (vachetta) leather", "crazy_horse": "crazy horse pull-up leather"}
KAT_EN = {"kartlik": "Card Holder", "cuzdan": "Wallet", "anahtarlik": "Key Holder"}


def listing(doc: Document, files: list[str]) -> str:
    d, b, ins = doc.design, doc.built, doc.instructions
    w, h, dz = doc.size
    kind = KAT_EN.get(d.kategori, "Leather Goods")
    feats = []
    if pull_strip_data(b):
        feats.append("pull-tab card ejector")
    if b.snaps:
        feats.append("snap closure")
    if b.locks and any(not lk.get("gecis") for lk in b.locks):
        feats.append("tab-and-slot lock")
    kinds = {f["tip"] for f in b.fasteners}
    if kinds:
        feats.append(" & ".join({"percin": "rivet", "vida": "chicago screw"}[k] for k in sorted(kinds)) + " reinforced")
    cards = sum(c.spec.adet for c in b.contents if c.spec.tip == "kart")
    title = (f"Stitchless {kind} PDF Pattern" + (f" with {feats[0].title()}" if feats else "")
             + " | No Sewing Leather Template" + (f" | {cards} Cards" if cards else ""))[:140]
    fmt = {"A4.pdf": "A4 PDF (1:1, tiled)", "Letter.pdf": "US Letter PDF (1:1, tiled)",
           "tam_boy.pdf": "Full-size single-sheet PDF (print shop / plotter)", ".svg": "SVG (laser / Cricut)",
           ".dxf": "DXF (laser / CNC)"}
    inc = [v for k, v in fmt.items() if any(f.endswith(k) for f in files)]
    tags = ["leather pattern", "stitchless wallet", "no sew leather", "card holder pattern", "leather template",
            "pdf pattern", "leathercraft", "minimalist wallet", "svg leather", "dxf laser pattern",
            "crazy horse leather" if d.malzeme == "crazy_horse" else "veg tan pattern", "diy wallet",
            "pull tab wallet" if pull_strip_data(b) else "snap card holder"]
    out = [
        "=== BAŞLIK (Title) ===", title, "",
        "=== AÇIKLAMA (Description) ===",
        f"A fully STITCHLESS {kind.lower()} pattern (model “{d.ad}”). No sewing and no glue: it is held together "
        "by folds" + (" and a tab-and-slot lock" if "tab-and-slot lock" in feats else "") + "."
        + (" Features: " + ", ".join(x for x in feats if x != "tab-and-slot lock") + "." if
           [x for x in feats if x != "tab-and-slot lock"] else ""),
        "",
        f"• Finished size: approx. {w:.0f} × {h:.0f} × {dz:.0f} mm ({w / 25.4:.2f} × {h / 25.4:.2f} × {dz / 25.4:.2f} in)",
        f"• Leather: {MAT_EN.get(d.malzeme, d.malzeme)}, {b.env['t']:g} mm" + (f", holds {cards} cards" if cards else ""),
        f"• Skill level: {'★' * ins.difficulty}{'☆' * (5 - ins.difficulty)}  •  Build time: ~{ins.hours:g} h",
        "• Pattern checked by a fold/collision simulation: every fold, slot and rivet hole lines up.",
        "",
        "WHAT YOU GET (instant download):",
        *[f"• {x}" for x in inc],
        "• Illustrated step-by-step instructions (in the PDF), bill of materials and tool list",
        "• Test square on every page to verify 100% print scale",
        "",
        "Print at 100% / 'actual size' (no fit-to-page). Digital file only — no physical item will be shipped.",
        "For personal use and small-batch handmade sales; reselling the pattern files is not permitted.",
        "",
        "=== ETİKETLER (Tags, max 13 × 20 karakter) ===",
        ", ".join(t[:20] for t in tags[:13]),
        "",
        "=== MALZEME (Materials) ===",
        ", ".join(["leather", MAT_EN.get(d.malzeme, d.malzeme)] + (["rivets"] if "percin" in kinds else [])
                  + (["chicago screws"] if "vida" in kinds else []) + (["snaps"] if b.snaps else [])
                  + ["edge finishing (tokonole)"]),
        "",
        "=== TÜRKÇE ÖZET ===",
        f"{d.ad}: {d.konsept}",
        f"Bitmiş ölçü ≈ {w:.0f} × {h:.0f} × {dz:.0f} mm, zorluk {ins.difficulty}/5, ~{ins.hours:g} saat.",
        "İlan fotoğrafları: *_urun.png, *_arka.png, *_acinim.png" + (", *_cekilmis.png" if pull_strip_data(b) else "")
        + " (fotoğraf gerçekliği için: sablon cikti ... --foto veya --gemini).",
    ]
    return "\n".join(out) + "\n"

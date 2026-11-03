"""Etsy SEO: başlık, 13 etiket, açıklama, nitelikler, fiyat gerekçesi, fotoğraf sırası + alt metin.

Kurallar (Etsy + Dagli):
- Başlık ≤ 140 karakter; Etsy kısa ve net başlığı tercih eder → ana ifade başta, ~70–110 karakter hedef.
- Tam olarak 13 etiket, her biri ≤ 20 karakter, tekrar yok; çok kelimeli ifadeler (long-tail).
- Etiketler başlıktaki kelimeleri birebir tekrarlamak zorunda değil; farklı arama ifadelerini kapsar.
- Açıklama ilk satırı: DIGITAL PATTERN uyarısı.
- Yapay zekâ yardımlı görsel varsa "Content: With an AI generator" + açıklamada beyan.
"""
from __future__ import annotations

import re

from .product import Product

TAG_MAX, TITLE_MAX = 20, 140


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", s.lower()))


def build_tags(prod: Product, market: dict | None) -> tuple[list[str], list[str]]:
    """13 etiket + neden seçildikleri (Türkçe not)."""
    seo = prod.seo
    notes = []
    cand: list[tuple[float, str, str]] = []
    vocab = _tokens(" ".join([seo.primary, *seo.keywords, prod.meta.name, *seo.use_cases]))
    mk = {t: c for t, c in (market or {}).get("tags", [])}
    for i, k in enumerate([seo.primary, *seo.keywords]):
        cand.append((100 - i + mk.get(_norm(k), 0) * 3, _norm(k), "ürün ifadesi" + (f", rakiplerde {mk[_norm(k)]}×" if _norm(k) in mk else "")))
    for t, c in mk.items():
        if len(_tokens(t) & vocab) >= 1 and not re.search(r"sew|stitch|snap|rivet", t) or re.search(r"no sew|stitchless", t):
            cand.append((40 + c * 3, _norm(t), f"rakip etiketi ({c} ilanda)"))
    for h in seo.holidays:
        cand.append((20, _norm(f"{h} gift diy")[:TAG_MAX].strip(), "sezon"))
    seen, tags = set(), []
    for score, t, why in sorted(cand, key=lambda x: -x[0]):
        if len(t) > TAG_MAX:
            t2 = t[:TAG_MAX].rsplit(" ", 1)[0]
            if len(t2) < 6:
                continue
            t = t2
        key = " ".join(sorted(t.split()))
        if not t or key in seen:
            continue
        seen.add(key)
        tags.append(t)
        notes.append(f"{t} — {why}")
        if len(tags) == 13:
            break
    return tags, notes


def _cap(k: str) -> str:
    w = k.title()
    for x in ("Pdf", "Svg", "Dxf", "Diy"):
        w = w.replace(x, x.upper())
    return w


def build_title(prod: Product, market: dict | None) -> str:
    """Ana ifade başta; her ek ifade en az bir yeni anlamlı kelime getirmeli; ~110 karakteri geçmez."""
    seo = prod.seo
    if seo.title:
        return seo.title[:TITLE_MAX]
    parts = [_cap(seo.primary)]
    used = _tokens(seo.primary) | {"pattern", "template", "leather"}
    cands = list(seo.keywords)
    if market:  # rakip başlıklarında sık geçen ve ürünle ilgili ikili ifadeler
        vocab = _tokens(" ".join([seo.primary, *seo.keywords, *seo.use_cases]))
        cands += [b for b, _ in market.get("title_bigrams", []) if _tokens(b) <= vocab]
    for k in cands:
        new = _tokens(k) - used - {"diy", "svg", "dxf", "cricut", "laser", "pdf"}
        if not new:
            continue
        cand = " | ".join(parts + [_cap(k)])
        if len(cand) + len(" | PDF SVG DXF") <= 110:
            parts.append(_cap(k))
            used |= _tokens(k)
        if len(parts) >= 4:
            break
    return " | ".join(parts + ["PDF SVG DXF"])[:TITLE_MAX]


def price_reason(prod: Product, market: dict | None) -> tuple[str, str]:
    lo, hi = prod.seo.price_usd
    if market and market.get("price"):
        p = market["price"]
        sug = round(min(max(p["median"], lo), hi), 2)
        return (f"{sug:.2f} USD",
                f"Rakip dijital kalıpların medyanı {p['median']} $, çeyrekler {p['q1']}–{p['q3']} $ ({p['n']} ilan, "
                f"{market['date']}). Ürünün hedef aralığı {lo:g}–{hi:g} $; dikişsiz kilit + test edilmiş tolerans + kesim "
                f"dosyaları medyanın altına inmemeyi destekler.")
    return f"{(lo + hi) / 2:.2f} USD", f"Rakip fiyat verisi yok; ürün aralığının ortası ({lo:g}–{hi:g} $). Taramadan sonra güncelleyin."


def lint(title: str, tags: list[str], desc: str) -> list[str]:
    errs = []
    if len(title) > TITLE_MAX:
        errs.append(f"başlık {len(title)} > 140 karakter")
    if len(title) > 115:
        errs.append(f"başlık uzun ({len(title)}); Etsy kısa başlığı tercih eder")
    if len(tags) != 13:
        errs.append(f"etiket sayısı {len(tags)} (13 olmalı)")
    for t in tags:
        if len(t) > TAG_MAX:
            errs.append(f"etiket > 20 karakter: {t}")
        if re.search(r"[^a-z0-9 '&-]", t):
            errs.append(f"etikette izin verilmeyen karakter: {t}")
    if len({" ".join(sorted(t.split())) for t in tags}) != len(tags):
        errs.append("tekrarlanan etiket var")
    if not desc.startswith("DIGITAL PATTERN"):
        errs.append("açıklama DIGITAL PATTERN uyarısıyla başlamıyor")
    if re.search(r"\bman\b|\bmen's\b|\bhis\b", desc.lower()):
        errs.append("açıklamada cinsiyet varsayımı var")
    return errs


def photos(prod: Product, ai_used: bool) -> list[tuple[str, str]]:
    """(dosya, alt metin) — sıra Etsy'deki sıradır."""
    n = prod.meta.name.lower()
    out = [("01_hero.png", f"Handmade {n} made from one piece of leather, no stitching, on a desk"),
           ("02_what_you_get.png", f"Preview of the {n} PDF pattern pages and cut files included in the download"),
           ("03_steps.png", f"Illustrated step-by-step assembly of the {n}, one drawing per step"),
           ("04_size_details.png", f"Finished size and details of the {n}: {prod.meta.finished_size}"),
           ("05_cut_files.png", f"SVG, Cricut SVG and DXF laser cut files for the {n}")]
    for s, _, _ in prod.shots:
        if s != "hero":
            out.append((f"ai_{s}.png", f"{prod.meta.name} – {s.replace('_', ' ')} view"))
    return out


def listing(prod: Product, market: dict | None, files: list[str], ai_images: bool = True) -> dict:
    m, seo = prod.meta, prod.seo
    title = build_title(prod, market)
    tags, tag_notes = build_tags(prod, market)
    price, why = price_reason(prod, market)
    parts = prod.parts()
    has = lambda s: any(s in f for f in files)
    get = ["• Pattern PDF, A4 and US Letter: 1:1 templates with a 50 mm check square, overview page, "
           f"{len(prod.steps())} illustrated steps (one drawing per step), lock close-ups, troubleshooting"]
    if has("FullSize"):
        get.append("• Full-size one-sheet PDF for a copy shop or plotter")
    if has("CutFiles"):
        get.append("• Cut files (ZIP): SVG for laser, Cricut SVG, DXF R12 with CUT and FOLD layers")
    desc = "\n".join([
        "DIGITAL PATTERN – this is an instant download, not a finished leather item. Nothing will be shipped.",
        "",
        seo.what_it_does,
        "",
        f"Made from {'one piece' if len(parts) == 1 else f'{len(parts)} pieces'} of leather"
        + (" – no stitching, no glue." if "stitch" not in seo.what_it_does.lower() else "."),
        f"Every lock is computer-checked for leather {m.t_test[0]:g}–{m.t_test[1]:g} mm, folds 1 mm off, slits 0.7 mm "
        "off and 1.5–3 mm punches, so it works with the leather you have.",
        "",
        "WHAT YOU GET",
        *get,
        "",
        "SIZE",
        f"• Finished: {m.finished_size}",
        f"• Leather: {m.leather}",
        "",
        "YOU WILL NEED",
        f"• {m.tools[0].upper() + m.tools[1:]}",
        "",
        "SKILL",
        f"• {m.skill} · {m.build_time}",
        "",
        "DOWNLOAD",
        "• Print at 100 % / Actual Size and check the 50 mm square before cutting.",
        "• Files are delivered as a ZIP / PDF right after purchase (Purchases & Reviews).",
        "",
        "LICENSE",
        "• Personal use and small-batch handmade sales of the finished items are welcome.",
        "• Please do not share, resell or redistribute the pattern files.",
        "",
        "NOTE ON IMAGES",
        "• Some product photos are digital renderings made with an AI tool from the real pattern; the step drawings "
        "are generated from the pattern itself." if ai_images else "• Photos show the real finished item.",
        "",
        *(["MATCHING PATTERNS", *[f"• {x}" for x in seo.cross_links], ""] if seo.cross_links else []),
        "© Dagli Leather Studio",
    ])
    return {
        "title": title, "tags": tags, "tag_notes": tag_notes, "description": desc, "price": price, "price_reason": why,
        "attributes": {"Self-published": "Yes", "Content": "With an AI generator" if ai_images else "Without AI",
                       "Occasion": seo.occasion or "-", "Holiday": ", ".join(seo.holidays[:1]) or "-",
                       "Craft type": "Leatherworking", "Digital download": "Yes"},
        "section": seo.section, "photos": photos(prod, ai_images), "cross_links": seo.cross_links,
        "lint": lint(title, tags, desc),
    }


def listing_md(L: dict, prod: Product) -> str:
    m = prod.meta
    out = [f"# Etsy ilanı — {m.name} v{m.version} (SKU {m.sku})", "",
           f"## Başlık ({len(L['title'])} karakter)", "", L["title"], "",
           "## 13 etiket", "", ", ".join(L["tags"]), "", "<details><summary>Etiket gerekçeleri</summary>", "",
           *[f"- {n}" for n in L["tag_notes"]], "", "</details>", "",
           "## Açıklama (İngilizce, olduğu gibi yapıştır)", "", "```", L["description"], "```", "",
           "## Nitelikler", "", *[f"- **{k}:** {v}" for k, v in L["attributes"].items()], "",
           f"## Fiyat: {L['price']}", "", L["price_reason"], "", f"## Mağaza bölümü: {L['section']}", "",
           "## Fotoğraf sırası + alt metin", ""]
    for i, (f, alt) in enumerate(L["photos"], 1):
        out.append(f"{i}. `{f}` — {alt}")
    out += ["", "Ana fotoğraf (1.) tek ve net bir sahne olmalı (kolaj değil); üstünde yazı bandı olabilir.",
            "Yapay zekâ görselleri geçicidir: deri prototip + çekme testinden sonra gerçek fotoğraflarla değiştirin.", ""]
    if L["lint"]:
        out += ["## ⚠ SEO kontrolü", "", *[f"- {e}" for e in L["lint"]], ""]
    else:
        out += ["SEO kontrolü: başlık, 13 etiket, açıklama kuralları ✓", ""]
    return "\n".join(out)

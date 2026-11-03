"""Etsy görselleri (2000×2000), 3B referans sayfası, yapay zekâ görsel promptları (EN + TR), Gemini ile üretim.

Etsy grafikleri ölçülebilir kalıbı ASLA göstermez: kalıp sayfaları bulanık + PREVIEW filigranlı.
"""
from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .house import ASSETS
from .product import Product

S = 2000
CREAM = (246, 241, 234)
INK = (29, 29, 27)
BROWN = (110, 59, 31)


def _font(size, bold=False):
    return ImageFont.truetype(os.path.join(ASSETS, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), size)


def _logo(h):
    lg = Image.open(os.path.join(ASSETS, "logo.png")).convert("RGBA")
    return lg.resize((int(lg.width * h / lg.height), h), Image.LANCZOS)


def _canvas(title: str, sub: str = ""):
    im = Image.new("RGB", (S, S), CREAM)
    d = ImageDraw.Draw(im)
    lg = _logo(150)
    im.paste(lg, (70, 60), lg)
    d.text((70 + lg.width + 40, 80), title.upper(), font=_font(78, True), fill=INK)
    if sub:
        d.text((70 + lg.width + 42, 180), sub, font=_font(44), fill=BROWN)
    return im, d


def _fit(im: Image.Image, w, h):
    k = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)


def _preview(im: Image.Image, blur=9):
    im = im.convert("RGB").filter(ImageFilter.GaussianBlur(blur))
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = _font(max(20, im.width // 9), True)
    for y in range(0, im.height, im.width // 3):
        d.text((im.width * 0.08, y + im.width * 0.05), "PREVIEW", font=f, fill=(200, 30, 40, 90))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def pdf_pages(path: str, scale=1.4) -> list[Image.Image]:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    return [pdf[i].render(scale=scale).to_pil().convert("RGB") for i in range(len(pdf))]


def _shadow_paste(base, im, x, y, r=18):
    sh = Image.new("RGBA", (im.width + 2 * r, im.height + 2 * r), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([r, r, r + im.width, r + im.height], fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(r / 2))
    base.paste(sh, (x - r + 8, y - r + 12), sh)
    base.paste(im, (x, y))


def hero(prod: Product, render: Image.Image, banner: str, photo: Image.Image | None = None) -> Image.Image:
    """Ana görsel: tek net sahne + alt bant. Onaylı yapay zekâ / gerçek fotoğraf varsa o kullanılır."""
    if photo is not None:
        im = photo.convert("RGB")
        k = max(S / im.width, S / im.height)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        im = im.crop(((im.width - S) // 2, (im.height - S) // 2, (im.width - S) // 2 + S, (im.height - S) // 2 + S))
    else:
        im = Image.new("RGB", (S, S), CREAM)
        r = _fit(render, S * 0.86, S * 0.74)
        im.paste(r, ((S - r.width) // 2, 140))
    d = ImageDraw.Draw(im)
    d.rectangle([0, S - 260, S, S], fill=(29, 29, 27))
    d.text((80, S - 225), banner.upper(), font=_font(70, True), fill=(255, 255, 255))
    d.text((80, S - 130), "PDF PATTERN · NO SEWING · NO GLUE · SVG / DXF", font=_font(46), fill=(230, 200, 160))
    lg = _logo(190).convert("RGBA")
    inv = Image.new("RGBA", lg.size, (255, 255, 255, 0))
    inv.putalpha(lg.split()[3])
    im.paste(inv, (S - lg.width - 60, S - 230), inv)
    return im


def what_you_get(prod: Product, pages: list[Image.Image], files: list[str]) -> Image.Image:
    im, d = _canvas("What you get", "instant download · print at home")
    thumbs = pages[:6]
    tw, th = 560, 400
    for i, p in enumerate(thumbs):
        t = _preview(_fit(p, tw, th))
        x = 90 + (i % 3) * (tw + 50) + (tw - t.width) // 2
        y = 330 + (i // 3) * (th + 60) + (th - t.height) // 2
        _shadow_paste(im, t, x, y)
    y = 330 + 2 * (th + 60) + 20
    lines = ["Pattern PDF · A4 + US Letter · 1:1 templates + 50 mm check square",
             f"{len(prod.steps())} illustrated steps · lock close-ups · troubleshooting"]
    if any("FullSize" in f for f in files):
        lines.append("Full-size copy-shop PDF")
    if any("CutFiles" in f for f in files):
        lines.append("Cut files: SVG (laser) · Cricut SVG · DXF")
    for ln in lines:
        d.text((100, y), "✓  " + ln, font=_font(52), fill=INK)
        y += 82
    return im


def steps_collage(prod: Product, step_imgs: list[Image.Image]) -> Image.Image:
    sts = prod.steps()
    n = min(len(step_imgs), 16)
    im, d = _canvas(f"{len(sts)} illustrated steps", "one drawing per step · no sewing")
    cols = 4 if n > 9 else 3
    rows = (n + cols - 1) // cols
    cw = (S - 140 - (cols - 1) * 30) // cols
    ch = min(cw, (S - 360 - (rows - 1) * 30) // rows)
    for i in range(n):
        x = 70 + (i % cols) * (cw + 30)
        y = 320 + (i // cols) * (ch + 30)
        t = step_imgs[i]
        if sts[i].reveals_pattern:
            t = t.filter(ImageFilter.GaussianBlur(5))
        cell = Image.new("RGB", (cw, ch), (255, 255, 255))
        tt = _fit(t, cw - 30, ch - 90)
        cell.paste(tt, ((cw - tt.width) // 2, 75))
        cd = ImageDraw.Draw(cell)
        cd.rectangle([18, 15, 78, 70], fill=INK)
        cd.text((48, 42), str(i + 1), font=_font(40, True), fill=(255, 255, 255), anchor="mm")
        cd.rounded_rectangle([0, 0, cw - 1, ch - 1], 18, outline=(60, 60, 60), width=3)
        im.paste(cell, (x, y))
    return im


def size_details(prod: Product, render: Image.Image) -> Image.Image:
    m = prod.meta
    im, d = _canvas("Size & details", m.finished_size)
    r = _fit(render, 1150, 1350)
    im.paste(r, (60, 330))
    x, y = 1250, 380
    rows = [("Finished", m.finished_size), ("Leather", m.leather.split(";")[0]), ("Pieces", str(len(prod.parts()))),
            ("Stitching / glue", "none"), ("Hardware", m.hardware), ("Skill", m.skill), ("Time", m.build_time)]
    for k, v in rows:
        d.text((x, y), k.upper(), font=_font(38, True), fill=BROWN)
        y += 52
        for ln in _wrap(v, 30):
            d.text((x, y), ln, font=_font(40), fill=INK)
            y += 52
        y += 30
    return im


def cut_files(prod: Product, flat: Image.Image) -> Image.Image:
    im, d = _canvas("Cut files included", "laser · Cricut · CNC")
    t = _preview(_fit(flat, 1700, 1050), blur=14)
    _shadow_paste(im, t, (S - t.width) // 2, 330)
    y = 330 + t.height + 70
    for i, (a, b) in enumerate([("SVG", "laser / Inkscape"), ("CRICUT SVG", "slits as thin shapes"), ("DXF R12", "CUT + FOLD layers")]):
        x = 110 + i * 610
        d.rounded_rectangle([x, y, x + 560, y + 190], 24, fill=(255, 255, 255), outline=INK, width=4)
        d.text((x + 280, y + 70), a, font=_font(62, True), fill=INK, anchor="mm")
        d.text((x + 280, y + 140), b, font=_font(36), fill=BROWN, anchor="mm")
    return im


def _wrap(s, n):
    out, cur = [], ""
    for w in s.split():
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


# ---------------------------------------------------------------- 3B referans + promptlar

def reference_sheet(prod: Product) -> Image.Image:
    """Yapay zekâya ilk eklenecek görsel: 3/4, diğer açı, kilit yakın planı, açıklama."""
    sc = prod.scene(prod.meta.t_draw)
    im = Image.new("RGB", (2400, 1600), (255, 255, 255))
    d = ImageDraw.Draw(im)
    im.paste(sc.render_pil(1.0, -35, 28, size=(1200, 1100)), (0, 120))
    im.paste(sc.render_pil(1.0, 145, 22, size=(1200, 1100)), (1200, 120))
    d.text((40, 30), f"{prod.meta.name.upper()} · 3D REFERENCE (shape is exact; colours/material are not)",
           font=_font(42, True), fill=INK)
    from .booklet import zoom_scene
    cls = prod.closeups()
    y = 1240
    if cls:
        c = cls[0]
        z = zoom_scene(sc, c).render_pil(c.fold, c.az, c.el, size=(700, 340))
        im.paste(z, (40, y))
        d.text((780, y + 20), f"LOCK CLOSE-UP: {c.title}", font=_font(34, True), fill=INK)
        for i, ln in enumerate(_wrap(c.text, 80)[:4]):
            d.text((780, y + 75 + i * 44), ln, font=_font(30), fill=INK)
    d.text((780, y + 270), "Grain side = smooth outside · flesh side hidden · edges burnished", font=_font(30), fill=BROWN)
    return im


def prompts_md(prod: Product) -> str:
    shots = prod.shots or [("hero", "Hero: three-quarter view on a warm oak desk, soft window light.",
                            "Ana görsel: meşe masada 3/4 açı, yumuşak pencere ışığı.")]
    block = prod.product_block or prod.meta.name
    no = "; ".join(prod.must_not)
    out = [f"# Yapay zekâ görsel promptları — {prod.meta.name} v{prod.meta.version}", "",
           "## Hangi dosyalar, hangi sırayla eklenir", "",
           "1. `ai_referans.png` (3B referans sayfası — şekil buradan alınır)",
           "2. İlk iyi görselden sonra: o görseli **onaylı fotoğraf** olarak 2. sırada ekle (tutarlılık için)",
           "3. Varsa gerçek prototip fotoğrafı (en güvenilir kaynak)", "",
           "Her görseli kalıpla karşılaştır: kilit yerleri, dil sayısı, yarıklar, kenar. Uymayanı atın.", "",
           "## Ortak ürün bloğu (her prompta başa koy)", "", "```",
           f"PRODUCT (keep exactly as in the attached 3D reference): {block}",
           "MATERIAL: real full-grain leather, natural grain and pores, soft waxy sheen, slightly rounded burnished edges, "
           "realistic thickness, tiny natural creases at folds.",
           f"MUST NOT APPEAR: {no}.",
           "PHOTO: professional product photography, natural light, true colours, sharp focus on the product, "
           "realistic shadows, no text overlay, square 1:1.", "```", "",
           "Türkçesi:", "", "```",
           f"ÜRÜN (ekteki 3B referanstaki gibi birebir): {prod.product_block_tr or block}",
           "MALZEME: gerçek tam damarlı deri, doğal gözenek, hafif mumlu parlaklık, perdahlı hafif yuvarlak kenarlar, "
           "gerçekçi kalınlık, kıvrımlarda küçük doğal kırışıklar.",
           f"GÖRÜNMEMELİ: {no}.",
           "FOTOĞRAF: profesyonel ürün fotoğrafı, doğal ışık, gerçek renkler, ürüne net odak, gerçekçi gölgeler, "
           "üstünde yazı yok, kare 1:1.", "```", "", "## Çekimler (ortak bloğun altına tek satır)", ""]
    for name, en, tr in shots:
        out += [f"### {name}", "", "```", en, "```", f"_TR: {tr}_", ""]
    out += ["## Hatırlatma", "",
            "Yapay zekâ görselleri geçicidir. Deri prototip ve çekme testinden sonra gerçek fotoğraflarla değiştir; "
            "açıklamadaki AI beyanını buna göre güncelle.", ""]
    return "\n".join(out)


def gemini_shots(prod: Product, ref: Image.Image, folder: str, approved: Image.Image | None = None, only=None, log=print):
    """Gemini ile her çekim için gerçekçi görsel. GEMINI_API_KEY gerekir."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError("pip install google-genai") from e
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise RuntimeError("GEMINI_API_KEY tanımlı değil (https://aistudio.google.com/apikey)")
    client = genai.Client()
    model = os.environ.get("DAGLI_GEMINI_IMAGE_MODEL") or _pick_image_model(client)
    block = prod_block_en(prod)
    made = []
    for name, en, _ in prod.shots:
        if only and name not in only:
            continue
        contents = [f"{block}\nSHOT: {en}\nThe first image is the exact 3D shape reference."
                    + (" The second image is the approved photo: keep the same leather, colour and finish." if approved else ""),
                    ref] + ([approved] if approved is not None else [])
        log(f"  Gemini ({model}): {name}")
        resp = client.models.generate_content(model=model, contents=contents,
                                              config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
        img = None
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else []) or []:
                if getattr(part, "inline_data", None) is not None and part.inline_data.data:
                    img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
        if img is None:
            log(f"    ⚠ {name}: görsel dönmedi")
            continue
        p = os.path.join(folder, f"ai_{name}.png")
        img.save(p)
        made.append(p)
        if approved is None and name == "hero":
            approved = img  # ilk iyi görsel sonraki çekimlerde tutarlılık referansı
    return made


def prod_block_en(prod: Product) -> str:
    return (f"PRODUCT (keep exactly as in the attached 3D reference): {prod.product_block or prod.meta.name}\n"
            "MATERIAL: real full-grain leather, natural grain and pores, soft waxy sheen, slightly rounded burnished "
            "edges, realistic thickness, tiny natural creases at folds.\n"
            f"MUST NOT APPEAR: {'; '.join(prod.must_not)}.\n"
            "PHOTO: professional product photography, natural light, true colours, sharp focus, realistic shadows, "
            "no text overlay, square 1:1.")


def _pick_image_model(client) -> str:
    try:
        names = [m.name.split("/")[-1] for m in client.models.list()]
        imgs = sorted((n for n in names if "image" in n and "gemini" in n), reverse=True)
        pro = [n for n in imgs if "pro" in n]
        return (pro or imgs or ["gemini-2.5-flash-image"])[0]
    except Exception:
        return "gemini-2.5-flash-image"

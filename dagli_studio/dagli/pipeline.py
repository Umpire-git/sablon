"""Kapılar arası akış: kontrol (2. kapı), deneme paketi (2. kapı teslimi), tam satış paketi (3. kapı)."""
from __future__ import annotations

import datetime as dt
import os
import shutil
import zipfile

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from . import house as Hs
from .booklet import Booklet, write_fullsize, zoom_scene
from .checks import Report, geometry_checks, sweep
from .product import Product


def check_product(prod: Product, quick: bool = False) -> Report:
    rep = Report()
    geometry_checks(prod.layout(), rep)
    rep.errors += prod.extra_checks()
    sweep(prod.lock_check, rep, prod.meta.t_test, quick=quick)
    if not prod.steps():
        rep.errors.append("Adım yok")
    return rep


# ---------------------------------------------------------------- 2. kapı teslimi

def trial(prod: Product, folder: str, log=print) -> list[str]:
    """Konsept sayfası + 1:1 kâğıt deneme PDF'i (A4 + Letter, 50 mm kare) + kontrol raporu."""
    os.makedirs(folder, exist_ok=True)
    m = prod.meta
    rep = check_product(prod)
    made = []
    p = os.path.join(folder, f"{m.slug}_konsept.pdf")
    _concept(prod, p, rep)
    made.append(p)
    for paper in ("A4", "Letter"):
        b = Booklet(prod, paper)
        path = os.path.join(folder, f"{m.slug}_paper_test_{paper}.pdf")
        _paper_test(b, path)
        made.append(path)
    with open(os.path.join(folder, "kontrol_raporu.txt"), "w", encoding="utf-8") as fh:
        fh.write(rep.text() + "\n\nBilgisayar testinin GÖSTEREMEDİKLERİ: derinin sertliği, dilin takılma kolaylığı, "
                 "kıvrımlardaki şişkinlik, gerçek kenar perdahı. Kâğıt/karton denemesi ve deri prototip şart.\n")
    made.append(os.path.join(folder, "kontrol_raporu.txt"))
    log(rep.text())
    return made


def _concept(prod: Product, path: str, rep: Report):
    from . import draw2d as D
    c = Canvas(path, pagesize=landscape(A4))
    W, H = landscape(A4)
    d = Hs.Doc(c, prod.meta.name, prod.meta.version, 1)
    d.new_page((W, H))
    top = d.header("CONCEPT SHEET · GATE 2", f"SKU {prod.meta.sku} · {dt.date.today().isoformat()}")
    sc = prod.scene(prod.meta.t_draw)
    sc.draw(c, 10 * mm, top - 95 * mm, 95 * mm, 92 * mm, 1.0, -35, 28)
    cls = prod.closeups()
    if cls:
        cl = cls[0]
        zoom_scene(sc, cl).draw(c, 108 * mm, top - 95 * mm, 80 * mm, 92 * mm, cl.fold, cl.az, cl.el)
        Hs.box_title(c, 110 * mm, top - 2 * mm, "LOCK: " + cl.title, 7)
    D.draw_fit(c, prod.layout(), 192 * mm, top - 95 * mm, W - 200 * mm, 92 * mm, mode="overview")
    y = top - 102 * mm
    Hs.box_title(c, 10 * mm, y, "CHECKS", 8)
    lines = rep.text().splitlines()[:14]
    for ln in lines:
        y -= Hs.para(c, ln, 10 * mm, y - 2 * mm, 130 * mm, 7) + 1
    Hs.box_title(c, 150 * mm, top - 102 * mm, "NOTES", 8)
    yy = top - 104 * mm
    for k, v in prod.at_a_glance():
        yy -= Hs.para(c, f"**{k}:** {v}", 150 * mm, yy, W - 160 * mm, 7) + 1
    yy -= Hs.para(c, "**Not shown by the computer test:** leather stiffness, ease of insertion, bulges at folds. "
                     "Make a card test, then a leather prototype with a pull test.", 150 * mm, yy - 2 * mm, W - 160 * mm, 7)
    d.footer()
    c.save()


def _paper_test(b: Booklet, path: str):
    """Yalnızca şablon sayfaları (+ gerekiyorsa sayfa haritası)."""
    plan = [x for x in b.page_plan() if x[0] in ("template", "printmap", "tile")]
    c = Canvas(path, pagesize=b.info_size)
    b.d = Hs.Doc(c, b.p.meta.name + " · PAPER TEST", b.p.meta.version, len(plan))
    for kind, arg in plan:
        getattr(b, f"_pg_{kind}")(arg, plan)
        b.d.footer()
    c.save()


# ---------------------------------------------------------------- 3. kapı

def step_images(prod: Product, folder: str) -> list:
    """Her adımın çizimi tek tek (Etsy kolajı için)."""
    import pypdfium2 as pdfium
    b = Booklet(prod, "A4")
    path = os.path.join(folder, "_steps_tmp.pdf")
    c = Canvas(path, pagesize=(120 * mm, 95 * mm))
    b.d = Hs.Doc(c, prod.meta.name, prod.meta.version, len(b.steps))
    for i, st in enumerate(b.steps):
        if i:
            c.showPage()
        b._draw_step(st, 4 * mm, 4 * mm, 112 * mm, 87 * mm, i + 1)
    c.save()
    pdf = pdfium.PdfDocument(path)
    ims = [pdf[i].render(scale=4).to_pil().convert("RGB") for i in range(len(pdf))]
    pdf.close()
    os.remove(path)
    return ims


def produce(prod: Product, out_root: str, market: dict | None = None, gemini: bool = False,
            approved_photo: str | None = None, hero_photo: str | None = None, log=print) -> str:
    from . import cutfiles, images, seo, verify
    m = prod.meta
    rep = check_product(prod)
    if not rep.ok:
        log(rep.text())
        raise SystemExit("Kontroller geçmedi: önce tasarımı düzeltin (dagli kontrol ...).")
    folder = os.path.join(out_root, f"{m.slug}_v{m.version}")
    upload = os.path.join(folder, "UPLOAD_TO_ETSY")
    etsy = os.path.join(folder, "etsy_gorselleri")
    ai = os.path.join(folder, "ai")
    for f in (upload, etsy, ai):
        os.makedirs(f, exist_ok=True)
    made = []
    log("1/6 Satış PDF'leri (A4, Letter, tam boy)...")
    for paper in ("A4", "Letter"):
        p = os.path.join(upload, f"{m.slug}_Pattern_{paper}.pdf")
        Booklet(prod, paper).write(p)
        made.append(p)
    full = os.path.join(upload, f"{m.slug}_FullSize_CopyShop.pdf")
    write_fullsize(prod, full)
    made.append(full)
    log("2/6 Kesim dosyaları (SVG, Cricut SVG, DXF, README)...")
    made.append(cutfiles.write_all(prod, upload))
    log("3/6 Denetim (sayfa boyutu, sürüm artığı, 1:1, taşma)...")
    vr = Report()
    for paper in ("A4", "Letter"):
        verify.check_pdf(os.path.join(upload, f"{m.slug}_Pattern_{paper}.pdf"), prod, vr, paper)
    verify.check_cutzip(made[-1], prod, vr)
    verify.check_scale(full, prod, vr)
    log("4/6 Yapay zekâ referansı ve promptlar...")
    ref = images.reference_sheet(prod)
    ref.save(os.path.join(ai, "ai_referans.png"))
    with open(os.path.join(ai, "PROMPTS.md"), "w", encoding="utf-8") as fh:
        fh.write(images.prompts_md(prod))
    ai_imgs = []
    if gemini:
        from PIL import Image
        try:
            ap = Image.open(approved_photo).convert("RGB") if approved_photo else None
            ai_imgs = images.gemini_shots(prod, ref, ai, ap, log=log)
        except Exception as e:
            log(f"  ⚠ Gemini: {e}")
    log("5/6 Etsy görselleri (2000×2000)...")
    from PIL import Image
    sc = prod.scene(m.t_draw)
    render = sc.render_pil(1.0, -35, 28, size=(1600, 1400), bg=(246, 241, 234))
    hp = hero_photo or next((p for p in ai_imgs if p.endswith("ai_hero.png")), None)
    pages = images.pdf_pages(os.path.join(upload, f"{m.slug}_Pattern_A4.pdf"))
    flat_pg = images.pdf_pages(full, scale=1.0)[0]
    outs = {
        "01_hero.png": images.hero(prod, render, m.name, Image.open(hp) if hp else None),
        "02_what_you_get.png": images.what_you_get(prod, pages, made),
        "03_steps.png": images.steps_collage(prod, step_images(prod, etsy)),
        "04_size_details.png": images.size_details(prod, render),
        "05_cut_files.png": images.cut_files(prod, flat_pg),
    }
    for name, im in outs.items():
        im.save(os.path.join(etsy, name))
    for p in ai_imgs:
        if not p.endswith("ai_hero.png"):
            shutil.copy(p, etsy)
    log("6/6 SEO'lu Etsy ilanı...")
    L = seo.listing(prod, market, made, ai_images=True)
    with open(os.path.join(folder, "LISTING.md"), "w", encoding="utf-8") as fh:
        fh.write(seo.listing_md(L, prod))
    z = os.path.join(folder, f"UPLOAD_TO_ETSY_{m.slug}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zz:
        for f in sorted(os.listdir(upload)):
            zz.write(os.path.join(upload, f), f)
    summary = (f"{m.name} v{m.version} ({m.sku}) – {dt.date.today().isoformat()}: satış paketi hazır "
               f"(A4/Letter/tam boy PDF, kesim ZIP, {len(outs)} Etsy görseli, ilan: {len(L['title'])} kr. başlık, "
               f"{len(L['tags'])} etiket, fiyat {L['price']}).\n"
               f"Tarama {rep.sweep_total} kombinasyon / {rep.sweep_failed} hata; denetim: "
               f"{'temiz' if vr.ok and not vr.warnings else f'{len(vr.errors)} hata, {len(vr.warnings)} uyarı'}. "
               "AI görselleri geçici – prototip fotoğrafıyla değiştir.")
    with open(os.path.join(folder, "OZET.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# {m.name} v{m.version}\n\n## Proje özetine yapıştır\n\n{summary}\n\n## Kontroller\n\n```\n{rep.text()}\n"
                 f"```\n\n## Dosya denetimi\n\n```\n{vr.text()}\n```\n\n## SEO\n\n"
                 + ("\n".join(f"- {e}" for e in L["lint"]) or "temiz") + "\n")
    log(vr.text())
    return folder

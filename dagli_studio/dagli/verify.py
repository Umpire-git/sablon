"""Çıktı denetimi: sayfa sayısı/boyutu, eski sürüm artıkları, 1:1 ölçek, SVG boyutu, metin taşması."""
from __future__ import annotations

import re
import zipfile

from .checks import Report
from .geom import bounds_of
from .product import Product


def check_pdf(path: str, prod: Product, rep: Report, paper: str):
    from pypdf import PdfReader
    r = PdfReader(path)
    v = prod.meta.version
    sizes = {"A4": {(595, 842), (842, 595)}, "Letter": {(612, 792), (792, 612)}}
    for i, pg in enumerate(r.pages, 1):
        w, h = round(float(pg.mediabox.width)), round(float(pg.mediabox.height))
        if paper in sizes and (w, h) not in sizes[paper]:
            rep.errors.append(f"{paper} PDF sayfa {i}: boyut {w}×{h} pt beklenmiyor")
        txt = pg.extract_text() or ""
        for old in set(re.findall(r"Pattern v(\d+(?:\.\d+)*)", txt)):
            if old != v:
                rep.errors.append(f"{paper} PDF sayfa {i}: eski sürüm yazısı 'Pattern v{old}' (güncel v{v})")
        if f"Page {i} of {len(r.pages)}" not in txt.replace("\n", " "):
            rep.warnings.append(f"{paper} PDF sayfa {i}: sayfa numarası bulunamadı")
    _overflow(path, rep, paper)


def _overflow(path: str, rep: Report, paper: str):
    """Sayfa kenarına 4 mm'den yakın mürekkep (filigran hariç) → taşma şüphesi."""
    try:
        import numpy as np
        import pypdfium2 as pdfium
    except ImportError:
        rep.info.append("pypdfium2 yok: taşma denetimi atlandı (pip install pypdfium2)")
        return
    pdf = pdfium.PdfDocument(path)
    for i in range(len(pdf)):
        im = np.asarray(pdf[i].render(scale=72 / 72 * 2).to_pil().convert("L"))
        h, w = im.shape
        px = int(4 / 25.4 * 144)
        edge = np.concatenate([im[:px].ravel(), im[-px:].ravel(), im[:, :px].ravel(), im[:, -px:].ravel()])
        if (edge < 140).mean() > 0.002:
            rep.warnings.append(f"{paper} PDF sayfa {i + 1}: kenara çok yakın çizim/metin (taşma olabilir)")


def check_cutzip(path: str, prod: Product, rep: Report):
    x0, y0, x1, y1 = bounds_of(prod.layout())
    want_w, want_h = x1 - x0 + 10, y1 - y0 + 10
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for need in (f"{prod.meta.slug}.svg", f"{prod.meta.slug}_Cricut.svg", f"{prod.meta.slug}.dxf", "README_Cut_Files.txt"):
            if need not in names:
                rep.errors.append(f"Kesim ZIP'inde {need} yok")
        for n in names:
            if n.endswith(".svg"):
                s = z.read(n).decode()
                m = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', s)
                if not m or abs(float(m[1]) - want_w) > 0.01 or abs(float(m[2]) - want_h) > 0.01:
                    rep.errors.append(f"{n}: boyut 1:1 değil")
            if n.endswith(".dxf"):
                s = z.read(n).decode()
                if "$INSUNITS\n70\n4" not in s:
                    rep.errors.append(f"{n}: birim mm değil")


def check_scale(path_full: str, prod: Product, rep: Report):
    """Tam boy PDF sayfa ölçüsü = yerleşim + kenar boşlukları (1:1)."""
    from pypdf import PdfReader
    pg = PdfReader(path_full).pages[0]
    x0, y0, x1, y1 = bounds_of(prod.layout())
    w_mm = float(pg.mediabox.width) / 72 * 25.4
    if abs(w_mm - (x1 - x0 + 30)) > 0.2:
        rep.errors.append(f"Tam boy PDF ölçeği 1:1 değil ({w_mm:.1f} mm, beklenen {x1 - x0 + 30:.1f})")

"""Kesim dosyaları: SVG (lazer), Cricut SVG (yarıklar ince kapalı şekil), DXF R12 (CUT/FOLD), README, ZIP."""
from __future__ import annotations

import math
import os
import zipfile

from .geom import Part, bounds_of, rings
from .product import Product

PAD = 5.0


def _flip(parts: list[Part]):
    x0, y0, x1, y1 = bounds_of(parts)
    W, H = x1 - x0 + 2 * PAD, y1 - y0 + 2 * PAD
    return (lambda x: x - x0 + PAD), (lambda y: (y1 - y) + PAD), W, H  # SVG y aşağı


def _d(pts, X, Y, close=True):
    s = "M" + " L".join(f"{X(x):.3f},{Y(y):.3f}" for x, y in pts)
    return s + (" Z" if close else "")


def _slit_shape(a, b, w=0.3):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    nx, ny = -math.sin(ang) * w / 2, math.cos(ang) * w / 2
    return [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]


def svg(prod: Product, cricut: bool = False) -> str:
    parts = prod.layout()
    X, Y, W, H = _flip(parts)
    m = prod.meta
    cut, fold = [], []
    n_slits = n_holes = 0
    for p in parts:
        for r in rings(p.outline):
            cut.append(f'<path d="{_d(r, X, Y)}"/>')
        for cu in p.cuts:
            if cricut:
                cut.append(f'<path d="{_d(_slit_shape(cu[0], cu[-1]), X, Y)}"/>')
            else:
                cut.append(f'<path d="{_d(cu, X, Y, False)}"/>')
        for s in p.slits:
            a, b = s.ends()
            n_slits += 1
            if cricut:
                cut.append(f'<path id="{s.label or "slit"}" d="{_d(_slit_shape(a, b), X, Y)}"/>')
            else:
                cut.append(f'<path id="{s.label or "slit"}" d="M{X(a[0]):.3f},{Y(a[1]):.3f} L{X(b[0]):.3f},{Y(b[1]):.3f}"/>')
        for h in p.stop_holes() + [hh for hh in p.holes if not hh.stop]:
            n_holes += 1
            cut.append(f'<circle cx="{X(h.center[0]):.3f}" cy="{Y(h.center[1]):.3f}" r="{h.d / 2:.3f}"/>')
        for fl in p.folds:
            fold.append(f'<path d="{_d(fl, X, Y, False)}"/>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="{W:.3f}mm" height="{H:.3f}mm" viewBox="0 0 {W:.3f} {H:.3f}">
<title>Dagli Leather Studio · {m.name} v{m.version} · cut file 1:1 (mm)</title>
<g id="CUT" inkscape:groupmode="layer" inkscape:label="CUT (red)" fill="none" stroke="#FF0000" stroke-width="0.1">
{chr(10).join(cut)}
</g>
<g id="FOLD" inkscape:groupmode="layer" inkscape:label="FOLD (blue, do not cut)" fill="none" stroke="#0000FF" stroke-width="0.1" stroke-dasharray="3,2">
{chr(10).join(fold)}
</g>
</svg>
"""


def dxf(prod: Product) -> str:
    parts = prod.layout()
    x0, y0, _, _ = bounds_of(parts)
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES",
           "0", "TABLE", "2", "LTYPE", "70", "2",
           "0", "LTYPE", "2", "CONTINUOUS", "70", "0", "3", "Solid line", "72", "65", "73", "0", "40", "0.0",
           "0", "LTYPE", "2", "DASHED", "70", "0", "3", "__ __", "72", "65", "73", "2", "40", "5.0", "49", "3.0", "49", "-2.0",
           "0", "ENDTAB",
           "0", "TABLE", "2", "LAYER", "70", "2",
           "0", "LAYER", "2", "CUT", "70", "0", "62", "1", "6", "CONTINUOUS",
           "0", "LAYER", "2", "FOLD", "70", "0", "62", "5", "6", "DASHED",
           "0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def ln(a, b, layer):
        out.extend(["0", "LINE", "8", layer, "10", f"{a[0] - x0 + PAD:.4f}", "20", f"{a[1] - y0 + PAD:.4f}", "30", "0",
                    "11", f"{b[0] - x0 + PAD:.4f}", "21", f"{b[1] - y0 + PAD:.4f}", "31", "0"])

    for p in parts:
        for r in rings(p.outline):
            for a, b in zip(r, r[1:]):
                ln(a, b, "CUT")
        for cu in p.cuts:
            for a, b in zip(cu, cu[1:]):
                ln(a, b, "CUT")
        for s in p.slits:
            ln(*s.ends(), "CUT")
        for h in p.stop_holes() + [hh for hh in p.holes if not hh.stop]:
            out.extend(["0", "CIRCLE", "8", "CUT", "10", f"{h.center[0] - x0 + PAD:.4f}", "20",
                        f"{h.center[1] - y0 + PAD:.4f}", "30", "0", "40", f"{h.d / 2:.4f}"])
        for fl in p.folds:
            for a, b in zip(fl, fl[1:]):
                ln(a, b, "FOLD")
    out.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(out) + "\n"


def readme(prod: Product) -> str:
    m = prod.meta
    parts = prod.layout()
    ns = sum(len(p.slits) for p in parts)
    nh = sum(len(p.stop_holes()) for p in parts)
    nw = sum(len([h for h in p.holes if not h.stop]) for p in parts)
    pieces = "One piece." if len(parts) == 1 else f"{len(parts)} pieces: " + ", ".join(p.name for p in parts) + "."
    return f"""DAGLI LEATHER STUDIO - {m.name.upper()} v{m.version} - CUT FILES

All files are 1:1, in millimetres. {pieces}
- {m.slug}.svg ........ laser cutters, Inkscape, Illustrator
- {m.slug}_Cricut.svg . Cricut Design Space (slits are thin closed shapes)
- {m.slug}.dxf ........ CNC / laser software (DXF R12, layers CUT and FOLD)

LAYERS
- CUT (red): outline, {ns} slits, {nh} stop holes of 2 mm{f', {nw} other holes / windows' if nw else ''}.
- FOLD (blue, dashed): do not cut. Hide this layer, or score very lightly.

NOTES
- Leather {m.t_range[0]:g}-{m.t_range[1]:g} mm. Slit names are on the template page of the PDF.
- Cricut: Knife Blade (Cricut Maker), StrongGrip mat. Punch the stop holes and cut the slits by hand if needed.
- Laser: test on a scrap first; mask the grain side.

For personal and small-scale crafting use. (c) Dagli Leather Studio. All rights reserved.
"""


def write_all(prod: Product, folder: str) -> str:
    m = prod.meta
    os.makedirs(folder, exist_ok=True)
    files = {f"{m.slug}.svg": svg(prod), f"{m.slug}_Cricut.svg": svg(prod, cricut=True),
             f"{m.slug}.dxf": dxf(prod), "README_Cut_Files.txt": readme(prod)}
    zpath = os.path.join(folder, f"{m.slug}_CutFiles_v{m.version}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name, txt in files.items():
            z.writestr(name, txt)
    return zpath

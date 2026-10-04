"""DXF (R12, mm) — lazer / CNC / CAD. Katmanlar: CUT, SLIT, HOLE, FOLD, GUIDE, GRAIN, TEXT."""
from __future__ import annotations

from ..geometry import Arc, Circle, Line
from ..pattern import Kind

ACI = {Kind.CUT: 7, Kind.SLIT: 1, Kind.HOLE: 6, Kind.FOLD: 5, Kind.GUIDE: 3, Kind.GRAIN: 8}


def _ascii(s: str) -> str:
    tr = str.maketrans("çğıİöşüÇĞÖŞÜ", "cgiIosuCGOSU")
    return s.translate(tr).replace("°", " der").encode("ascii", "replace").decode("ascii")


def write_dxf(title: str, pieces, path: str) -> None:
    from ..pattern import Pattern
    placed = Pattern(title, pieces).layout()
    out: list[str] = []
    a = out.append

    def g(code, val):
        a(f"{code}\n{val}")

    g(0, "SECTION"); g(2, "HEADER")
    g(9, "$ACADVER"); g(1, "AC1009")
    g(9, "$INSUNITS"); g(70, 4)       # mm
    g(9, "$MEASUREMENT"); g(70, 1)    # metrik
    g(0, "ENDSEC")
    g(0, "SECTION"); g(2, "TABLES")
    g(0, "TABLE"); g(2, "LTYPE"); g(70, 2)
    g(0, "LTYPE"); g(2, "CONTINUOUS"); g(70, 0); g(3, "Solid"); g(72, 65); g(73, 0); g(40, 0.0)
    g(0, "LTYPE"); g(2, "DASHED"); g(70, 0); g(3, "__ __"); g(72, 65); g(73, 2); g(40, 4.5); g(49, 3.0); g(49, -1.5)
    g(0, "ENDTAB")
    layers = list(ACI) + ["TEXT"]
    g(0, "TABLE"); g(2, "LAYER"); g(70, len(layers))
    for k in layers:
        name = k.value.upper() if isinstance(k, Kind) else k
        g(0, "LAYER"); g(2, name); g(70, 0); g(62, ACI.get(k, 7)); g(6, "DASHED" if k == Kind.FOLD else "CONTINUOUS")
    g(0, "ENDTAB"); g(0, "ENDSEC")
    g(0, "SECTION"); g(2, "ENTITIES")
    for p in placed:
        for kind, prim in p.items:
            layer = kind.value.upper()
            if isinstance(prim, Line):
                g(0, "LINE"); g(8, layer)
                g(10, f"{prim.x0:.4f}"); g(20, f"{prim.y0:.4f}"); g(30, 0.0)
                g(11, f"{prim.x1:.4f}"); g(21, f"{prim.y1:.4f}"); g(31, 0.0)
            elif isinstance(prim, Arc):
                g(0, "ARC"); g(8, layer)
                g(10, f"{prim.cx:.4f}"); g(20, f"{prim.cy:.4f}"); g(30, 0.0); g(40, f"{prim.r:.4f}")
                g(50, f"{prim.a0 % 360:.4f}"); g(51, f"{prim.a1 % 360 if prim.a1 % 360 else 360:.4f}")
            elif isinstance(prim, Circle):
                g(0, "CIRCLE"); g(8, layer)
                g(10, f"{prim.cx:.4f}"); g(20, f"{prim.cy:.4f}"); g(30, 0.0); g(40, f"{prim.r:.4f}")
        for t in p.texts:
            g(0, "TEXT"); g(8, "TEXT")
            g(10, f"{t.x:.3f}"); g(20, f"{t.y:.3f}"); g(30, 0.0); g(40, f"{t.size:.2f}"); g(1, _ascii(t.text))
            if t.angle:
                g(50, f"{t.angle:.2f}")
    g(0, "ENDSEC"); g(0, "EOF")
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(out) + "\n")

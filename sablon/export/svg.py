"""1:1 ölçekli SVG (mm birimli, katmanlı) — Cricut, lazer kesim, Inkscape için."""
from __future__ import annotations

from xml.sax.saxutils import escape

from ..geometry import Arc, Circle, Line
from ..pattern import Kind, Pattern, Piece

COLORS = {
    Kind.CUT: ("#000000", None), Kind.SLIT: ("#000000", None), Kind.HOLE: ("#000000", None),
    Kind.FOLD: ("#1f5fbf", "3 1.5"), Kind.STITCH: ("#c0392b", None), Kind.GUIDE: ("#c0392b", "1 1"),
    Kind.GRAIN: ("#555555", None),
}


def write_svg(title: str, pieces: list[Piece], path: str) -> None:
    placed = Pattern(title, pieces).layout()
    x0, y0, x1, y1 = Pattern.extent(placed)
    m = 10.0
    W, H = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    fx = lambda x: x - x0 + m  # noqa: E731
    fy = lambda y: (y1 + m) - y  # noqa: E731  (y ekseni ters)
    groups: dict[Kind, list[str]] = {k: [] for k in Kind}
    texts: list[str] = []
    for p in placed:
        for kind, prim in p.items:
            if isinstance(prim, Line):
                groups[kind].append(f'<line x1="{fx(prim.x0):.3f}" y1="{fy(prim.y0):.3f}" x2="{fx(prim.x1):.3f}" y2="{fy(prim.y1):.3f}"/>')
            elif isinstance(prim, Arc):
                sx, sy = prim.start
                ex, ey = prim.end
                large = 1 if (prim.a1 - prim.a0) > 180 else 0
                groups[kind].append(
                    f'<path d="M{fx(sx):.3f},{fy(sy):.3f} A{prim.r:.3f},{prim.r:.3f} 0 {large} 0 {fx(ex):.3f},{fy(ey):.3f}"/>')
            elif isinstance(prim, Circle):
                groups[kind].append(f'<circle cx="{fx(prim.cx):.3f}" cy="{fy(prim.cy):.3f}" r="{prim.r:.3f}"/>')
        for t in p.texts:
            anchor = {"start": "start", "end": "end"}.get(t.anchor, "middle")
            texts.append(
                f'<text x="{fx(t.x):.2f}" y="{fy(t.y):.2f}" font-size="{t.size}" text-anchor="{anchor}" '
                f'transform="rotate({-t.angle:.2f} {fx(t.x):.2f} {fy(t.y):.2f})">{escape(t.text)}</text>')
    body = []
    for kind, items in groups.items():
        if not items:
            continue
        color, dash = COLORS[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        fill = color if kind == Kind.STITCH else "none"
        body.append(f'<g id="{kind.value}" inkscape:label="{kind.value}" inkscape:groupmode="layer" '
                    f'stroke="{color}" stroke-width="0.25" fill="{fill}"{d}>' + "".join(items) + "</g>")
    body.append('<g id="text" font-family="Helvetica, Arial, sans-serif" fill="#444">' + "".join(texts) + "</g>")
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        f'width="{W:.3f}mm" height="{H:.3f}mm" viewBox="0 0 {W:.3f} {H:.3f}">'
        f'<title>{escape(title)}</title>' + "".join(body) + "</svg>"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

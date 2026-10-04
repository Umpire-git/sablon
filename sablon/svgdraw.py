"""Ön izleme (montajlı ürün) çizimleri için küçük SVG yardımcıları."""
from __future__ import annotations

from xml.sax.saxutils import escape


class Svg:
    """mm cinsinden çizer; y aşağı bakar (ekran yönü)."""

    def __init__(self, width: float, height: float, scale: float = 3.0):
        self.w, self.h, self.k = width, height, scale
        self.parts: list[str] = []

    def _n(self, v: float) -> str:
        return f"{v * self.k:.2f}"

    def rect(self, x, y, w, h, fill="none", stroke="#222", sw=0.4, rx=0.0, dash=None, opacity=1.0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{self._n(x)}" y="{self._n(y)}" width="{self._n(w)}" height="{self._n(h)}" rx="{self._n(rx)}" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{self._n(sw)}"{d}/>'
        )

    def path(self, d_mm: list[tuple], fill="none", stroke="#222", sw=0.4, dash=None, opacity=1.0, close=True):
        """d_mm: [("M",x,y), ("L",x,y), ("A",r,large,sweep,x,y)]"""
        out = []
        for cmd in d_mm:
            c = cmd[0]
            if c in "ML":
                out.append(f"{c}{self._n(cmd[1])},{self._n(cmd[2])}")
            elif c == "A":
                r, large, sweep, x, y = cmd[1:]
                out.append(f"A{self._n(r)},{self._n(r)} 0 {large} {sweep} {self._n(x)},{self._n(y)}")
        if close:
            out.append("Z")
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<path d="{" ".join(out)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{self._n(sw)}"{d}/>'
        )

    def line(self, x0, y0, x1, y1, stroke="#222", sw=0.3, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{self._n(x0)}" y1="{self._n(y0)}" x2="{self._n(x1)}" y2="{self._n(y1)}" stroke="{stroke}" stroke-width="{self._n(sw)}"{d}/>'
        )

    def circle(self, cx, cy, r, fill="none", stroke="#222", sw=0.3):
        self.parts.append(
            f'<circle cx="{self._n(cx)}" cy="{self._n(cy)}" r="{self._n(r)}" fill="{fill}" stroke="{stroke}" stroke-width="{self._n(sw)}"/>'
        )

    def text(self, x, y, s, size=3.2, anchor="middle", fill="#222", weight="normal"):
        self.parts.append(
            f'<text x="{self._n(x)}" y="{self._n(y)}" font-size="{self._n(size)}" text-anchor="{anchor}" '
            f'font-family="Helvetica, Arial, sans-serif" font-weight="{weight}" fill="{fill}">{escape(s)}</text>'
        )

    def dim_h(self, x0, x1, y, label, off=6.0):
        """Yatay ölçü çizgisi (y'nin `off` kadar altında/üstünde)."""
        yy = y + off
        self.line(x0, y, x0, yy + (1.5 if off > 0 else -1.5), stroke="#c0392b", sw=0.15)
        self.line(x1, y, x1, yy + (1.5 if off > 0 else -1.5), stroke="#c0392b", sw=0.15)
        self.line(x0, yy, x1, yy, stroke="#c0392b", sw=0.2)
        self.text((x0 + x1) / 2, yy - 1.0, label, size=2.8, fill="#c0392b")

    def dim_v(self, x, y0, y1, label, off=6.0):
        xx = x + off
        self.line(x, y0, xx + (1.5 if off > 0 else -1.5), y0, stroke="#c0392b", sw=0.15)
        self.line(x, y1, xx + (1.5 if off > 0 else -1.5), y1, stroke="#c0392b", sw=0.15)
        self.line(xx, y0, xx, y1, stroke="#c0392b", sw=0.2)
        anchor = "start" if off > 0 else "end"
        self.text(xx + (1.2 if off > 0 else -1.2), (y0 + y1) / 2 + 1, label, size=2.8, anchor=anchor, fill="#c0392b")

    def render(self) -> str:
        W, H = self.w * self.k, self.h * self.k
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.2f} {H:.2f}">'
            f'<rect width="100%" height="100%" fill="#fbf8f3"/>' + "".join(self.parts) + "</svg>"
        )

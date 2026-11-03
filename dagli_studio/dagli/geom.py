"""Düz kalıp geometrisi (mm, y yukarı).

Bir ürün bir veya birkaç Parça'dan (Part) oluşur. Her parçada:
  outline : dış hat (shapely Polygon; iç delik/pencere de olabilir)
  cuts    : açık kesim çizgileri (ör. dil çiftinin orta kesiği, boyun kesikleri)
  slits   : yarıklar — iki ucunda Ø d durdurma deliği, aradan kesilir
  holes   : yuvarlak delikler / pencereler
  folds   : kat çizgileri (kesilmez, kesikli çizilir)
  labels  : yazılar (parça adı, yarık adları ...)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

PUNCH = 2.0  # standart durdurma deliği Ø (mm)


@dataclass
class Slit:
    """Yarık: a→b ekseni boyunca açıklık `opening` (delik dış kenarından dış kenarına).

    Delik çapı değişse de açıklık sabit kalır: delik merkezleri arası = opening − d.
    """
    center: tuple[float, float]
    angle: float  # derece, yarık ekseni
    opening: float
    label: str = ""
    d: float = PUNCH

    def ends(self, d: float | None = None):
        d = self.d if d is None else d
        h = (self.opening - d) / 2
        a = math.radians(self.angle)
        cx, cy = self.center
        return ((cx - h * math.cos(a), cy - h * math.sin(a)), (cx + h * math.cos(a), cy + h * math.sin(a)))


@dataclass
class Hole:
    center: tuple[float, float]
    d: float
    label: str = ""
    stop: bool = False  # durdurma deliği (kesik ucu)


@dataclass
class Label:
    pos: tuple[float, float]
    text: str
    size: float = 3.0  # mm
    angle: float = 0.0
    color: str = "#555555"


@dataclass
class Part:
    name: str
    outline: Polygon
    color: str = "#c9a27e"  # genel bakış sayfasındaki parça rengi
    cuts: list[list[tuple[float, float]]] = field(default_factory=list)
    slits: list[Slit] = field(default_factory=list)
    holes: list[Hole] = field(default_factory=list)
    folds: list[list[tuple[float, float]]] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    note: str = ""  # şablon üstündeki kısa not, ör. "rolls into a tube"

    # ---- dönüşümler ----
    def transformed(self, dx=0.0, dy=0.0, rot=0.0, mirror=False) -> "Part":
        def P(pt):
            x, y = pt
            if mirror:
                x = -x
            a = math.radians(rot)
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            return (x + dx, y + dy)

        g = self.outline
        if mirror:
            g = affinity.scale(g, -1, 1, origin=(0, 0))
        g = affinity.translate(affinity.rotate(g, rot, origin=(0, 0)), dx, dy)
        ang = (lambda a: (180 - a if mirror else a) + rot)
        return Part(
            self.name, g, self.color,
            [[P(p) for p in c] for c in self.cuts],
            [Slit(P(s.center), ang(s.angle), s.opening, s.label, s.d) for s in self.slits],
            [Hole(P(h.center), h.d, h.label, h.stop) for h in self.holes],
            [[P(p) for p in f] for f in self.folds],
            [Label(P(lb.pos), lb.text, lb.size, ang(lb.angle) if lb.angle else rot, lb.color) for lb in self.labels],
            self.note,
        )

    def bounds(self):
        return self.outline.bounds

    def size(self):
        x0, y0, x1, y1 = self.bounds()
        return x1 - x0, y1 - y0

    def stop_holes(self, d: float | None = None) -> list[Hole]:
        """Yarık uçlarındaki ve kesik köklerindeki tüm durdurma delikleri."""
        out = [h for h in self.holes if h.stop]
        for s in self.slits:
            for e in s.ends(d):
                out.append(Hole(e, d or s.d, s.label, True))
        return out

    def leather_area_cm2(self) -> float:
        return self.outline.area / 100.0


# ---------------------------------------------------------------- yerleşim

def layout_row(parts: list[Part], gap: float = 10.0) -> list[Part]:
    """Parçaları soldan sağa, alt kenarları hizalı, araları `gap` olacak biçimde dizer."""
    out, x = [], 0.0
    for p in parts:
        x0, y0, x1, y1 = p.bounds()
        out.append(p.transformed(dx=x - x0, dy=-y0))
        x += (x1 - x0) + gap
    return out


def bounds_of(parts: list[Part]):
    xs0, ys0, xs1, ys1 = zip(*(p.bounds() for p in parts))
    return min(xs0), min(ys0), max(xs1), max(ys1)


# ---------------------------------------------------------------- yardımcı şekiller

def rounded_rect(w: float, h: float, r: float = 2.0, x0: float = 0.0, y0: float = 0.0) -> Polygon:
    b = box(x0 + r, y0 + r, x0 + w - r, y0 + h - r)
    return b.buffer(r, quad_segs=12) if r > 0 else box(x0, y0, x0 + w, y0 + h)


def circle(cx: float, cy: float, r: float, n: int = 96) -> Polygon:
    return Point(cx, cy).buffer(r, quad_segs=max(4, n // 4))


def fillet_inner(poly: Polygon, r: float) -> Polygon:
    """İç (içbükey) köşeleri yuvarlar — boyun köşelerinde yırtılmayı önler."""
    return poly.buffer(r, quad_segs=8, join_style="round").buffer(-r, quad_segs=8, join_style="round")


def fillet_outer(poly: Polygon, r: float) -> Polygon:
    return poly.buffer(-r, quad_segs=8).buffer(r, quad_segs=8)


def union(*polys) -> Polygon:
    g = unary_union(polys)
    if g.geom_type != "Polygon":
        raise ValueError(f"Parçalar tek parça değil ({g.geom_type}); bağlantıları kontrol et.")
    return g


def rings(poly: Polygon) -> list[list[tuple[float, float]]]:
    """Dış ve iç halkalar (kapalı nokta listeleri)."""
    return [list(poly.exterior.coords)] + [list(i.coords) for i in poly.interiors]


def seg_dist_to_boundary(poly: Polygon, pt) -> float:
    return poly.exterior.distance(Point(pt)) if not poly.interiors else poly.boundary.distance(Point(pt))


def line(*pts) -> LineString:
    return LineString(pts)

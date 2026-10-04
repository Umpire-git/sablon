"""Milimetre cinsinden 2B geometri ilkelleri.

Tüm koordinatlar mm'dir, y ekseni yukarı bakar (matematik yönü). Yaylar saat
yönünün tersine (a0 -> a1, derece) çizilir. Geometri kesin (analitik) tutulur;
yaylar PDF/SVG/DXF'e gerçek yay olarak aktarılır, çokgene çevrilmez.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Union


@dataclass(frozen=True)
class Line:
    x0: float
    y0: float
    x1: float
    y1: float

    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    def point_at(self, s: float) -> tuple[float, float]:
        L = self.length()
        k = 0.0 if L == 0 else s / L
        return (self.x0 + (self.x1 - self.x0) * k, self.y0 + (self.y1 - self.y0) * k)

    def bounds(self) -> tuple[float, float, float, float]:
        return (min(self.x0, self.x1), min(self.y0, self.y1), max(self.x0, self.x1), max(self.y0, self.y1))

    def moved(self, dx: float, dy: float) -> "Line":
        return Line(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)


@dataclass(frozen=True)
class Arc:
    """Merkez (cx, cy), yarıçap r; a0'dan a1'e saat yönünün tersine (a1 > a0)."""

    cx: float
    cy: float
    r: float
    a0: float
    a1: float

    def length(self) -> float:
        return math.radians(self.a1 - self.a0) * self.r

    def point_at(self, s: float) -> tuple[float, float]:
        a = math.radians(self.a0) + (s / self.r if self.r else 0.0)
        return (self.cx + self.r * math.cos(a), self.cy + self.r * math.sin(a))

    @property
    def start(self) -> tuple[float, float]:
        return self.point_at(0.0)

    @property
    def end(self) -> tuple[float, float]:
        return self.point_at(self.length())

    def bounds(self) -> tuple[float, float, float, float]:
        pts = [self.start, self.end]
        a = math.ceil(self.a0 / 90.0) * 90.0
        while a <= self.a1 + 1e-9:
            pts.append((self.cx + self.r * math.cos(math.radians(a)), self.cy + self.r * math.sin(math.radians(a))))
            a += 90.0
        xs, ys = zip(*pts)
        return (min(xs), min(ys), max(xs), max(ys))

    def moved(self, dx: float, dy: float) -> "Arc":
        return Arc(self.cx + dx, self.cy + dy, self.r, self.a0, self.a1)


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    r: float

    def bounds(self) -> tuple[float, float, float, float]:
        return (self.cx - self.r, self.cy - self.r, self.cx + self.r, self.cy + self.r)

    def moved(self, dx: float, dy: float) -> "Circle":
        return Circle(self.cx + dx, self.cy + dy, self.r)


Segment = Union[Line, Arc]
Primitive = Union[Line, Arc, Circle]


def merge_bounds(items: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    items = list(items)
    if not items:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        min(b[0] for b in items),
        min(b[1] for b in items),
        max(b[2] for b in items),
        max(b[3] for b in items),
    )


def polyline(points: list[tuple[float, float]], closed: bool = False) -> list[Line]:
    pts = list(points)
    if closed and pts[0] != pts[-1]:
        pts.append(pts[0])
    return [Line(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]) if a != b]


def rounded_rect(x: float, y: float, w: float, h: float, r: float) -> list[Segment]:
    """Köşeleri r yarıçaplı dikdörtgen (saat yönünün tersine, sol alttan)."""
    r = max(0.0, min(r, w / 2, h / 2))
    if r == 0:
        return polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True)
    return [
        Line(x + r, y, x + w - r, y),
        Arc(x + w - r, y + r, r, 270, 360),
        Line(x + w, y + r, x + w, y + h - r),
        Arc(x + w - r, y + h - r, r, 0, 90),
        Line(x + w - r, y + h, x + r, y + h),
        Arc(x + r, y + h - r, r, 90, 180),
        Line(x, y + h - r, x, y + r),
        Arc(x + r, y + r, r, 180, 270),
    ]


def path_length(segments: list[Segment]) -> float:
    return sum(s.length() for s in segments)


def points_along(segments: list[Segment], pitch: float, closed: bool = False) -> tuple[list[tuple[float, float]], float]:
    """Yol boyunca eşit aralıklı noktalar (dikiş delikleri).

    Gerçek aralık, istenen `pitch`e en yakın ve yolu tam bölen değerdir; böylece
    ilk ve son delik tam yol uçlarına düşer. (noktalar, gerçek_aralık) döner.
    """
    total = path_length(segments)
    if total <= 0:
        return [], 0.0
    n = max(1, round(total / pitch))
    step = total / n
    count = n if closed else n + 1
    pts: list[tuple[float, float]] = []
    for i in range(count):
        s = min(i * step, total)
        acc = 0.0
        for seg in segments:
            L = seg.length()
            if s <= acc + L + 1e-9:
                pts.append(seg.point_at(min(L, s - acc)))
                break
            acc += L
    return pts, step


# ---------------------------------------------------------------------------
# Genel amaçlı yardımcılar (köşe yuvarlatma, 3 noktadan yay, dönüşüm, üçgenleme)
# ---------------------------------------------------------------------------
Pt = tuple[float, float]


def _norm(v: Pt) -> Pt:
    L = math.hypot(v[0], v[1])
    return (v[0] / L, v[1] / L) if L else (0.0, 0.0)


def arc_between(c: Pt, r: float, p: Pt, q: Pt) -> Arc:
    """p ile q arasındaki KISA yayı (≤180°) Arc olarak döndürür."""
    a = math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))
    b = math.degrees(math.atan2(q[1] - c[1], q[0] - c[0]))
    sweep = (b - a) % 360
    if sweep > 180:
        a, sweep = b, 360 - sweep
    return Arc(c[0], c[1], r, a, a + sweep)


def arc_from_3pts(p: Pt, m: Pt, q: Pt) -> Arc:
    """p'den başlayıp m'den geçerek q'ya giden yay."""
    ax, ay = p
    bx, by = m
    cx, cy = q
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        raise ValueError("doğrusal noktalar")
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    ang = lambda P: math.degrees(math.atan2(P[1] - uy, P[0] - ux)) % 360  # noqa: E731
    a0, am, a1 = ang(p), ang(m), ang(q)
    # p→q saat yönünün tersine giderken m'yi içeriyor mu?
    if (am - a0) % 360 <= (a1 - a0) % 360:
        return Arc(ux, uy, r, a0, a0 + (a1 - a0) % 360)
    return Arc(ux, uy, r, a1, a1 + (a0 - a1) % 360)


def fillet(prev: Pt, v: Pt, nxt: Pt, r: float):
    """v köşesini r yarıçapla yuvarlar → (t1, yay, t2) veya r sığmazsa None."""
    if r <= 0:
        return None
    u = _norm((prev[0] - v[0], prev[1] - v[1]))
    w = _norm((nxt[0] - v[0], nxt[1] - v[1]))
    cosphi = max(-1.0, min(1.0, u[0] * w[0] + u[1] * w[1]))
    phi = math.acos(cosphi)
    if phi < 1e-6 or abs(phi - math.pi) < 1e-6:
        return None
    d = r / math.tan(phi / 2)
    if d > math.dist(prev, v) + 1e-9 or d > math.dist(nxt, v) + 1e-9:
        return None
    t1 = (v[0] + u[0] * d, v[1] + u[1] * d)
    t2 = (v[0] + w[0] * d, v[1] + w[1] * d)
    bis = _norm((u[0] + w[0], u[1] + w[1]))
    h = r / math.sin(phi / 2)
    c = (v[0] + bis[0] * h, v[1] + bis[1] * h)
    return t1, arc_between(c, r, t1, t2), t2


def line_intersection(p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> Pt | None:
    d = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
    if abs(d) < 1e-12:
        return None
    a = p1[0] * p2[1] - p1[1] * p2[0]
    b = p3[0] * p4[1] - p3[1] * p4[0]
    return ((a * (p3[0] - p4[0]) - (p1[0] - p2[0]) * b) / d, (a * (p3[1] - p4[1]) - (p1[1] - p2[1]) * b) / d)


def discretize(segs: list[Segment], max_deg: float = 6.0) -> list[Pt]:
    """Bitişik segmentleri nokta dizisine çevirir (3B ve çakışma testleri için)."""
    pts: list[Pt] = []

    def push(p: Pt):
        if not pts or math.dist(pts[-1], p) > 1e-6:
            pts.append(p)

    for s in segs:
        if isinstance(s, Line):
            push((s.x0, s.y0))
            push((s.x1, s.y1))
        else:
            n = max(2, int(math.ceil((s.a1 - s.a0) / max_deg)))
            seq = [s.point_at(s.length() * i / n) for i in range(n + 1)]
            # yay ters yönde gezilmiş olabilir: önceki noktaya yakın uçtan başla
            if pts and math.dist(pts[-1], seq[-1]) < math.dist(pts[-1], seq[0]):
                seq.reverse()
            for p in seq:
                push(p)
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop()
    return pts


def polygon_area(pts: list[Pt]) -> float:
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def point_in_polygon(p: Pt, poly: list[Pt]) -> bool:
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def dist_to_polygon_edge(p: Pt, poly: list[Pt]) -> float:
    best = float("inf")
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        best = min(best, math.dist(p, (a[0] + k * dx, a[1] + k * dy)))
    return best


def triangulate(poly: list[Pt]) -> list[tuple[int, int, int]]:
    """Kulak kırpma ile basit çokgen üçgenleme (indeks üçlüleri)."""
    idx = list(range(len(poly)))
    if polygon_area(poly) < 0:
        idx.reverse()
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                if cross(a, b, p) >= -1e-12 and cross(b, c, p) >= -1e-12 and cross(c, a, p) >= -1e-12:
                    ok = False
                    break
            if ok:
                tris.append((i0, i1, i2))
                idx.pop(k)
                break
        else:  # dejenere durum: kalan yelpaze
            break
    if len(idx) >= 3:
        for k in range(1, len(idx) - 1):
            tris.append((idx[0], idx[k], idx[k + 1]))
    return tris


def points_on_path(segments: list[Segment], pitch: float) -> list[Pt]:
    """Bitişik yol boyunca eşit aralıklı noktalar; ilk ve son nokta tam uçlarda."""
    pts, _ = points_along(segments, pitch)
    return pts


class Affine2:
    """2B afin dönüşüm: p' = O + x*d + y*n (d, n birim, n = d'nin 90° solu)."""

    def __init__(self, ox=0.0, oy=0.0, dx=1.0, dy=0.0):
        self.o = (ox, oy)
        self.d = (dx, dy)
        self.n = (-dy, dx)

    def apply(self, p: Pt) -> Pt:
        return (self.o[0] + p[0] * self.d[0] + p[1] * self.n[0], self.o[1] + p[0] * self.d[1] + p[1] * self.n[1])

    def vec(self, v: Pt) -> Pt:
        return (v[0] * self.d[0] + v[1] * self.n[0], v[0] * self.d[1] + v[1] * self.n[1])

    def compose(self, child: "Affine2") -> "Affine2":
        o = self.apply(child.o)
        d = self.vec(child.d)
        return Affine2(o[0], o[1], d[0], d[1])

    @property
    def angle(self) -> float:
        return math.degrees(math.atan2(self.d[1], self.d[0]))

    def seg(self, s):
        if isinstance(s, Line):
            a, b = self.apply((s.x0, s.y0)), self.apply((s.x1, s.y1))
            return Line(a[0], a[1], b[0], b[1])
        if isinstance(s, Arc):
            c = self.apply((s.cx, s.cy))
            return Arc(c[0], c[1], s.r, s.a0 + self.angle, s.a1 + self.angle)
        if isinstance(s, Circle):
            c = self.apply((s.cx, s.cy))
            return Circle(c[0], c[1], s.r)
        raise TypeError(s)


def seg_lines(prim, max_deg: float = 8.0) -> list[tuple[float, float, float, float]]:
    """Doğru ya da yay kesiği kısa doğru parçalarına böler (3B çizim için)."""
    if isinstance(prim, Line):
        return [(prim.x0, prim.y0, prim.x1, prim.y1)]
    pts = discretize([prim], max_deg)
    return [(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]

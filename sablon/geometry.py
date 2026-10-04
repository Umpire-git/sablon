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

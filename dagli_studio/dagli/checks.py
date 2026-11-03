"""Genel kontroller + en kötü durum taraması (2. kapı)."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from shapely.geometry import LineString, Point

from .geom import Part, bounds_of
from .locks import LockCase

PAPERS = {"A4": (210.0, 297.0), "Letter": (215.9, 279.4)}
MARGIN = 8.0


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    sweep_total: int = 0
    sweep_failed: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        out = []
        if self.sweep_total:
            out.append(f"En kötü durum taraması: {self.sweep_total} kombinasyon, {self.sweep_failed} hata")
        out += [f"HATA  {e}" for e in self.errors] + [f"UYARI {w}" for w in self.warnings] + [f"bilgi {i}" for i in self.info]
        return "\n".join(out) or "Tüm kontroller geçti."


def fits_one_page(parts: list[Part], paper: str, margin: float = MARGIN, reserve: float = 0.0):
    """Yerleşim tek sayfaya sığıyor mu? (dikey/yatay). reserve: kontrol karesi için ayrılan şerit."""
    x0, y0, x1, y1 = bounds_of(parts)
    w, h = x1 - x0, y1 - y0
    pw, ph = PAPERS[paper]
    for orient, (W, H) in (("portrait", (pw, ph)), ("landscape", (ph, pw))):
        if w <= W - 2 * margin and h <= H - 2 * margin - reserve:
            return orient
        if w <= W - 2 * margin - reserve and h <= H - 2 * margin:
            return orient
    return None


def geometry_checks(parts: list[Part], rep: Report, min_hole_edge=4.0):
    for p in parts:
        if not p.outline.is_valid:
            rep.errors.append(f"{p.name}: dış hat geçersiz (kendini kesiyor)")
        for s in p.slits:
            for e in s.ends():
                d = p.outline.exterior.distance(Point(e)) - s.d / 2
                if d < min_hole_edge - 1e-6:
                    rep.errors.append(f"{p.name} {s.label}: durdurma deliği kenara {d:.1f} mm (≥ {min_hole_edge:g})")
            ln = LineString(s.ends())
            if not p.outline.contains(ln):
                rep.errors.append(f"{p.name} {s.label}: yarık parçanın dışına taşıyor")
        for c in p.cuts:
            if len(c) >= 2:
                end = Point(c[-1])
                if not any(Point(h.center).distance(end) < 0.05 for h in p.holes if h.stop):
                    rep.warnings.append(f"{p.name}: bir kesik durdurma deliğinde bitmiyor")
    for a, b in itertools.combinations(parts, 2):
        if a.outline.intersects(b.outline):
            rep.errors.append(f"Açınımda {a.name} ile {b.name} üst üste biniyor")
    for paper in PAPERS:
        o = fits_one_page(parts, paper, reserve=0)
        if o:
            rep.info.append(f"Tüm parçalar tek {paper} sayfaya sığıyor ({o})")
        else:
            rep.info.append(f"Parçalar tek {paper} sayfaya sığmıyor → şablon sayfaları parça parça basılır (sayfa haritalı)")


def worst_case_grid(t_range=(0.2, 2.4), t_step=0.2, quick=False):
    ts = [round(t_range[0] + i * t_step, 2) for i in range(int(round((t_range[1] - t_range[0]) / t_step)) + 1)]
    if quick:
        ts = [ts[0], ts[len(ts) // 2], ts[-1]]
    for t, wrap, fold, so, sl, pu, mi in itertools.product(
            ts, (0.0, 1.0), (-1.0, 0.0, 1.0), (-0.7, 0.0, 0.7), (0.0, 0.6), (1.5, 2.0, 3.0), (False, True)):
        yield LockCase(t, wrap, fold, so, sl, pu, mi)


def sweep(check_fn, rep: Report, t_range=(0.2, 2.4), quick=False, show=8):
    """check_fn(case) -> list[str] hatalar. Tüm kombinasyonlar tek tek denenir."""
    seen: dict[str, int] = {}
    for case in worst_case_grid(t_range, quick=quick):
        rep.sweep_total += 1
        errs = check_fn(case)
        if errs:
            rep.sweep_failed += 1
            for e in errs:
                key = e.split(" [")[0]
                if key not in seen:
                    seen[key] = 0
                    if len(seen) <= show:
                        rep.errors.append(e)
                seen[key] += 1
    if len(seen) > show:
        rep.errors.append(f"... ve {len(seen) - show} farklı hata türü daha")

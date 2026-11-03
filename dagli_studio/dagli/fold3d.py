"""Basit 3B katlama sahnesi: düz parçalar menteşe çizgileri etrafında döner, kalınlıkla çizilir.

Kullanım (ürün modülünde):
    sc = Scene(t=1.6)
    root = sc.panel("govde", poly)                     # düz koordinatlarda shapely Polygon
    flap = sc.panel("kapak", poly2, parent=root, hinge=((0,60),(80,60)), angle=180)
    sc.render_pil(fold=1.0, az=-35, el=30)           # PIL görsel
    sc.draw(canvas, x, y, w, h, fold=0.5)             # PDF içine vektör çizim

angle: menteşe ekseni a→b etrafında sağ el kuralıyla döner. fold ∈ [0,1] tüm açılarla çarpılır
(0 = düz açınım, 1 = bitmiş ürün) — adım adım katlama çizimleri bundan üretilir.
Yüzler: üst (+z) = deri yüzü (grain), alt = et yüzü (flesh).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient


def rot(axis, ang):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    R = np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                  [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                  [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])
    M = np.eye(4)
    M[:3, :3] = R
    return M


def tr(v):
    M = np.eye(4)
    M[:3, 3] = v
    return M


def hexrgb(c: str):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mix(a, b, k):
    return tuple(a[i] * (1 - k) + b[i] * k for i in range(3))


@dataclass
class Panel:
    name: str
    poly: Polygon
    parent: "Panel | None" = None
    hinge: tuple = ((0, 0), (1, 0))
    angle: float = 0.0
    stage: tuple[float, float] = (0.0, 1.0)  # bu kat fold'un hangi aralığında yapılır (adım sırası)
    color: str | None = None
    lift: float = 0.0  # üst üste binen katmanlar için z kaydırma (kalınlık katı)
    decals: list = field(default_factory=list)  # [(nokta listesi, renk, kalınlık mm)]
    place: object = None  # kök panel için sabit 4x4 yerleşim (döndür/taşı)
    smooth: bool = False  # kavisli yüzey parçası: kenar çizgisi çizilmez

    def local(self, fold: float) -> np.ndarray:
        if self.parent is None:
            P = self.place if self.place is not None else np.eye(4)
            return P @ tr((0, 0, self.lift))
        s0, s1 = self.stage
        k = 0.0 if fold <= s0 else 1.0 if fold >= s1 else (fold - s0) / (s1 - s0)
        a = np.array([*self.hinge[0], 0.0])
        b = np.array([*self.hinge[1], 0.0])
        return tr(a) @ rot(b - a, math.radians(self.angle * k)) @ tr(-a) @ tr((0, 0, self.lift))

    def world(self, fold: float) -> np.ndarray:
        M = self.local(fold)
        return M if self.parent is None else self.parent.world(fold) @ M


@dataclass
class Prop:
    """Sahneye eklenen basit nesne (ör. AirTag, kart, kalem): kapalı 3B çokgen yüzleri."""
    faces: list  # [(Nx3 array, renk)]
    attach: Panel | None = None
    visible_from: float = 0.0  # bu fold değerinden sonra görünür


def _on_line(pt, hg, tol=0.05):
    (ax, ay), (bx, by) = hg
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1.0
    return abs((pt[0] - ax) * dy - (pt[1] - ay) * dx) / L < tol


def _bands(poly: Polygon, step: float = 12.0):
    from shapely.geometry import box
    x0, y0, x1, y1 = poly.bounds
    out = []
    y = y0
    while y < y1 - 1e-6:
        g = poly.intersection(box(x0 - 1, y, x1 + 1, min(y1, y + step)))
        for gg in getattr(g, "geoms", [g]):
            if gg.geom_type == "Polygon" and gg.area > 0.01:
                out.append(orient(gg, 1.0))
        y += step
    return out


class Scene:
    def __init__(self, t: float = 1.6, grain: str = "#7a4524", flesh: str = "#d9b98f", edge: str = "#4a2814"):
        self.t = t
        self.grain, self.flesh, self.edge = grain, flesh, edge
        self.panels: list[Panel] = []
        self.props: list[Prop] = []

    def panel(self, name, poly, parent=None, hinge=((0, 0), (1, 0)), angle=0.0, stage=(0.0, 1.0), color=None,
              lift=0.0, place=None, smooth=False) -> Panel:
        if poly.geom_type != "Polygon":  # kesişimden gelen çizgi/nokta artıklarını at
            polys = [g for g in getattr(poly, "geoms", []) if g.geom_type == "Polygon" and g.area > 0.05]
            if not polys:
                raise ValueError(f"{name}: panel çokgeni boş")
            poly = max(polys, key=lambda g: g.area)
        p = Panel(name, orient(poly, 1.0), parent, hinge, angle, stage, color, lift, place=place, smooth=smooth)
        self.panels.append(p)
        return p

    def prop_disc(self, center3, r, h, color="#d8d8d8", attach=None, visible_from=0.0, seg=40):
        cx, cy, cz = center3
        bot = np.array([[cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg), cz]
                        for i in range(seg)])
        top = bot + np.array([0, 0, h])
        faces = [(top, color), (bot[::-1], color)]
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((np.array([bot[i], bot[j], top[j], top[i]]), color))
        self.props.append(Prop(faces, attach, visible_from))

    def prop_box(self, x0, y0, z0, x1, y1, z1, color="#eeeeee", attach=None, visible_from=0.0):
        P = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                      [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
        idx = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.props.append(Prop([(P[list(f)], color) for f in idx], attach, visible_from))

    # ------------------------------------------------------------ geometri
    def faces(self, fold: float, explode: float = 0.0):
        """Dünya koordinatlarında yüzler: (Nx3, tür, renk, delikler)."""
        out = []
        h = self.t / 2
        for p in self.panels:
            M = p.world(fold)
            ext = np.array(p.poly.exterior.coords[:-1])
            holes = [np.array(i.coords[:-1]) for i in p.poly.interiors]

            def T(xy, z):
                P = np.c_[xy, np.full(len(xy), z), np.ones(len(xy))]
                return (M @ P.T).T[:, :3]

            col = p.color
            if p.smooth:  # kavisli yüzey: derinlik sıralaması için şeritlere böl
                for g in _bands(p.poly.buffer(0.3, join_style="mitre")):
                    e2 = np.array(g.exterior.coords[:-1])
                    h2 = [np.array(i.coords[:-1]) for i in g.interiors]
                    out.append((T(e2, h), "grain~", col, [T(hh, h) for hh in h2]))
                    out.append((T(e2[::-1], -h), "flesh~", col, [T(hh[::-1], -h) for hh in h2]))
            else:
                out.append((T(ext, h), "grain", col, [T(hh, h) for hh in holes]))
                out.append((T(ext[::-1], -h), "flesh", col, [T(hh[::-1], -h) for hh in holes]))
            hinges = ([p.hinge] if p.parent is not None else []) + [q.hinge for q in self.panels if q.parent is p]
            for ring in [ext] + holes:
                n = len(ring)
                for i in range(n):
                    a, b = ring[i], ring[(i + 1) % n]
                    if any(_on_line(a, hg) and _on_line(b, hg) for hg in hinges):
                        continue  # komşu panele bağlı iç kenar
                    q = np.array([a, b, b, a])
                    zs = np.array([-h, -h, h, h])
                    P = np.c_[q, zs, np.ones(4)]
                    out.append(((M @ P.T).T[:, :3], "edge", col, []))
            for pts, c, w in p.decals:
                out.append((T(np.array(pts), h + 0.02), "decal", c, w))
        for pr in self.props:
            if fold + 1e-9 < pr.visible_from:
                continue
            M = pr.attach.world(fold) if pr.attach else np.eye(4)
            for f, c in pr.faces:
                P = np.c_[f, np.ones(len(f))]
                out.append(((M @ P.T).T[:, :3], "prop", c, []))
        return out

    # ------------------------------------------------------------ çizim
    def project(self, fold=1.0, az=-35.0, el=30.0):
        a, e = math.radians(az), math.radians(el)
        # kamera: z yukarı, az etrafında dön, el kadar eğ
        R1 = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        R2 = np.array([[1, 0, 0], [0, math.sin(e), math.cos(e)], [0, -math.cos(e), math.sin(e)]])
        R = R2 @ R1
        view = np.array([0, 0, 1.0])  # kameraya doğru (dönüşüm sonrası)
        light = np.array([-0.45, 0.55, 0.70])
        light /= np.linalg.norm(light)
        polys = []
        for pts, kind, col, extra in self.faces(fold):
            P = (R @ pts.T).T
            if kind == "decal":
                polys.append((P[:, 2].max() + 0.05, P[:, :2], kind, col, extra, 1.0))
                continue
            if len(P) < 3:
                continue
            n = np.cross(P[1] - P[0], P[2] - P[0])
            if len(P) > 3:  # Newell normali
                n = np.zeros(3)
                for i in range(len(P)):
                    c, d = P[i], P[(i + 1) % len(P)]
                    n += np.array([(c[1] - d[1]) * (c[2] + d[2]), (c[2] - d[2]) * (c[0] + d[0]),
                                   (c[0] - d[0]) * (c[1] + d[1])])
            nn = np.linalg.norm(n)
            if nn < 1e-9:
                continue
            n /= nn
            if n @ view <= 0 and kind != "prop":
                continue  # arka yüz
            if kind == "prop" and n @ view <= 0:
                continue
            shade = 0.72 + 0.45 * max(0.0, float(n @ (R @ light)))
            holes = [(R @ hh.T).T[:, :2] for hh in extra] if kind[:5] in ("grain", "flesh") else []
            depth = float(P[:, 2].mean())
            polys.append((depth, P[:, :2], kind, col, holes, shade))
        polys.sort(key=lambda x: x[0])
        return polys

    def _color(self, kind, col, shade):
        kind = kind.rstrip("~")
        base = {"grain": hexrgb(col or self.grain), "flesh": hexrgb(self.flesh), "edge": hexrgb(self.edge)}
        if kind == "prop" or kind == "decal":
            c = hexrgb(col)
        else:
            c = base[kind]
            if kind == "flesh" and col:
                c = mix(hexrgb(col), (1, 1, 1), 0.55)
        return tuple(min(1.0, v * shade) for v in c)

    def _fit(self, polys, w, h, pad=0.06):
        pts = np.vstack([p[1] for p in polys]) if polys else np.zeros((1, 2))
        lo, hi = pts.min(0), pts.max(0)
        span = np.maximum(hi - lo, 1e-6)
        s = min(w * (1 - 2 * pad) / span[0], h * (1 - 2 * pad) / span[1])
        off = np.array([(w - span[0] * s) / 2, (h - span[1] * s) / 2]) - lo * s
        return s, off

    def render_pil(self, fold=1.0, az=-35.0, el=30.0, size=(1200, 900), bg=(255, 255, 255), ss=2,
                   outline=True, shadow=True, fit=None):
        W, H = size[0] * ss, size[1] * ss
        polys = self.project(fold, az, el)
        s, off = fit or self._fit(polys, W, H)
        im = Image.new("RGB", (W, H), bg)
        dr = ImageDraw.Draw(im)

        def tx(P):
            Q = P * s + off
            return [(float(x), float(H - y)) for x, y in Q]

        if shadow and polys:
            sh = Image.new("L", (W, H), 0)
            sd = ImageDraw.Draw(sh)
            for _, P, kind, *_ in polys:
                if kind != "decal":
                    sd.polygon([(x + 6 * ss, y + 10 * ss) for x, y in tx(P)], fill=70)
            sh = sh.filter(ImageFilter.GaussianBlur(14 * ss))
            im = Image.composite(Image.new("RGB", (W, H), (120, 110, 100)), im, sh)
            dr = ImageDraw.Draw(im)
        for depth, P, kind, col, extra, shade in polys:
            if kind == "decal":
                dr.line(tx(P), fill=tuple(int(255 * v) for v in hexrgb(col)), width=max(1, int(extra * s * 0.6)))
                continue
            c = tuple(int(255 * v) for v in self._color(kind, col, shade))
            line = outline and kind not in ("edge",) and not kind.endswith("~")
            if line:
                dr.polygon(tx(P), fill=c, outline=(40, 22, 12))
            else:  # kavisli yüzey şeritleri arasında kıl payı boşluk kalmasın
                dr.polygon(tx(P), fill=c, outline=c, width=max(2, ss + 1))
            for hh in extra:
                dr.polygon(tx(hh), fill=bg)
        if ss > 1:
            im = im.resize(size, Image.LANCZOS)
        return im

    def draw(self, c, x, y, w, h, fold=1.0, az=-35.0, el=30.0, line_w=0.35):
        """ReportLab tuvaline vektör çizim (pt cinsinden kutu)."""
        polys = self.project(fold, az, el)
        s, off = self._fit(polys, w, h)
        for depth, P, kind, col, extra, shade in polys:
            Q = P * s + off + np.array([x, y])
            if kind == "decal":
                c.setStrokeColorRGB(*hexrgb(col))
                c.setLineWidth(max(0.4, extra * s * 0.5))
                path = c.beginPath()
                path.moveTo(*Q[0])
                for q in Q[1:]:
                    path.lineTo(*q)
                c.drawPath(path, stroke=1, fill=0)
                continue
            r, g, b = self._color(kind, col, shade)
            c.setFillColorRGB(r, g, b)
            smooth = kind.endswith("~") or kind == "edge"
            if smooth:
                c.setStrokeColorRGB(r, g, b)
            else:
                c.setStrokeColorRGB(0.18, 0.1, 0.05)
            c.setLineWidth(line_w if not smooth else 0.25)
            path = c.beginPath()
            path.moveTo(*Q[0])
            for q in Q[1:]:
                path.lineTo(*q)
            path.close()
            for hh in extra:
                H2 = hh * s + off + np.array([x, y])
                path.moveTo(*H2[0])
                for q in H2[1:]:
                    path.lineTo(*q)
                path.close()
            c.drawPath(path, stroke=1, fill=1, fillMode=0)
        return s, off

    def screen_point(self, p3, fold=1.0, az=-35.0, el=30.0, panel: Panel | None = None):
        """Bir 3B noktanın (veya panelin düz koordinatlarındaki noktanın) ekran (normalize edilmemiş) konumu."""
        p = np.array([*p3, 1.0]) if len(p3) == 3 else np.array([*p3, 0.0, 1.0])
        if panel is not None:
            p = panel.world(fold) @ p
        a, e = math.radians(az), math.radians(el)
        R1 = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        R2 = np.array([[1, 0, 0], [0, math.sin(e), math.cos(e)], [0, -math.cos(e), math.sin(e)]])
        return (R2 @ R1 @ p[:3])[:2]

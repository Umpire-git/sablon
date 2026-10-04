"""Bağımlılıksız (numpy + Pillow) 3B görüntü üretici.

Her panel, kalınlığı kadar ekstrüde edilmiş bir levha olarak z-buffer ile çizilir;
yüz sınırları çizgi olarak vurgulanır (teknik çizim görünümü). Katlama oranı 0..1
verilerek montaj adımlarının ara hâlleri de çizilebilir.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

from .engine import Built
from .geometry import polygon_area, triangulate


def _hex(c: str, default=(0.72, 0.5, 0.3)):
    try:
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except Exception:
        return default


def _shade(col, k):
    return tuple(min(1.0, max(0.0, v * k)) for v in col)


class Mesh:
    def __init__(self):
        self.tris: list[np.ndarray] = []   # (3,3)
        self.cols: list[tuple] = []
        self.ids: list[int] = []

    def add_poly(self, pts3, col, fid):
        """Düzlemsel çokgen (yerel 2B üçgenleme önceden yapılmış olmalı)."""
        raise NotImplementedError

    def add_tri(self, a, b, c, col, fid):
        self.tris.append(np.array([a, b, c], dtype=float))
        self.cols.append(col)
        self.ids.append(fid)


def _slab(mesh: Mesh, poly2d, m: np.ndarray, z0: float, z1: float, col, fid_base: int, side_col=None):
    if len(poly2d) < 3:
        return
    pts = poly2d if polygon_area(poly2d) > 0 else poly2d[::-1]
    tris = triangulate(pts)
    P = np.array([[x, y, 0.0, 1.0] for x, y in pts])
    top = (m @ (P + np.array([0, 0, z1, 0])).T).T[:, :3]
    bot = (m @ (P + np.array([0, 0, z0, 0])).T).T[:, :3]
    for (i, j, k) in tris:
        mesh.add_tri(top[i], top[j], top[k], col, fid_base)
        mesh.add_tri(bot[i], bot[k], bot[j], col, fid_base + 1)
    sc = side_col or _shade(col, 0.8)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        mesh.add_tri(bot[i], bot[j], top[j], sc, fid_base + 2)
        mesh.add_tri(bot[i], top[j], top[i], sc, fid_base + 2)


def _disc(r, n=20, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def build_mesh(b: Built, fold=1.0, show_contents=True, show_hardware=True) -> Mesh:
    mesh = Mesh()
    base = _hex(b.design.renk or "")
    mats = b.matrices(fold)
    fid = 10
    for pid in b.order:
        p = b.panels[pid]
        col = base if not (p.mount and p.mount.ana_panel) else _shade(base, 1.08)
        _slab(mesh, p.poly, mats[pid], -p.t, 0.0, col, fid)
        fid += 3
        # dikiş delikleri / ipliği: iki yüzde küçük açık renkli noktalar
        if show_hardware:
            for mk in p.marks:
                from .pattern import Kind
                if mk.kind == Kind.STITCH:
                    c = mk.prim
                    for z0, z1 in ((0.0, 0.06), (-p.t - 0.06, -p.t)):
                        _slab(mesh, _disc(0.55, 6, c.cx, c.cy), mats[pid], z0, z1, (0.93, 0.9, 0.82), 2)
    if show_hardware:
        metal = (0.78, 0.76, 0.7)
        for s in b.snaps:
            p = b.panels[s.src]
            r = (12.5 if s.size == "L20" else 15.0 if s.size == "L24" else 10.0) / 2 if s.kind == "citcit" else 0
            if r:
                z = (-p.t - 1.6, -p.t) if s.src_side < 0 else (0.0, 1.6)
                _slab(mesh, _disc(r, 28, *s.src_xy), mats[s.src], *z, metal, fid)
                fid += 3
                if s.dst:
                    q = b.panels[s.dst]
                    z = (0.0, 1.2) if s.dst_side > 0 else (-q.t - 1.2, -q.t)
                    _slab(mesh, _disc(r * 0.55, 20, *s.dst_xy), mats[s.dst], *z, metal, fid)
                    fid += 3
    if show_contents:
        for cg in b.contents:
            p = b.panels[cg.panel]
            box = [(cg.x, cg.y), (cg.x + cg.w, cg.y), (cg.x + cg.w, cg.y + cg.h), (cg.x, cg.y + cg.h)]
            if cg.under:
                z0, z1 = -p.t - cg.s, -p.t
            else:
                z0, z1 = 0.02, cg.s
            _slab(mesh, box, mats[cg.panel], z0, z1, (0.88, 0.91, 0.95), fid, side_col=(0.75, 0.78, 0.83))
            fid += 3
    return mesh


def render(b: Built, path: str | None = None, fold=1.0, az=-35.0, el=28.0, size=(1200, 900), bg=(250, 247, 242),
           ss=2, show_contents=True, margin=0.08) -> Image.Image:
    mesh = build_mesh(b, fold, show_contents)
    if not mesh.tris:
        raise ValueError("boş model")
    T = np.stack(mesh.tris)  # (N,3,3)
    # kamera: ortografik; az = z ekseni etrafında, el = yükseklik
    a, e = math.radians(az), math.radians(el)
    # dünya: x sağ, y ileri, z yukarı (panelin iç yüzü +z). Görünüm vektörleri:
    right = np.array([math.cos(a), math.sin(a), 0.0])
    fwd = np.array([-math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), -math.sin(e)])  # kameradan sahneye
    up = np.cross(right, fwd)
    up /= np.linalg.norm(up)
    V = np.stack([right, up, -fwd])  # ekran x, ekran y, derinlik (büyük = kameraya yakın)
    P = T @ V.T  # (N,3,3)
    W, H = size[0] * ss, size[1] * ss
    mn = P[..., :2].reshape(-1, 2).min(0)
    mx = P[..., :2].reshape(-1, 2).max(0)
    span = max((mx - mn).max(), 1e-6)
    scale = min(W * (1 - 2 * margin) / max(mx[0] - mn[0], 1e-6), H * (1 - 2 * margin) / max(mx[1] - mn[1], 1e-6))
    cx, cy = (mn + mx) / 2
    sx = (P[..., 0] - cx) * scale + W / 2
    sy = H / 2 - (P[..., 1] - cy) * scale
    sz = P[..., 2]

    zbuf = np.full((H, W), -np.inf)
    img = np.zeros((H, W, 3))
    img[:] = np.array(bg) / 255
    idb = np.zeros((H, W), dtype=np.int32)
    light = np.array([0.35, 0.45, 0.82])
    light /= np.linalg.norm(light)
    light_v = V @ light
    for t in range(len(T)):
        x, y, z = sx[t], sy[t], sz[t]
        x0, x1 = int(max(0, math.floor(x.min()))), int(min(W - 1, math.ceil(x.max())))
        y0, y1 = int(max(0, math.floor(y.min()))), int(min(H - 1, math.ceil(y.max())))
        if x1 < x0 or y1 < y0:
            continue
        den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(den) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
        l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
        l2 = 1 - l0 - l1
        inside = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not inside.any():
            continue
        depth = l0 * z[0] + l1 * z[1] + l2 * z[2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = inside & (depth > sub + 1e-6)
        if not upd.any():
            continue
        # gölgeleme (iki yüzlü)
        tri_v = P[t]
        nrm = np.cross(tri_v[1] - tri_v[0], tri_v[2] - tri_v[0])
        nl = np.linalg.norm(nrm)
        k = 0.55 + 0.5 * abs(float(nrm @ light_v) / nl) if nl > 0 else 0.8
        col = np.array(_shade(mesh.cols[t], k))
        sub[upd] = depth[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = col
        idb[y0:y1 + 1, x0:x1 + 1][upd] = mesh.ids[t]
    # kenar çizgileri: yüz kimliği değişen pikseller
    edge = np.zeros((H, W), bool)
    edge[:, 1:] |= idb[:, 1:] != idb[:, :-1]
    edge[1:, :] |= idb[1:, :] != idb[:-1, :]
    zd = np.zeros((H, W), bool)
    zfin = np.where(np.isfinite(zbuf), zbuf, -1e6)
    zd[:, 1:] |= np.abs(zfin[:, 1:] - zfin[:, :-1]) > 2.0
    zd[1:, :] |= np.abs(zfin[1:, :] - zfin[:-1, :]) > 2.0
    small = (idb == 2)  # dikiş noktaları için çizgi yok
    lines = (edge | zd) & ~small
    img[lines] = img[lines] * 0.35
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    if ss > 1:
        out = out.resize(size, Image.LANCZOS)
    if path:
        out.save(path)
    return out


def fold_steps(b: Built) -> list[dict]:
    """kat_sirasi'na göre montaj durumları: her adımda o sıraya kadar olan katlar kapalı."""
    orders = sorted({p.spec.kat_sirasi for p in b.panels.values() if p.parent and p.spec.kat_sirasi > 0})
    states = []
    for k in [0] + orders:
        fold = {pid: (1.0 if (p.spec.kat_sirasi and p.spec.kat_sirasi <= k) or (p.parent and p.spec.kat_sirasi == 0 and k == orders[-1] if orders else False) else 0.0)
                for pid, p in b.panels.items()}
        states.append({"step": k, "fold": fold})
    return states

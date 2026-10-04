"""Fotoğraf benzeri 3B ürün görseli (numpy + Pillow, ek bağımlılık yok).

Ertelenmiş gölgelendirmeli z-buffer:
  * katlar yuvarlak kıvrım yüzeyi olarak çizilir (keskin menteşe yok),
  * deri: yerel koordinatta prosedürel doku + renk dalgalanması; crazy horse kıvrımlarda açılır,
  * kenarlar kenar boyası tonunda, çıtçıt/vida metal, kartlar parlak,
  * zemine yumuşak gölge, stüdyo arka planı, perspektif kamera, süper örnekleme.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageFilter

from .engine import Built
from .geometry import polygon_area, triangulate
from .pattern import Kind

# malzeme kimlikleri
LEATHER, EDGE, BENDM, METAL, CARD_TOP, CARD_SIDE, DARK = 1, 2, 3, 4, 5, 6, 7


def _hex(c: str, default=(0.62, 0.38, 0.2)):
    try:
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except Exception:
        return default


class Mesh:
    def __init__(self):
        self.P: list = []   # (3,3) köşe konumları
        self.N: list = []   # (3,3) köşe normalleri
        self.UV: list = []  # (3,2) doku koordinatı (mm)
        self.C: list = []   # temel renk
        self.M: list = []   # malzeme

    def tri(self, p, n, uv, col, mat):
        self.P.append(p)
        self.N.append(n)
        self.UV.append(uv)
        self.C.append(col)
        self.M.append(mat)


def _apply(m, pts):
    pts = np.asarray(pts, float)
    return (m[:3, :3] @ pts.T).T + m[:3, 3]


def _rot(m, n):
    v = (m[:3, :3] @ np.asarray(n, float).T).T
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _slab(mesh: Mesh, poly2d, m, z0, z1, col, mat_face=LEATHER, mat_side=EDGE, side_col=None):
    if len(poly2d) < 3:
        return
    pts = poly2d if polygon_area(poly2d) > 0 else poly2d[::-1]
    tris = triangulate(pts)
    P2 = np.array(pts)
    top = _apply(m, np.c_[P2, np.full(len(P2), z1)])
    bot = _apply(m, np.c_[P2, np.full(len(P2), z0)])
    nt, nb = _rot(m, [0, 0, 1]), _rot(m, [0, 0, -1])
    for (i, j, k) in tris:
        uv = P2[[i, j, k]]
        mesh.tri(top[[i, j, k]], np.tile(nt, (3, 1)), uv, col, mat_face)
        mesh.tri(bot[[i, k, j]], np.tile(nb, (3, 1)), uv[[0, 2, 1]], col, mat_face)
    sc = side_col or col
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        e = P2[j] - P2[i]
        L = np.hypot(*e)
        if L < 1e-9:
            continue
        nn = _rot(m, [e[1] / L, -e[0] / L, 0])
        uv = np.array([[0, 0], [L, 0], [L, 1], [0, 1]], float)
        q = np.array([bot[i], bot[j], top[j], top[i]])
        mesh.tri(q[[0, 1, 2]], np.tile(nn, (3, 1)), uv[[0, 1, 2]], sc, mat_side)
        mesh.tri(q[[0, 2, 3]], np.tile(nn, (3, 1)), uv[[0, 2, 3]], sc, mat_side)


def _bend(mesh: Mesh, b: Built, pid: str, fold, col, mats):
    """Çocuk panelin menteşesindeki yuvarlak kıvrım yüzeyi."""
    p = b.panels[pid]
    f = fold.get(pid, 0.0) if isinstance(fold, dict) else fold
    th = math.radians(p.angle * f)
    if abs(th) < 1e-3:
        return
    H = b.hinge_frame(pid, fold)
    zh = p.bend_r if p.angle >= 0 else -p.t - p.bend_r
    x0, x1 = p.hinge_x
    nseg = max(3, int(abs(math.degrees(th)) / 9))
    rows = []
    for k in range(nseg + 1):
        a = th * k / nseg
        s, c = math.sin(a), math.cos(a)
        ri = [(-(0 - zh) * s, zh + (0 - zh) * c), (-(-p.t - zh) * s, zh + (-p.t - zh) * c)]
        rows.append((ri, (0, -s, c), (0, s, -c), a))
    for k in range(nseg):
        (ia, na_in, na_out, aa), (ib, nb_in, nb_out, ab) = rows[k], rows[k + 1]
        for face, (na, nb) in ((0, (na_in, nb_in)), (1, (na_out, nb_out))):
            pa = [[x0, *ia[face]], [x1, *ia[face]]]
            pb = [[x0, *ib[face]], [x1, *ib[face]]]
            q = _apply(H, [pa[0], pa[1], pb[1], pb[0]])
            nA, nB = _rot(H, na), _rot(H, nb)
            N = np.array([nA, nA, nB, nB])
            v0, v1 = -aa * 3, -ab * 3
            uv = np.array([[x0, v0], [x1, v0], [x1, v1], [x0, v1]])
            order = ([0, 1, 2], [0, 2, 3]) if face == 0 else ([0, 2, 1], [0, 3, 2])
            for o in order:
                mesh.tri(q[o], N[o], uv[o], col, BENDM)
        # uç kapakları (kenar)
        for x, sgn in ((x0, -1), (x1, 1)):
            q = _apply(H, [[x, *ia[0]], [x, *ib[0]], [x, *ib[1]], [x, *ia[1]]])
            nn = _rot(H, [sgn, 0, 0])
            for o in ([0, 1, 2], [0, 2, 3]):
                mesh.tri(q[o], np.tile(nn, (3, 1)), np.zeros((3, 2)), col, EDGE)


def _dome(mesh: Mesh, m, cx, cy, z, r, h, up, col, rings=6, seg=28):
    """Metal kubbe (çıtçıt şapkası / vida başı). up: +1 yerel +z yönüne, -1 tersine."""
    prof = [(r, 0.0), (r, h * 0.35)] + [(r * math.cos(t), h * 0.35 + h * 0.65 * math.sin(t))
                                        for t in np.linspace(0.15, math.pi / 2, rings)]
    prev = None
    for (rr, hh) in prof:
        ring = [(cx + rr * math.cos(2 * math.pi * i / seg), cy + rr * math.sin(2 * math.pi * i / seg), z + up * hh)
                for i in range(seg)]
        nrm = [(math.cos(2 * math.pi * i / seg) * (1 - hh / (h + 1e-9)), math.sin(2 * math.pi * i / seg) * (1 - hh / (h + 1e-9)),
                up * (0.3 + hh / (h + 1e-9))) for i in range(seg)]
        cur = (_apply(m, ring), _rot(m, nrm))
        if prev is not None:
            for i in range(seg):
                j = (i + 1) % seg
                q = np.array([prev[0][i], prev[0][j], cur[0][j], cur[0][i]])
                N = np.array([prev[1][i], prev[1][j], cur[1][j], cur[1][i]])
                for o in ([0, 1, 2], [0, 2, 3]) if up > 0 else ([0, 2, 1], [0, 3, 2]):
                    mesh.tri(q[o], N[o], np.zeros((3, 2)), col, METAL)
        prev = cur
    top = _apply(m, [[cx, cy, z + up * h]])[0]
    for i in range(seg):
        j = (i + 1) % seg
        q = np.array([prev[0][i], prev[0][j], top])
        N = np.array([prev[1][i], prev[1][j], _rot(m, [0, 0, up])])
        mesh.tri(q if up > 0 else q[[0, 2, 1]], N if up > 0 else N[[0, 2, 1]], np.zeros((3, 2)), col, METAL)


def _decal_line(mesh, m, a, b_, z, w, col):
    a, b_ = np.array(a), np.array(b_)
    d = b_ - a
    L = np.hypot(*d) or 1
    n = np.array([-d[1], d[0]]) / L * w / 2
    q = _apply(m, [[*(a + n), z], [*(b_ + n), z], [*(b_ - n), z], [*(a - n), z]])
    nn = _rot(m, [0, 0, 1 if z >= 0 else -1])
    for o in ([0, 1, 2], [0, 2, 3]):
        mesh.tri(q[o], np.tile(nn, (3, 1)), np.zeros((3, 2)), col, DARK)


def _disc_decal(mesh, m, cx, cy, z, r, col, seg=14):
    pts = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    P = _apply(m, [[x, y, z] for x, y in pts])
    c = _apply(m, [[cx, cy, z]])[0]
    nn = _rot(m, [0, 0, 1 if z >= 0 else -1])
    for i in range(seg):
        mesh.tri(np.array([c, P[i], P[(i + 1) % seg]]), np.tile(nn, (3, 1)), np.zeros((3, 2)), col, DARK)


def build_mesh(b: Built, fold=1.0, show_contents=True, show_hardware=True) -> Mesh:
    mesh = Mesh()
    base = _hex(b.design.renk or "")
    mats = b.matrices(fold)
    edge_col = tuple(v * 0.55 for v in base)
    for pid in b.order:
        p = b.panels[pid]
        _slab(mesh, p.poly, mats[pid], -p.t, 0.0, base, LEATHER, EDGE, edge_col)
        if p.parent:
            _bend(mesh, b, pid, fold, base, mats)
        for mk in p.marks:
            if mk.kind == Kind.SLIT:
                for z in (0.03, -p.t - 0.03):
                    _decal_line(mesh, mats[pid], (mk.prim.x0, mk.prim.y0), (mk.prim.x1, mk.prim.y1), z, 0.7, (0.08, 0.05, 0.03))
            elif mk.kind == Kind.HOLE and mk.prim.r < 2.6:
                for z in (0.03, -p.t - 0.03):
                    _disc_decal(mesh, mats[pid], mk.prim.cx, mk.prim.cy, z, mk.prim.r, (0.08, 0.05, 0.03))
    if show_hardware:
        metal = (0.78, 0.74, 0.66)
        for s in b.snaps:
            p = b.panels[s.src]
            r = {"L20": 6.25, "L24": 7.5, "mini": 5.0}.get(s.size, 6.25)
            z, up = (-p.t, -1) if s.src_side < 0 else (0.0, 1)
            _dome(mesh, mats[s.src], *s.src_xy, z, r, 2.0, up, metal)
        for f in b.fasteners:
            p = b.panels[f["panel"]]
            r = 5.0 if f["tip"] == "vida" else 4.0
            # baş: kaynak panelin dış yüzünde; karşı baş son katın dış yüzünde
            _dome(mesh, mats[p.id], *f["xy"], -p.t, r, 1.4, -1, metal)
            last = b.panels[f["layers"][-1]]
            loc = b.to_local(last.id, b.world(p.id, f["xy"]), fold)
            side = -1 if loc[2] > 0 else 1
            zz = -last.t if side < 0 else 0.0
            _dome(mesh, mats[last.id], loc[0], loc[1], zz, r, 1.4, side, metal)
    if show_contents:
        from .geometry import discretize, rounded_rect
        for cg in b.contents:
            p = b.panels[cg.panel]
            box = discretize(rounded_rect(cg.x, cg.y, cg.w, cg.h, 3.18), 15)
            z0, z1 = ((-p.t - cg.s, -p.t) if cg.under else (cg.z0 + 0.05, cg.z0 + cg.s))
            _slab(mesh, box, mats[cg.panel], z0, z1, (0.20, 0.33, 0.55), CARD_TOP, CARD_SIDE, (0.93, 0.93, 0.9))
    return mesh


# --- doku ----------------------------------------------------------------------------
_NOISE = None


def _noise_tex(n=256, seed=7):
    global _NOISE
    if _NOISE is None:
        rng = np.random.default_rng(seed)
        acc = np.zeros((n, n))
        for octave, amp in ((8, 0.5), (16, 0.25), (32, 0.15), (128, 0.1)):
            g = rng.standard_normal((octave, octave))
            im = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-9) * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)
            acc += amp * (np.asarray(im, float) / 255 - 0.5)
        _NOISE = acc / np.abs(acc).max()
    return _NOISE


# --- çizim -------------------------------------------------------------------------------
def render(b: Built, path: str | None = None, fold=1.0, az=-35.0, el=28.0, size=(1200, 900), bg=None,
           ss=2, show_contents=True, margin=0.1, shadow=True, flip=False) -> Image.Image:
    """flip=True: ürünü ters çevirip arka yüzünü gösterir (ışık yine üstten)."""
    mesh = build_mesh(b, fold, show_contents)
    P = np.stack(mesh.P)
    Nn = np.stack(mesh.N)
    if flip:
        P = P * np.array([1.0, -1.0, -1.0])
        Nn = Nn * np.array([1.0, -1.0, -1.0])
    UV = np.stack(mesh.UV)
    C = np.array(mesh.C)
    MAT = np.array(mesh.M)
    W, H = size[0] * ss, size[1] * ss

    # kamera (perspektif)
    a, e = math.radians(az), math.radians(el)
    fwd = np.array([-math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), -math.sin(e)])
    right = np.array([math.cos(a), math.sin(a), 0.0])
    up = np.cross(right, fwd)
    up /= np.linalg.norm(up)
    allp = P.reshape(-1, 3)
    ctr = (allp.min(0) + allp.max(0)) / 2
    rad = np.linalg.norm(allp - ctr, axis=1).max()
    fov = math.radians(24)
    dist = rad / math.sin(fov / 2) * 1.05
    eye = ctr - fwd * dist
    V = np.stack([right, up, -fwd])

    def project(X):
        rel = (X - eye) @ V.T
        zc = -rel[..., 2]
        return rel[..., 0] / zc, rel[..., 1] / zc, zc

    px, py, pz = project(P)
    sx_all, sy_all = px.ravel(), py.ravel()
    span = max(sx_all.max() - sx_all.min(), (sy_all.max() - sy_all.min()) * W / H)
    scale = W * (1 - 2 * margin) / span
    cx = (sx_all.max() + sx_all.min()) / 2
    cy = (sy_all.max() + sy_all.min()) / 2
    X = (px - cx) * scale + W / 2
    Y = H / 2 - (py - cy) * scale
    Z = 1.0 / pz  # perspektif doğru enterpolasyon için 1/z

    zbuf = np.zeros((H, W))
    nbuf = np.zeros((H, W, 3))
    uvbuf = np.zeros((H, W, 2))
    cbuf = np.zeros((H, W, 3))
    mbuf = np.zeros((H, W), np.int8)
    for t in range(len(P)):
        x, y, z = X[t], Y[t], Z[t]
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
        ins = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not ins.any():
            continue
        depth = l0 * z[0] + l1 * z[1] + l2 * z[2]
        bias = 1e-7 if MAT[t] in (METAL, DARK) else 0.0
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = ins & (depth + bias > sub)
        if not upd.any():
            continue
        sub[upd] = depth[upd] + bias
        w0, w1, w2 = l0[upd], l1[upd], l2[upd]
        n = w0[:, None] * Nn[t, 0] + w1[:, None] * Nn[t, 1] + w2[:, None] * Nn[t, 2]
        nbuf[y0:y1 + 1, x0:x1 + 1][upd] = n
        uvbuf[y0:y1 + 1, x0:x1 + 1][upd] = w0[:, None] * UV[t, 0] + w1[:, None] * UV[t, 1] + w2[:, None] * UV[t, 2]
        cbuf[y0:y1 + 1, x0:x1 + 1][upd] = C[t]
        mbuf[y0:y1 + 1, x0:x1 + 1][upd] = MAT[t]

    # --- gölgelendirme
    mask = mbuf > 0
    n = nbuf[mask]
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    view = -fwd
    n[(n @ view) < 0] *= -1  # iki yüzlü
    L1 = np.array([-0.35, -0.55, 0.76]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.6, 0.3, 0.45]); L2 /= np.linalg.norm(L2)
    hv = (L1 + view); hv /= np.linalg.norm(hv)
    dif = 0.72 * np.clip(n @ L1, 0, 1) + 0.25 * np.clip(n @ L2, 0, 1)
    sky = 0.30 + 0.12 * n[:, 2]
    mat = mbuf[mask]
    col = cbuf[mask].copy()
    uv = uvbuf[mask]
    tex = _noise_tex()
    ti = (np.abs(uv * 2.2).astype(int)) % tex.shape[0]
    grain = tex[ti[:, 1], ti[:, 0]]
    ti2 = (np.abs(uv * 0.35).astype(int)) % tex.shape[0]
    mottle = tex[ti2[:, 1], ti2[:, 0]]
    crazy = b.design.malzeme == "crazy_horse"
    is_l = np.isin(mat, (LEATHER, BENDM))
    col[is_l] *= (1 + 0.07 * grain[is_l] + (0.16 if crazy else 0.06) * mottle[is_l])[:, None]
    bendm = mat == BENDM
    if crazy:
        col[bendm] = np.clip(col[bendm] * 1.35 + 0.05, 0, 1)  # pull-up: kıvrımda renk açılır
    shin = np.where(mat == METAL, 60.0, np.where(mat == CARD_TOP, 40.0, 9.0))
    ks = np.where(mat == METAL, 0.9, np.where(mat == CARD_TOP, 0.35, 0.10 if not crazy else 0.18))
    spec = ks * np.clip(n @ hv, 0, 1) ** shin
    shade = col * (dif + sky)[:, None] + spec[:, None]
    edge = mat == EDGE
    shade[edge] = col[edge] * (0.55 * np.clip(n[edge] @ L1, 0, 1) + 0.45)[:, None] + 0.04
    dark = mat == DARK
    shade[dark] = col[dark]

    # --- arka plan + yumuşak gölge
    yy = np.linspace(0, 1, H)[:, None]
    bg_top = np.array([0.965, 0.955, 0.94]) if bg is None else np.array(bg) / 255
    bg_bot = bg_top * 0.9
    img = np.broadcast_to(bg_top * (1 - yy[..., None]) + bg_bot * yy[..., None], (H, W, 3)).copy()
    if shadow:
        zmin = allp[:, 2].min()
        ld = -L1
        k = (allp[:, 2] - zmin) / max(1e-6, -ld[2])
        ground = allp + ld * k[:, None]
        ground[:, 2] = zmin
        gx_, gy_, gz_ = project(ground.reshape(P.shape))
        GX = (gx_ - cx) * scale + W / 2
        GY = H / 2 - (gy_ - cy) * scale
        smask = Image.new("L", (W, H), 0)
        from PIL import ImageDraw
        dr = ImageDraw.Draw(smask)
        for t in range(len(P)):
            dr.polygon([(GX[t, i], GY[t, i]) for i in range(3)], fill=255)
        # temas gölgesi (dik izdüşüm)
        down = allp.copy(); down[:, 2] = zmin
        dx_, dy_, _ = project(down.reshape(P.shape))
        DX = (dx_ - cx) * scale + W / 2
        DY = H / 2 - (dy_ - cy) * scale
        cmask = Image.new("L", (W, H), 0)
        dr2 = ImageDraw.Draw(cmask)
        for t in range(len(P)):
            dr2.polygon([(DX[t, i], DY[t, i]) for i in range(3)], fill=255)
        s1 = np.asarray(smask.filter(ImageFilter.GaussianBlur(W / 90)), float) / 255
        s2 = np.asarray(cmask.filter(ImageFilter.GaussianBlur(W / 300)), float) / 255
        img *= (1 - 0.28 * s1 - 0.22 * s2)[..., None]
    img[mask] = np.clip(shade, 0, 1)
    # ince siluet çizgisi (derinlik kopukluğu)
    zf = np.where(mask, zbuf, 0)
    sil = np.zeros((H, W), bool)
    thr = np.abs(zf).max() * 0.004 if mask.any() else 1
    sil[:, 1:] |= np.abs(zf[:, 1:] - zf[:, :-1]) > thr
    sil[1:, :] |= np.abs(zf[1:, :] - zf[:-1, :]) > thr
    img[sil] *= 0.6
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    if ss > 1:
        out = out.resize(size, Image.LANCZOS)
    if path:
        out.save(path)
    return out

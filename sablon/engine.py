"""Tasarım (DSL) → açınım kalıbı + 3B model + özellik izdüşümleri.

Ana fikirler
* Her panelin bir yerel çerçevesi var. Çocuk panel, ebeveyn kenarına menteşeyle bağlı.
* Deri keskin katlanmaz: iç yarıçapı r = BEND·t olan bir kıvrımla bükülür. Açınımda çocuk,
  kıvrımın nötr ekseni uzunluğu kadar uzaklaştırılır:
  kat_payi = radyan(|açı|) * (r + t/2). Bu şerit kalıba eklenir, kat çizgisi şeridin ortasına
  çizilir. Panel ölçüleri bitmiş ölçülerdir (kıvrımın başladığı yerden).
* 3B'de çocuk, iç yüzden r yukarıdaki (dağ katta dış yüzden r aşağıdaki) eksen etrafında
  açı × katlama_oranı kadar döner; kıvrım bölgesi ayrıca eğrisel yüzey olarak çizilir.
* Kilit yarığı, çıtçıt, perçin, vida gibi özellikler bitmiş (katlı) hâlde 3B'ye taşınır ve
  hedef panellere izdüşürülür: delikler/yarıklar katlanınca birebir üst üste gelir.
* `yariktan_gecer` panel (kilit kafası), hedef panelin öbür yüzüne geçirilir.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import materials as M
from .design import Icerik, Panel, Parca, Tasarim
from .expr import ExprError, evaluate
from .geometry import (Affine2, Circle, Line, Segment, arc_from_3pts, discretize, dist_to_polygon_edge, fillet,
                       point_in_polygon)
from .pattern import Kind, Piece, Text

EDGES = ("alt", "sag", "ust", "sol")
BEND = 0.5  # kıvrım iç yarıçapı / kalınlık


@dataclass
class Finding:
    level: str  # hata | uyari | bilgi
    code: str
    message: str
    where: str = ""

    def as_dict(self):
        return {"level": self.level, "code": self.code, "message": self.message, "where": self.where}


class BuildError(Exception):
    def __init__(self, findings: list[Finding]):
        super().__init__("; ".join(f.message for f in findings))
        self.findings = findings


@dataclass
class Mark:
    kind: Kind
    prim: object


@dataclass
class PanelGeo:
    id: str
    part: str
    spec: Panel
    w: float
    h: float
    angle: float
    taper: float
    t: float
    corners: list[float]                 # sol_alt, sag_alt, sag_ust, sol_ust
    outline: list[Segment] = field(default_factory=list)
    poly: list = field(default_factory=list)
    quad: list = field(default_factory=list)
    parent: str | None = None
    edge: str = ""
    hinge_o: tuple = (0.0, 0.0)          # ebeveyn yerelinde menteşe başlangıcı
    hinge_d: tuple = (1.0, 0.0)
    allow: float = 0.0
    flat: Affine2 = field(default_factory=Affine2)
    marks: list[Mark] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    child_edges: set = field(default_factory=set)
    mount: object = None                 # Montaj (kök + monte parça)
    mount_z: float = 0.0
    hinge_x: tuple = (0.0, 0.0)          # menteşe örtüşme aralığı (çocuk x'inde)
    through: float = 0.0                 # yarıktan geçiş kayması (3B)

    @property
    def bend_r(self) -> float:
        return BEND * self.t

    @property
    def edge_lines(self):
        V = self.quad
        return {"alt": (V[0], V[1]), "sag": (V[1], V[2]), "ust": (V[2], V[3]), "sol": (V[3], V[0])}


@dataclass
class ContentGeo:
    spec: Icerik
    panel: str
    x: float
    y: float
    w: float
    h: float
    s: float          # yığın kalınlığı
    under: bool       # True: monte cep panelinin altında (cep içinde)
    z0: float = 0.0   # içeriğin oturduğu yükseklik (altına giren katlar, ör. kilit kafası)


@dataclass
class SnapPair:
    no: int
    kind: str          # citcit
    size: str
    src: str
    dst: str | None
    src_xy: tuple
    dst_xy: tuple | None
    gap: float
    src_side: int = -1   # +1: iç yüz, -1: dış yüz (şapkanın görüneceği yüz)
    dst_side: int = 1    # erkek parçanın oturduğu yüz


@dataclass
class Built:
    design: Tasarim
    env: dict
    panels: dict[str, PanelGeo]
    parts: dict[str, Parca]
    part_t: dict[str, float]
    part_mat: dict[str, str]
    roots: dict[str, str]
    order: list[str]
    contents: list[ContentGeo]
    snaps: list[SnapPair]
    findings: list[Finding]
    hinge_lines: dict = field(default_factory=dict)
    fasteners: list = field(default_factory=list)
    locks: list = field(default_factory=list)

    # ---- 3B dönüşümler -------------------------------------------------------
    def hinge_frame(self, pid: str, fold=1.0) -> np.ndarray:
        """Çocuk panelin menteşe çerçevesi (dönmeden önce): kıvrım yüzeyini çizmek için."""
        p = self.panels[pid]
        return self.matrix(p.parent, fold) @ _T(p.hinge_o[0], p.hinge_o[1], 0) @ _B(p.hinge_d)

    def matrix(self, pid: str, fold: float | dict = 1.0) -> np.ndarray:
        cache: dict = {}
        return self._matrix(pid, fold, cache)

    def matrices(self, fold: float | dict = 1.0) -> dict[str, np.ndarray]:
        cache: dict = {}
        return {pid: self._matrix(pid, fold, cache) for pid in self.order}

    def _fold_of(self, p: PanelGeo, fold) -> float:
        if isinstance(fold, dict):
            return fold.get(p.id, 0.0)
        return fold

    def _matrix(self, pid, fold, cache) -> np.ndarray:
        if pid in cache:
            return cache[pid]
        p = self.panels[pid]
        if p.parent is None:
            if p.mount is not None and p.mount.ana_panel:
                host = self.panels[p.mount.ana_panel]
                m = self._matrix(host.id, fold, cache) @ _T(self.env_num(p.mount.x), self.env_num(p.mount.y), p.mount_z)
            else:
                m = _T(self._part_offset(p.part), 0, 0)
        else:
            f = self._fold_of(p, fold)
            a = math.radians(p.angle * f)
            zh = p.bend_r if p.angle >= 0 else -p.t - p.bend_r
            m = (self._matrix(p.parent, fold, cache) @ _T(p.hinge_o[0], p.hinge_o[1], 0)
                 @ _B(p.hinge_d) @ _T(0, 0, zh) @ _Rx(a) @ _T(0, 0, -zh))
            if p.through:
                m = m @ _T(0, 0, p.through * f)
        cache[pid] = m
        return m

    def env_num(self, s) -> float:
        return evaluate(s, self.env)

    def _part_offset(self, part: str) -> float:
        x = 0.0
        for pid, root in self.roots.items():
            if pid == part:
                return x
            rp = self.panels[root]
            if rp.mount is None or not rp.mount.ana_panel:
                x += max(rp.w, rp.h) + 40
        return x

    def world(self, pid: str, xy, z: float = 0.0, fold=1.0) -> np.ndarray:
        return (self.matrix(pid, fold) @ np.array([xy[0], xy[1], z, 1.0]))[:3]

    def to_local(self, pid: str, pw: np.ndarray, fold=1.0) -> np.ndarray:
        inv = np.linalg.inv(self.matrix(pid, fold))
        return (inv @ np.append(pw, 1.0))[:3]

    # ---- açınım kalıbı ------------------------------------------------------
    def pieces(self) -> list[Piece]:
        out = []
        for part_id, part in self.parts.items():
            pans = [p for p in self.panels.values() if p.part == part_id]
            cuts, folds = _classify(pans, self.hinge_lines.get(part_id, []))
            mat = M.material(self.part_mat[part_id])
            piece = Piece(part.ad or part_id, part.adet,
                          f"{mat.ad}, {self.part_t[part_id]:.1f} mm. Çizimde görünen yüz iç (süet) yüzdür.")
            piece.add_all(Kind.CUT, cuts)
            for (ln, label) in folds:
                piece.add(Kind.FOLD, ln)
                mx, my = (ln.x0 + ln.x1) / 2, (ln.y0 + ln.y1) / 2
                ang = math.degrees(math.atan2(ln.y1 - ln.y0, ln.x1 - ln.x0))
                if ang > 90 or ang <= -90:
                    ang -= 180
                piece.texts.append(Text(mx, my + 0.8, label, 2.2, ang))
            for p in pans:
                for mk in p.marks:
                    piece.add(mk.kind, p.flat.seg(mk.prim))
                for tx in p.texts:
                    x, y = p.flat.apply((tx.x, tx.y))
                    piece.texts.append(Text(x, y, tx.text, tx.size, _upright(tx.angle + p.flat.angle), tx.anchor))
                obstacles = [(m.prim.cx, m.prim.cy, m.prim.r + 2) for m in p.marks if isinstance(m.prim, Circle)]
                obstacles += [(t_.x, t_.y + 1, 3.0) for t_ in p.texts]
                ly = max((p.h * k for k in (0.5, 0.35, 0.65, 0.2, 0.8)),
                         key=lambda yy: min([math.hypot((ox - p.w / 2) / 3, oy - yy) - rr for ox, oy, rr in obstacles] or [99])
                         - abs(yy - p.h / 2) * 0.05)
                cx, cy = p.flat.apply((p.w / 2, ly))
                ang = p.flat.angle
                if ang > 90 or ang <= -90:
                    ang -= 180
                piece.texts.append(Text(cx, cy, (p.spec.ad or p.id).upper(), min(4.5, max(2.2, min(p.w, p.h) / 8)), ang))
            root = self.panels[self.roots[part_id]]
            gx0 = root.flat.apply((root.w * 0.85, root.h * 0.3))
            gx1 = root.flat.apply((root.w * 0.85, root.h * 0.7))
            if root.h > 25 and root.w > 25:
                piece.add(Kind.GRAIN, Line(gx0[0], gx0[1], gx1[0], gx1[1]))
            out.append(piece)
        return out

    def area_cm2(self, part_id: str) -> float:
        pans = [p for p in self.panels.values() if p.part == part_id]
        from .geometry import polygon_area
        a = 0.0
        for p in pans:
            a += abs(polygon_area(p.poly))
            if p.parent:
                a += p.allow * p.w
        return a / 100.0

    def finished_size(self) -> tuple[float, float, float]:
        pts = []
        for pid in self.order:
            p = self.panels[pid]
            m = self.matrix(pid, 1.0)
            for (x, y) in p.poly[:: max(1, len(p.poly) // 24)] + p.quad:
                for z in (0.0, -p.t):
                    pts.append((m @ np.array([x, y, z, 1.0]))[:3])
        a = np.array(pts)
        ext = sorted(a.max(0) - a.min(0), reverse=True)
        return tuple(float(v) for v in ext)


def _upright(a: float) -> float:
    a = (a + 180) % 360 - 180
    if a > 90:
        a -= 180
    elif a <= -90:
        a += 180
    return a


def fold_step_numbers(panels) -> dict[int, int]:
    """kat_sirasi → talimattaki 'Katlama n' numarası (yalnızca gerçekten katlanan seviyeler sayılır)."""
    levels = sorted({p.spec.kat_sirasi for p in panels if p.parent and abs(p.angle) > 1 and p.spec.kat_sirasi})
    return {lv: i + 1 for i, lv in enumerate(levels)}


# --- matris yardımcıları ---------------------------------------------------------
def _T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def _B(d):
    dx, dy = d
    m = np.eye(4)
    m[:3, :3] = [[dx, -dy, 0], [dy, dx, 0], [0, 0, 1]]
    return m


def _Rx(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[1:3, 1:3] = [[c, -s], [s, c]]
    return m


# --- panel ana hattı ---------------------------------------------------------------
def panel_outline(w, h, taper, corners, profiles: dict, env, where, findings) -> tuple[list, list]:
    """Yerel ana hat segmentleri ve taban dörtgeni (köşe noktaları)."""
    V = [(0.0, 0.0), (w, 0.0), (w - taper, h), (taper, h)]
    nodes = []   # [(nokta, yarıçap)]
    arcs = []    # her düğümden sonraki kenar: None (doğru) veya yay orta noktası

    def add_node(p, r=0.0):
        nodes.append((p, r))
        arcs.append(None)

    def edge_profile(a, b, prof, name):
        L = math.dist(a, b)
        e = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        out = (e[1], -e[0])
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        tip = prof.tip
        try:
            val = evaluate(prof.olcu, env) if prof.olcu not in ("", None) else 0.0
        except ExprError as ex:
            findings.append(Finding("hata", "ifade", f"{where} {name} profili: {ex}", where))
            val = 0.0
        if tip == "duz" or (tip != "yuvarlak" and val <= 0):
            return
        if tip == "sivri":
            add_node((mid[0] + out[0] * val, mid[1] + out[1] * val))
        elif tip in ("kavis", "yuvarlak"):
            d = L / 2 if tip == "yuvarlak" else min(val, L / 2)
            arcs[-1] = (mid[0] + out[0] * d, mid[1] + out[1] * d)
        elif tip == "oyuk":
            r = min(val, L / 2 - 1.0)
            if r <= 0:
                return
            add_node((mid[0] - e[0] * r, mid[1] - e[1] * r))
            arcs[-1] = (mid[0] - out[0] * r, mid[1] - out[1] * r)
            add_node((mid[0] + e[0] * r, mid[1] + e[1] * r))

    add_node(V[0], corners[0])
    add_node(V[1], corners[1])
    edge_profile(V[1], V[2], profiles["sag"], "sag")
    add_node(V[2], corners[2])
    edge_profile(V[2], V[3], profiles["ust"], "üst")
    add_node(V[3], corners[3])
    edge_profile(V[3], V[0], profiles["sol"], "sol")

    n = len(nodes)
    # köşe yuvarlatma: iki yanı da doğru olan düğümlerde
    trimmed = []  # her düğüm için (giriş noktası, yay|None, çıkış noktası)
    for i, (p, r) in enumerate(nodes):
        prev_is_line = arcs[i - 1] is None
        next_is_line = arcs[i] is None
        res = None
        if r > 0 and prev_is_line and next_is_line:
            res = fillet(nodes[i - 1][0], p, nodes[(i + 1) % n][0], r)
            if res is None:
                findings.append(Finding("uyari", "kose_sigmiyor", f"{where}: {r:.1f} mm köşe yarıçapı sığmıyor, köşe keskin bırakıldı.", where))
        elif r > 0:
            findings.append(Finding("uyari", "kose_profil", f"{where}: profilli kenara komşu köşe yuvarlatılamaz.", where))
        trimmed.append(res if res else (p, None, p))
    segs = []
    for i in range(n):
        t_in, arc, t_out = trimmed[i]
        if arc is not None:
            segs.append(arc)
        nxt_in = trimmed[(i + 1) % n][0]
        if arcs[i] is None:
            if math.dist(t_out, nxt_in) > 1e-9:
                segs.append(Line(t_out[0], t_out[1], nxt_in[0], nxt_in[1]))
        else:
            segs.append(arc_from_3pts(t_out, arcs[i], nxt_in))
    return segs, V


# --- kesim / kat sınıflandırma ----------------------------------------------------
def _key(ln: Line):
    if abs(ln.y0 - ln.y1) < 1e-6:
        return ("h", round(ln.y0, 3)), (min(ln.x0, ln.x1), max(ln.x0, ln.x1))
    if abs(ln.x0 - ln.x1) < 1e-6:
        return ("v", round(ln.x0, 3)), (min(ln.y0, ln.y1), max(ln.y0, ln.y1))
    return None, None


def _classify(pans: list[PanelGeo], hinge_data: list) -> tuple[list, list]:
    """Panel ve kat şeridi kenarlarından kesim çizgilerini çıkarır.

    hinge_data: [(iç_çizgiler[list[Line]], şerit_kenarları[list[Line]], kat_çizgisi, etiket)]
    """
    lines, cuts = [], []
    for p in pans:
        for s in p.outline:
            fs = p.flat.seg(s)
            (lines if isinstance(fs, Line) else cuts).append(fs)
    internal = []
    folds = []
    for inner, strip_edges, fold_line, label in hinge_data:
        internal += inner
        lines += strip_edges
        folds.append((fold_line, label))
    groups: dict = {}
    for ln in lines:
        k, iv = _key(ln)
        if k is None:
            cuts.append(ln)
        else:
            exact = ln.y0 if k[0] == "h" else ln.x0
            groups.setdefault(k, {"iv": [], "in": [], "c": exact})["iv"].append(iv)
    for ln in internal:
        k, iv = _key(ln)
        if k is not None and k in groups:
            groups[k]["in"].append(iv)
    for (axis, _), g in groups.items():
        c = g["c"]
        bps = sorted({round(v, 6) for iv in g["iv"] + g["in"] for v in iv})
        run = None
        for a, b in zip(bps, bps[1:]):
            if b - a < 1e-6:
                continue
            m = (a + b) / 2
            covered = any(lo - 1e-6 <= m <= hi + 1e-6 for lo, hi in g["iv"])
            inner = any(lo - 1e-6 <= m <= hi + 1e-6 for lo, hi in g["in"])
            if covered and not inner:
                run = (run[0], b) if run and abs(run[1] - a) < 1e-6 else (_flush(run, axis, c, cuts) or (a, b))
            else:
                _flush(run, axis, c, cuts)
                run = None
        _flush(run, axis, c, cuts)
    return cuts, folds


def _flush(run, axis, c, cuts):
    if run:
        a, b = run
        cuts.append(Line(a, c, b, c) if axis == "h" else Line(c, a, c, b))
    return None


# --- ana inşa ----------------------------------------------------------------------
def build(design: Tasarim) -> Built:
    F: list[Finding] = []
    env: dict[str, float] = {"t": 0.0, "kart_g": 85.6, "kart_y": 53.98, "kart_k": 0.76}
    try:
        env["t"] = evaluate(design.kalinlik, env)
    except ExprError as e:
        raise BuildError([Finding("hata", "ifade", f"kalınlık: {e}")])
    for v in design.degiskenler:
        try:
            env[v.ad] = evaluate(v.deger, env)
        except ExprError as e:
            F.append(Finding("hata", "ifade", f"değişken {v.ad}: {e}", v.ad))
    if any(f.level == "hata" for f in F):
        raise BuildError(F)

    def num(s, where, default=None):
        if (s is None or str(s).strip() == "") and default is not None:
            return default
        try:
            return evaluate(s, env)
        except ExprError as e:
            F.append(Finding("hata", "ifade", f"{where}: {e}", where))
            return default if default is not None else 0.0

    panels: dict[str, PanelGeo] = {}
    parts: dict[str, Parca] = {}
    part_t: dict[str, float] = {}
    part_mat: dict[str, str] = {}
    roots: dict[str, str] = {}
    order: list[str] = []
    hinge_lines: dict[str, list] = {}

    if design.malzeme not in M.MATERIALS:
        F.append(Finding("hata", "malzeme", f"Bilinmeyen malzeme '{design.malzeme}' ({', '.join(M.MATERIALS)})"))
    seen_parts = set()
    for part in design.parcalar:
        if part.id in seen_parts:
            F.append(Finding("hata", "kimlik", f"Parça kimliği tekrarlanıyor: {part.id}"))
        seen_parts.add(part.id)
        parts[part.id] = part
        part_t[part.id] = num(part.kalinlik, f"{part.id}.kalinlik", env["t"])
        mk = part.malzeme or design.malzeme
        if mk not in M.MATERIALS:
            F.append(Finding("hata", "malzeme", f"{part.id}: bilinmeyen malzeme '{mk}'"))
            mk = "vaketa"
        part_mat[part.id] = mk
        t = part_t[part.id]
        ids = [p.id for p in part.paneller]
        rts = [p for p in part.paneller if not p.ebeveyn]
        if len(rts) != 1:
            F.append(Finding("hata", "kok", f"{part.id}: tam olarak bir kök panel (ebeveyni boş) olmalı, {len(rts)} var."))
            continue
        for p in part.paneller:
            if p.id in panels:
                F.append(Finding("hata", "kimlik", f"Panel kimliği tekrarlanıyor: {p.id}"))
                continue
            if p.ebeveyn and p.ebeveyn not in ids:
                F.append(Finding("hata", "ebeveyn", f"{p.id}: ebeveyn '{p.ebeveyn}' bu parçada yok."))
            w = num(p.genislik, f"{p.id}.genislik")
            h = num(p.yukseklik, f"{p.id}.yukseklik")
            if w <= 0 or h <= 0:
                F.append(Finding("hata", "olcu", f"{p.id}: genişlik/yükseklik pozitif olmalı ({w:.1f} × {h:.1f})."))
                w, h = max(w, 1.0), max(h, 1.0)
            taper = num(p.daralma, f"{p.id}.daralma", 0.0)
            if taper * 2 >= w:
                F.append(Finding("hata", "daralma", f"{p.id}: daralma genişliğin yarısından büyük."))
                taper = 0.0
            c = p.koseler
            corners = [max(0.0, num(x, f"{p.id}.kose", 0.0)) for x in (c.sol_alt, c.sag_alt, c.sag_ust, c.sol_ust)]
            ang = num(p.aci, f"{p.id}.aci", 0.0) if p.ebeveyn else 0.0
            pg = PanelGeo(p.id, part.id, p, w, h, ang, taper, t, corners)
            if p.ebeveyn:
                pg.parent, pg.edge = p.ebeveyn, p.kenar
                if p.kenar not in EDGES:
                    F.append(Finding("hata", "kenar", f"{p.id}: geçersiz bağlantı kenarı '{p.kenar}'."))
                if corners[0] or corners[1]:
                    F.append(Finding("uyari", "mentese_kose", f"{p.id}: menteşe tarafındaki köşeler yuvarlatılmamalı.", p.id))
            panels[p.id] = pg
        roots[part.id] = rts[0].id
        if part.montaj.ana_panel:
            panels[rts[0].id].mount = part.montaj

    if any(f.level == "hata" for f in F):
        raise BuildError(F)

    # Ağaç sırası + döngü kontrolü
    for part_id, root in roots.items():
        queue = [root]
        visited = set()
        while queue:
            pid = queue.pop(0)
            if pid in visited:
                F.append(Finding("hata", "dongu", f"{pid}: panel ağacında döngü."))
                break
            visited.add(pid)
            order.append(pid)
            queue += [q.id for q in panels.values() if q.parent == pid]
        orphans = [p.id for p in panels.values() if p.part == part_id and p.id not in visited]
        if orphans:
            F.append(Finding("hata", "kopuk", f"Köke bağlanmayan paneller: {', '.join(orphans)}"))
    for pid in order:
        p = panels[pid]
        if p.parent:
            panels[p.parent].child_edges.add(p.edge)

    # Ana hatlar
    for pid in order:
        p = panels[pid]
        profs = {"ust": p.spec.profil_ust, "sol": p.spec.profil_sol, "sag": p.spec.profil_sag}
        for e in ("ust", "sol", "sag"):
            if e in p.child_edges and profs[e].tip != "duz":
                F.append(Finding("hata", "profil_mentese", f"{pid}: '{e}' kenarına panel bağlı, profil verilemez."))
        p.outline, p.quad = panel_outline(p.w, p.h, p.taper, p.corners, profs, env, pid, F)
        p.poly = discretize(p.outline)

    # Menteşeler: yerel konum + açınım dönüşümü
    for pid in order:
        p = panels[pid]
        if not p.parent:
            continue
        par = panels[p.parent]
        if par.parent and p.edge == "alt":
            F.append(Finding("hata", "kenar", f"{pid}: '{par.id}' panelinin alt kenarı zaten menteşe; başka kenar seçin."))
            continue
        if par.taper and p.edge in ("sol", "sag"):
            F.append(Finding("hata", "kenar", f"{pid}: daralan panelin yan kenarına panel bağlanamaz."))
            continue
        w, h, a = par.w, par.h, par.taper
        mid, d, L = {"alt": ((w / 2, 0.0), (-1.0, 0.0), w), "ust": ((w / 2, h), (1.0, 0.0), w - 2 * a),
                     "sag": ((w, h / 2), (0.0, -1.0), h), "sol": ((0.0, h / 2), (0.0, 1.0), h)}[p.edge]
        n = (-d[1], d[0])
        off = num(p.spec.ofset, f"{pid}.ofset", 0.0)
        s = off * (d[0] + d[1])  # +x / +y yönüne çevir
        o = (mid[0] + d[0] * (s - p.w / 2), mid[1] + d[1] * (s - p.w / 2))
        lo, hi = max(-L / 2, s - p.w / 2), min(L / 2, s + p.w / 2)
        if hi - lo <= 0.5:
            F.append(Finding("hata", "mentese", f"{pid}: '{par.id}' panelinin {p.edge} kenarıyla örtüşmüyor (ofset?)."))
            continue
        allow = math.radians(abs(p.angle)) * (BEND * p.t + p.t / 2)
        p.hinge_o, p.hinge_d, p.allow = o, d, allow
        p.hinge_x = (lo - (s - p.w / 2), hi - (s - p.w / 2))
        p.flat = par.flat.compose(Affine2(o[0] + n[0] * allow, o[1] + n[1] * allow, d[0], d[1]))
        # menteşe çizgileri (ebeveyn yerelinde → açınım)
        A = (mid[0] + d[0] * lo, mid[1] + d[1] * lo)
        B = (mid[0] + d[0] * hi, mid[1] + d[1] * hi)
        A2 = (A[0] + n[0] * allow, A[1] + n[1] * allow)
        B2 = (B[0] + n[0] * allow, B[1] + n[1] * allow)
        Am = (A[0] + n[0] * allow / 2, A[1] + n[1] * allow / 2)
        Bm = (B[0] + n[0] * allow / 2, B[1] + n[1] * allow / 2)
        tf = par.flat.seg
        inner = [tf(Line(*A, *B)), tf(Line(*A2, *B2))]
        strip = [tf(Line(*A, *B)), tf(Line(*A2, *B2))]
        if allow > 1e-6:
            strip += [tf(Line(*A, *A2)), tf(Line(*B, *B2))]
        kind = "vadi" if p.angle >= 0 else "dağ"
        step_no = fold_step_numbers(panels.values()).get(p.spec.kat_sirasi, "")
        label = f"katlama {step_no}: {kind} {abs(p.angle):.0f}°"
        if abs(p.angle) < 1e-6:
            label = "kat yok (düz)"
        hinge_lines.setdefault(p.part, []).append((inner, strip, tf(Line(*Am, *Bm)), label))

    if any(f.level == "hata" for f in F):
        raise BuildError(F)

    b = Built(design, env, panels, parts, part_t, part_mat, roots, order, [], [], F, hinge_lines)
    _overlap_check(b)
    _mount_and_contents(b, num)
    _features(b, num)
    _settle_contents(b)
    if any(f.level == "hata" for f in F):
        raise BuildError(F)
    return b


def _overlap_check(b: Built):
    for part in b.parts:
        pans = [p for p in b.panels.values() if p.part == part]
        polys = [(p.id, [p.flat.apply(q) for q in p.poly]) for p in pans]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                (ia, pa), (ib, pb) = polys[i], polys[j]
                if _polys_overlap(pa, pb):
                    b.findings.append(Finding("hata", "acinim_cakisma",
                                              f"Açınımda '{ia}' ile '{ib}' panelleri üst üste biniyor; tek parçadan kesilemez "
                                              "(ayrı parça yapın, ofset/ölçü değiştirin).", f"{ia},{ib}"))


def _polys_overlap(a, b) -> bool:
    def strictly_inside(p, poly):
        return point_in_polygon(p, poly) and dist_to_polygon_edge(p, poly) > 0.05

    if any(strictly_inside(p, b) for p in a) or any(strictly_inside(p, a) for p in b):
        return True
    ca = (sum(p[0] for p in a) / len(a), sum(p[1] for p in a) / len(a))
    cb = (sum(p[0] for p in b) / len(b), sum(p[1] for p in b) / len(b))
    if strictly_inside(ca, b) or strictly_inside(cb, a):
        return True
    for i in range(len(a)):
        p1, p2 = a[i], a[(i + 1) % len(a)]
        for j in range(len(b)):
            p3, p4 = b[j], b[(j + 1) % len(b)]
            if _proper_cross(p1, p2, p3, p4):
                return True
    return False


def _proper_cross(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-6 else (1 if v > 0 else -1)

    o1, o2, o3, o4 = orient(p1, p2, p3), orient(p1, p2, p4), orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 * o2 < 0 and o3 * o4 < 0


# --- monte parçalar ve içerik --------------------------------------------------------
def _mount_and_contents(b: Built, num):
    d = b.design
    F = b.findings
    for ic in d.icerikler:
        if ic.panel not in b.panels:
            F.append(Finding("hata", "icerik", f"İçerik paneli '{ic.panel}' yok."))
            continue
        p = b.panels[ic.panel]
        if ic.tip == "ozel":
            w = num(ic.genislik, "icerik.genislik", 50.0)
            h = num(ic.yukseklik, "icerik.yukseklik", 50.0)
            k = num(ic.kalinlik, "icerik.kalinlik", 1.0)
        else:
            w, h, k = M.CONTENTS.get(ic.tip, M.CONTENTS["kart"])
        s = k * max(1, ic.adet)
        x = num(ic.x, "icerik.x", (p.w - w) / 2)
        y = num(ic.y, "icerik.y", 0.3)
        under = p.mount is not None and p.mount.ana_panel != "" and p.parent is None
        b.contents.append(ContentGeo(ic, p.id, x, y, w, h, s, under))
        if under:
            p.lift += s
    placed: dict = {}
    for part_id, root in b.roots.items():
        rp = b.panels[root]
        if rp.mount is None or not rp.mount.ana_panel:
            continue
        mt = rp.mount
        if mt.ana_panel not in b.panels:
            F.append(Finding("hata", "montaj", f"{part_id}: ana panel '{mt.ana_panel}' yok."))
            continue
        host = b.panels[mt.ana_panel]
        if host.part == part_id:
            F.append(Finding("hata", "montaj", f"{part_id}: parça kendi paneline monte edilemez."))
            continue
        x, y = num(mt.x, f"{part_id}.montaj.x", 0.0), num(mt.y, f"{part_id}.montaj.y", 0.0)
        box = (x, y, x + rp.w, y + rp.h)
        key = (host.id, mt.yuz)
        below = 0.0
        for (bx, extra) in placed.get(key, []):
            if bx[0] < box[2] and box[0] < bx[2] and bx[1] < box[3] and box[1] < bx[3]:
                below += extra
        rp.mount_z = below + rp.t + rp.lift if mt.yuz == "ic" else -host.t - below
        placed.setdefault(key, []).append((box, rp.t + rp.lift))
        if x < -0.01 or y < -0.01 or x + rp.w > host.w + 0.01 or y + rp.h > host.h + 0.01:
            F.append(Finding("uyari", "montaj_tasma", f"'{part_id}' parçası '{host.id}' panelinin dışına taşıyor.", part_id))


# --- özellikler -------------------------------------------------------------------------
def _features(b: Built, num):
    d = b.design
    F = b.findings
    snap_no = 0
    for i, f in enumerate(d.ozellikler):
        where = f"özellik {i + 1} ({f.tip} @ {f.panel})"
        if f.panel not in b.panels:
            F.append(Finding("hata", "ozellik_panel", f"{where}: panel yok."))
            continue
        p = b.panels[f.panel]
        targets = []
        for t in f.hedefler:
            if t == p.id:
                continue
            if t not in b.panels:
                F.append(Finding("hata", "hedef", f"{where}: hedef panel '{t}' yok."))
            else:
                targets.append(t)
        x, y = num(f.x, where, p.w / 2), num(f.y, where, p.h / 2)

        if f.tip == "citcit":
            snap_no += 1
            sn = M.SNAPS.get(f.boyut or "L20")
            if sn is None:
                F.append(Finding("hata", "citcit_boyut", f"{where}: çıtçıt boyutu '{f.boyut}' (mini/L20/L24)."))
                continue
            dst = _resolve_target(b, p, (x, y), targets, where)
            _snap_marks(p, (x, y), sn.sapka_cap, sn.dikme_delik, f"Ç{snap_no} şapka+dişi")
            pair = SnapPair(snap_no, "citcit", sn.key, p.id, None, (x, y), None, 0.0)
            if dst:
                tid, loc = dst
                _snap_marks(b.panels[tid], (loc[0], loc[1]), sn.sapka_cap, sn.dikme_delik, f"Ç{snap_no} erkek+dikme")
                pair.dst, pair.dst_xy = tid, (float(loc[0]), float(loc[1]))
                pair.dst_side = 1 if loc[2] > 0 else -1
                back = b.to_local(p.id, b.world(tid, (loc[0], loc[1])))
                pair.src_side = -1 if back[2] > 0 else 1
                pair.gap = slab_gap(b, p.id, (x, y), tid)
            b.snaps.append(pair)
            continue

        if f.tip in ("percin", "vida", "delik"):
            fs = M.FASTENERS.get(f.tip)
            dia = num(f.boyut, where, fs.delik if fs else 4.0)
            placements = [(p, (x, y))] + _through(b, p, [(x, y)], targets, where)
            for tp, (lx, ly) in placements:
                tp.marks.append(Mark(Kind.HOLE, Circle(lx, ly, dia / 2)))
                if fs:
                    tp.marks.append(Mark(Kind.GUIDE, Circle(lx, ly, fs.bas_cap / 2)))
            if fs:
                p.texts.append(Text(x, y - fs.bas_cap / 2 - 3.0, "perçin" if f.tip == "percin" else "vida", 2.0))
                b.fasteners.append({"tip": f.tip, "panel": p.id, "xy": (x, y),
                                    "layers": [tp.id for tp, _ in placements], "where": where})
            continue

        if f.tip in ("yarik", "kilit_yarigi"):
            L, a = num(f.genislik, where, 10.0), math.radians(num(f.aci, where, 0.0))
            relief = 1.5
            pts = [(x, y), (x + L * math.cos(a), y + L * math.sin(a))]
            if f.tip == "kilit_yarigi":
                if not targets:
                    mid = ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
                    dst = _resolve_target(b, p, mid, [], where)
                    targets = [dst[0]] if dst else []
                todo = [(b.panels[k], v) for k, v in _group(_through(b, p, pts, targets, where, all_or_nothing=True)).items()
                        if len(v) == 2]
                if not todo:
                    F.append(Finding("hata", "kilit_hedef", f"{where}: kilit yarığı katlanınca hiçbir panele denk gelmiyor."))
                for tp, _ in todo:
                    b.locks.append({"neck": p.id, "target": tp.id, "length": L, "where": where})
            else:
                todo = [(p, pts)] + [(b.panels[k], v) for k, v in _group(_through(b, p, pts, targets, where, all_or_nothing=True)).items() if len(v) == 2]
            for tp, (q0, q1) in todo:
                tp.marks.append(Mark(Kind.SLIT, Line(q0[0], q0[1], q1[0], q1[1])))
                tp.marks.append(Mark(Kind.HOLE, Circle(q0[0], q0[1], relief / 2)))
                tp.marks.append(Mark(Kind.HOLE, Circle(q1[0], q1[1], relief / 2)))
            continue

        if f.tip in ("oval_delik", "pencere", "logo_alani"):
            w, h = num(f.genislik, where, 20.0), num(f.yukseklik, where, 6.0)
            a = num(f.aci, where, 0.0)
            r = min(w, h) / 2 if f.tip == "oval_delik" else (min(3.0, min(w, h) / 4) if f.tip == "pencere" else 0.0)
            from .geometry import rounded_rect
            T = Affine2(x, y, math.cos(math.radians(a)), math.sin(math.radians(a)))
            kind = Kind.GUIDE if f.tip == "logo_alani" else Kind.CUT
            targets_all = [(p, (x, y))] + (_through(b, p, [(x, y)], targets, where) if f.tip == "oval_delik" else [])
            for tp, (lx, ly) in targets_all:
                T = Affine2(lx, ly, math.cos(math.radians(a)), math.sin(math.radians(a)))
                for s_ in rounded_rect(-w / 2, -h / 2, w, h, r):
                    tp.marks.append(Mark(kind, T.seg(s_)))
            if f.tip == "logo_alani":
                p.texts.append(Text(x, y - 1, f.etiket or "logo / damga", 2.4))
            continue
        F.append(Finding("uyari", "ozellik_tip", f"{where}: desteklenmeyen özellik."))

    # kilit kafaları: yarıktan geçip hedefin öbür yüzüne
    for p in b.panels.values():
        if not p.spec.yariktan_gecer:
            continue
        lock = next((lk for lk in b.locks if lk["neck"] == p.parent), None)
        if lock is None:
            F.append(Finding("hata", "gecis", f"'{p.id}' yarıktan geçer olarak işaretli ama ebeveyninde kilit_yarigi yok."))
            continue
        tgt = b.panels[lock["target"]]
        rel = np.linalg.inv(b.matrix(p.id, 1.0)) @ b.matrix(tgt.id, 1.0)
        if abs(rel[2, 2]) < 0.9:
            F.append(Finding("hata", "gecis", f"'{p.id}' kilit kafası '{tgt.id}' paneline paralel değil."))
            continue
        z_in = rel[2, 3]
        z_out = z_in - rel[2, 2] * tgt.t
        far = z_in if abs(z_in) > abs(z_out) else z_out
        p.through = float(far + p.t) if far > 0 else float(far)


def _settle_contents(b: Built):
    """İçeriği, taban panelin iç yüzündeki katların (kilit kafası vb.) üstüne oturtur."""
    for cg in b.contents:
        if cg.under:
            continue
        inv = np.linalg.inv(b.matrix(cg.panel, 1.0))
        top = 0.0
        for q in b.panels.values():
            if q.id == cg.panel:
                continue
            m = inv @ b.matrix(q.id, 1.0)
            for (x, y) in q.poly[:: max(1, len(q.poly) // 40)] + q.quad:
                for z in (0.0, -q.t):
                    v = m @ np.array([x, y, z, 1.0])
                    if cg.x < v[0] < cg.x + cg.w and cg.y < v[1] < cg.y + cg.h and 0.05 < v[2] < 3 * q.t + 0.5:
                        top = max(top, float(v[2]))
        cg.z0 = top


def _group(placements):
    g = {}
    for tp, q in placements:
        g.setdefault(tp.id, []).append(q)
    return g


def _through(b: Built, p: PanelGeo, pts, targets, where, all_or_nothing=False):
    """Kaynak paneldeki noktaları katlı hâlde hedef panellere izdüşürür."""
    out = []
    m = b.matrix(p.id, 1.0)
    for tid in targets:
        tp = b.panels[tid]
        inv = np.linalg.inv(b.matrix(tid, 1.0))
        rel = inv @ m
        if abs(float(rel[2, 2])) < 0.95:
            b.findings.append(Finding("hata", "hedef_aci", f"{where}: '{tid}' paneli katlanınca kaynakla paralel değil; delikler eşleşmez.", tid))
            continue
        locs = [(rel @ np.array([x, y, 0.0, 1.0]))[:3] for (x, y) in pts]
        inside = [point_in_polygon((q[0], q[1]), tp.poly) and dist_to_polygon_edge((q[0], q[1]), tp.poly) > 0.3 for q in locs]
        gap = max(abs(q[2]) for q in locs) if locs else 0
        if gap > 25:
            b.findings.append(Finding("uyari", "hedef_uzak", f"{where}: '{tid}' paneli {gap:.0f} mm uzakta; gerçekten üst üste mi?", tid))
        n_in = sum(inside)
        if n_in == 0:
            b.findings.append(Finding("hata", "hedef_disarida", f"{where}: katlanınca '{tid}' panelinin dışına düşüyor.", tid))
            continue
        if n_in < len(pts):
            b.findings.append(Finding("hata", "hedef_kismi", f"{where}: '{tid}' paneline yalnızca kısmen denk geliyor.", tid))
            if all_or_nothing:
                continue
        for q, ok in zip(locs, inside):
            if ok:
                out.append((tp, (float(q[0]), float(q[1]))))
    return out


def _resolve_target(b: Built, p: PanelGeo, xy, targets, where):
    """Çıtçıt / kilit için karşı paneli bul (verilmediyse en yakın paralel panel)."""
    m = b.matrix(p.id, 1.0)
    pw = m @ np.array([xy[0], xy[1], 0.0, 1.0])
    cands = targets or [q.id for q in b.panels.values() if q.id != p.id and q.id != p.parent and q.parent != p.id]
    best = None
    for tid in cands:
        tp = b.panels[tid]
        inv = np.linalg.inv(b.matrix(tid, 1.0))
        if abs((inv @ m)[2, 2]) < 0.95:
            continue
        q = inv @ pw
        if not point_in_polygon((q[0], q[1]), tp.poly):
            continue
        if not targets and abs(q[2]) > 30:
            continue
        if best is None or abs(q[2]) < abs(best[1][2]):
            best = (tid, q[:3])
    if best is None:
        b.findings.append(Finding("hata", "karsilik_yok",
                                  f"{where}: katlanınca karşısına gelen panel bulunamadı; bu nokta boşluğa düşüyor."))
    return best


def slab_gap(b: Built, src: str, xy, dst: str) -> float:
    """Katlı hâlde kaynak paneldeki noktada iki levha arası boşluk (negatif: iç içe)."""
    inv = np.linalg.inv(b.matrix(dst, 1.0))
    m = b.matrix(src, 1.0)
    za = (inv @ m @ np.array([xy[0], xy[1], 0.0, 1.0]))[2]
    zb = (inv @ m @ np.array([xy[0], xy[1], -b.panels[src].t, 1.0]))[2]
    lo, hi = min(za, zb), max(za, zb)
    t = b.panels[dst].t
    if lo >= 0:
        return float(lo)
    if hi <= -t:
        return float(-t - hi)
    return float(-min(hi - (-t), 0 - lo))


def _snap_marks(p: PanelGeo, xy, cap, hole, label):
    x, y = xy
    if hole > 0:
        p.marks.append(Mark(Kind.HOLE, Circle(x, y, hole / 2)))
    p.marks.append(Mark(Kind.GUIDE, Circle(x, y, cap / 2)))
    p.texts.append(Text(x, y - cap / 2 - 3.2, label, 2.2))

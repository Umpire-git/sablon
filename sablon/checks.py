"""Tasarım kontrolleri: ürünü 3B'de katlayıp 'kafada kurar', üretim ve kullanım hatalarını bulur.

* Katlı hâlde ve her montaj adımında paneller birbirinin içinden geçiyor mu? (çarpışma)
* Kartlar/içerik ayrılan hacme sığıyor mu, tutuluyor mu, çıkarılabiliyor mu?
* Dil-yarık kilidi tutar mı, yarık kenara/menteşeye çok mu yakın?
* Çıtçıt kapanınca iki yüz temas ediyor mu; perçin/vida o kalınlığı kavrar mı?
* Malzemeye uygunluk (vaketa / crazy horse).
"""
from __future__ import annotations

import math

import numpy as np

from . import materials as M
from .engine import Built, Finding, slab_gap
from .geometry import dist_to_polygon_edge

EPS = 0.2


def _pip(xy: np.ndarray, poly: list) -> np.ndarray:
    """Vektörel nokta-çokgen içinde testi."""
    x, y = xy[:, 0], xy[:, 1]
    inside = np.zeros(len(xy), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (x < xin)
    return inside


def _edge_dist(xy: np.ndarray, poly: list) -> np.ndarray:
    best = np.full(len(xy), np.inf)
    for i in range(len(poly)):
        a, b = np.array(poly[i]), np.array(poly[(i + 1) % len(poly)])
        ab = b - a
        L2 = float(ab @ ab) or 1e-12
        k = np.clip(((xy - a) @ ab) / L2, 0, 1)
        proj = a + k[:, None] * ab
        best = np.minimum(best, np.linalg.norm(xy - proj, axis=1))
    return best


def _samples(p, step=2.5) -> np.ndarray:
    """Panel levhasının iç noktaları (yerel; orta düzlem ve yüzlere yakın iki düzlem)."""
    poly = np.array(p.poly)
    (x0, y0), (x1, y1) = poly.min(0), poly.max(0)
    step = max(step, (x1 - x0) / 120, (y1 - y0) / 120)  # örnek sayısını sınırla
    gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
    pts = np.c_[gx.ravel(), gy.ravel()]
    if not len(pts):
        return np.zeros((0, 3))
    pts = pts[_pip(pts, p.poly) & (_edge_dist(pts, p.poly) > 0.6)]
    return np.vstack([np.c_[pts, np.full(len(pts), z)] for z in (-p.t * 0.5, -p.t * 0.15, -p.t * 0.85)])


def _inside_slab(pts_local: np.ndarray, p) -> np.ndarray:
    z = pts_local[:, 2]
    zin = (z < -EPS) & (z > -p.t + EPS)
    if not zin.any():
        return zin
    xy = pts_local[:, :2]
    res = np.zeros(len(pts_local), bool)
    idx = np.where(zin)[0]
    sub = xy[idx]
    ok = _pip(sub, p.poly) & (_edge_dist(sub, p.poly) > 0.5)
    res[idx] = ok
    return res


def _bend_world(b: Built, pid: str, fold) -> np.ndarray:
    """Çocuk panelin menteşesindeki kıvrım bölgesinin dünya koordinatlı örnek noktaları."""
    import math as _m
    p = b.panels[pid]
    f = fold.get(pid, 0.0) if isinstance(fold, dict) else fold
    th = _m.radians(p.angle * f)
    if abs(th) < 1e-3:
        return np.zeros((0, 4))
    H = b.hinge_frame(pid, fold)
    zh = p.bend_r if p.angle >= 0 else -p.t - p.bend_r
    xs = np.linspace(p.hinge_x[0] + 0.8, p.hinge_x[1] - 0.8, max(2, int((p.hinge_x[1] - p.hinge_x[0]) / 2.5)))
    pts = []
    for a in np.linspace(th * 0.15, th * 0.85, 5):
        for z0 in (-p.t * 0.5,):
            y = -(z0 - zh) * _m.sin(a)
            z = zh + (z0 - zh) * _m.cos(a)
            for x in xs:
                pts.append((x, y, z, 1.0))
    P = np.array(pts)
    return (H @ P.T).T


def _inside_bend(Pw: np.ndarray, b: Built, pid: str, fold) -> np.ndarray:
    """Dünya noktalarından hangileri pid panelinin kıvrım hacminin içinde?"""
    import math as _m
    p = b.panels[pid]
    f = fold.get(pid, 0.0) if isinstance(fold, dict) else fold
    th = _m.radians(p.angle * f)
    if abs(th) < 1e-3 or not len(Pw):
        return np.zeros(len(Pw), bool)
    H = np.linalg.inv(b.hinge_frame(pid, fold))
    L = (H @ Pw.T).T
    x, y, z = L[:, 0], L[:, 1], L[:, 2]
    r = p.bend_r
    if p.angle >= 0:
        zh = r
        a = np.arctan2(y, -(z - zh))
    else:
        zh = -p.t - r
        a = -np.arctan2(y, (z - zh))
    rho = np.hypot(y, z - zh)
    ok = (x > p.hinge_x[0] + 0.3) & (x < p.hinge_x[1] - 0.3)
    ok &= (rho > r + EPS) & (rho < r + p.t - EPS)
    ok &= (np.sign(a) == np.sign(th)) & (np.abs(a) > 0.02) & (np.abs(a) < abs(th) - 0.02)
    return ok


def collisions(b: Built, fold=1.0, samples=None) -> list[tuple[str, str, int]]:
    mats = b.matrices(fold)
    inv = {pid: np.linalg.inv(m) for pid, m in mats.items()}
    samples = samples or {pid: _samples(b.panels[pid]) for pid in b.order}
    world = {}
    for pid, S in samples.items():
        parts = []
        if len(S):
            H = np.c_[S, np.ones(len(S))]
            parts.append((mats[pid] @ H.T).T)
        if b.panels[pid].parent:
            bw = _bend_world(b, pid, fold)
            if len(bw):
                parts.append(bw)
        if parts:
            world[pid] = np.vstack(parts)
    out = []
    ids = list(b.order)
    for i, a in enumerate(ids):
        for c in ids[i + 1:]:
            pa, pc = b.panels[a], b.panels[c]
            if pa.parent == c or pc.parent == a:
                continue
            n = 0
            if c in world:
                loc = (inv[a] @ world[c].T).T[:, :3]
                n += int(_inside_slab(loc, pa).sum())
            if a in world:
                loc = (inv[c] @ world[a].T).T[:, :3]
                n += int(_inside_slab(loc, pc).sum())
            # kıvrım hacimleri (aynı kıvrımı paylaşan komşular hariç)
            if a in world and pc.parent and pc.parent != a and b.panels[a].parent != pc.parent:
                n += int(_inside_bend(world[a], b, c, fold).sum())
            if c in world and pa.parent and pa.parent != c and pc.parent != pa.parent:
                n += int(_inside_bend(world[c], b, a, fold).sum())
            if n > 3:
                out.append((a, c, n))
    return out


def content_hits(b: Built, cg) -> list[tuple[str, int]]:
    """İçerik kutusunun içine giren panel levhaları."""
    m = b.matrix(cg.panel, 1.0)
    z0, z1 = (-b.panels[cg.panel].t - cg.s, -b.panels[cg.panel].t) if cg.under else (cg.z0, cg.z0 + cg.s)
    gx, gy, gz = np.meshgrid(np.linspace(cg.x + 1, cg.x + cg.w - 1, 18), np.linspace(cg.y + 1, cg.y + cg.h - 1, 12),
                             np.linspace(z0 + 0.1, z1 - 0.1, max(3, int((z1 - z0) / 0.4))))
    P = np.c_[gx.ravel(), gy.ravel(), gz.ravel(), np.ones(gx.size)]
    W = (m @ P.T).T
    hits = []
    for pid in b.order:
        if pid == cg.panel:
            continue
        loc = (np.linalg.inv(b.matrix(pid, 1.0)) @ W.T).T[:, :3]
        n = int(_inside_slab(loc, b.panels[pid]).sum())
        if n > 2:
            hits.append((pid, n))
    return hits


def run_checks(b: Built, steps: bool = True) -> list:
    out = list(b.findings)
    d = b.design
    mat = M.material(d.malzeme)
    t = b.env["t"]
    lo, hi = mat.kalinlik_onerilen
    if not lo - 1e-6 <= t <= hi + 1e-6:
        out.append(Finding("uyari", "kalinlik", f"{mat.ad} için önerilen kalınlık {lo}–{hi} mm; tasarım {t:g} mm."))
    if t < 1.2:
        out.append(Finding("uyari", "ince_dikissiz", f"{t:g} mm deri dikişsiz yapıda şeklini tutmaz; 1.4–1.6 mm önerilir."))
    if t > 1.8 + 1e-6:
        out.append(Finding("hata", "kalin_deri", f"{t:g} mm deri kartlık/cüzdan için fazla kalın: ürün hantal olur, katlar "
                                                 "açılır, kilit zor takılır. En fazla 1.6–1.8 mm kullanın."))

    # --- katlı hâlde çarpışma (hatalı üretim)
    samples = {pid: _samples(b.panels[pid]) for pid in b.order}
    for a, c, n in collisions(b, 1.0, samples):
        out.append(Finding("hata", "carpisma",
                           f"Katlanınca '{a}' ile '{c}' panelleri birbirinin içinden geçiyor ({n} nokta). "
                           "Ölçü, kat açısı veya sırt/körük genişliğini düzeltin.", f"{a},{c}"))
    # --- montaj simülasyonu: her kat sırasıyla katlanırken bir panel diğerinin içinden geçiyor mu?
    if steps:
        levels = sorted({p.spec.kat_sirasi for p in b.panels.values() if p.parent and p.spec.kat_sirasi})
        passing = {(p.id, lk["target"]) for p in b.panels.values() if p.spec.yariktan_gecer
                   for lk in b.locks if lk["neck"] == p.parent}
        # ince monte şeritler esnektir: katlanırken bükülüp yol verir (bitmiş hâl yine denetlenir)
        flexible = {p.id for p in b.panels.values()
                    if b.part_t[p.part] <= 1.2 and b.panels[b.roots[p.part]].mount is not None
                    and b.panels[b.roots[p.part]].mount.ana_panel}
        reported = set()
        for k in levels:
            for frac in (0.25, 0.5, 0.75, 0.9, 0.95, 0.98):
                fold = {pid: (1.0 if 0 < p.spec.kat_sirasi < k else frac if p.spec.kat_sirasi == k else 0.0)
                        for pid, p in b.panels.items()}
                for a, c, n in collisions(b, fold, samples):
                    if (a, c) in passing or (c, a) in passing or (a, c) in reported or a in flexible or c in flexible:
                        continue
                    reported.add((a, c))
                    out.append(Finding("hata", "montaj_carpisma",
                                       f"Kat {k} katlanırken '{a}' ile '{c}' birbirinin içinden geçmek zorunda: bu ürün bu "
                                       "sırayla yapılamaz. Kat sırasını, açıyı veya sırt/körük ölçüsünü düzeltin.", f"{a},{c}"))

    # --- katlar
    for p in b.panels.values():
        if not p.parent:
            continue
        a = abs(p.angle)
        if a >= 150 and p.t >= 1.6:
            out.append(Finding("bilgi", "sert_kat", f"'{p.id}' {a:.0f}° katlanıyor; {p.t:g} mm deride kat çizgisini içten "
                                                    "V-kanal ile hafif inceltin.", p.id))
        if p.w < 3 * p.t + 4 or p.h < p.t:
            out.append(Finding("uyari", "ince_panel", f"'{p.id}' paneli ({p.w:.1f}×{p.h:.1f}) bu kalınlıkta katlanamayacak kadar dar.", p.id))

    # --- dil-yarık kilitleri
    if any(not lk.get("gecis") for lk in b.locks) and not mat.sert:
        out.append(Finding("uyari", "kilit_yumusak",
                           f"{mat.ad} yumuşak; dil-yarık kilidi zamanla gevşer. Kilit dillerini 1.6 mm ve üzeri tutun, "
                           "kafayı yarıktan en az 3 mm geniş yapın."))
    for lk in b.locks:
        neck = b.panels[lk["neck"]]
        if lk.get("gecis"):  # şerit geçiş yuvası: kafa kontrolü yok, yalnız yarık-kenar mesafesi
            tgt = b.panels[lk["target"]]
            for mk in tgt.marks:
                if mk.kind.value == "slit":
                    for q in ((mk.prim.x0, mk.prim.y0), (mk.prim.x1, mk.prim.y1)):
                        if dist_to_polygon_edge(q, tgt.poly) < max(5.0, 3 * tgt.t):
                            out.append(Finding("hata", "yarik_kenar", f"'{tgt.id}' üzerindeki şerit yuvası kenara çok yakın; "
                                                                      "aradaki köprü yırtılır.", tgt.id))
                            break
            continue
        need = max(8.0, 5 * neck.t)
        if neck.w < need:
            out.append(Finding("hata", "dar_dil", f"'{neck.id}' dil boynu {neck.w:.1f} mm; en az {need:.0f} mm olmalı, yoksa kopar.", neck.id))
        if lk["length"] < neck.w + 0.5 * neck.t:
            out.append(Finding("hata", "yarik_dar", f"'{neck.id}' yarığı ({lk['length']:.1f} mm) boyundan dar; dil yarıktan geçmez "
                                                    f"(≥ boyun + t = {neck.w + neck.t:.1f}).", neck.id))
        heads = [q for q in b.panels.values() if q.parent == neck.id]
        if not heads:
            out.append(Finding("hata", "kafa_yok", f"'{neck.id}' kilit dilinin kafası yok; dil yarıktan kayıp çıkar.", neck.id))
        from .calibration import lock_margin
        need_diff = lock_margin(mat.key)
        for h in heads:
            diff = h.w - lk["length"]
            if diff < need_diff:
                out.append(Finding("hata", "kilit_tutmaz",
                                   f"'{h.id}' kilit kafası yarıktan yalnızca {diff:.1f} mm geniş; kendiliğinden çıkar (≥{need_diff:g} mm).", h.id))
            elif diff > 8:
                out.append(Finding("uyari", "kilit_zor", f"'{h.id}' kafası yarıktan {diff:.1f} mm geniş; takması zor, yarık yırtılır.", h.id))
            if not h.spec.yariktan_gecer:
                out.append(Finding("uyari", "kafa_gecis", f"'{h.id}' yarıktan geçer olarak işaretlenmemiş.", h.id))
        tgt = b.panels[lk["target"]]
        for mk in tgt.marks:
            if mk.kind.value == "slit":
                for q in ((mk.prim.x0, mk.prim.y0), (mk.prim.x1, mk.prim.y1)):
                    dd = dist_to_polygon_edge(q, tgt.poly)
                    if dd < max(5.0, 3 * tgt.t):
                        out.append(Finding("hata", "yarik_kenar",
                                           f"'{tgt.id}' üzerindeki yarık kenara {dd:.1f} mm; aradaki köprü yırtılır (≥{max(5.0, 3 * tgt.t):.0f} mm).", tgt.id))
                        break

    # --- çıtçıt
    for s in b.snaps:
        sn = M.SNAPS[s.size]
        r = sn.sapka_cap / 2
        for pid, xy in ((s.src, s.src_xy), (s.dst, s.dst_xy)):
            if pid is None:
                continue
            q = b.panels[pid]
            dd = dist_to_polygon_edge(xy, q.poly)
            if dd < r + 2:
                out.append(Finding("uyari", "citcit_kenar", f"Ç{s.no}: '{pid}' kenarına {dd:.1f} mm; şapka taşar (≥{r + 2:.1f}).", pid))
            if q.parent and xy[1] < r + 3:
                out.append(Finding("uyari", "citcit_kat", f"Ç{s.no}: '{pid}' kat çizgisine çok yakın; kapak düzgün katlanmaz.", pid))
        if s.dst:
            if s.gap < -0.2:
                out.append(Finding("hata", "citcit_ic_ice", f"Ç{s.no}: kapak, karşı panelin içine giriyor ({-s.gap:.1f} mm). Sırtı büyütün."))
            elif s.gap > 2.5:
                out.append(Finding("uyari", "citcit_bosluk",
                                   f"Ç{s.no}: kapak ile karşı panel arası {s.gap:.1f} mm; çıtçıt kapanırken kapak gerilip eğilir. "
                                   "Kapak sırtını/körüğünü bu kadar azaltın."))
            grip = b.panels[s.src].t + b.panels[s.dst].t
            if grip > sn.kavrama * 2:
                out.append(Finding("uyari", "citcit_dikme", f"Ç{s.no}: kalın deri ({grip:.1f} mm toplam); uzun dikmeli çıtçıt kullanın."))
        if not mat.sert:
            out.append(Finding("bilgi", "citcit_takviye", f"Ç{s.no}: {mat.ad} yumuşak; çıtçıt arkasına ince vaketa pul koyun."))

    # --- perçin / vida
    for f in b.fasteners:
        fs = M.FASTENERS[f["tip"]]
        tot = sum(b.panels[x].t for x in f["layers"])
        lo_g, hi_g = fs.kavrama
        if len(f["layers"]) < 2:
            out.append(Finding("uyari", "tek_kat", f"{f['where']}: {fs.ad} tek kattan geçiyor, bir şey birleştirmiyor (hedefler?)."))
        elif tot > hi_g:
            out.append(Finding("hata", "kavrama", f"{f['where']}: {len(f['layers'])} kat = {tot:.1f} mm; {fs.ad} en çok ~{hi_g:g} mm kavrar."))
        elif tot < lo_g:
            out.append(Finding("uyari", "kavrama_az", f"{f['where']}: toplam {tot:.1f} mm; {fs.ad} için ince, sallanır (pul ekleyin)."))
        for x_ in f["layers"][1:]:
            gap = slab_gap(b, f["panel"], f["xy"], x_)
            if gap > 1.0:
                out.append(Finding("hata", "kat_bosluk", f"{f['where']}: '{f['panel']}' ile '{x_}' arasında {gap:.1f} mm boşluk; "
                                                         "perçin/vida katları birbirine değmeli (duvar/sırt ölçüsünü düzeltin)."))
            elif gap < -0.2:
                out.append(Finding("hata", "kat_ic_ice", f"{f['where']}: '{f['panel']}' ile '{x_}' iç içe geçiyor."))
        p = b.panels[f["panel"]]
        dd = dist_to_polygon_edge(f["xy"], p.poly)
        if dd < fs.bas_cap / 2 + 1.5:
            out.append(Finding("uyari", "percin_kenar", f"{f['where']}: kenara {dd:.1f} mm; baş taşar/yırtar (≥{fs.bas_cap / 2 + 1.5:.1f})."))

    # --- monte parçalar bağlı mı?
    for part_id, root in b.roots.items():
        rp = b.panels[root]
        if rp.mount is None or not rp.mount.ana_panel:
            continue
        pids = {q.id for q in b.panels.values() if q.part == part_id}
        joins = sum(1 for f in b.fasteners if set(f["layers"]) & pids and len(f["layers"]) > 1)
        joins += sum(1 for lk in b.locks if (lk["neck"] in pids or lk["target"] in pids) and not lk.get("gecis"))
        joins += sum(1 for s in b.snaps if s.src in pids or s.dst in pids)
        if joins == 0:
            out.append(Finding("hata", "bagsiz", f"'{part_id}' parçası ana panele hiçbir perçin/vida/kilit/çıtçıtla bağlı değil."))
        elif joins == 1:
            out.append(Finding("uyari", "tek_baglanti", f"'{part_id}' tek noktadan bağlı; döner. En az iki bağlantı kullanın."))

    # --- içerik: sığıyor mu, tutuluyor mu, çıkıyor mu?
    pulled_ids = {d["content"] for d in pull_strip_data(b)}
    for cg in b.contents:
        p = b.panels[cg.panel]
        label = f"{cg.spec.adet} {dict(kart='kart', banknot='banknot', anahtar='anahtar').get(cg.spec.tip, 'içerik')}"
        if cg.x < -0.01 or cg.x + cg.w > p.w + 0.01 or cg.y < -0.01:
            out.append(Finding("hata", "icerik_tasiyor", f"{label}: '{p.id}' paneline sığmıyor ({cg.w:.1f} mm > {p.w:.1f} mm).", p.id))
            continue
        hits = content_hits(b, cg)
        for pid, n in hits:
            out.append(Finding("hata", "hacim_yetersiz",
                               f"{label} ({cg.s:.1f} mm yığın) katlı hâlde '{pid}' paneline çarpıyor: ayrılan hacim yetersiz. "
                               "Körük/sırt/yan duvarı yığın kalınlığı kadar büyütün.", pid))
        covers = _covers(b, cg)
        if not covers:
            out.append(Finding("hata", "icerik_acik", f"{label}: '{p.id}' üzerinde içeriği örten panel yok; düşer.", p.id))
            continue
        top = cg.y + cg.h
        cover_top = max(c[1] for c in covers)
        if cover_top < cg.y + cg.h * 0.45:
            out.append(Finding("uyari", "tutmuyor", f"{label}: içeriğin yalnızca alt %{100 * (cover_top - cg.y) / cg.h:.0f}'i örtülü; kolay düşer.", p.id))
        notch = any(b.panels[c[0]].spec.profil_ust.tip == "oyuk" for c in covers)
        pulled = b.contents.index(cg) in pulled_ids
        if cover_top >= top - 3 and not notch and p.h >= top - 3 and not pulled:
            out.append(Finding("uyari", "erisim", f"{label}: içerik tamamen örtülü; tutup çekecek yer yok. "
                                                  "Ön paneli alçaltın veya başparmak oyuğu ekleyin.", p.id))

    # --- çekme şeridi: çekince kartlar ne kadar yükselir, tutulabilir mi?
    out += _pull_strips(b)

    # --- deri kullanımı ve ölçü
    for part_id, part in b.parts.items():
        a = b.area_cm2(part_id) * part.adet
        out.append(Finding("bilgi", "deri", f"'{part.ad or part_id}': ~{a:.0f} cm² deri (fire hariç)."))
    if not any(f.level == "hata" for f in out):
        w, h, dd = b.finished_size()
        out.append(Finding("bilgi", "olcu", f"Bitmiş ürün ≈ {w:.0f} × {h:.0f} × {dd:.0f} mm."))
    seen, uniq = set(), []
    for f in out:
        k = (f.level, f.message)
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    order = {"hata": 0, "uyari": 1, "bilgi": 2}
    return sorted(uniq, key=lambda f: order[f.level])


def _covers(b: Built, cg) -> list[tuple[str, float]]:
    """İçeriğin üstünü örten paneller ve içerik panelinin y ekseninde ulaştıkları en üst nokta."""
    base = b.panels[cg.panel]
    if cg.under:
        return [(base.id, cg.y + cg.h)]
    inv = np.linalg.inv(b.matrix(base.id, 1.0))
    res = []
    for q in b.panels.values():
        if q.id == base.id:
            continue
        m = inv @ b.matrix(q.id, 1.0)
        if abs(m[2, 2]) < 0.95:
            continue
        z = m[2, 3]
        if not (0 < z < cg.z0 + cg.s + 20):
            continue
        pts = np.array([(m @ np.array([x, y, 0, 1.0]))[:2] for x, y in q.poly])
        if pts[:, 0].min() < cg.x + cg.w - 5 and cg.x + 5 < pts[:, 0].max() and pts[:, 1].min() < cg.y + cg.h and cg.y < pts[:, 1].max():
            mid = (pts[:, 0] > cg.x + cg.w * 0.3) & (pts[:, 0] < cg.x + cg.w * 0.7)
            ymax = pts[mid, 1].max() if mid.any() else pts[:, 1].max()
            res.append((q.id, float(ymax)))
    return res


def _descendants(b: Built, pid: str) -> list[str]:
    out, todo = [], [pid]
    while todo:
        k = todo.pop()
        kids = [q.id for q in b.panels.values() if q.parent == k]
        out += kids
        todo += kids
    return out


def pull_fold(b: Built) -> dict:
    """Şerit çekilmiş görünüm için katlar: kartların üstünü kapatan kapaklar (taban panelin üst kenarından çıkanlar) açık."""
    fold = {pid: 1.0 for pid in b.panels}
    for d in pull_strip_data(b):
        for q in b.panels.values():
            if q.parent == d["base"] and q.spec.kenar == "ust":
                for k in [q.id] + _descendants(b, q.id):
                    fold[k] = 0.0
    return fold


def pull_strip_data(b: Built) -> list[dict]:
    """Çekme şeritleri: monte bir şerit kartların altından U çizip tabana yatıyorsa.

    Her biri için: içerik indeksi, taban paneli, şeridin dönüş kolu (child), kartların yükselmesi (lift),
    tam çekişte görünen kart boyu ve şerit ucunun gövdeden taşması.
    """
    res = []
    for ci, cg in enumerate(b.contents):
        if cg.under:
            continue
        base = b.panels[cg.panel]
        inv = np.linalg.inv(b.matrix(base.id, 1.0))

        def to_base(pid, x, y):
            return (inv @ b.matrix(pid, 1.0) @ np.array([x, y, 0.0, 1.0]))[:3]

        base_top = max(y for _, y in base.poly)
        for part_id, root in b.roots.items():
            rp = b.panels[root]
            if rp.mount is None or not rp.mount.ana_panel:
                continue
            for c in b.panels.values():
                if c.parent != root or abs(c.angle) < 150:
                    continue
                ys = [to_base(q, x, y)[1] for q in [c.id] + _descendants(b, c.id) for x, y in b.panels[q].quad]
                zs = [to_base(c.id, x, y)[2] for x, y in c.quad]
                if max(abs(z) for z in zs) > 3 * c.t + 1:
                    continue  # tabana yatmıyor: çekme şeridi değil
                anchors = [to_base(f["panel"], *f["xy"])[1] for f in b.fasteners if f["panel"] == root]
                anchor = max(anchors) if anchors else max(to_base(root, x, y)[1] for x, y in rp.quad)
                lift = max(0.0, anchor - 6 - cg.y)
                res.append({"part": part_id, "name": b.parts[part_id].ad or part_id, "child": c.id, "base": base.id,
                            "pass": [q.id for q in b.panels.values() if q.parent == c.id and q.spec.yariktan_gecer
                                     and any(lk["neck"] == c.id and lk.get("gecis") for lk in b.locks)],
                            "arm_len": float(c.h),
                            "content": ci, "lift": float(lift), "visible": float(cg.y + cg.h + lift - base_top),
                            "tab": float(max(ys) - base_top)})
    return res


def _pull_strips(b: Built) -> list:
    res = []
    for d in pull_strip_data(b):
        res.append(Finding("bilgi", "cekme", f"{d['name']}: çekince kartlar ~{d['lift']:.0f} mm yükselir; en üstte "
                                             f"~{d['visible']:.0f} mm görünür. Şeridin tutma ucu gövdeden {d['tab']:.0f} mm taşar."))
        if d["visible"] < 15:
            res.append(Finding("uyari", "cekme_az", f"{d['name']}: çekince kartların yalnızca ~{d['visible']:.0f} mm'si görünür; "
                                                    "tutmak için ≥15 mm gerekir (perçini yukarı alın / şeridi uzatın)."))
        if d["tab"] < 12:
            res.append(Finding("uyari", "cekme_ucu", f"{d['name']}: şerit ucu gövdeden {d['tab']:.0f} mm taşıyor; parmakla "
                                                     "tutmak için ≥12 mm olmalı."))
    return res

"""Tasarım kontrolleri: ürünü 'kafada kurup' kullanım ve üretim sorunlarını bulur.

Motorun inşa sırasında bulduğu geometri hataları (açınım çakışması, çıtçıtın karşılığının
boşluğa düşmesi...) burada malzeme ve kullanım kurallarıyla birleştirilir.
"""
from __future__ import annotations

import math

import numpy as np

from . import materials as M
from .engine import Built, Finding, stitch_runs


def run_checks(b: Built) -> list[Finding]:
    out = list(b.findings)
    d = b.design
    mat = M.material(d.malzeme)
    t = b.env["t"]
    lo, hi = mat.kalinlik_onerilen
    if not lo - 1e-6 <= t <= hi + 1e-6:
        out.append(Finding("uyari", "kalinlik", f"{mat.ad} için önerilen kalınlık {lo}–{hi} mm; tasarım {t} mm."))

    pitch = b.env_num(d.dikis_araligi) if d.dikis_araligi else 3.85
    near = min(M.PRICKING_IRONS, key=lambda s: abs(s - pitch))
    if abs(near - pitch) > 0.05:
        out.append(Finding("uyari", "zimba", f"{pitch} mm zımba adımı standart değil; en yakın {near} mm."))
    e_def = b.env_num(d.kenar_payi) if d.kenar_payi else 3.5
    if e_def < 2.5:
        out.append(Finding("uyari", "kenar_payi", f"Dikiş kenar payı {e_def} mm; deri kenardan yırtılabilir (≥3 mm)."))

    # --- katlar
    for p in b.panels.values():
        if not p.parent:
            continue
        a = abs(p.angle)
        if a >= 150 and p.t >= 1.6 and p.bulge == 0:
            msg = (f"'{p.id}' {a:.0f}° katlanıyor, {p.t} mm deride kat yeri çatlayabilir; içten V-kanal ile inceltin "
                   "veya araya sırt/körük paneli ekleyin.")
            out.append(Finding("uyari", "sert_kat", msg, p.id))
        if p.w < 3 * p.t + 4 or p.h < 2 * p.t + 2:
            out.append(Finding("uyari", "ince_panel", f"'{p.id}' paneli ({p.w:.1f}×{p.h:.1f}) bu kalınlıkta katlanamayacak kadar dar.", p.id))

    # --- dil / kilit yapıları (dikişsiz)
    slits = [f for f in d.ozellikler if f.tip == "kilit_yarigi"]
    if slits:
        if not mat.sert:
            out.append(Finding("uyari", "kilit_yumusak",
                               f"{mat.ad} yumuşak; dil-yarık kilidi zamanla gevşer. Dil bölgesine içten ince vaketa takviye "
                               "yapıştırın veya vaketa kullanın."))
        for f in slits:
            p = b.panels.get(f.panel)
            if p is None:
                continue
            neck = p.w
            if neck < max(8.0, 5 * p.t):
                out.append(Finding("hata", "dar_dil", f"'{p.id}' dil boynu {neck:.1f} mm; en az {max(8.0, 5 * p.t):.0f} mm olmalı.", p.id))
            heads = [q for q in b.panels.values() if q.parent == p.id]
            for h in heads:
                L = b.env_num(f.genislik) if f.genislik else neck
                diff = h.w - L
                if diff < 1.5:
                    out.append(Finding("hata", "kilit_tutmaz",
                                       f"'{h.id}' kilit kafası yarıktan yalnızca {diff:.1f} mm geniş; kendiliğinden çıkar (≥2 mm).", h.id))
                elif diff > 7:
                    out.append(Finding("uyari", "kilit_zor", f"'{h.id}' kilit kafası yarıktan {diff:.1f} mm geniş; takması zor, yarık yırtılabilir.", h.id))

    # --- çıtçıt / mıknatıs
    for s in b.snaps:
        p = b.panels[s.src]
        if s.kind == "citcit":
            sn = M.SNAPS[s.size]
            r = sn.sapka_cap / 2
            for pid, xy in ((s.src, s.src_xy), (s.dst, s.dst_xy)):
                if pid is None:
                    continue
                q = b.panels[pid]
                from .geometry import dist_to_polygon_edge
                dist = dist_to_polygon_edge(xy, q.poly)
                if dist < r + 2:
                    out.append(Finding("uyari", "citcit_kenar", f"Ç{s.no}: '{pid}' kenarına {dist:.1f} mm; şapka taşar (≥{r + 2:.1f}).", pid))
                if q.parent and xy[1] < r + 2:
                    out.append(Finding("uyari", "citcit_kat", f"Ç{s.no}: '{pid}' kat çizgisine çok yakın; kapak düzgün katlanmaz.", pid))
            if s.dst:
                grip = p.t + b.panels[s.dst].t
                if grip > sn.kavrama:
                    out.append(Finding("uyari", "citcit_dikme",
                                       f"Ç{s.no}: iki kat toplam {grip:.1f} mm; {sn.ad} dikmesi ~{sn.kavrama} mm sıkıştırır. "
                                       "Uzun dikmeli çıtçıt kullanın veya bölgeyi inceltin."))
                if s.gap > 5:
                    out.append(Finding("uyari", "citcit_bosluk",
                                       f"Ç{s.no}: kapak ile karşı panel arası {s.gap:.1f} mm; kapak gergin kalır veya çıtçıt kapanmaz. "
                                       "Kapak sırtını/körüğünü içeriğe göre ayarlayın."))
            if not mat.sert:
                out.append(Finding("bilgi", "citcit_takviye",
                                   f"Ç{s.no}: {mat.ad} yumuşak; çıtçıt arkasına ~10 mm yuvarlak deri pul (takviye) koyun."))
        else:
            out.append(Finding("bilgi", "miknatis", f"M{s.no}: mıknatıs iki kat deri arasına gizlenmeli (astar veya cep parçası)."))

    # --- dikiş katmanı kalınlığı
    for st in b.stitches:
        layers = 1 + len(st["targets"])
        tot = sum(b.panels[x].t for x in [st["panel"]] + st["targets"])
        if tot > 4.5:
            out.append(Finding("uyari", "kalin_dikis", f"'{st['panel']}' dikişinde {layers} kat = {tot:.1f} mm; el zımbası zorlanır, kenarları inceltin."))

    # --- içerik (kart/banknot) sığıyor mu? Çevre kuralı: iç genişlik ≥ içerik + yığın kalınlığı
    for cg in b.contents:
        p = b.panels[cg.panel]
        label = f"{cg.spec.adet} {'kart' if cg.spec.tip == 'kart' else cg.spec.tip}"
        if cg.x < -0.01 or cg.x + cg.w > p.w + 0.01 or cg.y < -0.01:
            out.append(Finding("hata", "icerik_tasiyor", f"{label}: '{p.id}' paneline sığmıyor ({cg.w:.1f} mm > {p.w:.1f} mm).", p.id))
            continue
        widths = _pocket_widths(b, cg)
        if widths is None:
            out.append(Finding("uyari", "icerik_acik", f"{label}: '{p.id}' üzerinde içeriği tutan cep/kapak bulunamadı.", p.id))
            continue
        inner, how = widths
        need = cg.w + cg.s + 1.0
        if inner < need - 1e-6:
            out.append(Finding("hata", "cep_dar",
                               f"{label}: {how} iç genişlik {inner:.1f} mm, gereken ≥ {need:.1f} mm "
                               f"(içerik {cg.w:.1f} + yığın {cg.s:.1f} + 1 mm pay). Dolu cep kapanmaz/kart girmez.", p.id))
        elif inner > cg.w + cg.s + 5:
            out.append(Finding("uyari", "cep_bol", f"{label}: {how} iç genişlik {inner:.1f} mm; tek kart kaldığında kayar.", p.id))

    # --- erişim: kart cepten çıkarılabiliyor mu?
    for cg in b.contents:
        top = cg.y + cg.h
        covers = _covering_tops(b, cg)
        if covers and all(c >= top - 3 for c in covers) and not _has_notch(b, cg):
            out.append(Finding("uyari", "erisim", f"'{cg.panel}' içeriği tamamen örtülü; kartı tutacak yer yok. "
                                                  "Cep ağzını alçaltın veya başparmak oyuğu ekleyin.", cg.panel))

    # --- aynı panelde birbirine çok yakın (ama çakışmayan) dikiş delikleri
    from .pattern import Kind
    for p in b.panels.values():
        pts = [(m.prim.cx, m.prim.cy) for m in p.marks if m.kind == Kind.STITCH]
        bad = 0
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dd = math.dist(pts[i], pts[j])
                if 0.3 < dd < 0.6 * pitch:
                    bad += 1
        if bad:
            tips = []
            for st in b.stitches:
                if p.id in [st["panel"]] + st["targets"]:
                    r = max(st.get("end_rem") or [0.0])
                    if 0.05 < r < pitch - 0.05:
                        tips.append(f"'{st['panel']}' yüksekliğini {-r:+.1f} veya {pitch - r:+.1f} mm değiştirin")
            out.append(Finding("uyari", "delik_cakisma",
                               f"'{p.id}': {bad} dikiş deliği başka bir dikişin deliğine {0.6 * pitch:.1f} mm'den yakın "
                               f"(deri yırtılır). Ortak kenara dikilen parçaların yan dikiş boyu zımba adımının ({pitch:g} mm) "
                               "katı olmalı" + (": " + "; ".join(tips) if tips else "."), p.id))

    # --- malzeme kullanımı
    for part_id, part in b.parts.items():
        a = b.area_cm2(part_id) * part.adet
        kind = "deri" if M.material(b.part_mat[part_id]).tur == "deri" else "malzeme"
        out.append(Finding("bilgi", "deri", f"'{part.ad or part_id}': ~{a:.0f} cm² {kind} (fire hariç)."))
    if not any(f.level == "hata" for f in out):
        w, h, dd = b.finished_size()
        out.append(Finding("bilgi", "olcu", f"Bitmiş ürün ≈ {w:.0f} × {h:.0f} × {dd:.0f} mm."))
    # tekrarları ayıkla
    seen, uniq = set(), []
    for f in out:
        k = (f.level, f.message)
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    order = {"hata": 0, "uyari": 1, "bilgi": 2}
    return sorted(uniq, key=lambda f: order[f.level])


def _covering(b: Built, cg):
    """İçeriğin üstünü örten paneller ve içeriğin panel yerelindeki konumları."""
    base = b.panels[cg.panel]
    res = []
    if cg.under:
        res.append(base)
        return res
    inv = np.linalg.inv(b.matrix(base.id, 1.0))
    for q in b.panels.values():
        if q.id == base.id:
            continue
        m = inv @ b.matrix(q.id, 1.0)
        if abs(m[2, 2]) < 0.95:
            continue
        z = m[2, 3]
        if not (0 < z < cg.s + 15):
            continue
        pts = [(m @ np.array([x, y, 0, 1.0]))[:2] for x, y in q.quad]
        xs, ys = [v[0] for v in pts], [v[1] for v in pts]
        if min(xs) < cg.x + cg.w and cg.x < max(xs) and min(ys) < cg.y + cg.h and cg.y < max(ys):
            res.append(q)
    return res


def _pocket_widths(b: Built, cg):
    """Cebin iç genişliği: dikiş hatları arası (monte cep / dikişli kat) veya yan duvar arası."""
    best = None
    for q in _covering(b, cg):
        ref = q if not cg.under else b.panels[cg.panel]
        # bu panelin sol/sağ kenarlarındaki dikişler
        edges = set()
        e = None
        for f in list(b.design.ozellikler) + b.auto_features:
            if f.panel == ref.id and f.tip == "dikis":
                edges |= set(f.kenarlar)
                e = b.env_num(f.kenar_payi) if f.kenar_payi else (b.env_num(b.design.kenar_payi) if b.design.kenar_payi else 3.5)
        if {"sol", "sag"} <= edges:
            runs = stitch_runs(ref, ["sol", "sag"], e)
            xs = [s.x0 for r in runs for s in r if hasattr(s, "x0")]
            inner = (max(xs) - min(xs)) if xs else ref.w - 2 * e
            inner = ref.w - 2 * e if inner <= 0 else inner
            cand = (inner, f"'{ref.id}' dikişleri arası")
        else:
            # yan duvarlı (körüklü) yapı: duvarlar ana panelin kenarlarındadır → panel genişliği - kalınlık
            walls = [w for w in b.panels.values() if w.parent == q.id and w.edge in ("sol", "sag") and abs(w.angle) >= 60]
            if len(walls) >= 2:
                gap = min(w.h for w in walls)  # duvar yüksekliği yığını taşır
                if gap + 1e-6 < cg.s:
                    return (0.0, f"'{q.id}' yan duvarı {gap:.1f} mm (yığın {cg.s:.1f} mm) —")
                return (q.w - q.t + cg.s, f"'{q.id}' yan duvarları arası")
            continue
        if best is None or cand[0] < best[0]:
            best = cand
    return best


def _covering_tops(b: Built, cg):
    tops = []
    base = b.panels[cg.panel]
    inv = np.linalg.inv(b.matrix(base.id, 1.0))
    for q in _covering(b, cg):
        if cg.under:
            tops.append(b.env_num(q.mount.y) + q.h if q.mount else q.h)
            continue
        m = inv @ b.matrix(q.id, 1.0)
        ys = [(m @ np.array([x, y, 0, 1.0]))[1] for x, y in q.poly]
        tops.append(max(ys))
    return tops


def _has_notch(b: Built, cg):
    for q in _covering(b, cg):
        if q.spec.profil_ust.tip == "oyuk":
            return True
    return False

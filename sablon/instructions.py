"""Yapım aşamaları: malzeme listesi, aletler ve tasarımdan türetilmiş sıralı adımlar.

Sıralama, atölye mantığını izler: önce düzken yapılabilecekler (delik, çıtçıt, cep
dikişi), sonra katlama gerektiren dikişler, en son kilitleme ve kenar bitirme.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import materials as M
from .engine import Built


@dataclass
class Step:
    title: str
    text: list[str]
    image: dict | None = None   # {"fold": ..., "caption": ...}


@dataclass
class Instructions:
    bom: list[tuple[str, str]]
    tools: list[str]
    steps: list[Step]
    difficulty: int
    hours: float
    notes: list[str] = field(default_factory=list)


def _path_level(b: Built, a: str, c: str) -> int:
    """İki panelin birbirine göre konumu hangi kat sırasından sonra oturur?"""
    pa, pc = b.panels[a], b.panels[c]
    if pa.part != pc.part:
        # monte parça ↔ ana panel: monte kökten itibaren göreli konum sabit
        return 0

    def chain(x):
        out = []
        while x:
            out.append(x)
            x = b.panels[x].parent
        return out

    ca, cc = chain(a), chain(c)
    common = next((x for x in ca if x in cc), None)
    if common is None:
        return 0
    path = ca[:ca.index(common)] + cc[:cc.index(common)]
    return max([b.panels[x].spec.kat_sirasi for x in path] or [0])


def make(b: Built) -> Instructions:
    d = b.design
    mat = M.material(d.malzeme)
    t = b.env["t"]
    feats = list(d.ozellikler) + b.auto_features
    has = lambda tip: any(f.tip == tip for f in feats)  # noqa: E731
    stitches = b.stitches
    snaps = [s for s in b.snaps if s.kind == "citcit"]
    magnets = [s for s in b.snaps if s.kind == "miknatis"]
    mounted = [pid for pid, r in b.roots.items() if b.panels[r].mount is not None and b.panels[r].mount.ana_panel]
    fold_levels = sorted({p.spec.kat_sirasi for p in b.panels.values() if p.parent and abs(p.angle) > 1 and p.spec.kat_sirasi})
    unordered_folds = [p for p in b.panels.values() if p.parent and abs(p.angle) > 1 and not p.spec.kat_sirasi]
    if unordered_folds:
        fold_levels = sorted(set(fold_levels) | {max(fold_levels or [0]) + 1})
        for p in unordered_folds:
            p.spec.kat_sirasi = fold_levels[-1]
    lock_levels = {b.panels[f.panel].spec.kat_sirasi for f in feats if f.tip == "kilit_yarigi"}

    # --- dikişlerin katlama gereksinimi
    st_level = []
    for st in stitches:
        lv = max([_path_level(b, st["panel"], tg) for tg in st["targets"]] or [0])
        st_level.append(lv)
    thread_cm = sum(4 * st["length"] + 300 for st in stitches) / 10

    # --- malzeme listesi
    area = sum(b.area_cm2(pid) * part.adet for pid, part in b.parts.items())
    bom = [(f"{mat.ad}, {t:g} mm", f"≈ {area * 1.25 / 100:.1f} dm² (%25 fire dahil) ≈ {area * 1.25 / 929:.2f} ft²")]
    for pid, part in b.parts.items():
        if b.part_mat[pid] != d.malzeme or abs(b.part_t[pid] - t) > 1e-6:
            pm = M.material(b.part_mat[pid])
            bom.append((f"{part.ad or pid}: {pm.ad}, {b.part_t[pid]:g} mm", f"≈ {b.area_cm2(pid) * part.adet * 1.25 / 100:.1f} dm²"))
    if stitches:
        bom.append((M.thread_for(t), f"≈ {thread_cm:.0f} cm (dikiş başına 4×hat + 30 cm)"))
    by_size: dict = {}
    for s in snaps:
        by_size[s.size] = by_size.get(s.size, 0) + 1
    for k, n in by_size.items():
        bom.append((M.SNAPS[k].ad, f"{n} takım (şapka, dişi, erkek, dikme)"))
        if not mat.sert:
            bom.append(("Takviye pulu (Ø10–12 mm ince vaketa)", f"{n * 2} adet"))
    if magnets:
        bom.append(("Gizli mıknatıs çifti", f"{len(magnets)} çift"))
    n_rivet = sum(1 for f in feats if f.tip == "percin")
    if n_rivet:
        bom.append(("Perçin (çift başlı)", f"{n_rivet} adet"))
    if mounted or magnets:
        bom.append(("Deri yapıştırıcısı", mat.yapistirma.split(";")[0]))
    if mat.tur == "deri":
        bom.append(("Kenar bitirme", "kenar boyası" if not mat.nemlendirme else "tokonole / kitre veya su + kenar boyası (isteğe bağlı)"))

    # --- aletler
    tools = ["Keskin deri bıçağı veya maket bıçağı + yedek uç", "Çelik cetvel (≥30 cm)", "Kesim altlığı",
             "Ölçek kontrolü için cetvel/kumpas"]
    if any(abs(p.angle) > 1 for p in b.panels.values() if p.parent):
        tools.append("Kemik bıçak (kat çizgisi için)")
    if stitches:
        pitch = b.env_num(d.dikis_araligi) if d.dikis_araligi else 3.85
        e = b.env_num(d.kenar_payi) if d.kenar_payi else 3.5
        tools += [f"Zımba (pricking iron) {pitch:g} mm, 4–6 diş + 2 diş (kavisler için)",
                  f"Kenar çizici / pergel ({e:g} mm)", "2 adet künt saraç iğnesi", "Plastik/ahşap tokmak"]
    holes = set()
    for p in b.panels.values():
        for mk in p.marks:
            if mk.kind.value == "hole":
                holes.add(round(mk.prim.r * 2, 1))
    if holes:
        tools.append("Yuvarlak zımba: " + ", ".join(f"Ø{h:g} mm" for h in sorted(holes)))
    for k in by_size:
        tools.append(f"{M.SNAPS[k].ad} çakma aparatı")
    if mat.tur == "deri":
        tools += [M.beveler_for(t), "Zımpara 400/800/1200", "Perdah aleti (ahşap/kanvas)" if mat.nemlendirme else "Kenar boyası aplikatörü"]
    skive = t >= 1.6 and any(abs(p.angle) >= 150 for p in b.panels.values() if p.parent)
    if skive:
        tools.append("İnceltme (skiving) bıçağı")

    # --- adımlar
    steps: list[Step] = []
    steps.append(Step("Kalıbı hazırlayın", [
        "PDF'i yazıcıda '%100 / Gerçek boyut' ile basın; 50 mm kareyi cetvelle ölçün.",
        "Çok sayfalı baskıda sayfaları ◆ işaretlerinden hizalayıp bantlayın.",
        "Kalıbı kartona (ör. 1 mm mukavva) yapıştırıp kesin: tekrar tekrar kullanılabilir, kenarı bıçağa kılavuz olur.",
        "Delik, çıtçıt ve dikiş noktalarını kartonda iğneyle delin; deriye aktarırken kullanacaksınız."]))
    parts_txt = [f"{(part.ad or pid)}: {part.adet} adet ({b.part_t[pid]:g} mm {M.material(b.part_mat[pid]).ad})"
                 for pid, part in b.parts.items()]
    steps.append(Step("Deriyi seçin ve kalıbı yerleştirin", [mat.kesim_notu] + parts_txt +
                      ["Omurga okunu derinin sırt çizgisine paralel tutun; kat çizgileri omurgaya dik gelirse kat daha temiz olur."],
                      {"fold": 0.0, "caption": "Kesilmiş parça(lar) — açınım", "view": "flat"}))
    cut = ["Önce iç kesimleri yapın: yarık uçlarındaki delikleri zımbalayıp yarıkları delikten deliğe kesin.",
           "Sonra dış hattı cetvel boyunca, bıçağı dik tutarak tek seferde kesin; kavislerde bıçağı kaldırmadan dönün.",
           "Kat çizgilerini ve çıtçıt noktalarını süet yüze kurşun kalem veya gümüş kalemle işaretleyin."]
    steps.append(Step("Kesim", cut))
    if skive:
        steps.append(Step("İnceltme (skiving)", [
            f"{t:g} mm deride 180° katlanan çizgileri iç yüzden V-kanal ile kalınlığın ~%40'ı kadar inceltin.",
            "Üst üste dikilecek kenarları 10 mm genişlikte yarı kalınlığa kadar inceltmek dikiş kenarını zarifleştirir."]))
    pre = (["Dikiş sonrası ulaşılamayacak kenarları (cep ağızları, kapak ucu iç kenarı) şimdi bitirin."] if stitches else []) + [
           f"Kenarları {M.beveler_for(t)} ile pah kırın.", mat.kenar] if mat.tur == "deri" else []
    if pre:
        steps.append(Step("Kenar kırma ve ön perdah", pre))
    if holes or has("yarik") or has("oval_delik") or has("pencere"):
        txt = ["Kalıptaki zımba deliklerini (artı işaretli) uygun çaptaki yuvarlak zımbayla açın."]
        if has("yarik") or has("kilit_yarigi"):
            txt.append("Yarıkları uçlarındaki yırtılma önleyici deliklerden başlayıp delikte bitirerek kesin.")
        if has("oval_delik") or has("pencere"):
            txt.append("Kayış yuvası / pencere gibi iç kesimlerde köşeleri önce yuvarlak zımbayla açıp aradaki düzlükleri bıçakla birleştirin.")
        steps.append(Step("Delikler ve iç kesimler", txt))
    if snaps or magnets:
        txt = []
        for s in snaps:
            src = b.panels[s.src].spec.ad or s.src
            dst = (b.panels[s.dst].spec.ad or s.dst) if s.dst else "?"
            txt.append(f"Ç{s.no} ({M.SNAPS[s.size].ad}): şapka + dişi parça '{src}' paneline, şapka "
                       f"{'dış' if s.src_side < 0 else 'iç'} yüzde görünecek şekilde; erkek + dikme '{dst}' paneline, "
                       f"erkek {'dış' if s.dst_side < 0 else 'iç'} yüzde olacak şekilde çakılır.")
        if snaps:
            txt.append("Çıtçıtları cep ve gövde dikilmeden ÖNCE çakın; sonra arka tarafına ulaşılamaz.")
            if not mat.sert:
                txt.append("Yumuşak deride dikmenin arkasına takviye pulu koyun; aksi hâlde çıtçıt zamanla deriyi yırtar.")
        for s in magnets:
            txt.append(f"M{s.no}: mıknatısları kalıptaki dairelere yapıştırın; üzerine kapatma katı (astar/cep) gelecek.")
        steps.append(Step("Donanım (çıtçıt / mıknatıs)", txt))

    def stitch_step(idxs, title):
        txt = []
        for i in idxs:
            st = stitches[i]
            names = ", ".join(b.panels[x].spec.ad or x for x in [st["panel"]] + st["targets"])
            txt.append(f"{st['label'] or 'Dikiş'} ({names}): {st['holes']} delik, hat {st['length']:.0f} mm, "
                       f"≈ {(4 * st['length'] + 300) / 10:.0f} cm ip.")
        txt += ["Katları kenarları hizalı olacak şekilde ince yapıştırıcıyla birleştirin (dikiş hattının dışında kalan 3–4 mm şerit).",
                "Zımbayı kalıptaki noktalara oturtarak tüm katları birlikte delin; köşelerde 2 dişli zımba kullanın.",
                "Saraç dikişi: ipin iki ucuna iğne takın, her delikten iki iğneyi karşılıklı geçirin; başta ve sonda 2 delik geri dikin.",
                "İpi kesip ucunu çakmakla eritin veya bir delik içine gizleyin."]
        steps.append(Step(title, txt))

    flat_st = [i for i, lv in enumerate(st_level) if lv == 0]
    if flat_st:
        stitch_step(flat_st, "Düzken dikiş (cepler / monte parçalar)")
    for lv in fold_levels:
        group = [p for p in b.panels.values() if p.parent and p.spec.kat_sirasi == lv and abs(p.angle) > 1]
        names = ", ".join(sorted({p.spec.ad or p.id for p in group}))
        kinds = {("vadi" if p.angle > 0 else "dağ") for p in group}
        txt = [f"Katlanan paneller: {names} ({' / '.join(sorted(kinds))} kat).", mat.katlama]
        if lv in lock_levels:
            txt.append("Kilit kafasını hafifçe bükerek yarığa itin; kafa yarıktan geniş olduğu için içeride kilitlenir.")
        steps.append(Step(f"Katlama {lv}", txt, {"fold": {pid: (1.0 if p.parent and 0 < p.spec.kat_sirasi <= lv else 0.0)
                                                           for pid, p in b.panels.items()},
                                                  "caption": f"Katlama {lv} sonrası"}))
        due = [i for i, l in enumerate(st_level) if l == lv]
        if due:
            stitch_step(due, f"Katlı hâlde dikiş ({lv})")
    if mat.tur == "deri":
        steps.append(Step("Kenar bitirme", [f"Dış kenarları birlikte zımparalayın (katlar tek kenar gibi görünsün).", mat.kenar]))
    fin = [mat.son_islem]
    if b.contents:
        c = b.contents[0]
        fin.append(f"İçine {c.spec.adet} {'kart' if c.spec.tip == 'kart' else c.spec.tip} koyup bir gece bekletin; "
                   "deri içeriğe göre şekil alır.")
    steps.append(Step("Son işlem", fin, {"fold": 1.0, "caption": "Bitmiş ürün"}))

    n_holes = sum(st["holes"] * (1 + len(st["targets"])) for st in stitches)
    score = 1 + (len(stitches) > 0) + (len(fold_levels) > 2) + (len(snaps) + len(magnets) > 0) + (n_holes > 150) + (len(b.parts) > 2)
    difficulty = max(1, min(5, score))
    hours = 0.75 + n_holes * 0.012 + len(fold_levels) * 0.15 + len(snaps) * 0.1 + len(b.parts) * 0.3
    return Instructions(bom, tools, steps, difficulty, round(hours * 2) / 2)

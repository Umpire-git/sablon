"""Dikişsiz yapım aşamaları: malzeme listesi, aletler ve tasarımdan türetilmiş sıralı adımlar.

Atölye mantığı: kesim → iç kesimler ve delikler (düzken) → kenar bitirme (katlamadan önce,
tüm kenarlara ulaşılabilirken) → tek kattaki çıtçıtlar → kat sırasıyla katlama ve kilitleme →
katları birleştiren perçin/vidalar (o katlar oturduktan sonra) → içerikle şekillendirme.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import materials as M
from .engine import Built, fold_step_numbers


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


def _rel_level(b: Built, a: str, c: str) -> int:
    """İki panelin birbirine göre son konumuna hangi kat sırasından sonra ulaştığı."""
    pa, pc = b.panels[a], b.panels[c]
    if pa.part != pc.part:
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


def _name(b: Built, pid: str) -> str:
    return b.panels[pid].spec.ad or pid


def make(b: Built) -> Instructions:
    d = b.design
    mat = M.material(d.malzeme)
    t = b.env["t"]
    feats = list(d.ozellikler)
    has = lambda tip: any(f.tip == tip for f in feats)  # noqa: E731
    snaps = b.snaps
    fold_levels = sorted({p.spec.kat_sirasi for p in b.panels.values() if p.parent and p.spec.kat_sirasi})
    for p in b.panels.values():
        if p.parent and abs(p.angle) > 1 and not p.spec.kat_sirasi:
            p.spec.kat_sirasi = (max(fold_levels) + 1) if fold_levels else 1
    fold_levels = sorted({p.spec.kat_sirasi for p in b.panels.values() if p.parent and p.spec.kat_sirasi})

    # --- malzeme listesi
    area = sum(b.area_cm2(pid) * part.adet for pid, part in b.parts.items())
    bom = [(f"{mat.ad}, {t:g} mm", f"≈ {area * 1.3 / 100:.1f} dm² (%30 fire dahil) ≈ {area * 1.3 / 929:.2f} ft²")]
    by_size: dict = {}
    for s in snaps:
        by_size[s.size] = by_size.get(s.size, 0) + 1
    for k, n in by_size.items():
        bom.append((M.SNAPS[k].ad, f"{n} takım (şapka, dişi, erkek, dikme)"))
        if not mat.sert:
            bom.append(("Takviye pulu (Ø12 mm, ince vaketa)", f"{n} adet"))
    for tip in ("percin", "vida"):
        n = sum(1 for f in b.fasteners if f["tip"] == tip)
        if n:
            fs = M.FASTENERS[tip]
            tot = max(sum(b.panels[x].t for x in f["layers"]) for f in b.fasteners if f["tip"] == tip)
            bom.append((fs.ad, f"{n} adet (dikme boyu ~{tot + 0.5:.1f} mm toplam kalınlığa göre)"))
    bom.append(("Kenar bitirme", "su + tokonole/kitre, isteğe bağlı kenar boyası" if mat.nemlendirme
                else "kenar boyası + arı mumu"))
    bom.append(("Dikiş ve yapıştırıcı", "GEREKMEZ (dikişsiz tasarım)"))

    # --- aletler
    tools = ["Keskin deri bıçağı + yedek uç", "Çelik cetvel (≥30 cm)", "Kesim altlığı", "Kemik bıçak (kat çizgileri)"]
    holes = set()
    for p in b.panels.values():
        for mk in p.marks:
            if mk.kind.value == "hole":
                holes.add(round(mk.prim.r * 2, 1))
    if holes:
        tools.append("Yuvarlak zımba: " + ", ".join(f"Ø{h:g} mm" for h in sorted(holes)))
    if has("oval_delik"):
        tools.append("Oval (kemer) zımbası veya iki yuvarlak zımba + bıçak")
    for k in by_size:
        tools.append(f"{M.SNAPS[k].ad} çakma aparatı + plastik tokmak")
    if any(f["tip"] == "percin" for f in b.fasteners):
        tools.append("Perçin çakma aparatı")
    if any(f["tip"] == "vida" for f in b.fasteners):
        tools.append("Düz tornavida (şikago vidası için), isteğe bağlı vida sabitleyici")
    tools += [M.beveler_for(t), "Zımpara 400/800/1200",
              "Perdah aleti + sünger (ılık su)" if mat.nemlendirme else "Kenar boyası aplikatörü + saç kurutma makinesi"]
    if t >= 1.8 and any(abs(p.angle) >= 150 for p in b.panels.values() if p.parent):
        tools.append("İnceltme (V-kanal) bıçağı")

    # --- adımlar
    steps: list[Step] = []
    steps.append(Step("Kalıbı hazırlayın", [
        "PDF'i '%100 / Gerçek boyut' ile basın; 50 mm kareyi cetvelle ölçün.",
        "Çok sayfalı baskıda sayfaları ◆ işaretlerinden hizalayıp bantlayın.",
        "Kalıbı asetat (şeffaf şablon plastiği) üzerine aktarıp kesin: kalıcı olur, kenarı bıçağa kılavuzluk eder.",
        "Yarık, delik ve çıtçıt noktalarını şablonda iğneyle delin; deriye aktarırken kullanacaksınız."]))
    parts_txt = [f"{(part.ad or pid)}: {part.adet} adet" for pid, part in b.parts.items()]
    steps.append(Step("Deriyi seçin ve kalıbı yerleştirin", [mat.kesim_notu] + parts_txt + [
        "Dikişsiz yapıda deri yükü kendisi taşır: kilit dilleri ve katların derinin en sıkı (sırt) bölgesine gelmesine "
        "dikkat edin; karın ve kenar bölgelerinden kesmeyin."], {"fold": 0.0, "caption": "Kesilmiş parça (açınım)", "view": "flat"}))
    cut = ["Önce iç kesimler: yarık uçlarındaki küçük delikleri zımbalayın, yarıkları delikten deliğe kesin "
           "(delik, yarığın yırtılmasını durdurur)."]
    if has("oval_delik") or has("pencere"):
        cut.append("Oval yuva / pencere köşelerini önce yuvarlak zımbayla açıp aradaki düzlükleri bıçakla birleştirin.")
    cut += ["Sonra dış hattı cetvel boyunca, bıçağı dik tutarak tek seferde kesin; kavislerde bıçağı kaldırmadan dönün.",
            "Kat çizgilerini süet yüze kurşun kalemle işaretleyin."]
    steps.append(Step("Kesim", cut))
    if holes:
        steps.append(Step("Delikler", ["Artı işaretli zımba deliklerini kalıptaki çaplarla, deri düzken açın. Çıtçıt ve "
                                       "vida delikleri katlanınca karşılıklı gelecek şekilde hesaplandı; yerini değiştirmeyin."]))
    steps.append(Step("Kenar bitirme (katlamadan önce)", [
        "Dikişsiz üründe tüm kenarlar görünür kalır: katlamadan önce, düzken bitirmek çok daha kolaydır.",
        f"Kenarları {M.beveler_for(t)} ile her iki yüzden pah kırın.", mat.kenar,
        "Yarık kenarlarını da hafifçe perdahlayın: dil geçerken deriyi kesmez."]))
    prep = [mat.katlama]
    if t >= 1.8 and any(abs(p.angle) >= 150 for p in b.panels.values() if p.parent):
        prep.append("180° katlanan çizgileri iç yüzden V-kanal ile hafifçe inceltin.")
    steps.append(Step("Kat çizgilerini hazırlayın", prep +
                      ["Her kat çizgisini cetvel ve kemik bıçakla süet yüzden bastırarak çizin; vadi katlar süet yüze, "
                       "dağ katlar damar yüze doğru katlanır."]))
    if snaps:
        txt = []
        for s in snaps:
            src = _name(b, s.src)
            dst = _name(b, s.dst) if s.dst else "?"
            txt.append(f"Ç{s.no} ({M.SNAPS[s.size].ad}): şapka + dişi '{src}' paneline (şapka "
                       f"{'damar/dış' if s.src_side < 0 else 'süet/iç'} yüzde); erkek + dikme '{dst}' paneline "
                       f"(erkek {'damar/dış' if s.dst_side < 0 else 'süet/iç'} yüzde).")
        txt.append("Çıtçıtları deri düzken çakın: katlandıktan sonra arka tarafa ulaşılamaz.")
        if not mat.sert:
            txt.append("Yumuşak deride dikmenin arkasına takviye pulu koyun.")
        steps.append(Step("Çıtçıtlar", txt))

    fast_level = [max(_rel_level(b, f["panel"], x) for x in f["layers"][1:]) if len(f["layers"]) > 1 else 0
                  for f in b.fasteners]
    def fastener_step(idxs):
        if not idxs:
            return
        kinds = sorted({b.fasteners[i]["tip"] for i in idxs})
        title = " ve ".join("Perçinler" if k == "percin" else "Şikago vidaları" for k in kinds)
        txt = [f"{len(idxs)} adet: " + "; ".join(", ".join(_name(b, x) for x in b.fasteners[i]["layers"]) for i in idxs) + ".",
               "Delikler artık üst üste; dikmeyi içten, başı dıştan geçirin."]
        if "vida" in kinds:
            txt.append("Şikago vidasına bir damla vida sabitleyici sürerek sıkın.")
        if "percin" in kinds:
            txt.append("Perçini düz bir örs üzerinde tek, kararlı bir darbeyle çakın.")
        steps.append(Step(title, txt))

    fastener_step([i for i, lv in enumerate(fast_level) if lv == 0])
    lock_necks = {lk["neck"] for lk in b.locks}
    for lv in fold_levels:
        group = [p for p in b.panels.values() if p.parent and p.spec.kat_sirasi == lv]
        folding = [p for p in group if abs(p.angle) > 1]
        heads = [p for p in group if p.spec.yariktan_gecer]
        txt = []
        if folding:
            names = ", ".join(sorted({_name(b, p.id) for p in folding}))
            kinds = " / ".join(sorted({"vadi" if p.angle > 0 else "dağ" for p in folding}))
            txt.append(f"Katlanan paneller: {names} ({kinds} kat, {', '.join(sorted({f'{abs(p.angle):.0f}°' for p in folding}))}).")
        if any(p.id in lock_necks for p in folding):
            txt.append("Dil boyunlarını gövdenin altından geçirerek yarıkların hizasına getirin.")
        if heads:
            txt.append("Kilit kafasını uzunlamasına hafifçe bükün, yarıktan içeri itin ve düzeltin: kafa yarıktan "
                       "geniş olduğu için içeride kilitlenir. Zorlanırsa yarığın kenarlarını değil, kafayı bükün.")
        title = "Kilitleme" if heads and not folding else f"Katlama {fold_step_numbers(b.panels.values()).get(lv, lv)}"
        steps.append(Step(title, txt, {"fold": {pid: (1.0 if p.parent and 0 < p.spec.kat_sirasi <= lv else 0.0)
                                                for pid, p in b.panels.items()},
                                       "caption": f"{title} sonrası"}))
        fastener_step([i for i, l in enumerate(fast_level) if l == lv])
    shape = []
    if b.contents:
        c = b.contents[0]
        what = {"kart": "kart", "banknot": "banknot", "anahtar": "anahtar"}.get(c.spec.tip, "içerik")
        shape.append(f"İçine {c.spec.adet} {what} koyun; ürün bu hacme göre şekil alacak.")
    if mat.nemlendirme:
        shape.append("Katları ve gövdeyi süngerle hafif nemlendirip elle şekillendirin, bir gece içeriğiyle kurumaya bırakın.")
    else:
        shape.append("Saç kurutma makinesiyle ılıtıp elle bastırarak şekillendirin; soğurken şeklini alır.")
    steps.append(Step("Şekillendirme", shape))
    steps.append(Step("Son işlem", [mat.son_islem], {"fold": 1.0, "caption": "Bitmiş ürün"}))
    from .checks import pull_strip_data
    for d in pull_strip_data(b):
        steps.append(Step("Kullanım: çekme şeridi", [
            f"Gövdenin altından taşan şerit ucunu tutup aşağı doğru çekin: şerit U kıvrımından makara gibi döner, "
            f"kartlar yaklaşık {d['lift']:.0f} mm yükselir ve üstten {d['visible']:.0f} mm görünür.",
            "Kartları elle geri ittiğinizde şerit de eski yerine döner.",
            "Şerit ucunu birkaç kez çekip bırakarak deriyi alıştırın; ilk günlerde biraz sert gelmesi normaldir.",
        ], {"fold": 1.0, "pull": 1.0, "caption": "Şerit çekilmiş: kartlar yükseldi"}))

    n_feat = len(b.locks) + len(snaps) + len(b.fasteners)
    score = 1 + (len(fold_levels) > 2) + (len(b.locks) > 0) + (n_feat > 3) + (len(b.parts) > 1)
    difficulty = max(1, min(5, score))
    hours = 0.75 + 0.2 * len(fold_levels) + 0.15 * n_feat + 0.3 * len(b.parts)
    return Instructions(bom, tools, steps, difficulty, round(hours * 2) / 2)

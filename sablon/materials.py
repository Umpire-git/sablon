"""Deri ve donanım bilgi bankası (vaketa, crazy horse, çıtçıt, perçin, şikago vidası...).

Değerler atölye pratiğinden alınmış yaklaşık değerlerdir; tedarikçinizin ölçüleriyle
güncelleyebilirsiniz. Kontroller ve yapım talimatları buradan beslenir.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Material:
    key: str
    ad: str
    tur: str                      # "deri"
    aciklama: str
    kalinlik_onerilen: tuple[float, float]
    renk: str                     # 3B ön izleme varsayılan rengi
    sert: bool                    # dikişsiz kilit/katlı yapı tutar mı
    nemlendirme: bool             # kat yerinde nemlendirme/kalıplama uygun mu
    kenar: str                    # kenar bitirme önerisi
    katlama: str
    yapistirma: str
    son_islem: str
    kesim_notu: str
    notlar: tuple[str, ...] = field(default_factory=tuple)


MATERIALS: dict[str, Material] = {
    m.key: m
    for m in [
        Material(
            "vaketa", "Vaketa (bitkisel tabaklı dana)", "deri",
            "Sıkı, dolgun, bitkisel tabaklanmış dana derisi. Kenarı çok iyi perdahlanır, ıslakken kalıplanır, "
            "zamanla patina yapar.",
            (1.0, 2.0), "#c4925e", True, True,
            "Kenar kırıcıyla pah kırın, 400→800→1200 kum zımparalayın, su veya tokonole/kitre ile kanvas veya "
            "ahşap perdah aletiyle parlatın. İsteğe bağlı kenar boyası.",
            "Kat çizgisini kemik bıçakla bastırın; deri hafif nemliyken (ılık su, sünger) katlayıp ağırlık "
            "altında kurutun. 1.6 mm üzerinde kat yerini içten V-kanal ile inceltin.",
            "Kontak (neopren) veya su bazlı deri yapıştırıcısı; yapıştırma yüzeyini hafifçe zımparalayın.",
            "Kuruduktan sonra ince kat deri balmı / neatsfoot yağı; parlak isteniyorsa mum bazlı cila.",
            "Sırt (omurga) bölgesinden, damar yüzü kusursuz alandan kesin; karın kısmı esner, kullanmayın.",
        ),
        Material(
            "crazy_horse", "Crazy Horse (yağlı-mumlu pull-up deri)", "deri",
            "Yağ ve mumla doyurulmuş, bükülünce/çizilince rengi açılan (pull-up) deri. Vintage görünüm; "
            "vaketaya göre daha yumuşak ve esnek.",
            (1.2, 2.2), "#5b3820", False, False,
            "Yağlı yapı nedeniyle su ile perdahlanmaz: pah kırıp zımparalayın, ardından kenar boyası (2–3 ince kat, "
            "aralarda zımpara) veya arı mumu ile sıcak perdah uygulayın.",
            "NEMLENDİRMEYİN (lekelenir). Kemik bıçakla bastırıp katlayın; hafif ısı (saç kurutma makinesi) "
            "pull-up rengini geri getirir. Kat yerinde renk açılması doğaldır.",
            "Yağlı yüzey yapıştırıcıyı iterek tutar: yapıştırma bölgesini zımparalayıp kontak yapıştırıcıyı "
            "iki kat sürün.",
            "Yumuşak bezle ovun; çizikler parmak sıcaklığıyla kaybolur. Gerekirse pull-up wax.",
            "Pull-up çizilmeleri kesimde de oluşur: kalıbı arka (süet) yüze çizin, damar yüzü kesim altlığına "
            "temiz bez koyun.",
            ("Yumuşak olduğu için çıtçıt ve kilit dili bölgelerinde içten takviye (ince vaketa/astar) önerilir.",),
        ),
    ]
}


@dataclass(frozen=True)
class Snap:
    key: str
    ad: str
    sapka_cap: float   # şapka (kapak) çapı mm
    dikme_delik: float # zımba deliği çapı mm
    kavrama: float     # şapka+erkek arasında sıkıştırılabilecek toplam deri kalınlığı (yaklaşık)


SNAPS = {
    s.key: s for s in [
        Snap("mini", "Mini çıtçıt (10 mm)", 10.0, 2.5, 3.0),
        Snap("L20", "Çıtçıt no:20 (12.5 mm)", 12.5, 3.0, 3.8),
        Snap("L24", "Çıtçıt no:24 (15 mm)", 15.0, 3.5, 4.5),
    ]
}

@dataclass(frozen=True)
class Fastener:
    key: str
    ad: str
    bas_cap: float     # baş (kapak) çapı mm
    delik: float       # zımba deliği mm
    kavrama: tuple[float, float]  # birleştirebileceği toplam deri kalınlığı aralığı (yaklaşık)


FASTENERS = {
    "percin": Fastener("percin", "Çift başlı perçin (8 mm baş)", 8.0, 2.5, (2.0, 6.0)),
    "vida": Fastener("vida", "Şikago vidası (10 mm baş, 5 mm dikme)", 10.0, 4.5, (3.0, 7.0)),
}

CONTENTS = {  # tip: (genişlik, yükseklik, tek kalınlık)
    "kart": (85.6, 53.98, 0.76),          # ISO/IEC 7810 ID-1
    "banknot": (160.0, 72.0, 0.1),        # en büyük yaygın banknot ölçüsüne yakın (zarf payı)
    "anahtar": (30.0, 60.0, 3.0),
}


def material(key: str) -> Material:
    try:
        return MATERIALS[key]
    except KeyError:
        raise KeyError(f"Bilinmeyen malzeme '{key}'. Mevcut: {', '.join(MATERIALS)}") from None


def beveler_for(t: float) -> str:
    if t <= 1.2:
        return "no:1 (0.8 mm) kenar kırıcı"
    if t <= 2.0:
        return "no:2 (1.0 mm) kenar kırıcı"
    return "no:3 (1.2 mm) kenar kırıcı"

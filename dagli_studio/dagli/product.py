"""Ürün modülü arayüzü.

Her ürün `urunler/<kisa_ad>.py` dosyasında `Product` alt sınıfı olarak tanımlanır ve
modül düzeyinde `PRODUCT = SinifAdi()` verir. Motor gerisini yapar: kontroller, en kötü durum
taraması, satış PDF'leri (A4 + Letter + tam boy), kesim dosyaları, Etsy görselleri,
SEO'lu ilan, yapay zekâ görsel promptları.

Zorunlu:
  meta             : Meta (ad, SKU, sürüm, ölçü, deri aralığı ...)
  parts()          : list[Part] — düz parçalar (mm)
  scene(t)         : fold3d.Scene — 3B katlama (fold 0→1)
  steps()          : list[Step] — kesim adımları otomatik çizilir, katlama adımları sahneden
  lock_check(case) : list[str] — tek bir en kötü durum kombinasyonu için kilit hataları

İsteğe bağlı: closeups(), troubleshooting, care, words, seo
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Callable

from .geom import Part
from .locks import LockCase


@dataclass
class Meta:
    name: str  # İngilizce ürün adı, ör. "No-Stitch Round Pen Cup"
    slug: str  # dosya adı, ör. "Dagli_Round_Pen_Cup"
    sku: str
    version: str = "1.0"
    kind: str = "pattern"  # "pattern" | "signature" (yalnız bitmiş ürün satılır)
    finished_size: str = ""
    leather: str = "1.4–2.0 mm (3.5–5 oz) firm leather"
    t_range: tuple[float, float] = (1.2, 2.0)  # müşteriye önerilen deri aralığı
    t_test: tuple[float, float] = (0.2, 2.4)  # en kötü durum taraması aralığı
    tested: str = ""  # "Made and tested in 2.0 mm oiled pull-up leather." (prototip yoksa boş)
    hardware: str = "none"
    lock_summary: str = ""
    tools: str = ("craft knife, steel ruler, cutting mat, Ø 2 mm round punch (1.5–3 mm also work), "
                  "bone folder, edge slicker or edge paint")
    matching: str = ""  # eşleşen diğer kalıplar
    build_time: str = "about 1 hour"
    skill: str = "Beginner – no sewing"
    grain_color: str = "#7a4524"
    flesh_color: str = "#d9b98f"
    t_draw: float = 1.6  # 3B çizimlerde kullanılan kalınlık


@dataclass
class Step:
    text: str
    kind: str = "fold"  # print|trace|punch|slits|outline|cuts|edges|crease|fold|done|custom
    fold: float = 1.0  # kind=fold/done: 3B sahnenin katlanma oranı
    az: float = -35.0
    el: float = 30.0
    caption: str = ""  # çizim altındaki kısa yazı
    reveals_pattern: bool = False  # Etsy kolajında bulanıklaştırılır
    draw: Callable | None = None  # kind=custom: draw(canvas, x, y, w, h, product)
    arrows: list = field(default_factory=list)  # [((x0,y0),(x1,y1))] kutu içinde 0..1 normalize


@dataclass
class Closeup:
    title: str
    text: str
    fold: float = 1.0
    az: float = 0.0
    el: float = 20.0
    caption: str = ""
    draw: Callable | None = None
    zoom_panels: list[str] | None = None  # yalnızca bu paneller (yakın plan)
    zoom_near: tuple[str, float] | None = None  # (panel adı, yarıçap mm): o panelin çevresi


@dataclass
class Seo:
    """Etsy SEO girdileri. Rakip taramasından gelen kelimelerle `seo.py` birleştirir."""
    primary: str  # ana arama ifadesi, ör. "leather pen holder pattern"
    title: str = ""  # elle başlık (boşsa otomatik)
    keywords: list[str] = field(default_factory=list)  # ürüne özgü ifadeler
    occasion: str = ""  # Etsy "Occasion" niteliği
    holidays: list[str] = field(default_factory=list)
    section: str = "PDF Patterns"
    price_usd: tuple[float, float] = (8.0, 12.0)
    cross_links: list[str] = field(default_factory=list)
    what_it_does: str = ""
    use_cases: list[str] = field(default_factory=list)


class Product:
    meta: Meta
    seo: Seo
    troubleshooting: list[tuple[str, str]] = []
    care: list[tuple[str, str]] = []
    words: list[tuple[str, str]] = [
        ("Grain / flesh side", "smooth outer face / rougher inner face."),
        ("Stop hole", "Ø 2 mm hole at each slit end; stops tearing."),
        ("Fold line", "dashed line: crease it on the flesh side, never cut it."),
    ]
    # AI görsel promptları için
    product_block: str = ""  # tam şekil tarifi (İngilizce)
    product_block_tr: str = ""
    must_not: list[str] = ["stitching", "glue lines", "rivets or snaps", "logos or text", "extra pockets"]
    shots: list[tuple[str, str, str]] = []  # (dosya_adı, İngilizce satır, Türkçe çeviri)

    def parts(self) -> list[Part]:
        raise NotImplementedError

    def layout(self) -> list[Part]:
        """Açınım yerleşimi (tek sayfa). Varsayılan: yan yana."""
        from .geom import layout_row
        return layout_row(self.parts())

    def scene(self, t: float | None = None):
        raise NotImplementedError

    def steps(self) -> list[Step]:
        raise NotImplementedError

    def closeups(self) -> list[Closeup]:
        return []

    def lock_check(self, case: LockCase) -> list[str]:
        return []

    def extra_checks(self) -> list[str]:
        """Ürüne özgü ek kontroller (hata metinleri)."""
        return []

    def at_a_glance(self) -> list[tuple[str, str]]:
        m = self.meta
        parts = self.parts()
        out = [("Finished size", m.finished_size),
               ("Pieces", f"{len(parts)} – " + ", ".join(p.name.lower() for p in parts) if len(parts) > 1 else "1 – one piece"),
               ("Leather", m.leather)]
        need = []
        for p in parts:
            w, h = p.size()
            need.append(f"{p.name.lower()} ≈ {w / 10 + 1:.0f} × {h / 10 + 1:.0f} cm")
        out.append(("Leather needed", "; ".join(need)))
        out.append(("Hardware / stitching / glue", m.hardware if m.hardware != "none" else "none"))
        if m.lock_summary:
            out.append(("Locks", m.lock_summary))
        out.append(("Skill / time", f"{m.skill} · {m.build_time}"))
        if m.matching:
            out.append(("Matching patterns", m.matching))
        return out


def load(path: str) -> Product:
    """urunler/xyz.py → PRODUCT nesnesi."""
    import types
    path = os.path.abspath(path)
    name = "urun_" + os.path.splitext(os.path.basename(path))[0]
    mod = types.ModuleType(name)
    mod.__file__ = path
    sys.modules[name] = mod
    with open(path, encoding="utf-8") as fh:  # önbelleksiz: dosya hızla yeniden yazılsa da güncel hali okunur
        exec(compile(fh.read(), path, "exec"), mod.__dict__)
    if not hasattr(mod, "PRODUCT"):
        raise SystemExit(f"{path}: modülde PRODUCT = ... tanımı yok")
    return mod.PRODUCT

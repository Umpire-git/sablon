"""Parametrik şablon altyapısı.

Her ürün tipi bir `Template` alt sınıfıdır: parametreleri (mm), geometriyi,
türetilmiş ölçüleri, tasarım/kullanım kontrollerini ve montaj adımlarını tanımlar.
Yapay zekâ geometri çizmez; yalnızca bu parametreleri seçer/değiştirir. Böylece
çıktı her zaman deterministik ve milimetre hassasiyetindedir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from ..pattern import Pattern


@dataclass(frozen=True)
class Param:
    name: str
    label: str
    default: float
    min: float
    max: float
    unit: str = "mm"
    help: str = ""
    integer: bool = False

    def clamp(self, v: float) -> float:
        v = min(self.max, max(self.min, float(v)))
        return float(round(v)) if self.integer else round(v, 2)


@dataclass
class Finding:
    level: str  # "hata" | "uyari" | "bilgi"
    code: str
    message: str
    suggestion: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message, "suggestion": self.suggestion}


@dataclass
class Measure:
    label: str
    value: float
    unit: str = "mm"


class Template:
    key: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    material: ClassVar[str]
    params: ClassVar[list[Param]]

    # --- parametre yönetimi -------------------------------------------------
    @classmethod
    def param(cls, name: str) -> Param:
        for p in cls.params:
            if p.name == name:
                return p
        raise KeyError(f"'{cls.key}' şablonunda '{name}' parametresi yok")

    @classmethod
    def defaults(cls) -> dict[str, float]:
        return {p.name: p.default for p in cls.params}

    @classmethod
    def resolve(cls, values: dict[str, float] | None = None) -> dict[str, float]:
        """Varsayılanları doldurur, bilinmeyen adları reddeder, aralığa kırpar."""
        out = cls.defaults()
        for k, v in (values or {}).items():
            out[k] = cls.param(k).clamp(v)
        return out

    # --- alt sınıfların dolduracağı kısımlar -------------------------------
    def __init__(self, values: dict[str, float] | None = None):
        self.v = self.resolve(values)

    def build(self) -> Pattern:
        raise NotImplementedError

    def measures(self) -> dict[str, Measure]:
        """Kullanıcının 'şurası uzun' derken kastedebileceği adlandırılmış ölçüler."""
        return {}

    def checks(self) -> list[Finding]:
        return []

    def assembly(self) -> list[str]:
        return []

    def preview_svg(self) -> str:
        return ""

    # --- ortak yardımcılar ----------------------------------------------
    def summary(self) -> dict:
        return {
            "template": self.key,
            "title": self.title,
            "params": self.v,
            "measures": {k: {"label": m.label, "value": round(m.value, 2), "unit": m.unit} for k, m in self.measures().items()},
            "findings": [f.as_dict() for f in self.checks()],
        }

"""Şablon kataloğu. Yeni ürün tipi eklemek için Template alt sınıfı yazıp buraya kaydedin."""
from .base import Finding, Measure, Param, Template
from .dikisli_kartlik import DikisliKartlik
from .dikissiz_kartlik import DikissizKartlik
from .kutu import TuckKutu

REGISTRY: dict[str, type[Template]] = {t.key: t for t in (DikissizKartlik, DikisliKartlik, TuckKutu)}


def get(key: str) -> type[Template]:
    try:
        return REGISTRY[key]
    except KeyError:
        raise KeyError(f"Bilinmeyen şablon '{key}'. Mevcut: {', '.join(REGISTRY)}") from None


__all__ = ["REGISTRY", "get", "Template", "Param", "Finding", "Measure"]

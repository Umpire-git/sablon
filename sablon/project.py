"""Proje dosyası: tasarım (JSON) + değişiklik geçmişi."""
from __future__ import annotations

import json
import os
from datetime import datetime

from .design import Tasarim, from_dict


def load(path: str) -> tuple[Tasarim, list[dict]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    hist = data.pop("gecmis", [])
    return from_dict(data), hist


def save(path: str, design: Tasarim, history: list[dict] | None = None) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    data = design.model_dump()
    data["gecmis"] = history or []
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log(history: list[dict], source: str, request: str, changes: list[str]) -> None:
    history.append({"zaman": datetime.now().isoformat(timespec="seconds"), "kaynak": source,
                    "istek": request, "degisiklikler": changes})


def diff(a: Tasarim, b: Tasarim) -> list[str]:
    """İki tasarım arasındaki alan değişikliklerini okunur liste olarak verir."""
    out: list[str] = []

    def walk(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                walk(x.get(k), y.get(k), f"{path}.{k}" if path else k)
        elif isinstance(x, list) and isinstance(y, list) and all(isinstance(i, dict) and "id" in i for i in x + y):
            xm, ym = {i["id"]: i for i in x}, {i["id"]: i for i in y}
            for k in xm.keys() - ym.keys():
                out.append(f"- {path}[{k}] kaldırıldı")
            for k in ym.keys() - xm.keys():
                out.append(f"+ {path}[{k}] eklendi")
            for k in xm.keys() & ym.keys():
                walk(xm[k], ym[k], f"{path}[{k}]")
        elif isinstance(x, list) and isinstance(y, list) and all(isinstance(i, dict) and "ad" in i for i in x + y) and path == "degiskenler":
            xm, ym = {i["ad"]: i["deger"] for i in x}, {i["ad"]: i["deger"] for i in y}
            for k in sorted(set(xm) | set(ym)):
                if xm.get(k) != ym.get(k):
                    out.append(f"~ değişken {k}: {xm.get(k)} → {ym.get(k)}")
        elif x != y:
            if isinstance(x, list) or isinstance(y, list):
                out.append(f"~ {path}: liste değişti")
            else:
                out.append(f"~ {path}: {x} → {y}")

    walk(a.model_dump(), b.model_dump(), "")
    return out


def set_value(design: Tasarim, key: str, value: str) -> str:
    """ayarla: 'degisken=deger', 'panel.alan=deger' veya tasarım alanı ('kalinlik=1.6')."""
    d = design
    if "." in key:
        pid, field = key.split(".", 1)
        for part in d.parcalar:
            for p in part.paneller:
                if p.id == pid:
                    if field.startswith("profil_") and "." in field:
                        pk, sub = field.split(".", 1)
                        setattr(getattr(p, pk), sub, value)
                    elif field.startswith("kose."):
                        setattr(p.koseler, field[5:], value)
                    elif field == "kat_sirasi":
                        p.kat_sirasi = int(float(value))
                    else:
                        if not hasattr(p, field):
                            raise KeyError(f"panel alanı yok: {field}")
                        setattr(p, field, value)
                    return f"{pid}.{field} = {value}"
        raise KeyError(f"panel bulunamadı: {pid}")
    for v in d.degiskenler:
        if v.ad == key:
            v.deger = value
            return f"değişken {key} = {value}"
    if key in ("kalinlik", "malzeme", "renk", "dikis_araligi", "kenar_payi", "ad"):
        setattr(d, key, value)
        return f"{key} = {value}"
    raise KeyError(f"'{key}' bulunamadı (değişken, panel.alan veya tasarım alanı olmalı)")

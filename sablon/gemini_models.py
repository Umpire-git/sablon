"""Gemini model seçimi: anahtarın erişebildiği modelleri Google'dan sorgular, en uygununu seçer.

Model adları sık değiştiği için sabit ad yazmak yerine:
  * metin/tasarım: en yeni 'pro' (yoksa en yeni 'flash'; 'lite' en son çare)
  * kota dolarsa yedek: en yeni 'flash' (lite olmayan)
  * görsel: adı 'image' içeren en yeni model (pro tercih)
Ortam değişkenleri her zaman önceliklidir: SABLON_GEMINI_TEXT_MODEL, SABLON_GEMINI_MODEL (görsel).
"""
from __future__ import annotations

import os
import re

_CACHE: dict = {}
_SKIP = ("embedding", "tts", "audio", "live", "native-audio", "aqa", "imagen", "veo", "robotics", "computer-use", "learnlm",
         "gemma")


def _version(name: str) -> tuple:
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2) or 0))


def _stable_bonus(name: str) -> int:
    return 0 if ("preview" in name or "exp" in name) else 1


def list_models(client) -> list[str]:
    if "names" in _CACHE:
        return _CACHE["names"]
    names = []
    for m in client.models.list():
        acts = getattr(m, "supported_actions", None) or []
        name = (getattr(m, "name", "") or "").split("/")[-1]
        if "gemini" in name and (not acts or "generateContent" in acts):
            names.append(name)
    _CACHE["names"] = names
    return names


def _rank(names, want: str, image: bool):
    out = []
    for n in names:
        low = n.lower()
        if any(s in low for s in _SKIP):
            continue
        if ("image" in low) != image:
            continue
        tier = 3 if want in low and "lite" not in low else 0
        if want == "flash" and "lite" in low:
            tier = 1
        if not tier:
            continue
        out.append(((tier, _version(low), _stable_bonus(low), -len(low)), n))
    return [n for _, n in sorted(out, reverse=True)]


def pick_text(client) -> str:
    env = os.environ.get("SABLON_GEMINI_TEXT_MODEL")
    if env:
        return env
    names = list_models(client)
    for want in ("pro", "flash"):
        r = _rank(names, want, image=False)
        if r:
            return r[0]
    lite = [n for n in names if "lite" in n and "image" not in n]
    if lite:
        return sorted(lite, key=_version, reverse=True)[0]
    return "gemini-2.5-pro"


def pick_fallback(client, current: str) -> str | None:
    """Kota dolduğunda denenecek daha hafif model (lite olmayan flash)."""
    for n in _rank(list_models(client), "flash", image=False):
        if n != current and "lite" not in n:
            return n
    return None


def pick_image(client) -> str:
    env = os.environ.get("SABLON_GEMINI_MODEL")
    if env:
        return env
    names = list_models(client)
    for want in ("pro", "flash"):
        r = _rank(names, want, image=True)
        if r:
            return r[0]
    any_img = [n for n in names if "image" in n]
    return sorted(any_img, key=_version, reverse=True)[0] if any_img else "gemini-2.5-flash-image"


def reset_cache():
    _CACHE.clear()

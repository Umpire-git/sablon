"""Blender ile fotogerçekçi ürün görselleri.

Geometri motorun 3B modelinden birebir alınır (yapay zekâ bir şey uydurmaz); Blender yalnızca
ışık, malzeme ve kamerayı gerçekçi hesaplar.

Blender şu sırayla aranır:
  1. Python paketi:  pip install bpy   (Python 3.11 gerekir)
  2. SABLON_BLENDER ortam değişkeni (blender.exe yolu)
  3. PATH'teki 'blender' veya Windows/macOS/Linux'taki standart kurulum klasörleri
"""
from __future__ import annotations

import glob
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

from .engine import Built

VIEWS = {
    "urun": dict(fold=1.0, az=-35.0, el=32.0, flip=False),
    "arka": dict(fold=1.0, az=-35.0, el=32.0, flip=True),
    "yari_acik": dict(fold=0.55, az=-30.0, el=40.0, flip=False),
    "acinim": dict(fold=0.0, az=0.0, el=89.0, flip=False),
}


class BlenderYok(RuntimeError):
    pass


def _hex(c: str):
    c = (c or "#9a5a2e").lstrip("#")
    srgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    # Blender renkleri doğrusal (linear) bekler
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in srgb]


def scene_data(b: Built, fold=1.0, az=-35.0, el=32.0, flip=False, size=(1600, 1200), contents=True,
               doku: str | None = None) -> dict:
    from .render3d import build_mesh
    mesh = build_mesh(b, fold, show_contents=contents)
    P = np.stack(mesh.P).astype(float)
    N = np.stack(mesh.N).astype(float)
    if flip:
        P = P * np.array([1.0, -1.0, -1.0])
        N = N * np.array([1.0, -1.0, -1.0])
    allp = P.reshape(-1, 3)
    ctr = (allp.min(0) + allp.max(0)) / 2
    rad = float(np.linalg.norm(allp - ctr, axis=1).max())
    a, e = math.radians(az), math.radians(el)
    fwd = np.array([-math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), -math.sin(e)])
    fov = 2 * math.atan(18 / 85) * min(1.0, size[1] / size[0])  # 85 mm objektif, yatay kadraj
    dist = rad / math.sin(fov / 2) * 1.08
    eye = ctr - fwd * dist
    return {
        "P": P.ravel().round(4).tolist(), "N": N.ravel().round(4).tolist(),
        "UV": np.stack(mesh.UV).ravel().round(3).tolist(), "M": [int(m) for m in mesh.M],
        "base": _hex(b.design.renk), "crazy": b.design.malzeme == "crazy_horse",
        "accent": _hex(next((pt.renk for pt in b.parts.values() if getattr(pt, "renk", "")), b.design.renk)),
        "floor": [0.62, 0.58, 0.53], "zmin": float(allp[:, 2].min()), "ctr": ctr.tolist(),
        "radius": rad, "eye": eye.tolist(), "size": list(size),
        "doku": os.path.abspath(doku) if doku else os.environ.get("SABLON_DOKU", ""),
    }


def find_blender() -> str | None:
    env = os.environ.get("SABLON_BLENDER")
    if env and os.path.exists(env):
        return env
    exe = shutil.which("blender")
    if exe:
        return exe
    pats = [r"C:\Program Files\Blender Foundation\Blender*\blender.exe",
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/opt/blender*/blender", os.path.expanduser("~/blender*/blender")]
    for pat in pats:
        hits = sorted(glob.glob(pat), reverse=True)
        if hits:
            return hits[0]
    return None


def _has_bpy() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except Exception:
        return False


def _command(script: str, args: list[str]) -> list[str]:
    if _has_bpy():
        return [sys.executable, script, "--", *args]
    exe = find_blender()
    if not exe:
        raise BlenderYok(
            "Blender bulunamadı. https://www.blender.org/download/ adresinden Blender'ı kurun "
            "(veya SABLON_BLENDER ortam değişkenine blender.exe yolunu yazın).")
    return [exe, "-b", "--factory-startup", "-P", script, "--", *args]


def render_photo(data: dict, out_path: str, quality: str = "kaliteli") -> str:
    """Render'ı ayrı süreçte çalıştırır (ekran kartı sürücüsü çökerse ana program etkilenmez).
    Hızlı modda Eevee başarısız olursa kendiliğinden Cycles'a geçer."""
    out_path = os.path.abspath(out_path)
    script = os.path.join(os.path.dirname(__file__), "blender_render.py")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        tmp = f.name
    try:
        tries = [quality, "hizli-cycles"] if quality == "hizli" else [quality]
        err = ""
        for q in tries:
            if os.path.exists(out_path):
                os.unlink(out_path)
            res = subprocess.run(_command(script, [tmp, out_path, q]), capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(out_path):
                used = [ln.split()[-1] for ln in res.stdout.splitlines() if ln.startswith("SABLON_RENDER")]
                return used[-1] if used else "blender"
            err = (res.stderr or res.stdout)[-2000:]
        raise RuntimeError("Blender render başarısız:\n" + err)
    finally:
        os.unlink(tmp)


def render_photos(b: Built, base: str, quality: str = "kaliteli", views=None, log=print, doku: str | None = None) -> list[str]:
    size = (1000, 750) if quality == "hizli" else (1600, 1200)
    out = []
    for name in views or VIEWS:
        v = VIEWS[name]
        data = scene_data(b, v["fold"], v["az"], v["el"], v["flip"], size, contents=name != "acinim", doku=doku)
        path = f"{base}_foto_{name}.png"
        import time
        t0 = time.time()
        how = render_photo(data, path, quality)
        log(f"  {path}  ({how}, {time.time() - t0:.0f} sn)")
        out.append(path)
    return out

"""Gemini ile fotoğraf gerçekliğinde ürün görseli (görselden görsele).

Motorun ölçüsü doğru 3B görseli (Blender varsa onun, yoksa yerleşik çizicinin) Gemini'ye
referans olarak verilir; Gemini aynı şekli koruyarak gerçek deri ürün fotoğrafı üretir.
Şekil bizden gelir, gerçekçilik Gemini'den. Yine de yapay zekâ ayrıntı değiştirebilir:
her görseli kalıpla karşılaştırıp kontrol edin.

Gerekenler:  pip install google-genai   ve   GEMINI_API_KEY ortam değişkeni
(ücretsiz anahtar: https://aistudio.google.com/apikey). Model: SABLON_GEMINI_MODEL
ortam değişkeniyle değiştirilebilir.
"""
from __future__ import annotations

import io
import os

from PIL import Image

MODEL = os.environ.get("SABLON_GEMINI_MODEL", "gemini-2.5-flash-image")

LEATHER = {
    "vaketa": ("smooth full-grain vegetable-tanned cowhide leather (Turkish 'vaketa'), firm, with a subtle natural "
               "grain, slightly waxy satin sheen and hand-burnished, slightly darker rounded edges"),
    "crazy_horse": ("oiled and waxed 'crazy horse' pull-up leather: rich, mottled colour that turns lighter where the "
                    "leather is bent or stretched, soft waxy sheen, faint natural scratches, painted/burnished edges"),
}

SCENES = {
    "studyo": "on a seamless warm light-grey studio backdrop with soft diffused light and a gentle contact shadow",
    "ahsap": "on a warm oak wooden table, soft window light from the left, shallow depth of field background",
    "keten": "on natural beige linen fabric, soft daylight, minimal lifestyle product photo",
    "mermer": "on a white marble surface, soft bright daylight, clean premium product photo",
}


class GeminiYok(RuntimeError):
    pass


def prompt(design, scene: str = "studyo") -> str:
    leather = LEATHER.get(design.malzeme, LEATHER["vaketa"])
    return (
        "Turn this 3D render into a high-end, photorealistic product photograph of a handmade leather card holder.\n"
        f"Material: {leather}. Leather colour approximately {design.renk}, thickness about {design.kalinlik} mm.\n"
        "STRICT RULES:\n"
        "- Keep the EXACT shape, proportions, outline, fold positions, flap shape, tab-and-slot locks, snap/rivet "
        "positions and camera angle of the reference image. Do not redesign the product.\n"
        "- The product is STITCHLESS: do NOT add any stitching, seams, thread or glue lines.\n"
        "- Do not add logos, text, extra pockets, extra hardware or straps.\n"
        "- Make it look like real leather: natural softness, gently rounded folds, slight surface irregularities, "
        "realistic light falloff. Cards inside (if visible) stay as plain cards.\n"
        f"Scene: {SCENES.get(scene, SCENES['studyo'])}. Sharp focus on the product, professional e-commerce lighting."
    )


def _client():
    try:
        from google import genai
    except ImportError as e:
        raise GeminiYok("Gemini paketi kurulu değil: pip install google-genai") from e
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise GeminiYok("GEMINI_API_KEY tanımlı değil. Ücretsiz anahtar: https://aistudio.google.com/apikey")
    return genai.Client()


def realistic(image: Image.Image, design, scene: str = "studyo", client=None) -> Image.Image:
    from google.genai import types
    client = client or _client()
    resp = client.models.generate_content(
        model=MODEL,
        contents=[prompt(design, scene), image],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            data = getattr(part, "inline_data", None)
            if data is not None and data.data:
                return Image.open(io.BytesIO(data.data)).convert("RGB")
    text = " ".join(getattr(p, "text", "") or "" for c in resp.candidates or [] for p in (c.content.parts or []))
    raise RuntimeError(f"Gemini görsel döndürmedi. Yanıt: {text[:300] or '(boş)'}")


def realistic_set(images: dict[str, Image.Image], design, base: str, scenes=("studyo",), log=print, client=None) -> list[str]:
    out = []
    for name, im in images.items():
        for sc in scenes:
            path = f"{base}_gercekci_{name}_{sc}.png"
            realistic(im, design, sc, client).save(path)
            log(f"  {path}")
            out.append(path)
    return out

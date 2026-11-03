"""Claude ile: rakip araştırması (web), fikir üretimi (1. kapı), ürün modülü tasarımı + onarım döngüsü (2. kapı).

Anahtar: ANTHROPIC_API_KEY (veya `ant auth login`). Model: DAGLI_MODEL (varsayılan claude-opus-5-5).
Reddedilen isteklerde sunucu tarafı yedek model devreye girer (fallbacks="default").
"""
from __future__ import annotations

import json
import os
import re
import traceback

from pydantic import BaseModel

MODEL = os.environ.get("DAGLI_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

BRAND = """Dagli Leather Studio brand concept (every product must fit):
one piece of leather (plus at most one strap), no stitching, no glue, folds like origami, locks itself with an
engineered mechanism (hook/slit, tongue pair, pinwheel, pull-tab, hidden lock), useful every day. Hardware only if
unavoidable (one snap max). Never assume the buyer's gender."""


class AIError(RuntimeError):
    pass


def _client():
    try:
        import anthropic
    except ImportError as e:
        raise AIError("pip install anthropic") from e
    return anthropic.Anthropic()


def _stream_text(messages, system: str, tools=None, effort="high", max_tokens=64000, log=print) -> tuple[str, object]:
    """Uzun istekler için akış; web aramasında pause_turn devam ettirilir."""
    client = _client()
    msgs = list(messages)
    for _ in range(6):
        kw = dict(model=MODEL, max_tokens=max_tokens, system=system, messages=msgs,
                  output_config={"effort": effort}, betas=[FALLBACK_BETA], fallbacks="default")
        if tools:
            kw["tools"] = tools
        with client.beta.messages.stream(**kw) as st:
            resp = st.get_final_message()
        if resp.stop_reason == "refusal":
            raise AIError("Model isteği reddetti: " + str(getattr(resp, "stop_details", "")))
        if resp.stop_reason == "pause_turn":
            msgs = msgs + [{"role": "assistant", "content": resp.content}]
            continue
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return text, resp
    raise AIError("Web araması çok uzun sürdü (pause_turn sınırı)")


def _parse(text: str, schema: type[BaseModel], instruction: str):
    """Serbest metni şemaya döker (yapılandırılmış çıktı)."""
    client = _client()
    resp = client.messages.parse(
        model=MODEL, max_tokens=16000, output_format=schema,
        messages=[{"role": "user", "content": f"{instruction}\n\n<source>\n{text}\n</source>"}])
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise AIError("Yapılandırılmış çıktı alınamadı")
    return resp.parsed_output


# ---------------------------------------------------------------- rakip araştırması

class Comp(BaseModel):
    title: str
    price: float | None = None
    currency: str = "USD"
    shop: str = ""
    url: str = ""
    favorites: int | None = None
    reviews: int | None = None
    tags: list[str] = []
    digital: bool | None = None


class CompList(BaseModel):
    listings: list[Comp]
    notes: str


def research_competitors(query: str, n: int = 30, log=print) -> tuple[list[dict], str]:
    log(f"  Claude web araması: “{query}” (Etsy rakipleri)...")
    sys = ("You research Etsy competitors for a leather pattern designer. Use web search. Only report what you "
           "actually saw on a page (titles, prices, shop names, URLs, review/favourite counts if shown). Never invent "
           "numbers; leave a field empty when unknown.")
    prompt = (f"Find up to {n} Etsy listings that compete with: “{query}”. Prefer digital PDF leather patterns. "
              "For each: exact title, price in USD (convert only if the page shows USD; else give currency), shop, URL, "
              "reviews/favourites if shown, and whether it is a digital download. Then write short notes: which "
              "constructions dominate (stitched, snaps, rivets, no-sew), what buyers praise or complain about in "
              "visible reviews, gaps a no-sew origami-lock design could fill, and seasonal timing (gift dates in the "
              "next 3–8 weeks).")
    text, _ = _stream_text([{"role": "user", "content": prompt}], sys,
                           tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 12,
                                   "allowed_domains": ["etsy.com"]}], effort="medium", log=log)
    data = _parse(text, CompList, "Extract the competitor listings and the notes. Keep notes in Turkish, concise.")
    return [c.model_dump() for c in data.listings], data.notes


# ---------------------------------------------------------------- 1. kapı: fikirler

def ideas(brief: str, market_md: str = "", log=print) -> str:
    sys = BRAND + ("\nYou are the product designer of Dagli Leather Studio. Write in Turkish, short and clear, natural "
                   "(not AI-sounding). Be honest when an idea is forced or overlaps an existing product. Do not invent "
                   "statistics; use only the market report given.")
    prompt = f"""Brief: {brief}

Market report (from Etsy competitor scan):
{market_md or '(no market data)'}

Gate 1 – offer 2–3 product ideas that fit the brand concept. For each idea:
- what it is (one piece, how it folds, which lock)
- why it sells now (season: pattern buyers buy 3–6 weeks before a gifting date)
- how it differs from competitors (they usually use snaps/rivets/stitching)
- how fast it can be made, rough flat size (must fit ONE A4 / US Letter page if possible)
- risks
Then recommend one and ask: signature product (sell finished only) or pattern?
Format: Markdown, headings per idea."""
    text, _ = _stream_text([{"role": "user", "content": prompt}], sys, effort="high", log=log)
    return text


# ---------------------------------------------------------------- 2. kapı: tasarım kodu

def _api_doc() -> str:
    parts = []
    for f in ("product.py", "geom.py", "locks.py", "fold3d.py"):
        with open(os.path.join(HERE, f), encoding="utf-8") as fh:
            parts.append(f"### dagli/{f}\n```python\n{fh.read()}\n```")
    with open(os.path.join(ROOT, "urunler", "round_pen_cup.py"), encoding="utf-8") as fh:
        parts.append(f"### Example product (verified): urunler/round_pen_cup.py\n```python\n{fh.read()}\n```")
    return "\n\n".join(parts)


DESIGN_RULES = """Design rules (Gate 2):
- Parametric geometry in mm with shapely. One Python module, `PRODUCT = <Class>()` at the end.
- Flat layout must print on ONE A4 and ONE US Letter page (landscape allowed, ≥ 8 mm margins) whenever the product
  size allows; otherwise the booklet tiles pages automatically.
- No part overlaps in the flat layout; slit stop holes ≥ 4 mm from any edge; hook shoulders ≥ 1.5 mm per side;
  neck narrower than the slit opening by ≥ 3 mm. Use dagli.locks.Tongue / Slit and check_tongue_slit.
- lock_check(case) must model the real tolerances: wrapping a corner shifts tabs by about 1.3·t; tube circumference
  changes with t; folds ±1 mm (case.fold); slits marked ±0.7 mm off (case.slit_off) and cut 0.6 mm long
  (case.slit_long); punches 1.5/2/3 mm (case.punch, opening kept constant in the pattern); mirrored tracing
  (case.mirror) for asymmetric designs. Every combination from leather 0.2 to 2.4 mm must pass.
- Stop holes Ø 2 mm. Round inner corners at necks (fillet_inner), tapered hook tips.
- scene(t): fold3d.Scene with panels hinged so fold 0→1 shows the assembly order (use Panel.stage); grain side out.
- steps(): print, trace, punch, slits, outline (cuts if any), edges, crease, then every fold/lock step (kind="fold"
  with a fold value and a good camera az/el), finished state. One short English instruction per step.
- closeups(): the lock(s), using zoom_near.
- English texts for the PDF; never assume the user's gender. Fill troubleshooting, care, words, seo, shots,
  product_block (+ Turkish product_block_tr) and must_not."""


def design(idea: str, out_path: str, rounds: int = 4, log=print) -> tuple[bool, str]:
    """Claude ürün modülünü yazar; motor kontrol eder; hatalar geri verilir. (başarılı mı, son rapor)"""
    sys = (BRAND + "\nYou write Python product modules for the Dagli pattern engine. Output ONLY one complete Python "
           "file in a ```python block. Use only the engine API shown.\n\n" + DESIGN_RULES + "\n\n# Engine API\n" + _api_doc())
    msgs = [{"role": "user", "content": f"Design this product as a new module:\n\n{idea}"}]
    report = ""
    for r in range(1, rounds + 1):
        log(f"  Tasarım turu {r}/{rounds}: Claude modülü yazıyor...")
        text, resp = _stream_text(msgs, sys, effort="xhigh", log=log)
        m = re.search(r"```python\n(.*?)```", text, re.S)
        if not m:
            msgs += [{"role": "assistant", "content": resp.content},
                     {"role": "user", "content": "Return the complete module in one ```python block."}]
            continue
        code = m.group(1)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(code)
        ok, report = _evaluate(out_path)
        log(f"    {report.splitlines()[0] if report else ''}")
        if ok:
            return True, report
        msgs += [{"role": "assistant", "content": resp.content},
                 {"role": "user", "content": "The engine found problems. Fix the design (smallest consistent change, "
                                             "keep what works) and return the full module again.\n\n" + report}]
    return False, report


def _evaluate(path: str) -> tuple[bool, str]:
    from .pipeline import check_product
    from .product import load
    try:
        prod = load(path)
        rep = check_product(prod, quick=False)
        prod.scene(prod.meta.t_draw).render_pil(1.0, size=(200, 150), ss=1)
        prod.steps()
        return rep.ok, rep.text()
    except Exception:
        return False, "Modül çalışmadı:\n" + traceback.format_exc(limit=6)


def ideas_to_json(md: str) -> str:
    return json.dumps({"ideas_markdown": md}, ensure_ascii=False)

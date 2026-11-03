"""Etsy rakip taraması (1. kapı).

Kaynaklar (biri yeter, birden fazlası birleştirilir):
  1. Etsy Open API v3   — ETSY_API_KEY (ve varsa ETSY_SHARED_SECRET). En sağlam veri: başlık, 13 etiket, fiyat, favori.
  2. Claude web araması — ANTHROPIC_API_KEY. Etsy arama sonuçlarını ve ilanları okur, özetler.
  3. CSV                — elle kopyalanmış liste (title, price, tags, favorites, url sütunları).

Çıktı: pazar/<konu>/rapor.md (Türkçe özet) + veri.json (ham ilanlar + analiz).
Rakamlar uydurulmaz: yalnızca bulunan ilanlardan hesaplanır, kaynak ve tarih yazılır.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import statistics
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field

STOP = set("a an and the for with of to in on by your my diy pdf digital download instant pattern patterns template "
           "templates leather handmade gift".split())
FEATURE_WORDS = {
    "stitched": r"\bstitch(?:ed|ing)?\b|\bsew(?:n|ing)?\b|\bhand ?sewn\b",
    "no-sew": r"\bno[- ]?(?:sew|stitch)\b|\bstitchless\b|\bsewless\b|\bseamless\b",
    "snap": r"\bsnaps?\b|\bpress stud\b",
    "rivet": r"\brivets?\b|\bchicago screws?\b",
    "glue": r"\bglue[ds]?\b",
    "svg/cricut": r"\bsvg\b|\bcricut\b",
    "dxf/laser": r"\bdxf\b|\blaser\b",
    "video": r"\bvideo\b|\btutorial\b",
}


@dataclass
class Listing:
    title: str
    price: float | None = None  # USD
    currency: str = "USD"
    tags: list[str] = field(default_factory=list)
    favorites: int | None = None
    reviews: int | None = None
    shop: str = ""
    url: str = ""
    digital: bool | None = None
    source: str = ""


# ---------------------------------------------------------------- kaynaklar

def from_etsy_api(query: str, limit: int = 100, log=print) -> list[Listing]:
    key = os.environ.get("ETSY_API_KEY", "")
    if not key:
        raise RuntimeError("ETSY_API_KEY tanımlı değil (https://www.etsy.com/developers/register)")
    secret = os.environ.get("ETSY_SHARED_SECRET", "")
    header = f"{key}:{secret}" if secret and ":" not in key else key
    out: list[Listing] = []
    offset = 0
    while len(out) < limit:
        q = urllib.parse.urlencode({"keywords": query, "limit": min(100, limit - len(out)), "offset": offset,
                                    "sort_on": "score"})
        req = urllib.request.Request(f"https://openapi.etsy.com/v3/application/listings/active?{q}",
                                     headers={"x-api-key": header, "User-Agent": "dagli-studio/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        res = data.get("results", [])
        for it in res:
            pr = it.get("price") or {}
            price = pr.get("amount") / pr.get("divisor", 100) if pr.get("amount") is not None else None
            out.append(Listing(
                title=it.get("title", ""), price=price, currency=pr.get("currency_code", "USD"),
                tags=[t.lower() for t in it.get("tags", [])], favorites=it.get("num_favorers"),
                url=it.get("url", ""), shop=str(it.get("shop_id", "")),
                digital=(it.get("listing_type") == "download") or bool(it.get("is_digital")), source="etsy-api"))
        if len(res) < 100:
            break
        offset += len(res)
    log(f"  Etsy API: {len(out)} ilan")
    return out


def from_csv(path: str) -> list[Listing]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            price = re.sub(r"[^\d.,]", "", r.get("price", "")).replace(",", ".")
            out.append(Listing(
                title=r.get("title", ""), price=float(price) if price else None,
                tags=[t.strip().lower() for t in re.split(r"[;,|]", r.get("tags", "")) if t.strip()],
                favorites=int(r["favorites"]) if r.get("favorites", "").isdigit() else None,
                reviews=int(r["reviews"]) if r.get("reviews", "").isdigit() else None,
                shop=r.get("shop", ""), url=r.get("url", ""), source="csv"))
    return out


def from_web(query: str, n: int = 30, log=print) -> tuple[list[Listing], str]:
    """Claude web araması ile Etsy'deki rakip ilanları bulur (yalnızca sayfada görünen bilgiler)."""
    from .ai import research_competitors
    items, notes = research_competitors(query, n, log=log)
    return [Listing(**{**i, "source": "web"}) for i in items], notes


# ---------------------------------------------------------------- analiz

def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'\-]+", s.lower()) if w not in STOP and len(w) > 2]


def analyze(items: list[Listing], query: str) -> dict:
    digital = [i for i in items if i.digital is not False]
    prices = sorted(i.price for i in digital if i.price)
    tag_c = Counter(t for i in items for t in set(i.tags))
    word_c = Counter(w for i in items for w in set(_words(i.title)))
    bigram_c = Counter()
    for i in items:
        ws = _words(i.title)
        bigram_c.update(set(" ".join(p) for p in zip(ws, ws[1:])))
    def text(i, k):
        t = (i.title + " " + " ".join(i.tags)).lower()
        return re.sub(FEATURE_WORDS["no-sew"], " ", t) if k == "stitched" else t  # "no sew" dikişli sayılmaz

    feat = {k: sum(1 for i in items if re.search(rx, text(i, k))) for k, rx in FEATURE_WORDS.items()}
    title_len = [len(i.title) for i in items if i.title]
    top = sorted((i for i in items if i.favorites), key=lambda i: -(i.favorites or 0))[:10]
    res = {
        "query": query, "date": dt.date.today().isoformat(), "count": len(items),
        "sources": sorted({i.source for i in items}),
        "price": None, "tags": tag_c.most_common(40), "title_words": word_c.most_common(30),
        "title_bigrams": bigram_c.most_common(25), "features": feat,
        "title_len_median": int(statistics.median(title_len)) if title_len else None,
        "top_by_favorites": [asdict(i) for i in top],
    }
    if len(prices) >= 3:
        q = statistics.quantiles(prices, n=4)
        res["price"] = {"n": len(prices), "min": prices[0], "q1": round(q[0], 2), "median": round(statistics.median(prices), 2),
                        "q3": round(q[2], 2), "max": prices[-1]}
    return res


def report_md(an: dict, notes: str = "") -> str:
    n = an["count"] or 1
    L = [f"# Rakip taraması: “{an['query']}”", "",
         f"Tarih: {an['date']} · ilan sayısı: {an['count']} · kaynak: {', '.join(an['sources']) or '-'}", ""]
    if an["price"]:
        p = an["price"]
        L += ["## Fiyat (dijital kalıplar, USD)", "",
              f"- Alt çeyrek **{p['q1']}** · medyan **{p['median']}** · üst çeyrek **{p['q3']}** "
              f"(en düşük {p['min']}, en yüksek {p['max']}, {p['n']} ilan)", ""]
    L += ["## Rakiplerde ne var (ilan oranı)", ""]
    names = {"stitched": "dikişli", "no-sew": "dikişsiz / no-sew", "snap": "çıtçıt", "rivet": "perçin / vida",
             "glue": "yapıştırıcı", "svg/cricut": "SVG / Cricut dosyası", "dxf/laser": "DXF / lazer dosyası",
             "video": "video anlatım"}
    for k, v in an["features"].items():
        L.append(f"- {names[k]}: {v}/{an['count']} (%{100 * v // n})")
    L += ["", "## En sık etiketler", "", ", ".join(f"{t} ({c})" for t, c in an["tags"][:25]) or "(etiket verisi yok — "
          "Etsy API anahtarıyla gelir)", "", "## Başlıklarda en sık ifadeler", "",
          ", ".join(f"{t} ({c})" for t, c in an["title_bigrams"][:20]), "",
          f"Başlık uzunluğu medyanı: {an['title_len_median']} karakter", ""]
    if an["top_by_favorites"]:
        L += ["## En çok favorilenenler", ""]
        for i in an["top_by_favorites"]:
            L.append(f"- {i['favorites']} ♥ · {i['price'] or '?'} $ · {i['title'][:90]}")
        L.append("")
    if notes:
        L += ["## Web araştırması notları", "", notes.strip(), ""]
    return "\n".join(L)


def run(query: str, folder: str, etsy=True, web=False, csv_path: str | None = None, limit=100, log=print) -> dict:
    items: list[Listing] = []
    notes = ""
    if etsy and os.environ.get("ETSY_API_KEY"):
        try:
            items += from_etsy_api(query, limit, log)
        except Exception as e:  # ağ / anahtar hatası: diğer kaynaklarla devam
            log(f"  ⚠ Etsy API: {e}")
    elif etsy:
        log("  Etsy API anahtarı yok (ETSY_API_KEY) → atlandı")
    if csv_path:
        items += from_csv(csv_path)
        log(f"  CSV: {len(items)} ilan")
    if web or not items:
        if os.environ.get("ANTHROPIC_API_KEY") or web:
            try:
                w, notes = from_web(query, log=log)
                items += w
            except Exception as e:
                log(f"  ⚠ Web araştırması: {e}")
    if not items:
        raise SystemExit("Hiç rakip verisi toplanamadı. ETSY_API_KEY veya ANTHROPIC_API_KEY tanımlayın ya da --csv verin.")
    an = analyze(items, query)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "veri.json"), "w", encoding="utf-8") as fh:
        json.dump({"analysis": an, "listings": [asdict(i) for i in items], "notes": notes}, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(folder, "rapor.md"), "w", encoding="utf-8") as fh:
        fh.write(report_md(an, notes))
    return an


def load(folder: str | None) -> dict | None:
    if not folder:
        return None
    p = os.path.join(folder, "veri.json") if os.path.isdir(folder) else folder
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)["analysis"]

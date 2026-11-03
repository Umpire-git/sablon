"""dagli — Dagli Leather Studio kalıp üretim hattı.

  dagli pazar "leather pen holder pattern"          → rakip taraması (Etsy API / Claude web / CSV)
  dagli fikir "masa düzenleyici, hediye sezonu"     → 1. kapı: 2–3 fikir + öneri (Claude)
  dagli tasarla fikir.md -o urunler/yeni.py         → 2. kapı: Claude ürün kodunu yazar, motor sınar, onarır
  dagli kontrol urunler/yeni.py                     → geometri + en kötü durum taraması
  dagli deneme urunler/yeni.py                      → 2. kapı teslimi: konsept sayfası + 1:1 kâğıt deneme PDF
  dagli uret urunler/yeni.py --pazar pazar/x        → 3. kapı: PDF'ler, kesim ZIP, Etsy görselleri, SEO ilan, promptlar
  dagli gorsel urunler/yeni.py --onayli foto.png    → Gemini ile gerçekçi ürün görselleri
  dagli ornekler                                    → hazır ürün modülleri
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _slug(s):
    s = s.lower().translate(str.maketrans("çğıöşü", "cgiosu"))
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:50] or "konu"


def cmd_pazar(a):
    from . import market
    folder = a.klasor or os.path.join("pazar", _slug(a.sorgu))
    print(f"Rakip taraması: “{a.sorgu}”")
    an = market.run(a.sorgu, folder, etsy=not a.etsy_yok, web=a.web, csv_path=a.csv, limit=a.adet)
    print(f"\n{an['count']} ilan incelendi → {folder}/rapor.md")
    if an.get("price"):
        p = an["price"]
        print(f"Fiyat medyanı {p['median']} $ (çeyrekler {p['q1']}–{p['q3']} $)")


def cmd_fikir(a):
    from .ai import ideas
    md = ""
    if a.pazar:
        p = os.path.join(a.pazar, "rapor.md") if os.path.isdir(a.pazar) else a.pazar
        md = open(p, encoding="utf-8").read()
    print("Claude fikirleri hazırlıyor (1. kapı)...")
    txt = ideas(a.tarif, md)
    out = a.cikti or "fikirler.md"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(txt)
    print(f"\n→ {out}\nBeğendiğin fikri seç ve onayla; sonra: dagli tasarla {out} --sec \"fikir adı\" -o urunler/yeni.py")


def cmd_tasarla(a):
    from .ai import design
    idea = open(a.fikir, encoding="utf-8").read() if os.path.exists(a.fikir) else a.fikir
    if a.sec:
        idea = f"Selected idea: {a.sec}\n\n{idea}"
    ok, rep = design(idea, a.cikti, rounds=a.tur)
    print(rep)
    print(f"\n{'✓ Kontrollerden geçti' if ok else '✗ Hâlâ hata var (dosyayı elle veya yeni turla düzeltin)'}: {a.cikti}")
    if ok:
        print(f"Sıradaki: dagli deneme {a.cikti}")


def cmd_kontrol(a):
    from .pipeline import check_product
    from .product import load
    prod = load(a.urun)
    rep = check_product(prod, quick=a.hizli)
    print(rep.text())
    sys.exit(0 if rep.ok else 1)


def cmd_deneme(a):
    from .pipeline import trial
    from .product import load
    prod = load(a.urun)
    folder = a.klasor or os.path.join("teslim", f"{prod.meta.slug}_v{prod.meta.version}", "deneme")
    for p in trial(prod, folder):
        print(f"  {p}")
    print("Kâğıt/karton denemesini yap; sorun yoksa 3. kapı: dagli uret " + a.urun)


def cmd_uret(a):
    from . import market
    from .pipeline import produce
    from .product import load
    prod = load(a.urun)
    if prod.meta.kind == "signature" and not a.zorla:
        sys.exit("Bu ürün 'signature' (yalnızca bitmiş ürün satılır): kalıp paketi üretilmez. --zorla ile geçebilirsiniz.")
    mk = market.load(a.pazar)
    if a.pazar and not mk:
        print(f"⚠ Pazar verisi bulunamadı: {a.pazar} (fiyat ve etiketler pazar verisi olmadan seçilecek)")
    folder = produce(prod, a.klasor, mk, gemini=a.gemini, approved_photo=a.onayli, hero_photo=a.kapak)
    print(f"\nSatış paketi: {folder}")
    print("  UPLOAD_TO_ETSY_*.zip → Etsy'ye dijital dosya olarak yükle")
    print("  etsy_gorselleri/      → ilan fotoğrafları (LISTING.md'deki sırayla)")
    print("  LISTING.md            → başlık, 13 etiket, açıklama, nitelikler, fiyat, alt metinler")
    print("  ai/PROMPTS.md         → gerçekçi görsel promptları (EN + TR) ve eklenecek dosyalar")
    print("  OZET.md               → proje özetine yapıştırılacak 2 satır")


def cmd_gorsel(a):
    from PIL import Image

    from . import images
    from .product import load
    prod = load(a.urun)
    folder = a.klasor or os.path.join("teslim", f"{prod.meta.slug}_v{prod.meta.version}", "ai")
    os.makedirs(folder, exist_ok=True)
    ref = images.reference_sheet(prod)
    ref.save(os.path.join(folder, "ai_referans.png"))
    with open(os.path.join(folder, "PROMPTS.md"), "w", encoding="utf-8") as fh:
        fh.write(images.prompts_md(prod))
    ap = Image.open(a.onayli).convert("RGB") if a.onayli else None
    only = a.cekim.split(",") if a.cekim else None
    for p in images.gemini_shots(prod, ref, folder, ap, only):
        print(f"  {p}")
    print("Her görseli kalıpla karşılaştır. İyi olanı --onayli ile ver, kalan çekimleri tekrar üret.")


def cmd_ornekler(a):
    for p in sorted(glob.glob(os.path.join(ROOT, "urunler", "*.py"))):
        from .product import load
        prod = load(p)
        print(f"  {os.path.relpath(p)}  —  {prod.meta.name} v{prod.meta.version} ({prod.meta.sku})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dagli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("pazar", help="Etsy rakip taraması")
    s.add_argument("sorgu")
    s.add_argument("-d", "--klasor")
    s.add_argument("--web", action="store_true", help="Claude web araması da yap")
    s.add_argument("--csv", help="Elle hazırlanmış rakip listesi (title, price, tags, favorites, url)")
    s.add_argument("--etsy-yok", action="store_true", help="Etsy API'yi kullanma")
    s.add_argument("-n", "--adet", type=int, default=100)
    s.set_defaults(f=cmd_pazar)

    s = sub.add_parser("fikir", help="1. kapı: fikirler (Claude)")
    s.add_argument("tarif")
    s.add_argument("--pazar", help="pazar/<konu> klasörü")
    s.add_argument("-o", "--cikti")
    s.set_defaults(f=cmd_fikir)

    s = sub.add_parser("tasarla", help="2. kapı: ürün modülünü Claude yazar, motor sınar")
    s.add_argument("fikir", help="fikir metni veya fikirler.md")
    s.add_argument("--sec", help="seçilen fikrin adı")
    s.add_argument("-o", "--cikti", required=True)
    s.add_argument("--tur", type=int, default=4)
    s.set_defaults(f=cmd_tasarla)

    s = sub.add_parser("kontrol", help="Kontroller + en kötü durum taraması")
    s.add_argument("urun")
    s.add_argument("--hizli", action="store_true")
    s.set_defaults(f=cmd_kontrol)

    s = sub.add_parser("deneme", help="2. kapı teslimi: konsept + 1:1 kâğıt deneme")
    s.add_argument("urun")
    s.add_argument("-d", "--klasor")
    s.set_defaults(f=cmd_deneme)

    s = sub.add_parser("uret", help="3. kapı: tam satış paketi")
    s.add_argument("urun")
    s.add_argument("-d", "--klasor", default="teslim")
    s.add_argument("--pazar", help="pazar/<konu> klasörü (fiyat + etiketler)")
    s.add_argument("--gemini", action="store_true", help="Gemini ile gerçekçi görseller de üret")
    s.add_argument("--onayli", help="onaylı fotoğraf (tutarlılık referansı)")
    s.add_argument("--kapak", help="ana görsel için fotoğraf (gerçek prototip veya onaylı AI)")
    s.add_argument("--zorla", action="store_true")
    s.set_defaults(f=cmd_uret)

    s = sub.add_parser("gorsel", help="Gemini ile gerçekçi ürün görselleri")
    s.add_argument("urun")
    s.add_argument("--onayli")
    s.add_argument("--cekim", help="yalnızca bu çekimler, ör. hero,lock")
    s.add_argument("-d", "--klasor")
    s.set_defaults(f=cmd_gorsel)

    s = sub.add_parser("ornekler", help="Hazır ürün modülleri")
    s.set_defaults(f=cmd_ornekler)

    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()

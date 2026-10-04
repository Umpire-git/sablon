"""Komut satırı:  sablon <komut> ...   (python -m sablon)"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys

from . import project as P
from .design import from_dict

ICON = {"hata": "✖", "uyari": "⚠", "bilgi": "•"}
ROOT = os.path.dirname(os.path.dirname(__file__))


def _slug(s: str) -> str:
    tr = str.maketrans("çğıİöşüÇĞÖŞÜ", "cgiIosuCGOSU")
    return re.sub(r"[^a-z0-9]+", "_", s.translate(tr).lower()).strip("_")[:40] or "tasarim"


def _report(findings, quiet_info=False) -> int:
    errs = 0
    for f in findings:
        errs += f.level == "hata"
        if quiet_info and f.level == "bilgi":
            continue
        print(f"  {ICON[f.level]} {f.message}")
    return errs


def _summary(design):
    from .ai import evaluate
    findings = evaluate(design)
    print(f"\n{design.ad}  [{design.malzeme}, {design.kalinlik} mm]")
    if design.konsept:
        print(f"  {design.konsept}")
    return _report(findings)


def cmd_ornekler(a):
    for path in sorted(glob.glob(os.path.join(ROOT, "ornekler", "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        print(f"{os.path.splitext(os.path.basename(path))[0]:<28} {d.get('ad')}  —  {d.get('malzeme')}")


def cmd_yeni(a):
    src = a.ornek if os.path.exists(a.ornek) else os.path.join(ROOT, "ornekler", a.ornek + ".json")
    if not os.path.exists(src):
        raise SystemExit(f"Örnek bulunamadı: {a.ornek} ('sablon ornekler' ile listeleyin)")
    design, hist = P.load(src)
    P.log(hist, "ornek", os.path.basename(src), [])
    P.save(a.cikti, design, hist)
    print(f"Proje oluşturuldu: {a.cikti}")
    _summary(design)


def cmd_fikir(a):
    from .ai import AIError, ideas
    from .export.document import make_document
    from .export.pdf import write_contact_sheet
    os.makedirs(a.klasor, exist_ok=True)
    previous = []
    for path in sorted(glob.glob(os.path.join(a.klasor, "*.json"))):
        try:
            d, _ = P.load(path)
            previous.append(f"{d.ad}: {d.konsept[:160]}")
        except Exception:
            pass
    try:
        res = ideas(a.tarif, a.adet, previous=previous, malzeme=a.malzeme or "")
    except AIError as e:
        raise SystemExit(f"Hata: {e}")
    start = len(glob.glob(os.path.join(a.klasor, "*.json")))
    docs = []
    for i, (d, findings) in enumerate(res, start + 1):
        path = os.path.join(a.klasor, f"{i:02d}_{_slug(d.ad)}.json")
        hist: list = []
        P.log(hist, "ai:fikir", a.tarif, [])
        P.save(path, d, hist)
        print(f"\n[{i:02d}] {d.ad}  →  {path}\n  {d.konsept}")
        _report(findings, quiet_info=True)
        if not any(f.level == "hata" for f in findings):
            try:
                docs.append((path, make_document(d, quick=True)))
            except Exception as ex:  # görsel üretimi fikri engellemesin
                print(f"  (görsel üretilemedi: {ex})")
    if docs:
        sheet = os.path.join(a.klasor, "koleksiyon.pdf")
        write_contact_sheet(docs, sheet, a.tarif)
        print(f"\nKarşılaştırma sayfası: {sheet}")
    print("\nBeğendiğinizi düzeltin/çıktı alın:  sablon duzelt <dosya> \"...\"   sablon cikti <dosya>")


def cmd_duzelt(a):
    from .ai import AIError, revise
    design, hist = P.load(a.proje)
    try:
        rev, new, findings = revise(design, a.geri_bildirim)
    except AIError as e:
        raise SystemExit(f"Hata: {e}")
    print(f"Anlaşılan: {rev.anlasilan}")
    if rev.soru:
        print(f"Soru: {rev.soru}")
    changes = P.diff(design, new)
    for c in changes:
        print(f"  {c}")
    if not changes:
        print("  (değişiklik yok)")
    P.log(hist, "ai:duzelt", a.geri_bildirim, changes)
    P.save(a.proje, new, hist)
    _report(findings)


def cmd_ayarla(a):
    design, hist = P.load(a.proje)
    done = []
    for kv in a.degerler:
        if "=" not in kv:
            raise SystemExit(f"'{kv}' anlaşılmadı; ad=deger biçiminde yazın (ör. kart_adet=6, kapak.yukseklik=40)")
        k, v = kv.split("=", 1)
        try:
            done.append(P.set_value(design, k.strip(), v.strip()))
        except KeyError as e:
            raise SystemExit(str(e).strip("'\""))
    for d in done:
        print(f"  {d}")
    P.log(hist, "elle", " ".join(a.degerler), done)
    P.save(a.proje, design, hist)
    _summary(design)


def cmd_kontrol(a):
    design, _ = P.load(a.proje)
    errs = _summary(design)
    try:
        from .engine import build
        b = build(design)
        print("\nPaneller:")
        for pid in b.order:
            p = b.panels[pid]
            print(f"  {pid:<14} {p.spec.ad:<14} {p.w:7.1f} × {p.h:6.1f} mm  açı {p.angle:5.0f}°  kat {p.spec.kat_sirasi}")
        print("\nDeğişkenler: " + ", ".join(f"{k}={v:g}" for k, v in b.env.items()))
    except Exception:
        pass
    sys.exit(1 if errs and a.kati else 0)


def cmd_incele(a):
    from .ai import AIError, review
    design, hist = P.load(a.proje)
    try:
        r = review(design)
    except AIError as e:
        raise SystemExit(f"Hata: {e}")
    print("\nÜrüne dönüşüm (zihinsel canlandırma):\n" + r.urun_hikayesi)
    print("\nOlası kullanım sorunları:")
    for risk in r.riskler:
        print(f"  [{risk.onem}] {risk.baslik}: {risk.detay}\n      → {risk.oneri}")
    print("\nSatış önerileri:")
    for t in r.satis_onerileri:
        print(f"  • {t}")
    if a.uygula:
        high = [x for x in r.riskler if x.onem == "yuksek"]
        if high:
            from .ai import revise
            fb = "Şu riskleri gider:\n" + "\n".join(f"- {x.baslik}: {x.oneri}" for x in high)
            rev, new, findings = revise(design, fb)
            changes = P.diff(design, new)
            for c in changes:
                print(f"  {c}")
            P.log(hist, "ai:incele", fb, changes)
            P.save(a.proje, new, hist)
            _report(findings)


def cmd_cikti(a):
    from .engine import BuildError
    from .export.document import make_document
    from .export.dxf import write_dxf
    from .export.pdf import write_pdf
    from .export.svg import write_svg
    from .viewer import write_viewer

    design, _ = P.load(a.proje)
    try:
        doc = make_document(design, images=False)
    except BuildError as e:
        _report(e.findings)
        raise SystemExit("Tasarım derlenemedi.")
    errs = [f for f in doc.findings if f.level == "hata"]
    if errs and not a.zorla:
        _report(errs)
        raise SystemExit("Tasarımda hata var; önce düzeltin veya --zorla kullanın.")
    os.makedirs(a.klasor, exist_ok=True)
    base = os.path.join(a.klasor, a.ad or os.path.splitext(os.path.basename(a.proje))[0])
    kinds = [k.strip().lower() for k in a.bicim.split(",")]
    made = []
    need_img = any(k in kinds for k in ("a4", "letter", "full", "gorsel"))
    if need_img:
        from .export.document import render_images
        print("3B görseller hazırlanıyor...")
        render_images(doc, quick=a.hizli)
    if "a4" in kinds:
        write_pdf(doc, f"{base}_A4.pdf", "A4"); made.append(f"{base}_A4.pdf")
    if "letter" in kinds:
        write_pdf(doc, f"{base}_Letter.pdf", "Letter"); made.append(f"{base}_Letter.pdf")
    if "full" in kinds:
        write_pdf(doc, f"{base}_tam_boy.pdf", "full"); made.append(f"{base}_tam_boy.pdf")
    if "svg" in kinds:
        write_svg(design.ad, doc.pieces, f"{base}.svg"); made.append(f"{base}.svg")
    if "dxf" in kinds:
        write_dxf(design.ad, doc.pieces, f"{base}.dxf"); made.append(f"{base}.dxf")
    if "3b" in kinds:
        write_viewer(doc.built, f"{base}_3B.html"); made.append(f"{base}_3B.html")
    if "gorsel" in kinds:
        from .render3d import render
        b = doc.built
        shots = {"urun": doc.images["hero"],
                 "arka": render(b, fold=1.0, az=-35, el=30, flip=True, size=(1400, 1000), ss=1 if a.hizli else 2),
                 "yari_acik": render(b, fold=0.55, az=-30, el=40, size=(1400, 1000), ss=1 if a.hizli else 2),
                 "acinim": doc.images["flat"]}
        for k, im in shots.items():
            path = f"{base}_{k}.png"
            im.save(path)
            made.append(path)
    if a.foto:
        from .foto import BlenderYok, render_photos
        print(f"Blender ile fotogerçekçi görseller ({a.foto}) hazırlanıyor; görsel başına "
              f"{'birkaç saniye–yarım dakika' if a.foto == 'hizli' else '1–3 dakika'} sürebilir...")
        try:
            made += render_photos(doc.built, base, a.foto)
        except BlenderYok as e:
            print(f"  ⚠ {e}")
    print("Oluşturulan dosyalar:")
    for m in made:
        print(f"  {m}")


def cmd_ogren(a):
    from .ai import AIError, learn_pdf
    for path in a.pdfler:
        try:
            info, out = learn_pdf(path)
        except AIError as e:
            raise SystemExit(f"Hata ({path}): {e}")
        n = len(info.kurallar) + len(info.teknikler) + len(info.tasarim_motifleri) + len(info.talimat_uslubu)
        print(f"{path} → {out}  ({n} madde). Bundan sonraki tüm tasarımlarda kullanılacak.")


def cmd_gecmis(a):
    _, hist = P.load(a.proje)
    for h in hist:
        print(f"\n{h['zaman']}  [{h['kaynak']}]  {h.get('istek', '')}")
        for c in h.get("degisiklikler", []):
            print(f"  {c}")


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(prog="sablon", description="Yaratıcı, mm hassasiyetli kalıp tasarım aracı")
    sub = ap.add_subparsers(dest="komut", required=True)

    s = sub.add_parser("fikir", help="Tariften birbirinden farklı tasarımlar üret (Claude)")
    s.add_argument("tarif"); s.add_argument("-n", "--adet", type=int, default=4)
    s.add_argument("-d", "--klasor", default="fikirler"); s.add_argument("--malzeme", default="")
    s.set_defaults(f=cmd_fikir)

    s = sub.add_parser("ornekler", help="Hazır örnek tasarımlar"); s.set_defaults(f=cmd_ornekler)
    s = sub.add_parser("yeni", help="Örnekten proje başlat")
    s.add_argument("ornek"); s.add_argument("-o", "--cikti", default="proje.json"); s.set_defaults(f=cmd_yeni)

    s = sub.add_parser("duzelt", help="'Burası uzun olmuş' gibi geri bildirimle düzelt (Claude)")
    s.add_argument("proje"); s.add_argument("geri_bildirim"); s.set_defaults(f=cmd_duzelt)

    s = sub.add_parser("ayarla", help="Değişken / panel alanı değiştir (ör. kart_adet=6 kapak.yukseklik=40)")
    s.add_argument("proje"); s.add_argument("degerler", nargs="+"); s.set_defaults(f=cmd_ayarla)

    s = sub.add_parser("kontrol", help="Ölçüler ve tasarım kontrolleri")
    s.add_argument("proje"); s.add_argument("--kati", action="store_true", help="Hata varsa çıkış kodu 1")
    s.set_defaults(f=cmd_kontrol)

    s = sub.add_parser("incele", help="Ürünü canlandırıp kullanım risklerini bul (Claude)")
    s.add_argument("proje"); s.add_argument("--uygula", action="store_true", help="Yüksek önemli önerileri uygula")
    s.set_defaults(f=cmd_incele)

    s = sub.add_parser("cikti", help="PDF kitapçık, SVG, DXF, 3B görüntüleyici, ürün görselleri")
    s.add_argument("proje"); s.add_argument("-d", "--klasor", default="cikti"); s.add_argument("--ad")
    s.add_argument("--bicim", default="a4,letter,full,svg,dxf,3b,gorsel")
    s.add_argument("--hizli", action="store_true", help="Düşük çözünürlüklü görseller (hızlı)")
    s.add_argument("--foto", choices=["hizli", "kaliteli"], help="Blender ile fotogerçekçi ürün görselleri")
    s.add_argument("--zorla", action="store_true")
    s.set_defaults(f=cmd_cikti)

    s = sub.add_parser("ogren", help="Referans PDF'lerden bilgi çıkarıp bilgi bankasına ekle (Claude)")
    s.add_argument("pdfler", nargs="+"); s.set_defaults(f=cmd_ogren)

    s = sub.add_parser("gecmis", help="Değişiklik geçmişi"); s.add_argument("proje"); s.set_defaults(f=cmd_gecmis)

    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()

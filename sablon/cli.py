"""Komut satırı arayüzü:  python -m sablon <komut> ..."""
from __future__ import annotations

import argparse
import os
import sys

from .project import Change, Project
from .templates import REGISTRY, get

ICON = {"hata": "✖", "uyari": "⚠", "bilgi": "•"}


def _kv(items: list[str]) -> dict[str, float]:
    out = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"'{it}' anlaşılmadı; ad=deger biçiminde yazın (ör. kart_sayisi=6)")
        k, v = it.split("=", 1)
        out[k.strip()] = float(v.replace(",", "."))
    return out


def _report(proj: Project, measures: bool = True) -> int:
    tpl = proj.instance()
    print(f"\n{tpl.title}" + (f" — {proj.name}" if proj.name else ""))
    if measures:
        print("\nÖlçüler:")
        for k, m in tpl.measures().items():
            val = f"{m.value:.0f}" if m.unit == "adet" else f"{m.value:.1f}"
            print(f"  {m.label:<45} {val:>8} {m.unit}   [{k}]")
    print("\nKontroller:")
    errors = 0
    for f in tpl.checks():
        errors += f.level == "hata"
        sug = ""
        if f.suggestion:
            sug = "  → öneri: " + ", ".join(f"{k}={v}" for k, v in f.suggestion.items())
        print(f"  {ICON[f.level]} {f.message}{sug}")
    return errors


def _print_changes(changes: list[Change]):
    if not changes:
        print("Değişiklik yok.")
    for c in changes:
        print(f"  {c.param}: {c.old} → {c.new}" + (f"   ({c.reason})" if c.reason else ""))


def cmd_liste(a):
    for t in REGISTRY.values():
        print(f"\n{t.key}  —  {t.title}\n  {t.description}\n  Malzeme: {t.material}")
        if a.detay:
            for p in t.params:
                print(f"    {p.name:<18} {p.default:>7} {p.unit:<5} [{p.min}–{p.max}]  {p.label}")


def cmd_yeni(a):
    T = get(a.sablon)
    proj = Project(template=T.key, name=a.ad or "")
    proj.apply([Change(k, 0.0, v) for k, v in _kv(a.degerler).items()], source="elle")
    proj.save(a.cikti)
    print(f"Proje oluşturuldu: {a.cikti}")
    _report(proj)


def cmd_ayarla(a):
    proj = Project.load(a.proje)
    _print_changes(proj.apply([Change(k, 0.0, v) for k, v in _kv(a.degerler).items()], source="elle"))
    proj.save(a.proje)
    _report(proj)


def cmd_kontrol(a):
    proj = Project.load(a.proje)
    sys.exit(1 if _report(proj) and a.katı else 0)


def cmd_otomatik(a):
    from .ai import autofix
    proj = Project.load(a.proje)
    _print_changes(autofix(proj))
    proj.save(a.proje)
    _report(proj, measures=False)


def cmd_tarif(a):
    from .ai import AIError, autofix, design_from_description
    try:
        proj, choice = design_from_description(a.metin)
    except AIError as e:
        raise SystemExit(f"Hata: {e}")
    if not choice.supported:
        print(f"⚠ Bu ürün tipi henüz katalogda yok: {choice.missing_capability}\n"
              f"  En yakın şablonla başlandı: {proj.template}")
    for s in choice.assumptions:
        print(f"  varsayım: {s}")
    fixed = autofix(proj)
    if fixed:
        print("Kural motoru otomatik düzeltti:")
        _print_changes(fixed)
    proj.save(a.cikti)
    print(f"\nProje kaydedildi: {a.cikti}")
    _report(proj)


def cmd_duzelt(a):
    from .ai import AIError, autofix, revise
    proj = Project.load(a.proje)
    try:
        rev, applied = revise(proj, a.geri_bildirim)
    except AIError as e:
        raise SystemExit(f"Hata: {e}")
    print(f"Anlaşılan: {rev.understood_as}")
    if rev.question:
        print(f"Soru: {rev.question}")
    _print_changes(applied)
    if not a.dokunma:
        fixed = autofix(proj)
        if fixed:
            print("Değişikliğin yol açtığı hatalar otomatik giderildi:")
            _print_changes(fixed)
    proj.save(a.proje)
    _report(proj)


def cmd_incele(a):
    from .ai import AIError, review
    proj = Project.load(a.proje)
    try:
        r = review(proj)
    except AIError as e:
        raise SystemExit(f"Hata: {e}")
    print("\nÜrüne dönüşüm (zihinsel canlandırma):\n" + r.product_story)
    print("\nOlası kullanım sorunları:")
    for risk in r.risks:
        print(f"  [{risk.severity}] {risk.title}: {risk.detail}")
        for c in risk.changes:
            print(f"      → {c.name} = {c.new_value}  ({c.reason})")
    print("\nSatış önerileri:")
    for t in r.selling_tips:
        print(f"  • {t}")
    if a.uygula:
        ch = [Change(c.name, 0.0, c.new_value, c.reason) for risk in r.risks if risk.severity == "yuksek"
              for c in risk.changes]
        print("\nYüksek önemli öneriler uygulandı:")
        _print_changes(proj.apply(ch, source="ai:incele"))
        proj.save(a.proje)


def cmd_cikti(a):
    from .export.dxf import write_dxf
    from .export.pdf import write_pdf
    from .export.svg import write_svg

    proj = Project.load(a.proje)
    tpl = proj.instance()
    errs = [f for f in tpl.checks() if f.level == "hata"]
    if errs and not a.zorla:
        for f in errs:
            print(f"  ✖ {f.message}")
        raise SystemExit("Tasarımda hata var; önce düzeltin ('otomatik' komutu) veya --zorla kullanın.")
    os.makedirs(a.klasor, exist_ok=True)
    base = os.path.join(a.klasor, a.ad or os.path.splitext(os.path.basename(a.proje))[0])
    kinds = [k.strip().lower() for k in a.bicim.split(",")]
    made = []
    if "a4" in kinds:
        write_pdf(tpl, f"{base}_A4.pdf", "A4"); made.append(f"{base}_A4.pdf")
    if "letter" in kinds:
        write_pdf(tpl, f"{base}_Letter.pdf", "Letter"); made.append(f"{base}_Letter.pdf")
    if "full" in kinds:
        write_pdf(tpl, f"{base}_tam_boy.pdf", "full"); made.append(f"{base}_tam_boy.pdf")
    if "svg" in kinds:
        write_svg(tpl, f"{base}.svg"); made.append(f"{base}.svg")
    if "dxf" in kinds:
        write_dxf(tpl, f"{base}.dxf"); made.append(f"{base}.dxf")
    if "onizleme" in kinds:
        with open(f"{base}_onizleme.svg", "w", encoding="utf-8") as f:
            f.write(tpl.preview_svg())
        made.append(f"{base}_onizleme.svg")
    print("Oluşturulan dosyalar:")
    for m in made:
        print(f"  {m}")


def cmd_gecmis(a):
    proj = Project.load(a.proje)
    for h in proj.history:
        print(f"\n{h['time']}  [{h['source']}]  {h.get('request', '')}")
        for c in h["changes"]:
            print(f"  {c['param']}: {c['old']} → {c['new']}  {c.get('reason', '')}")


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(prog="sablon", description="Parametrik, mm hassasiyetli kalıp/şablon üretici")
    sub = ap.add_subparsers(dest="komut", required=True)

    s = sub.add_parser("liste", help="Şablon kataloğu"); s.add_argument("--detay", action="store_true")
    s.set_defaults(f=cmd_liste)

    s = sub.add_parser("yeni", help="Şablondan yeni proje")
    s.add_argument("sablon"); s.add_argument("degerler", nargs="*", help="ad=deger")
    s.add_argument("-o", "--cikti", default="proje.json"); s.add_argument("--ad")
    s.set_defaults(f=cmd_yeni)

    s = sub.add_parser("tarif", help="Doğal dil tariften proje (Claude)")
    s.add_argument("metin"); s.add_argument("-o", "--cikti", default="proje.json")
    s.set_defaults(f=cmd_tarif)

    s = sub.add_parser("ayarla", help="Parametreleri elle değiştir")
    s.add_argument("proje"); s.add_argument("degerler", nargs="+")
    s.set_defaults(f=cmd_ayarla)

    s = sub.add_parser("duzelt", help="'Burası uzun olmuş' gibi geri bildirimle düzelt (Claude)")
    s.add_argument("proje"); s.add_argument("geri_bildirim")
    s.add_argument("--dokunma", action="store_true", help="Sonrasında otomatik hata düzeltme yapma")
    s.set_defaults(f=cmd_duzelt)

    s = sub.add_parser("otomatik", help="Kural hatalarını otomatik düzelt (AI'sız)")
    s.add_argument("proje"); s.set_defaults(f=cmd_otomatik)

    s = sub.add_parser("kontrol", help="Ölçüler ve tasarım kontrolleri")
    s.add_argument("proje"); s.add_argument("--katı", action="store_true", help="Hata varsa çıkış kodu 1")
    s.set_defaults(f=cmd_kontrol)

    s = sub.add_parser("incele", help="Ürüne dönüşümü canlandır, kullanım risklerini bul (Claude)")
    s.add_argument("proje"); s.add_argument("--uygula", action="store_true")
    s.set_defaults(f=cmd_incele)

    s = sub.add_parser("cikti", help="PDF/SVG/DXF üret")
    s.add_argument("proje"); s.add_argument("-d", "--klasor", default="cikti"); s.add_argument("--ad")
    s.add_argument("--bicim", default="a4,letter,full,svg,dxf,onizleme")
    s.add_argument("--zorla", action="store_true")
    s.set_defaults(f=cmd_cikti)

    s = sub.add_parser("gecmis", help="Değişiklik geçmişi"); s.add_argument("proje")
    s.set_defaults(f=cmd_gecmis)

    a = ap.parse_args(argv)
    try:
        a.f(a)
    except KeyError as e:
        raise SystemExit(str(e).strip("'\""))


if __name__ == "__main__":
    main()

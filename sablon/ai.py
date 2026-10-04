"""Claude ile yaratıcı tasarım, düzeltme, inceleme ve PDF'lerden öğrenme.

İlke: Claude geometri çizmez; tasarım dilinde (design.Tasarim) paneller, menteşeler ve
özellikler tanımlar. Motor (engine) mm hassasiyetinde geometriyi üretir ve kontrol eder;
hata çıkarsa bulgular Claude'a geri verilip onarım istenir. Böylece hem yaratıcılık
hem ölçü doğruluğu korunur.
"""
from __future__ import annotations

import base64
import glob
import json
import os
import random

from pydantic import BaseModel, Field

from .checks import run_checks
from .design import Tasarim, from_dict
from .engine import BuildError, build

MODEL = os.environ.get("SABLON_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.environ.get("SABLON_GEMINI_TEXT_MODEL", "")  # boşsa erişilebilir modellerden otomatik seçilir


def provider() -> str:
    """claude | gemini. SABLON_AI ile seçilir; yoksa hangi anahtar tanımlıysa o."""
    p = os.environ.get("SABLON_AI", "").strip().lower()
    if p in ("claude", "gemini"):
        return p
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return "claude"
HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)


class AIError(RuntimeError):
    pass


# --- bilgi bankası --------------------------------------------------------------------
def knowledge() -> str:
    parts = []
    for path in sorted(glob.glob(os.path.join(HERE, "bilgi", "*.md"))) + sorted(glob.glob(os.path.join(HERE, "bilgi", "kullanici", "*.md"))):
        with open(path, encoding="utf-8") as f:
            parts.append(f.read())
    from . import materials as M
    mats = "\n".join(f"- {m.key}: {m.ad}. {m.aciklama} Önerilen kalınlık {m.kalinlik_onerilen[0]}–{m.kalinlik_onerilen[1]} mm. "
                     f"Sert/kilit tutar: {'evet' if m.sert else 'hayır'}. Katlama: {m.katlama}" for m in M.MATERIALS.values())
    snaps = ", ".join(f"{s.key} (şapka Ø{s.sapka_cap})" for s in M.SNAPS.values())
    fast = ", ".join(f"{f.key}: {f.ad}, delik Ø{f.delik}, kavrama {f.kavrama[0]}–{f.kavrama[1]} mm" for f in M.FASTENERS.values())
    parts.append(f"# Malzemeler\n{mats}\n\n# Çıtçıt boyutları\n{snaps}\n\n# Perçin / vida\n{fast}")
    ex = []
    for path in sorted(glob.glob(os.path.join(ROOT, "ornekler", "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = from_dict(json.load(f))
        ex.append(f"## Örnek: {os.path.basename(path)}\n```json\n{json.dumps(d.model_dump(), ensure_ascii=False)}\n```")
    parts.append("# Doğrulanmış örnek tasarımlar (biçim ve yaklaşım için; kopyalama, esinlen)\n" + "\n\n".join(ex))
    return "\n\n".join(parts)


SYSTEM_HEAD = """Sen yaratıcı ve titiz bir DİKİŞSİZ deri ürün tasarımcısı ve endüstriyel kalıpçısın. Kullanıcı Etsy'de
satılacak, dikiş ve yapıştırıcı gerektirmeyen deri ürün PDF kalıpları hazırlıyor (vaketa veya crazy horse). Tasarımlarını aşağıdaki tasarım dilinde (JSON) ifade edersin; parametrik motor
bunları milimetre hassasiyetinde kalıba, 3B modele, kontrollere ve yapım talimatına çevirir.

Çalışma ilkelerin:
- Ürünü kafanda gerçekten kur: kesim, katlama sırası, kilitlerin takılması, içine kart girip çıkması, kapağın kapanması,
  6 ay günlük kullanım. Her ölçünün fiziksel bir gerekçesi olsun.
- Yaratıcı ol ama yapılabilir kal: her tasarım el aletleriyle üretilebilmeli.
- Tutarlı kimlikler kullan; açınımda panel çakışmasından kaçın; kalınlık/hacim kurallarına uy.
- Metinleri Türkçe yaz; ürün adları satışa uygun, kısa ve akılda kalıcı olsun."""


def system_blocks() -> list[dict]:
    return [{"type": "text", "text": SYSTEM_HEAD + "\n\n" + knowledge(), "cache_control": {"type": "ephemeral"}}]


# --- şemalar ------------------------------------------------------------------------------
class Fikirler(BaseModel):
    tasarimlar: list[Tasarim]


class Onarim(BaseModel):
    tasarim: Tasarim
    aciklama: str


class Revizyon(BaseModel):
    anlasilan: str = Field(description="Geri bildirimi nasıl yorumladığın: hangi ölçü, ne kadar, neden")
    degisiklikler: list[str] = Field(description="Yapılan değişikliklerin kısa listesi")
    soru: str = Field(description="Gerçekten belirsizse kullanıcıya soru; değilse boş")
    tasarim: Tasarim


class Risk(BaseModel):
    onem: str = Field(description="yuksek | orta | dusuk")
    baslik: str
    detay: str = Field(description="Kullanımda ne olur, neden olur")
    oneri: str = Field(description="Somut tasarım değişikliği (ölçü/özellik)")


class Inceleme(BaseModel):
    urun_hikayesi: str = Field(description="Kalıbın kesilip yapılıp kullanılmasının adım adım zihinsel canlandırması")
    riskler: list[Risk]
    satis_onerileri: list[str] = Field(description="Etsy listesi, fotoğraf ve PDF için öneriler")


class Bilgi(BaseModel):
    baslik: str
    kurallar: list[str] = Field(description="Genellenebilir ölçü/pay/tolerans kuralları")
    teknikler: list[str] = Field(description="Yapım teknikleri ve sıralama ipuçları")
    tasarim_motifleri: list[str] = Field(description="Tasarım fikirleri/motifleri (birebir kopya değil, ilke olarak)")
    talimat_uslubu: list[str] = Field(description="PDF talimatının anlatım biçimi, sayfa düzeni, alıcıya yönelik iyi uygulamalar")


# --- Claude çağrısı ----------------------------------------------------------------------
def _client():
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise AIError("'anthropic' paketi kurulu değil: pip install anthropic") from e
    return anthropic.Anthropic()


def _ask(content, schema: type[BaseModel], client=None, max_tokens: int = 64000, effort: str = "high", pdf: bytes | None = None):
    """Yapılandırılmış (şemaya uyan) yanıt ister; sağlayıcı istemciden veya ortamdan seçilir."""
    if client is not None:
        use = "gemini" if hasattr(client, "models") and not hasattr(client, "beta") else "claude"
    else:
        use = provider()
    if use == "gemini":
        return _ask_gemini(content, schema, client, max_tokens, pdf)
    return _ask_claude(content, schema, client, max_tokens, effort, pdf)


def _ask_claude(content, schema, client, max_tokens, effort, pdf):
    import anthropic

    client = client or _client()
    if pdf is not None:
        content = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                    "data": base64.standard_b64encode(pdf).decode()}},
                   {"type": "text", "text": content}]
    try:
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_blocks(),
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            # Güvenlik sınıflandırıcısı reddederse istek sunucu tarafında yedek modelle yeniden çalışır.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": content}],
            output_format=schema,
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise AIError("Claude API anahtarı bulunamadı/geçersiz. ANTHROPIC_API_KEY ortam değişkenini ayarlayın "
                      "(veya Gemini kullanmak için SABLON_AI=gemini ve GEMINI_API_KEY).") from e
    except anthropic.RateLimitError as e:
        raise AIError("Claude API hız sınırına takıldı; biraz sonra tekrar deneyin.") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API hatası ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Claude API'ye bağlanılamadı (ağ).") from e
    if msg.stop_reason == "refusal":
        raise AIError("Model isteği yanıtlamayı reddetti.")
    if msg.stop_reason == "max_tokens":
        raise AIError("Yanıt token sınırında kesildi; daha az fikir isteyin.")
    parsed = getattr(msg, "parsed_output", None)
    if parsed is not None:
        return parsed
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
    try:
        return schema.model_validate_json(text)
    except Exception as e:
        raise AIError(f"Model yanıtı şemaya uymadı: {e}") from e


def _gemini_client():
    try:
        from google import genai
    except ImportError as e:  # pragma: no cover
        raise AIError("Gemini paketi kurulu değil: pip install google-genai") from e
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise AIError("GEMINI_API_KEY tanımlı değil. Ücretsiz anahtar: https://aistudio.google.com/apikey")
    return genai.Client()


def _ask_gemini(content, schema, client, max_tokens, pdf):
    """Gemini: önce JSON şemasıyla zorlanmış çıktı; şema reddedilirse şemayı metinle verip doğrular."""
    from google.genai import errors, types

    client = client or _gemini_client()
    system = system_blocks()[0]["text"]
    parts = []
    if pdf is not None:
        parts.append(types.Part.from_bytes(data=pdf, mime_type="application/pdf"))
    parts.append(content)
    js = schema.model_json_schema()
    attempts = [
        types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens,
                                    response_mime_type="application/json", response_json_schema=js,
                                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)),
        types.GenerateContentConfig(system_instruction=system + "\n\nYanıtı YALNIZCA şu JSON şemasına uyan tek bir "
                                    "JSON nesnesi olarak ver:\n" + json.dumps(js, ensure_ascii=False),
                                    max_output_tokens=max_tokens, response_mime_type="application/json",
                                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)),
    ]
    from . import gemini_models as GM
    try:
        model = GEMINI_MODEL or GM.pick_text(client)
    except Exception:
        model = "gemini-2.5-pro"
    last = None
    i = 0
    while i < len(attempts):
        cfg = attempts[i]
        try:
            resp = client.models.generate_content(model=model, contents=parts, config=cfg)
        except errors.ClientError as e:
            code = getattr(e, "code", None)
            if code in (401, 403):
                raise AIError("Gemini anahtarı geçersiz veya yetkisiz (GEMINI_API_KEY).") from e
            if code == 429:
                try:
                    alt = GM.pick_fallback(client, model)
                except Exception:
                    alt = None
                if alt:
                    print(f"  (Gemini {model} kotası doldu; {alt} ile devam ediliyor)")
                    model = alt
                    continue
                raise AIError("Gemini kotası/hız sınırı doldu; biraz sonra tekrar deneyin "
                              "(ücretsiz kotada dakikalık sınır düşüktür).") from e
            if code == 404:
                raise AIError(f"Gemini modeli bulunamadı: {model}. 'sablon modeller' ile erişilebilir modelleri görün, "
                              "SABLON_GEMINI_TEXT_MODEL ile birini seçin.") from e
            last = e
            i += 1
            continue  # şema reddedildi → şemasız dene
        except errors.APIError as e:
            raise AIError(f"Gemini API hatası: {e}") from e
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        text = getattr(resp, "text", None) or ""
        try:
            return schema.model_validate_json(text)
        except Exception as e:  # bozuk/eksik JSON
            last = e
            i += 1
    raise AIError(f"Gemini yanıtı şemaya uymadı: {last}")


# --- doğrulama + onarım döngüsü -----------------------------------------------------------
def evaluate(design: Tasarim) -> list:
    """Tasarımı derler ve kontrol eder; bulgu listesi döner (hata varsa level='hata')."""
    try:
        b = build(design)
    except BuildError as e:
        return e.findings
    return run_checks(b)


def _errors(findings) -> list:
    return [f for f in findings if f.level == "hata"]


def repair(design: Tasarim, findings, client=None, rounds: int = 2, log=print) -> tuple[Tasarim, list]:
    for _ in range(rounds):
        errs = _errors(findings)
        if not errs:
            break
        warns = [f for f in findings if f.level == "uyari"]
        prompt = (
            "Bu tasarım motorda derlendiğinde aşağıdaki sorunlar çıktı. Tasarım fikrini ve karakterini koruyarak "
            "HATALARIN hepsini, mümkünse uyarıları da gider. Tam tasarımı döndür.\n\n"
            f"# Tasarım\n```json\n{json.dumps(design.model_dump(), ensure_ascii=False)}\n```\n\n"
            "# Hatalar\n" + "\n".join(f"- {f.message}" for f in errs) +
            ("\n\n# Uyarılar\n" + "\n".join(f"- {f.message}" for f in warns) if warns else "")
        )
        res: Onarim = _ask(prompt, Onarim, client, max_tokens=32000)
        log(f"  onarım: {res.aciklama}")
        design = res.tasarim
        findings = evaluate(design)
    return design, findings


# --- üst düzey işlemler ------------------------------------------------------------------
def _moves(k: int, rng: random.Random) -> list[str]:
    with open(os.path.join(HERE, "bilgi", "tasarim_hamleleri.md"), encoding="utf-8") as f:
        moves = [ln[2:].strip() for ln in f if ln.startswith("- ")]
    return rng.sample(moves, min(k, len(moves)))


def ideas(brief: str, n: int = 4, client=None, previous: list[str] | None = None, seed: int | None = None,
          malzeme: str = "", log=print, rejected_out: list | None = None) -> list[tuple[Tasarim, list]]:
    """Bir tariften birbirinden belirgin biçimde farklı n tasarım üretir, doğrular ve onarır."""
    rng = random.Random(seed)
    sparks = _moves(max(3, n + 1), rng)
    axes = ["klasik ve satış garantili", "modern minimal", "yapısal olarak yenilikçi (alışılmadık katlama/kilit)",
            "lüks detaylı", "üretimi en kolay (yeni başlayan için)", "deneysel / sanatsal"]
    rng.shuffle(axes)
    prompt = (
        f"# İstek\n{brief}\n\n"
        f"{n} adet BİRBİRİNDEN BELİRGİN BİÇİMDE FARKLI, DİKİŞSİZ tasarım üret. Farklılık yapısal olsun (parça sayısı, "
        "katlama mimarisi, kilit/kapanma mekanizması, bölme düzeni, açılım yönü), yalnızca ölçü değil. İsteğin zorunlu koşullarına "
        "(ör. 'kapaklı', 'çıtçıtlı') her tasarımda uy; geri kalanında özgür ol.\n"
        f"Her tasarım için farklı bir yön benimse: {', '.join(axes[:n])}.\n"
        f"Bu turun ilham kıvılcımları (en az birini cesurca kullan): {'; '.join(sparks)}.\n"
        + (f"Varsayılan malzeme: {malzeme}.\n" if malzeme else "")
        + ("\nDaha önce üretilenler (bunları TEKRARLAMA):\n" + "\n".join(f"- {p}" for p in previous) + "\n" if previous else "")
        + "\nHer tasarımda: içerikleri (kart vb.) tanımla, kat_sirasi'nı montaj mantığına göre ver, konsepti 2-4 cümleyle "
          "neyin farklı olduğunu anlatacak şekilde yaz."
    )
    extra = max(1, n // 3)
    valid, rejected = [], []
    seen = list(previous or [])
    for round_ in range(3):
        need = n - len(valid)
        if need <= 0:
            break
        k = need + extra
        who = ("Gemini" if (client is not None and not hasattr(client, "beta")) or (client is None and provider() == "gemini")
               else "Claude")
        log(f"{who} {k} fikir tasarlıyor (ilham: {', '.join(sparks[:3])})...")
        ask = prompt.replace(f"{n} adet BİRBİRİNDEN", f"{k} adet BİRBİRİNDEN")
        if seen and round_ > 0:
            ask += "\nBunlar zaten üretildi, TEKRARLAMA:\n" + "\n".join(f"- {x}" for x in seen)
        res: Fikirler = _ask(ask, Fikirler, client)
        for d in res.tasarimlar:
            f = evaluate(d)
            if _errors(f):
                log(f"'{d.ad}': {len(_errors(f))} hata, onarılıyor...")
                d, f = repair(d, f, client, rounds=3, log=log)
            (rejected if _errors(f) else valid).append((d, f))
            seen.append(f"{d.ad}: {d.konsept[:120]}")
    if rejected:
        log(f"{len(rejected)} fikir onarıldıktan sonra da üretilebilir değildi; elendi.")
    if rejected_out is not None:
        rejected.sort(key=lambda df: len(_errors(df[1])))
        rejected_out.extend(rejected)
    valid.sort(key=lambda df: sum(x.level == "uyari" for x in df[1]))
    return valid[:n]


def revise(design: Tasarim, feedback: str, client=None, log=print) -> tuple[Revizyon, Tasarim, list]:
    findings = evaluate(design)
    prompt = (
        f"# Mevcut tasarım\n```json\n{json.dumps(design.model_dump(), ensure_ascii=False)}\n```\n\n"
        "# Motorun ölçüleri ve kontrolleri\n" + "\n".join(f"- [{f.level}] {f.message}" for f in findings) +
        _measures_txt(design) +
        f"\n\n# Kullanıcının geri bildirimi\n{feedback}\n\n"
        "Geri bildirimi karşılayan en küçük tutarlı değişikliği yap (gerekirse bağlı ölçüleri de dengele). "
        "Tasarımın geri kalanını olduğu gibi koru. Tam tasarımı döndür."
    )
    rev: Revizyon = _ask(prompt, Revizyon, client, max_tokens=32000)
    new = rev.tasarim
    f2 = evaluate(new)
    if _errors(f2):
        log("Değişiklik hataya yol açtı, onarılıyor...")
        new, f2 = repair(new, f2, client, log=log)
    return rev, new, f2


def review(design: Tasarim, client=None) -> Inceleme:
    findings = evaluate(design)
    try:
        from .instructions import make
        steps = make(build(design)).steps
        steps_txt = "\n".join(f"{i}. {s.title}: {' '.join(s.text)}" for i, s in enumerate(steps, 1))
    except BuildError:
        steps_txt = "(derlenemedi)"
    prompt = (
        f"# Tasarım\n```json\n{json.dumps(design.model_dump(), ensure_ascii=False)}\n```\n\n"
        "# Kural kontrolleri\n" + "\n".join(f"- [{f.level}] {f.message}" for f in findings) + _measures_txt(design) +
        f"\n\n# Üretilen yapım adımları\n{steps_txt}\n\n"
        "Bu kalıbın gerçek ürüne dönüşümünü adım adım zihninde canlandır: kesim, katlama, kilitleme, ilk kullanım, 6 ay "
        "günlük kullanım. Kural kontrollerinin yakalayamadığı kullanım zorluklarını, dayanıklılık risklerini ve yeni "
        "başlayan bir Etsy alıcısının talimatta takılabileceği yerleri bul; her biri için somut öneri ver."
    )
    return _ask(prompt, Inceleme, client, max_tokens=32000)


def learn_pdf(path: str, client=None) -> tuple[Bilgi, str]:
    """Kullanıcının PDF'ini okuyup genellenebilir bilgiyi bilgi/kullanici/ altına yazar."""
    with open(path, "rb") as f:
        pdf = f.read()
    content = ("Bu, kullanıcının referans aldığı bir dikişsiz deri kalıp/talimat PDF'i. Genellenebilir bilgiyi çıkar: "
               "ölçü ve pay kuralları, kilit/yarık/kat toleransları, yapım sırası ve teknikler, tasarım motifleri "
               "(ilke olarak, birebir kopya değil), talimat anlatım üslubu ve sayfa düzeni. Başkasının tasarımını "
               "çoğaltmaya yarayacak birebir ölçü listesi çıkarma; kendi tasarımlarımızı geliştirmeye yarayacak "
               "dersleri yaz.")
    info: Bilgi = _ask(content, Bilgi, client, max_tokens=16000, pdf=pdf)
    name = os.path.splitext(os.path.basename(path))[0]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:60]
    out = os.path.join(HERE, "bilgi", "kullanici", f"{safe}.md")
    md = [f"# {info.baslik}", f"_Kaynak: {os.path.basename(path)}_", ""]
    for title, items in (("Kurallar", info.kurallar), ("Teknikler", info.teknikler),
                         ("Tasarım motifleri", info.tasarim_motifleri), ("Talimat üslubu", info.talimat_uslubu)):
        if items:
            md += [f"## {title}"] + [f"- {x}" for x in items] + [""]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return info, out


def _measures_txt(design: Tasarim) -> str:
    try:
        b = build(design)
    except BuildError:
        return ""
    lines = [f"- {k} = {v:g}" for k, v in b.env.items()]
    for pid in b.order:
        p = b.panels[pid]
        lines.append(f"- panel {pid}: {p.w:.1f} × {p.h:.1f} mm, açı {p.angle:g}°")
    w, h, d = b.finished_size()
    lines.append(f"- bitmiş ürün ≈ {w:.1f} × {h:.1f} × {d:.1f} mm")
    return "\n\n# Hesaplanmış değerler\n" + "\n".join(lines)

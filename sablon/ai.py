"""Claude ile doğal dil arayüzü.

İlke: Claude ASLA koordinat/geometri üretmez. Yalnızca
  1) tarifi bir şablona ve parametre değerlerine çevirir,
  2) "şurası uzun olmuş" gibi geri bildirimleri parametre değişikliklerine çevirir,
  3) türetilmiş ölçüler, kural kontrolleri ve montaj adımları üzerinden ürünü
     "kafasında kurup" kullanım sorunlarını yorumlar.
Geometri her zaman deterministik şablon motorunda üretilir; böylece mm hassasiyeti
yapay zekânın hatasına bağlı değildir. Tüm değerler şablonun sınırlarına kırpılır.
"""
from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field

from .project import Change, Project
from .templates import REGISTRY, Template

MODEL = os.environ.get("SABLON_MODEL", "claude-opus-5-5")

SYSTEM = """Sen deri, kâğıt/karton ve tekstil ürünlerinde uzman bir endüstriyel kalıp (şablon) tasarımcısısın.
Kullanıcı Etsy'de satılacak PDF kalıplar hazırlıyor. Kalıplar, aşağıdaki parametrik şablon motoruyla
milimetre hassasiyetinde üretilir. Sen geometri ÇİZMEZSİN; yalnızca şablon seçer ve parametre değerlerini
belirlersin. Her şey mm cinsindendir (aksi belirtilmedikçe).

Kurallar:
- Yalnızca katalogdaki şablon anahtarlarını ve parametre adlarını kullan; sınırların dışına çıkma.
- Kullanıcının gündelik ifadelerini ("biraz", "çok", "burası") somut mm değişikliklerine çevir; ilişkileri
  (relations) kullanarak hangi parametrenin hangi ölçüyü etkilediğini hesapla.
- Fiziksel gerçekliği düşün: malzeme kalınlığı, katlanma payları, kartın girip çıkması, kilidin tutması,
  dikiş kenar mesafesi, parmakla tutulabilirlik, yırtılma noktaları.
- Emin olmadığın şeyi varsayım olarak açıkça yaz. Gerçekten belirsizse soru sor.
- Tüm açıklamaları Türkçe yaz."""


def catalog() -> str:
    parts = []
    for t in REGISTRY.values():
        ps = "\n".join(
            f"    - {p.name} ({p.label}; {p.unit}; varsayılan {p.default}; aralık {p.min}–{p.max}"
            f"{'; tamsayı' if p.integer else ''}){' — ' + p.help if p.help else ''}"
            for p in t.params
        )
        parts.append(
            f"## {t.key}: {t.title}\n{t.description}\nMalzeme: {t.material}\n"
            f"İlişkiler:\n{getattr(t, 'relations', '')}\nParametreler:\n{ps}"
        )
    return "\n\n".join(parts)


def state(tpl: Template) -> str:
    return json.dumps(tpl.summary(), ensure_ascii=False, indent=1)


# --- yapılandırılmış çıktı şemaları ------------------------------------------
class ParamValue(BaseModel):
    name: str
    value: float


class ParamChange(BaseModel):
    name: str
    new_value: float
    reason: str


class DesignChoice(BaseModel):
    supported: bool = Field(description="Katalogdaki bir şablon bu isteği karşılıyor mu")
    template: str = Field(description="Seçilen şablon anahtarı (desteklenmiyorsa en yakını)")
    name: str = Field(description="Ürün için kısa, satışa uygun Türkçe ad")
    params: list[ParamValue] = Field(description="Yalnızca varsayılandan farklı olması gereken parametreler")
    assumptions: list[str]
    missing_capability: str = Field(description="Desteklenmiyorsa eksik olan özellik; destekleniyorsa boş")


class Revision(BaseModel):
    understood_as: str = Field(description="Geri bildirimi nasıl yorumladığın (hangi ölçü, ne kadar)")
    changes: list[ParamChange]
    question: str = Field(description="Geri bildirim gerçekten belirsizse kullanıcıya soru; değilse boş")


class Risk(BaseModel):
    severity: str = Field(description="yuksek | orta | dusuk")
    title: str
    detail: str = Field(description="Ürün kullanılırken ne olur, neden olur")
    changes: list[ParamChange] = Field(description="Önerilen parametre değişiklikleri (yoksa boş)")


class Review(BaseModel):
    product_story: str = Field(description="Kalıbın kesilip katlanıp/dikilip kullanılmasının adım adım zihinsel canlandırması")
    risks: list[Risk]
    selling_tips: list[str] = Field(description="Etsy listesi ve PDF için öneriler")


# --- Claude çağrısı ---------------------------------------------------------------
class AIError(RuntimeError):
    pass


def _client():
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise AIError("'anthropic' paketi kurulu değil: pip install anthropic") from e
    return anthropic.Anthropic()


def _ask(prompt: str, schema: type[BaseModel], client=None):
    import anthropic

    client = client or _client()
    try:
        resp = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            # Güvenlik sınıflandırıcısı reddederse istek sunucu tarafında yedek modelle yeniden çalışır.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
    except anthropic.AuthenticationError as e:
        raise AIError("Claude API anahtarı bulunamadı/geçersiz. ANTHROPIC_API_KEY ortam değişkenini ayarlayın.") from e
    except anthropic.RateLimitError as e:
        raise AIError("Claude API hız sınırına takıldı; biraz sonra tekrar deneyin.") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API hatası ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Claude API'ye bağlanılamadı (ağ).") from e
    if resp.stop_reason == "refusal":
        raise AIError("Model isteği yanıtlamayı reddetti.")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise AIError("Model yanıtı eksik kaldı; isteği kısaltıp tekrar deneyin.")
    return resp.parsed_output


# --- üst düzey işlemler -------------------------------------------------------
def design_from_description(text: str, client=None) -> tuple[Project, DesignChoice]:
    prompt = (
        f"# Şablon kataloğu\n{catalog()}\n\n# Kullanıcının tarifi\n{text}\n\n"
        "En uygun şablonu seç ve parametreleri belirle. Kullanıcı ölçü vermediyse ürün tipine göre endüstri "
        "standardı değerleri kullan ve varsayım olarak yaz."
    )
    choice: DesignChoice = _ask(prompt, DesignChoice, client)
    key = choice.template if choice.template in REGISTRY else next(iter(REGISTRY))
    proj = Project(template=key, name=choice.name, notes=list(choice.assumptions))
    changes = [Change(pv.name, 0.0, pv.value, "tariften") for pv in choice.params
               if any(p.name == pv.name for p in REGISTRY[key].params)]
    proj.apply(changes, source="ai:tarif", request=text)
    return proj, choice


def revise(project: Project, feedback: str, client=None) -> tuple[Revision, list[Change]]:
    tpl = project.instance()
    t = type(tpl)
    prompt = (
        f"# Şablon\n{t.key}: {t.title}\nİlişkiler:\n{getattr(t, 'relations', '')}\n"
        f"Parametre sınırları: " + json.dumps({p.name: [p.min, p.max] for p in t.params}, ensure_ascii=False) +
        f"\n\n# Mevcut durum (parametreler, türetilmiş ölçüler, kontrol bulguları)\n{state(tpl)}\n\n"
        f"# Geçmiş değişiklikler\n{json.dumps(project.history[-5:], ensure_ascii=False)}\n\n"
        f"# Kullanıcının geri bildirimi\n{feedback}\n\n"
        "Geri bildirimi karşılayan en az sayıda parametre değişikliğini öner. Başka ölçüleri bozacaksa "
        "(ör. kilit kafası çakışması) dengeleyici değişikliği de ekle."
    )
    rev: Revision = _ask(prompt, Revision, client)
    if rev.question and not rev.changes:
        return rev, []
    names = {p.name for p in t.params}
    applied = project.apply([Change(c.name, 0.0, c.new_value, c.reason) for c in rev.changes if c.name in names],
                            source="ai:duzelt", request=feedback)
    return rev, applied


def review(project: Project, client=None) -> Review:
    tpl = project.instance()
    t = type(tpl)
    prompt = (
        f"# Şablon\n{t.key}: {t.title}\n{t.description}\nMalzeme: {t.material}\n"
        f"İlişkiler:\n{getattr(t, 'relations', '')}\n\n# Mevcut durum\n{state(tpl)}\n\n"
        f"# Montaj adımları\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(tpl.assembly(), 1)) +
        "\n\nBu kalıbın gerçek ürüne dönüşümünü adım adım zihninde canlandır: kesim, katlama/dikiş, ilk kullanım, "
        "6 ay günlük kullanım. Kural kontrollerinin yakalayamadığı kullanım zorluklarını ve dayanıklılık "
        "risklerini bul; her biri için somut parametre değişikliği öner. Etsy alıcısının (yeni başlayan "
        "zanaatkâr) kalıbı yanlış anlayabileceği noktaları da belirt."
    )
    return _ask(prompt, Review, client)


def autofix(project: Project, max_rounds: int = 6) -> list[Change]:
    """Kural motorunun 'hata' bulgularındaki önerileri, hata kalmayana dek uygular (AI gerektirmez)."""
    applied: list[Change] = []
    for _ in range(max_rounds):
        errs = [f for f in project.instance().checks() if f.level == "hata" and f.suggestion]
        if not errs:
            break
        ch = [Change(k, 0.0, v, f.message) for f in errs for k, v in f.suggestion.items()]
        got = project.apply(ch, source="otomatik-duzeltme")
        if not got:
            break
        applied += got
    return applied

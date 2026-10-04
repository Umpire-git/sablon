# Şablon — parametrik kalıp üretici

Etsy'de satılacak PDF kalıplar (dikişsiz deri cüzdan, kartlık, karton kutu…) için
**milimetre hassasiyetinde**, düzeltilebilir ve kendi kendini kontrol eden bir kalıp aracı.

```
tarif ("4 kartlık dikişsiz cüzdan") ──► Claude: şablon + parametre seçimi
                                            │
                    ┌───────────────────────▼────────────────────────┐
                    │  Parametrik geometri motoru (deterministik)     │
                    │  mm cinsinden gerçek doğru/yay, katlama payları │
                    └───────┬──────────────┬───────────────┬─────────┘
                            ▼              ▼               ▼
                     Kural kontrolleri  Montaj adımları  Montajlı ön izleme
                     (kart sığar mı,    (katlama sırası,  (önden/arkadan/yan)
                      kilit tutar mı…)   dağ/vadi katı)
                            │
   "burası uzun olmuş" ──► Claude: geri bildirim → parametre değişikliği → otomatik hata düzeltme
                            │
                            ▼
        PDF A4 + US Letter (parçalı, hizalama işaretli) · tam boy PDF · SVG (Cricut/lazer) · DXF (CNC)
```

## Neden yapay zekâ doğrudan çizmiyor?

Dil modelleri koordinat üretirken milimetre hatası yapabilir. Bu yüzden geometri **her zaman**
parametrik şablon motorunda hesaplanır; Claude yalnızca hangi şablonun ve hangi değerlerin
kullanılacağına karar verir ve "şurası uzun" gibi ifadeleri parametre değişikliğine çevirir.
Sonuç: aynı parametreler → her seferinde birebir aynı, ölçüsü doğru kalıp. Tüm değerler
şablonun güvenli aralığına kırpılır ve her değişiklik proje dosyasının geçmişine yazılır.

## Kurulum

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...      # yalnızca tarif / duzelt / incele komutları için
```

## Kullanım

```bash
sablon liste --detay                                   # şablonlar ve parametreleri

# 1) Tariften başla (Claude)
sablon tarif "6 kartlık, başparmak oyuklu dikişsiz deri kartlık, 1.6 mm deri" -o cuzdan.json
#    ...veya elle:
sablon yeni dikissiz_kartlik kart_sayisi=6 deri_kalinligi=1.6 -o cuzdan.json

# 2) Ölçüleri ve kontrolleri gör
sablon kontrol cuzdan.json

# 3) Düzelt
sablon duzelt cuzdan.json "ön panel çok yüksek olmuş, kartların yarısı görünsün"   # Claude
sablon ayarla cuzdan.json on_panel_orani=0.6                                       # elle
sablon otomatik cuzdan.json                                                        # kural hatalarını gider

# 4) Ürüne dönüşümü canlandır, kullanım risklerini bul (Claude)
sablon incele cuzdan.json            # --uygula: yüksek önemli önerileri uygular

# 5) Satışa hazır dosyalar
sablon cikti cuzdan.json -d cikti/
sablon gecmis cuzdan.json
```

`cikti` komutu şunları üretir:

| Dosya | Ne için |
|---|---|
| `*_A4.pdf`, `*_Letter.pdf` | Ev yazıcısı. Kapak (50 mm + 2 inç ölçek testi), ölçüler, çizgi lejantı, sayfa birleştirme haritası, kontroller, montaj adımları, ardından ◆ hizalama işaretli parça sayfaları. Etsy alıcılarının çoğu ABD'de olduğu için **iki boyut da** verin. |
| `*_tam_boy.pdf` | Tek sayfada tamamı (A0 plotter / fotokopici / matbaa). |
| `*.svg` | 1:1 mm, katmanlı (cut / fold / stitch …) — Cricut, Glowforge, Inkscape. |
| `*.dxf` | R12, mm, katmanlı — lazer kesim, CNC, CAD. |
| `*_onizleme.svg` | Montajlı ürünün önden / arkadan / yandan ölçülü görünümü (Etsy görseli taslağı). |

## Şablonlar

| Anahtar | Ürün | Öne çıkan mühendislik detayları |
|---|---|---|
| `dikissiz_kartlik` | Tek parça dikişsiz deri kartlık | Kart sayısı × kart kalınlığından körük hesabı, deri kalınlığı katlama payı, dil-yarık kilidi (kafa > yarık), yarık ucu yırtılma önleyici delikler, katlanınca yarık ↔ dil hizası, başparmak oyuğu |
| `dikisli_kartlik` | Gövde + 2 kademeli cep | Dikiş delikleri tüm parçalarda birebir örtüşür, zımba adımı hattı tam bölecek şekilde ayarlanır, iplik boyu, 3 kat kalınlık kontrolü |
| `kutu` | Ters kilitli karton kutu | İç ölçüden panel ölçüsü (karton kalınlığı), ortak kenar → otomatik bigi, toz kapağı çakışma kontrolü, hangi kâğıda sığdığı |

## Kontroller ("olası kullanım zorlukları")

Her şablon kendi kurallarını taşır; örnek (dikişsiz kartlık):

- yan boşluk < 0.75 mm → **hata**: kartlar dolu ceple sıkışır
- kilit kafası − yarık < 1.5 mm → **hata**: kilit kendiliğinden açılır; > 6 mm → takılmaz/yırtar
- dil boynu < 5 × deri kalınlığı → **hata**: boyundan kopar
- sağ/sol kilit kafaları arka panelde çakışıyor → **hata**
- başparmak oyuğu yok ve kart taşmıyor → **uyarı**: kart çıkmaz
- deri ≥ 1.6 mm → **bilgi**: kat yerlerini V-kanal ile inceltin

Her bulgu, düzeltmek için somut bir parametre önerisi taşır; `sablon otomatik` bunları uygular.
`sablon incele` ise Claude'a ürünü kesimden 6 aylık kullanıma kadar canlandırtarak kuralların
yakalayamadığı riskleri (aşınma, köşe yırtılması, alıcının yanlış anlayabileceği adımlar) buldurur.

## Yeni ürün tipi eklemek

`sablon/templates/` altına `Template` alt sınıfı yazın: `params`, `build()` (geometri),
`measures()`, `checks()`, `assembly()`, `preview_svg()`; sonra `templates/__init__.py`'deki
`REGISTRY`'ye ekleyin. Claude Code'a "çantam için şu ölçülerde şablon ekle" diyerek de
yazdırabilirsiniz; testler (`pytest`) kesim hattının kapalı olduğunu ve PDF ölçeğini doğrular.

## Gerçekçi sınırlar

- Araç yalnızca katalogdaki ürün tiplerini üretir; tamamen yeni bir yapı (ör. fermuarlı çanta)
  için önce şablonu eklenmelidir — tarif bu durumda "desteklenmiyor" der ve en yakınını önerir.
- Deri doğal bir malzemedir: esneme, kalınlık farkı ve tabaklama türü sonucu etkiler.
  Satıştan önce **en az bir fiziksel prototip** kesip kontrol edin; gerekirse `duzelt` ile düzeltin.
- Alıcının yazıcısı "sayfaya sığdır" ile basarsa ölçek bozulur — PDF'teki ölçek karesi bunun için.

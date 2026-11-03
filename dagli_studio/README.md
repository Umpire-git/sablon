# Dagli Studio — dikişsiz origami deri kalıp üretim hattı

Sohbetlerde elle yaptığımız akışın (dagli-pattern-pipeline becerisi) yazılımı:
**Etsy rakip taraması → fikir → parametrik tasarım + en kötü durum testi → ev stili satış PDF'i →
kesim dosyaları → SEO'lu Etsy ilanı → Etsy görselleri → gerçekçi ürün görselleri.**
Her kapıda durur, onayını bekler.

```
1. KAPI  dagli pazar "…"   → pazar/<konu>/rapor.md   (fiyat çeyrekleri, sık etiketler, rakiplerde dikiş/çıtçıt oranı)
         dagli fikir "…"   → fikirler.md             (2–3 fikir, öneri, "signature mı kalıp mı?")
2. KAPI  dagli tasarla …   → urunler/<ürün>.py       (Claude yazar → motor sınar → hata varsa Claude onarır)
         dagli kontrol …   → çakışma, delik-kenar, omuz, boyun + 2592 kombinasyonluk en kötü durum taraması
         dagli deneme …    → konsept sayfası + 1:1 kâğıt deneme PDF'i (A4 + Letter, 50 mm kare)
3. KAPI  dagli uret …      → teslim/<ürün>_v<sürüm>/  (tam satış paketi, aşağıda)
         dagli gorsel …    → Gemini ile gerçekçi çekimler (hero, kilit, elde, yaşam, atölye)
```

## Kurulum (Windows)

1. Python 3.11+ kur (<https://www.python.org/downloads/>), ilk ekranda **Add python.exe to PATH** işaretli.
2. Bu klasörde **`kurulum.bat`**'a çift tıkla (bir kez).
3. **`dagli.bat`**'a çift tıkla → menüden seç.

Anahtarlar (komut penceresinde bir kez, sonra pencereyi kapatıp aç):

| Ne için | Değişken | Nereden |
|---|---|---|
| Rakip verisi (en sağlam: 13 etiket, fiyat, favori) | `setx ETSY_API_KEY "keystring"` (+ gerekirse `setx ETSY_SHARED_SECRET "…"`) | <https://www.etsy.com/developers/register> |
| Web'de rakip araştırması, fikir, tasarım kodu | `setx ANTHROPIC_API_KEY "…"` | <https://console.anthropic.com/> |
| Gerçekçi ürün görselleri | `setx GEMINI_API_KEY "…"` | <https://aistudio.google.com/apikey> |

Hiçbiri olmadan da çalışan kısım: **kontrol, deneme, uret** (PDF'ler, kesim dosyaları, Etsy grafikleri, ilan,
promptlar). Promptları ChatGPT/Gemini'ye elle de yapıştırabilirsin.

## 3. kapı paketi (`dagli uret`)

```
teslim/Dagli_Round_Pen_Cup_v2.0/
  UPLOAD_TO_ETSY/                       → Etsy'ye yüklenecek dijital dosyalar
    …_Pattern_A4.pdf, …_Pattern_Letter.pdf   ev stili kitapçık (logo, filigran, © alt bilgi, 50 mm kare)
    …_FullSize_CopyShop.pdf             tek sayfa gerçek boy (fotokopici/plotter)
    …_CutFiles_v2.0.zip                 SVG (lazer), Cricut SVG (yarıklar ince kapalı şekil), DXF R12 (CUT/FOLD), README
  UPLOAD_TO_ETSY_….zip                  aynısı tek ZIP
  etsy_gorselleri/ 01_hero … 05_cut_files (2000×2000; kalıp bulanık + PREVIEW, ölçülemez)
  LISTING.md                            başlık (≤140), tam 13 etiket (≤20), açıklama, nitelikler, fiyat gerekçesi,
                                        mağaza bölümü, fotoğraf sırası + alt metin, SEO kontrolü
  ai/ai_referans.png + PROMPTS.md       3B referans sayfası; ortak ürün bloğu + çekim satırları (EN + TR),
                                        hangi dosya hangi sırayla eklenir
  OZET.md                               proje özetine yapıştırılacak 2 satır + kontrol/denetim raporu
```

Kitapçık düzeni senin PDF'lerinle aynı: tek sayfaya sığan ürün → sayfa 1 = 1:1 şablon + kare; sığmayan →
genel bakış, baskı & sayfa haritası (20 mm bindirme, artı işaretleri), parça parça şablon sayfaları. Ardından
genel bakış (renkli parçalar, kırmızı "REFERENCE ONLY · DO NOT CUT" çerçevesi, At a glance, Before you start,
What is in this PDF), 3×3 adım sayfaları (her adıma tek çizim, rozet + metin), kilit yakın planları, yardım
sayfası (sorun giderme, bakım, terimler).

Denetim kendiliğinden yapılır: her sayfa boyutu (A4/Letter), "Page n of N", eski sürüm yazısı ("Pattern vX")
artığı, kenara taşan çizim/metin, kesim dosyalarının 1:1 boyutu ve mm birimi, tam boy PDF ölçeği.

## Yeni ürün nasıl eklenir

Her ürün `urunler/` içinde tek bir Python dosyasıdır (`PRODUCT = …`). Örnek: `urunler/round_pen_cup.py`
(Round Pen Cup v1.1'in parametrik yeniden kurulumu: DF 39,6 · RB 40,8 · alçak yarık 8,5 mm).
Dosyada: parçalar (shapely, mm), kilitler (`Tongue`, `Slit`), 3B katlama sahnesi (adım sırası `stage` ile),
adımlar, yakın planlar, `lock_check` (tek bir en kötü durum için kilit hataları), SEO girdileri, görsel tarifi.

`dagli tasarla` bu dosyayı Claude'a yazdırır; motor kontrol eder ve hataları geri verir (en fazla 4 tur).
Kendin de düzenleyebilirsin; sonra `dagli kontrol`.

En kötü durum taraması (beceri kuralları): deri 0,2 → 2,4 mm (0,2 adım) × sıkı/gevşek sarım (+1 mm) × kat
±1 mm × yarık işareti ±0,7 mm × yarık 0,6 mm uzun kesim × zımba 1,5/2/3 mm × ters çizim = 2592 kombinasyon;
hepsi geçmeli. Durdurma deliği Ø 2 mm, zımba değişse de yarık açıklığı sabit; delik kenara ≥ 4 mm; omuz
≥ 1,5 mm/yan; boyun yarıktan ≥ 3 mm dar; boyun iç köşeleri yuvarlatılır, kanca ucu sivri.

## Bilmen gerekenler

- Bilgisayar testi derinin sertliğini, dilin takılma kolaylığını ve kıvrım şişkinliğini **gösteremez**:
  kâğıt/karton denemesi ve deri prototip + çekme testi şart.
- Yapay zekâ görselleri geçicidir; prototipten sonra gerçek fotoğrafla değiştir (`--kapak foto.jpg`).
  Ana Etsy görseli tek net sahnedir (kolaj değil); ilan açıklamasında AI beyanı otomatik yazılır.
- Fiyat önerisi yalnızca taranan rakip ilanlardan hesaplanır; veri yoksa ürünün kendi aralığı kullanılır ve
  bu açıkça yazılır. Rakam uydurulmaz.
- Etsy API bu bulut ortamından erişilemedi; kendi bilgisayarında çalışır. Anahtar yoksa `--web` (Claude) veya
  `--csv` ile elle hazırlanmış liste kullanılabilir.

## Testler

```bash
pip install -e ".[dev]"
pytest
```

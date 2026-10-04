# Şablon — dikişsiz deri ürün kalıp tasarım aracı

Etsy'de satılacak **dikişsiz** deri ürün PDF kalıpları (kartlık, cüzdan, kılıf…) için:
**tarif → birbirinden farklı tasarım fikirleri → milimetre hassasiyetinde kalıp →
3B ön izleme → görselli yapım kitapçığı.** Malzeme: vaketa veya crazy horse. Dikiş ve
yapıştırıcı yoktur; birleştirme kat, dil-yarık kilidi, çıtçıt, perçin ve şikago vidasıyla yapılır.

```
"kapaklı, çıtçıtlı dikişsiz kartlık"                       "kapak biraz kısa olmuş"
        │                                                          │
        ▼                                                          ▼
  Claude: N farklı tasarım ──► Tasarım dili (JSON) ◄── Claude: en küçük tutarlı değişiklik
                                     │
                                     ▼
                     Katlama-farkındalıklı motor (deterministik, mm)
                     · paneller + yuvarlak kıvrımlı katlar + kat payı
                     · çıtçıt karşılığı, kilit yarığı, perçin/vida delikleri katlanınca otomatik hizalanır
                     · 3B ÇARPIŞMA ve MONTAJ SİMÜLASYONU: paneller birbirinin içinden geçiyor mu,
                       kartlar sığıyor mu, bu sırayla katlanabilir mi, kilit tutar mı, çıtçıt kapanır mı
                                     │  hata varsa Claude'a geri → onarım
                                     ▼
   PDF kitapçık (A4 + Letter + tam boy) · SVG · DXF · interaktif 3B (HTML) · ürün görselleri (PNG)
```

## Neden yapay zekâ doğrudan çizmiyor?

Dil modelleri koordinat üretirken milimetre hatası yapabilir. Bu yüzden Claude **tasarlar**
(hangi paneller, hangi kenardan kaç derece katlanır, kilit dili nereden geçer, çıtçıt nereye),
geometriyi ise motor **hesaplar ve fiziksel olarak sınar**. Hatalı tasarım (birbirinin içinden
geçen paneller, sığmayan kartlar, boşluğa düşen çıtçıt, tutmayan kilit, katlanma sırası imkânsız
ürün) çıktı üretilmeden yakalanır ve Claude'a onarım için geri verilir.

## Kurulum (Windows, adım adım)

1. **Python** kurun: <https://www.python.org/downloads/> → 3.11 veya 3.12. Kurulumun ilk ekranında
   **"Add python.exe to PATH"** kutusunu işaretleyin.
2. **Blender** kurun (fotogerçekçi görseller için, ücretsiz): <https://www.blender.org/download/> → normal kurulum.
   Araç Blender'ı kendisi bulur; ayrıca açmanız gerekmez.
3. **Bu projeyi indirin**: GitHub'da depo sayfasında dalı seçip **Code → Download ZIP**, ZIP'i bir klasöre açın.
4. Klasördeki **`kurulum.bat`** dosyasına çift tıklayın (bir kez).
5. **`deneme.bat`** dosyasına çift tıklayın: örnek kartlığın kalıbı, PDF kitapçığı, 3B dosyası ve Blender
   fotoğrafları `deneme_cikti` klasörüne üretilir ve klasör açılır.

**Yapay zekâ ile yeni fikirler (Gemini veya Claude):** bir anahtar yeterlidir.
- Gemini (ücretsiz kotası var, görseller için de kullanılır): <https://aistudio.google.com/apikey> →
  `setx GEMINI_API_KEY "anahtarınız"`
- Claude: <https://console.anthropic.com/> → `setx ANTHROPIC_API_KEY "anahtarınız"`

Pencereyi kapatıp yeniden açın, sonra **`fikir.bat`**'a çift tıklayın: ne istediğinizi yazarsınız, fikirler
`fikirler` klasörüne ve karşılaştırma sayfası `koleksiyon.pdf`'e gelir. İkisi de tanımlıysa seçmek için
`sablon fikir "..." --ai gemini`.

Gemini modeli **otomatik seçilir**: program anahtarınızın erişebildiği modelleri Google'dan sorgular; tasarım için
en yeni **Pro**'yu (ör. 3.1 Pro), Pro'nun kotası dolarsa en yeni **Flash**'ı (ör. 3.8 Flash; Lite değil), görseller
için en yeni görsel modelini kullanır. Görmek için: `sablon modeller`. Elle seçmek için
`setx SABLON_GEMINI_TEXT_MODEL "model-adı"` (görsel: `SABLON_GEMINI_MODEL`). Claude modeli: `SABLON_MODEL`.

**Yalnızca uygulanabilir fikirler gösterilir:** her fikir motorda derlenir ve 3B çarpışma, montaj sırası, kart
hacmi, kilit, çıtçıt teması, kalınlık kontrollerinden SIFIR hatayla geçmelidir. Hatalı fikir yapay zekâya
onartılır (3 tur); onarılamazsa elenir ve yerine yeni fikir istenir.

Mac/Linux: `pip install -e ".[dev]"`, Blender'ı kurun (veya Python 3.11'de `pip install bpy`).

### Gerçek fotoğraf gibi görseller: Gemini (önerilen)

Bilgisayarda hesaplanan 3B görsel ölçüsü doğru ama "çizim" gibi durur. Gerçek deri fotoğrafı görünümü için
motorun görseli Gemini'ye **referans** olarak verilir; Gemini aynı şekli koruyarak ürün fotoğrafı üretir.

1. Ücretsiz anahtar alın: <https://aistudio.google.com/apikey>
2. Komut penceresinde: `setx GEMINI_API_KEY "anahtarınız"` → pencereyi kapatıp yeniden açın.
3. `sablon cikti proje.json --foto hizli --gemini studyo,ahsap` (sahneler: `studyo`, `ahsap`, `keten`, `mermer`).
   `deneme.bat` anahtar tanımlıysa bunu kendisi yapar.

Gemini'ye dikiş, logo, ek cep eklememesi ve şekli birebir koruması söylenir; yine de yapay zekâ ayrıntı
değiştirebilir — **her görseli kalıpla karşılaştırın** (kapak ucu, kilit dilleri, çıtçıt yeri). Ana Etsy
görseli için en güvenilir kaynak yine prototipin gerçek fotoğrafıdır.

### Fotogerçekçi görseller ve bilgisayar gücü

`sablon cikti proje.json --foto hizli` veya `--foto kaliteli`:

| Ayar | Motor | Süre (yaklaşık, görsel başına) | Ne için |
|---|---|---|---|
| `hizli` | Eevee (ekran kartıyla), yoksa Cycles 24 örnek | saniyeler – yarım dakika | Ön izleme |
| `kaliteli` | Cycles 64 örnek + gürültü giderici | 1–3 dk (i5 + MX ekran kartı sınıfı) | Etsy görselleri |

**Gerçek deri dokusu (önerilir):** ücretsiz (CC0) bir PBR deri dokusu indirin, ör. ambientCG'de "Leather"
araması → bir doku → **1K-JPG** ZIP (veya Poly Haven → Textures → leather). ZIP'i proje klasöründe `doku`
adlı klasöre açın. `deneme.bat` bu klasörü kendisi kullanır; elle: `sablon cikti proje.json --foto kaliteli --doku doku`.
Doku yalnızca gözenek/kırışık desenini verir; renk tasarımdaki deri renginden gelir.

Görseller: `_foto_urun` (önden), `_foto_arka` (ters çevrilmiş), `_foto_yari_acik` (katlanırken), `_foto_acinim`.
Model yumuşak deri gibi üretilir: perdahlı yuvarlak kenarlar, panellerde hafif bombe ve dalgalanma, kıvrımlarda
t·0.8 yarıçap (kalınlık değişmez).
Geometri motorun modelinden birebir alınır; Blender yalnızca ışık ve malzemeyi gerçekçi hesaplar, yani
görseldeki ürün kalıptan çıkan üründür. Daha yüksek kalite için `SABLON_ORNEK=128` ortam değişkeni verilebilir.

## Hazır modeller (yapay zekâ gerekmez)

`hazir_modeller/` klasöründe simülasyondan hatasız geçmiş, düz katlanan ince (≈14 mm, 7 kart) çekme şeritli
kartlıklar var: Origami Kemer, Para Kemerli Çakıl, Ok Uçlu Kapak. Hepsi tek parça gövde + perçinsiz örgülü şerit. `paket.bat`'a çift tıklayın: her model için
A4/Letter/tam boy PDF kalıp, SVG, DXF, 3B görüntüleyici, ürün görselleri, Etsy metni ve (Blender kuruluysa)
fotoğraf gerçekliğinde görseller kendi klasörüne üretilir. Tamamen ücretsizdir.

## Kullanım

```bash
# 1) Fikir üret (her çalıştırmada farklı ilham; aynı klasördekileri tekrarlamaz)
sablon fikir "kapaklı, çıtçıtlı dikişsiz kartlık" -n 5 --malzeme crazy_horse
#    → fikirler/01_....json ... + fikirler/koleksiyon.pdf (3B görselli karşılaştırma)
#    --tam: her uygun fikir kendi klasöründe hazır satış paketiyle gelir
#           (A4/Letter/tam boy PDF kalıp, SVG, DXF, 3B HTML, ürün görselleri, Etsy ilan metni)
#    Yapay zekâ hataları ve ürünü kullanılmaz kılan uyarıları (tek perçin, kart tutulamıyor,
#    şerit ucu kısa...) kendisi düzeltir; düzeltemediklerini fikirler/elenenler/ altına nedenleriyle yazar.

# 2) Beğendiğini düzelt
sablon duzelt fikirler/03_zarf_kartlik.json "kapak biraz kısa, çıtçıt daha aşağıda olsun"
sablon ayarla fikirler/03_zarf_kartlik.json kart_adet=6 kapak.yukseklik="Hb*0.6"
sablon kontrol fikirler/03_zarf_kartlik.json

# 3) Ürünü canlandırıp kullanım risklerini bul (Claude)
sablon incele fikirler/03_zarf_kartlik.json --uygula

# 4) Satışa hazır dosyalar
sablon cikti fikirler/03_zarf_kartlik.json -d cikti/

# Hazır örneklerle başlamak (API anahtarı gerekmez)
sablon ornekler
sablon yeni kapakli_citcitli_kartlik -o proje.json

# Kendi referans PDF'lerinden öğren (bilgi bankasına eklenir, sonraki tüm tasarımlarda kullanılır)
sablon ogren referans1.pdf referans2.pdf
```

`cikti` komutunun ürettikleri:

| Dosya | Ne için |
|---|---|
| `*_A4.pdf`, `*_Letter.pdf` | Satılacak kitapçık: kapakta 3B ürün görseli ve özet (ölçü, malzeme, zorluk, süre); ölçek testi; çizgi lejantı; sayfa birleştirme haritası; **malzeme listesi** (deri dm², çıtçıt, vida…); **alet listesi**; **görselli, sıralı yapım aşamaları** (kesim → kenar bitirme → çıtçıt → katlama → kilitleme → vida → şekillendirme); tasarım kontrolleri; ◆ hizalama işaretli 1:1 kalıp |
| `*_tam_boy.pdf` | Tek sayfada kalıbın tamamı (plotter / matbaa / lazer) |
| `*.svg` / `*.dxf` | 1:1 mm, katmanlı (kesim, yarık, kat, delik…) — Cricut, lazer, CNC |
| `*_3B.html` | Tarayıcıda döndürülebilen 3B model; kaydırıcıyla açınım ↔ bitmiş ürün katlama animasyonu, adım adım montaj |
| `*_urun.png`, `*_arka.png`, `*_yari_acik.png`, `*_acinim.png` | Etsy listesi için ürün görselleri |

## Kalibrasyon: kalıplar SENİN derine göre (önerilir, bir kez)

Deri tabakhaneye ve partiye göre farklı katlanır; 1–2 mm sapma kilidi ve kartın oturmasını bozar.

```bash
sablon kalibrasyon --malzeme vaketa --kalinlik 1.6 -o kalibrasyon.pdf   # deneme kalıbı
# basın, kendi derinizden kesin: katlama şeridini 180° katlayın, F boyunu kumpasla ölçün;
# 2/3/4 mm'lik kilit dillerinden takılabilen ve tutan en darını seçin
sablon kalibre vaketa --kalinlik 1.6 --katlama 59.1 --kilit 3
sablon kalibre --goster
```

Değerler `kalibrasyon.json`'a yazılır; bundan sonra tüm kat payları, kıvrım yarıçapı, kilit kontrolleri ve
3B görseller bu değerleri kullanır. Crazy horse için ayrıca yapın.

## Malzemeler

- Kartlık/cüzdan için kalınlık **1.2–1.8 mm** (tipik 1.4–1.6); 1.8 mm üstü hata sayılır.
- `vaketa`: bitkisel tabaklı, sert; kalıplanır, kenarı su/tokonole ile perdahlanır. Dikişsiz kilitler için ideal.
- `crazy_horse`: yağlı-mumlu pull-up deri; daha yumuşak, nemlendirilmez, kenarı boyanır. Kilit kafaları daha geniş
  istenir, çıtçıta takviye pulu önerilir; 3B görselde kıvrım yerlerinde renk açılması gösterilir.

Değerler `sablon/materials.py` içinde düzenlenebilir.

## Tasarım dili (kısaca)

Bir ürün; **parçalar** (ayrı kesilen deriler), her parçada bir **panel ağacı** (kök panel + kenarlarına
menteşeyle bağlı çocuk paneller, kat açısı ve sırasıyla), **monte parçalar** (perçin/vida/çıtçıtla bağlanan),
**özellikler** (kilit yarığı, çıtçıt, perçin, şikago vidası, yarık, oval yuva, delik, pencere, logo alanı) ve
**içeriklerden** (kart, banknot, anahtar) oluşur. Ölçüler değişkenli ifadeler olabilir: `"kart_g + 2*bosluk"`.
Ayrıntılar: [`sablon/bilgi/tasarim_dili.md`](sablon/bilgi/tasarim_dili.md). Doğrulanmış örnekler (`sablon ornekler`):
dil-yarık kilitli kartlık, kapaklı çıtçıtlı kartlık, şikago vidalı kartlık, dil kilitli kapaklı (metal parçasız) kartlık,
kanat kilitli dikey kartlık. Bu örnekler Claude'a da biçim örneği olarak verilir.

Motorun "kafada kurduğu" şeyler:

- **Gerçek kıvrım**: deri keskin katlanmaz; her kat iç yarıçapı ≈0.8·t olan bir kıvrımdır, kat payı
  `radyan(|açı|)·(r + t/2)` olarak kalıba eklenir.
- **Katlanınca hizalama**: çıtçıtın erkek parçası, kilit yarığı ve vida/perçin delikleri, katlanınca
  karşısına gelen panelde otomatik konumlanır.
- **Kilit kafası yarıktan geçer**: 3B modelde ve kontrollerde kafa hedef panelin öbür yüzüne geçer;
  kartlar kafaların üstüne oturur (körük buna göre hesaplanmalı — motor eksikse yakalar).
- **Çarpışma**: bitmiş üründe hiçbir panel diğerinin içinden geçemez; kart hacmi hiçbir panele çarpamaz.
- **Montaj simülasyonu**: her kat, sırasıyla adım adım katlanır; bir panelin diğerinin içinden geçmek zorunda
  kaldığı (yapılamayan) sıralar hata verir.
- **Temas**: çıtçıtlı kapak karşı panele oturmalı; vida/perçin katları birbirine değmeli.
- **Montaj sırası**: kenarlar katlamadan önce bitirilir, çıtçıtlar düzken çakılır, vidalar katlar oturunca takılır.

## Kendi PDF'lerinizden öğrenme

`sablon ogren dosya.pdf` PDF'i Claude'a okutur; ölçü/pay kuralları, teknikler, tasarım motifleri
ve talimat üslubunu `sablon/bilgi/kullanici/` altına yazar. Bu dosyalar sonraki tüm fikir, düzeltme
ve incelemelerde bilgi bankasına eklenir. Başkalarının tasarımları birebir kopyalanmaz; genel
dersler çıkarılır.

## Testler

```bash
pytest
```

Testler kesim hatlarının kapalı olduğunu, örneklerin dikişsiz ve deri olduğunu, katlanınca çıtçıt/kilit/vida
karşılıklarının üst üste geldiğini, bilerek bozulmuş tasarımlarda (kısa sırt, ince körük, değmeyen vida katları,
dar kilit kafası, boşluğa düşen çıtçıt, açınım çakışması) hatanın yakalandığını, PDF ölçeğinin 1:1 olduğunu ve
Claude akışının (sahte istemciyle) doğrulama + onarım döngüsünü sınar.

## Gerçekçi sınırlar

- Paneller dikdörtgen tabanlıdır (köşe yuvarlatma, şev, kavis/sivri/oyuk/yarım daire uçlarla). Serbest eğrili,
  kalıplanmış (ıslak şekillendirilmiş) formlar henüz yok.
- 3B görselde deri levha + yuvarlak kıvrım olarak gösterilir; kart yığınının deriyi esnetmesi yaklaşık temsil edilir.
- Deri doğal bir malzemedir: satıştan önce **mutlaka bir fiziksel prototip** yapın.
- İnteraktif 3B dosyası three.js'i internetten (jsDelivr) yükler.

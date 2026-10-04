# Şablon — yaratıcı, mm hassasiyetli kalıp tasarım aracı

Etsy'de satılacak PDF kalıplar (deri kartlık, cüzdan, kılıf, karton kutu…) için:
**tarif → birbirinden farklı tasarım fikirleri → milimetre hassasiyetinde kalıp →
3B ön izleme → görselli yapım kitapçığı.**

```
"kapaklı, çıtçıtlı kartlık"                              "kapak biraz kısa olmuş"
        │                                                          │
        ▼                                                          ▼
  Claude: N farklı tasarım ──► Tasarım dili (JSON) ◄── Claude: en küçük tutarlı değişiklik
  (her seferinde farklı ilham        │
   kıvılcımları + bilgi bankası)     ▼
                     Katlama-farkındalıklı motor (deterministik, mm)
                     · paneller + menteşeler + kat payı
                     · 3B katlama → çıtçıt/dikiş/yarık karşılıkları otomatik hizalanır
                     · malzemeye duyarlı kontroller (kart sığıyor mu, kapak kapanıyor mu…)
                                     │  hata varsa Claude'a geri → onarım
                                     ▼
   PDF kitapçık (A4 + Letter + tam boy) · SVG · DXF · interaktif 3B (HTML) · ürün görselleri (PNG)
```

## Neden yapay zekâ doğrudan çizmiyor?

Dil modelleri koordinat üretirken milimetre hatası yapabilir. Bu yüzden Claude **tasarlar**
(hangi paneller, hangi kenardan kaç derece katlanır, çıtçıt nereye, cep nereye dikilir),
geometriyi ise motor **hesaplar**. Claude'un yaratıcılığı ile motorun hassasiyeti birleşir:
her tasarım derlenir, kontrol edilir; hata varsa bulgular Claude'a geri verilip onarılır.

## Kurulum

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...      # fikir / duzelt / incele / ogren komutları için
```

## Kullanım

```bash
# 1) Fikir üret (her çalıştırmada farklı ilham; aynı klasördekileri tekrarlamaz)
sablon fikir "kapaklı, çıtçıtlı kartlık" -n 5 --malzeme crazy_horse
#    → fikirler/01_....json ... + fikirler/koleksiyon.pdf (3B görselli karşılaştırma)

# 2) Beğendiğini düzelt
sablon duzelt fikirler/03_zarf_kartlik.json "kapak biraz kısa, çıtçıt daha aşağıda olsun"
sablon ayarla fikirler/03_zarf_kartlik.json kart_adet=8 kapak.yukseklik="H*0.6"
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
| `*_A4.pdf`, `*_Letter.pdf` | Satılacak kitapçık: kapakta 3B ürün görseli ve özet (ölçü, malzeme, zorluk, süre); ölçek testi; çizgi lejantı; sayfa birleştirme haritası; **malzeme listesi** (deri dm², ip boyu, çıtçıt…); **alet listesi**; **görselli yapım aşamaları**; tasarım kontrolleri; ◆ hizalama işaretli 1:1 kalıp sayfaları |
| `*_tam_boy.pdf` | Tek sayfada kalıbın tamamı (plotter / matbaa / lazer) |
| `*.svg` / `*.dxf` | 1:1 mm, katmanlı (kesim, kat, dikiş, delik…) — Cricut, lazer, CNC |
| `*_3B.html` | Tarayıcıda döndürülebilen 3B model; kaydırıcıyla açınım ↔ bitmiş ürün katlama animasyonu, adım adım montaj |
| `*_urun.png`, `*_arka.png`, `*_yari_acik.png`, `*_acinim.png` | Etsy listesi için ürün görselleri |

## Malzemeler

`vaketa` (bitkisel tabaklı, kalıplanır, perdahlanır), `crazy_horse` (yağlı-mumlu pull-up,
yumuşak; nemlendirilmez, kenar boyası), `krom_nappa`, `karton`. Malzeme seçimi kontrolleri
(ör. crazy horse'ta dikişsiz kilit zayıf → takviye), katlama/kenar/yapıştırma talimatlarını ve
3B rengini değiştirir. Değerler `sablon/materials.py` içinde düzenlenebilir.

## Tasarım dili (kısaca)

Bir ürün; **parçalar** (ayrı kesilen deriler), her parçada bir **panel ağacı** (kök panel +
kenarlarına menteşeyle bağlı çocuk paneller, kat açısı ve sırasıyla), **monte parçalar**
(cep vb.: hangi panele, hangi yüze, hangi kenarlardan dikildiği), **özellikler** (çıtçıt,
mıknatıs, dikiş, kilit yarığı, perçin, kayış yuvası, pencere, logo alanı) ve **içeriklerden**
(kart, banknot) oluşur. Ölçüler değişkenli ifadeler olabilir: `"kart_g + S + 2 + 2*e"`.
Ayrıntılar: [`sablon/bilgi/tasarim_dili.md`](sablon/bilgi/tasarim_dili.md), örnekler: `ornekler/`.

Motorun "kafada kurduğu" şeyler:

- **Kat payı**: her menteşeye `radyan(|açı|)·t/2` eklenir; panel ölçüleri bitmiş ölçüdür.
- **Katlanınca hizalama**: çıtçıtın erkek parçası, katlanınca karşısına gelen panelde otomatik
  konumlanır; dikiş delikleri üst üste gelen katlarda birebir aynı noktaya düşer; dikişsiz kilidin
  yarığı dilin geçtiği yere kesilir.
- **Ortak delik ızgarası**: kademeli ceplerde delikler gövdede ortak noktalara düşer; düşmezse
  "şu cebi 1.5 mm kısaltın" gibi somut öneri verir.
- **Hacim/çevre kuralı**: dikişli cebin iç genişliği ≥ kart + yığın kalınlığı + 1 mm; sırtı olmayan
  kapak dolu hâlde kapanmaz; çıtçıt boşluğa düşüyorsa hata.
- **Montaj sırası**: düzken yapılabilecekler (çıtçıt, cep dikişi) önce, katlama gerektiren dikişler
  katlamadan sonra.

## Kendi PDF'lerinizden öğrenme

`sablon ogren dosya.pdf` PDF'i Claude'a okutur; ölçü/pay kuralları, teknikler, tasarım motifleri
ve talimat üslubunu `sablon/bilgi/kullanici/` altına yazar. Bu dosyalar sonraki tüm fikir, düzeltme
ve incelemelerde bilgi bankasına eklenir. Başkalarının tasarımları birebir kopyalanmaz; genel
dersler çıkarılır.

## Testler

```bash
pytest
```

Testler kesim hatlarının kapalı olduğunu, katlanınca çıtçıt/dikiş karşılıklarının üst üste
geldiğini, kademeli cep deliklerinin ortak olduğunu, PDF ölçeğinin 1:1 olduğunu ve Claude
akışının (sahte istemciyle) doğrulama + onarım döngüsünü sınar.

## Gerçekçi sınırlar

- Paneller dikdörtgen tabanlıdır (köşe yuvarlatma, şev, kavis/sivri/oyuk/yarım daire uçlarla).
  Serbest eğrili 3B formlar (ör. kalıplanmış bombeli çanta) henüz yok.
- 3B görsel, deriyi düz levha olarak gösterir; kabarma ve esneme yaklaşık temsil edilir.
- Deri doğal bir malzemedir: satıştan önce **mutlaka bir fiziksel prototip** yapın.
- İnteraktif 3B dosyası three.js'i internetten (jsDelivr) yükler.

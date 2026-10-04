# Tasarım dili (DSL) kılavuzu — DİKİŞSİZ DERİ ÜRÜNLER

Ürünü JSON tasarım olarak tanımlarsın; motor bunu mm hassasiyetinde açınım kalıbına, 3B modele,
çarpışma/montaj simülasyonuna, kontrollere ve yapım talimatına çevirir. Geometri çizmezsin — paneller,
menteşeler ve özellikler tanımlarsın. Tüm ölçüler mm, açılar derece. Her alan zorunludur; kullanılmayan
metin alanına "", listeye [] yaz.

TÜM ÜRÜNLER DİKİŞSİZDİR. Dikiş ve yapıştırıcı yoktur. Birleştirme yalnızca şunlarla yapılır:
katlama, dil-yarık kilidi (kilit_yarigi + yariktan_gecer kafa), çıtçıt, çift başlı perçin, şikago vidası,
içeriğin geçirildiği yarıklar. Malzeme yalnızca deridir: vaketa veya crazy_horse. Kartlık ve cüzdanlarda kalınlık 1.2–1.8 mm
(tipik 1.4–1.6 mm); 1.8 mm üstü hata sayılır.

## Değişkenler ve ifadeler
- Ölçü alanları sayı ya da ifade içeren metindir: "kart_g + 2*bosluk".
- Hazır değişkenler: t (deri kalınlığı), kart_g = 85.6, kart_y = 53.98, kart_k = 0.76 (tek kart kalınlığı).
- `degiskenler` sırayla hesaplanır. Fonksiyonlar: min, max, round, abs, sqrt, ceil, floor, sin/cos/tan (derece).
- Anahtar ölçüleri (kart adedi, yığın kalınlığı S, genişlik W, yükseklikler) değişkene bağla ki düzeltmeler yayılsın.

## Parça ve panel
- Bir `parca` tek deriden kesilen bir parçadır; panellerden oluşan bir ağaçtır, tam olarak bir kök panel olur.
- Kök panel yerel koordinatı: sol alt (0,0), x sağa, y yukarı. +z'ye bakan yüz derinin İÇ (süet) yüzüdür.
- Kenar adları: alt (y=0), ust (y=yukseklik), sol (x=0), sag (x=genislik).
- Çocuk panel ebeveynin bir kenarına menteşeyle bağlanır: çocuğun `alt`ı menteşedir, `ust`u serbest uçtur,
  `genislik` menteşe boyunca, `yukseklik` dışa doğrudur. Çocuğun x'i: menteşede durup serbest uca bakarken
  soldan sağa artar. Çocuk kenarın ortasına ortalanır; `ofset` ebeveynin +x (yatay kenar) / +y (dikey kenar)
  yönünde kaydırır. Çocuk kenardan geniş olabilir (kilit kafası).
- Çocuğun `alt`ı zaten menteşedir; oraya başka panel bağlanamaz.
- `aci`: + vadi (süet yüzler birbirine yaklaşır), − dağ. 180 = ebeveynin üzerine yatar, 90 = duvar, 0 = düz devam.
- Deri keskin katlanmaz: motor her kata iç yarıçapı t/2 olan kıvrım ve kat payı ekler. Panel ölçüleri bitmiş
  ölçülerdir. İki 90° kat arasındaki körük/duvar, kıvrımlar nedeniyle yaklaşık t kadar ek hacim kazanır.
- `kat_sirasi`: montajda katlanma sırası (1,2,3…). Aynı anda katlananlar aynı numara. Duvar ve ona bağlı dil
  boynu genellikle AYNI adımda katlanır (yoksa dil sallanır). Kilit kafasının kat sırası "kilitleme" adımıdır.
- `koseler`: menteşe tarafı köşeleri (sol_alt, sag_alt) çocuk panellerde 0.
- `daralma`: serbest uçta iki yandan içe çekilme (yamuk); daralan panelin yanına panel bağlanamaz.
- Profiller (ust, sol, sag; panel bağlı kenarda olmaz): duz; kavis (dışa bombe, olcu = sehim);
  sivri (zarf ucu, olcu = derinlik); oyuk (ortada başparmak oyuğu, olcu = yarıçap); yuvarlak (yarım daire uç).
- Açınımda bir parçanın panelleri ÜST ÜSTE BİNEMEZ.

## Dikişsiz bağlantılar
### Dil-yarık kilidi (en güçlü dikişsiz bağlantı)
- Bir duvarın serbest ucuna bağlı DİL BOYNU paneli (genişlik ≥ max(8, 5t), aci 90 → hedef panelin dış yüzüne yatar),
  boynun ucuna bağlı KAFA paneli: aci "0", `yariktan_gecer`: true, genislik = boyun + t + (3–5) (yarıktan ≥2 mm,
  crazy horse'ta ≥3 mm geniş), yukseklik 8–10, uç köşeleri yuvarlak.
- Boyun panelinde `kilit_yarigi`: x "-t/2", y = boyun yüksekliği, genislik "boyun + t", aci "0", hedefler [hedef panel].
  Yarık yalnızca hedef panelde kesilir; hedefte kenara ≥ max(5, 3t) mm uzak olmalı.
- Duvar yüksekliği: dilin hedef panelin dış yüzüne oturması için duvar = (iç hacim) + t.
### Çıtçıt
- Kaynak (kapak) panelde merkez (x,y), boyut mini|L20|L24. Karşılığı katlanınca otomatik bulunur.
- Kapak, karşı panelin dış yüzüne TEMAS etmeli (boşluk ≤ 2.5 mm): kapak sırtı yüksekliği ≈ karşı panelin
  dış yüzünün yüksekliği (ör. iç hacim + t). Şapka kenara ≥ yarıçap + 2 mm uzak; kat çizgisine yakın olmasın.
### Perçin / şikago vidası
- Bir panelde (x,y) + hedefler: katlanınca ÜST ÜSTE GELEN ve BİRBİRİNE DEĞEN katları birleştirir.
  Katlar arasında boşluk olmamalı (motor kontrol eder). Toplam kalınlık: perçin 2–6 mm, vida 3–7 mm.
  Kenara ≥ baş yarıçapı + 1.5 mm (perçin baş Ø8, vida baş Ø10).
### Yarıklar
- `yarik`: kartın ya da bir şeridin geçtiği düz kesik; uçlarına motor yırtılma önleyici delik koyar.
- `oval_delik`: kayış/şerit yuvası (genislik × yukseklik). Şerit/kapak dilini oval yuvaya geçirme de bir kilittir.

## Monte parça
- Ayrı kesilen parça, başka bir panele (ana_panel, x, y, yuz ic/dis) yerleştirilir ve PERÇİN/VİDA/ÇITÇIT ile en az
  iki noktadan bağlanır (motor bağlantısız parçayı hata sayar).

## İçerik (`icerikler`)
- tip kart|banknot|anahtar|ozel, adet, panel (içeriğin oturduğu panel). Motor içerik hacminin hiçbir panele
  çarpmadığını, örtüldüğünü ve çıkarılabildiğini kontrol eder. Kart yığını S = adet·kart_k (+0.6 oynama).

## Motorun hata saydığı şeyler (bunları baştan önle)
1. Katlı hâlde iki panelin birbirinin içinden geçmesi.
2. Montaj sırasında (kat_sirasi ile katlanırken) bir panelin diğerinin içinden geçmek zorunda kalması.
3. İçeriğin (kartlar) bir panele çarpması → körük/duvar/sırt S kadar olmalı.
4. Çıtçıt / kilit yarığının katlanınca boşluğa düşmesi; kilit kafasının yarıktan dar olması.
5. Perçin/vida katlarının birbirine değmemesi.
6. Açınımda panellerin çakışması.

## Çekme şeridi (pull-up / pull-tab mekanizması)
Şerit çekilince kartlar yukarı çıkar. Doğrulanmış kuruluş (örnek: cekme_seritli_kartlik.json):
- Ayrı bir PARÇA (ince deri, `kalinlik` "1.0") olarak ön panelin İÇ yüzüne monte edilir (`montaj.ana_panel` = ön
  panel, `yuz` "ic"), alt alta İKİ perçinle ön panele bağlanır (hedefler: ön panel).
- Şeridin kök paneli ön panel boyunca aşağı iner; `alt` kenarına bağlı ikinci panel `aci` "180" ile kartların
  ALTINDAN U çizip arka panelin iç yüzüne yatar ve arka panelin üstünden tutma ucu olarak çıkar
  (yükseklik = arka panel + 15–20 mm, ucu `yuvarlak` profil).
- U kıvrımının yarıçapını elle ver: `kivrim_yaricapi` = ru = (g + 2*kr − 2*ts)/2 (kr: hazır değişken, deriye göre
  kıvrım yarıçapı; ts: şerit kalınlığı; g: alt körük). Montaj y'si ≥ ru + ts + 1.5 olmalı ki U gövdeden taşmasın.
- Körük, kartlara ek olarak şeridin iki kolunu (ve içeri giren kilit kafalarını) taşımalı: g = S + t + 2*ts.
- Motor çekince kartların kaç mm yükseleceğini ve tutma ucunun yeterliliğini raporlar (≥15 mm görünmeli).

### Kapaklı çekme şeridi (şerit yuvası) — örnek: tek_merkez_kilitli_cek_cikar.json
Kapak arka panelin üstünden kartları örtüyorsa şerit ucu üstten çıkamaz (sırtla çakışır). Doğru kuruluş:
- Şerit kökü ön panelin içinde ALÇAKTA kalır (kısa kök, iki perçin); kapağın merkez kilit kafası kökün ÜSTÜNE düşer
  (kafa ile kök aynı yüzde, üst üste binmemeli). Kilit yarığı yüksekliği ≈ montaj y + kök boyu + 11.
- Şeridin dönüş kolu arka panelin içinde yukarı çıkar ve arka paneldeki bir ŞERİT YUVASINDAN dışarı geçer:
  kolun üst kenarına `kilit_yarigi` (genislik = şerit eni + ts, hedefler: arka panel) ve kolun `ust` kenarına
  `aci` "0", `yariktan_gecer` true bir "tutma ucu" paneli (genişliği şerit enini GEÇMEZ; kilit değil kayar geçiş).
- Yuva arka panelin üst kenarından ~8 mm aşağıda; tutma ucu arka panelin üstünden ≥12 mm taşacak boyda (~26 mm).
- Arka panel kartlardan 2–3 mm uzun; kartların görünmesi için şerit kökünün üst perçini yeterince yüksek olmalı.
- Kapaklı tasarımlarda kapağın kenarına profil verilecekse o kenara panel bağlanmamalı (profil yalnız serbest kenarda).

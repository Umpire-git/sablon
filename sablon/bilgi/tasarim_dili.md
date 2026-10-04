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


## İnce, düz katlanan kuruluş (tercih edilen; referans kalıpların dili)
Körük/kutu yerine düz katlanan, 1.0–1.2 mm sert deriden ince ürünler daha çok satar. Doğrulanmış örnekler:
hazir_modeller/01_origami_kemer.json, 02_para_kemerli_cakil.json, 03_ok_uclu_kapak.json.
- Ön panel arka panelin `alt` kenarına `aci` "180" ve `kivrim_yaricapi` "g/2" ile bağlanır: alt kenar yuvarlak bir
  kat olur, körük gerekmez. g = kart yığını + 2*ts (şerit) + t (içeri giren kulak kafası).
- Yan kapama: ön panelin yanlarından `aci` 90, yüksekliği "g" olan dar duvar → `aci` 90 kulak boynu (arka yüzün
  dışına yatar) → `yariktan_gecer` kanca kafa (profil `sivri` 3) arka paneldeki kilit_yarigi'na girer. Metal yok.
- Kenar profilleri: `dalga` (ortada yumuşak başparmak çukuru), `kavis` eksi ölçü = içbükey kenar (ok uçlu kapak için
  `daralma` + yanlarda kavis -3 + uçta kavis +6).
- `kavisli_yarik`: yay biçimli kesik (hilal/mercek süsleri); uçlarına otomatik yırtılma deliği konur.
- Parçaya `renk` verilebilir: kontrast renkli çekme şeridi (ör. #3a2418) ürünün imzası olur.

### Perçinsiz (örgülü) çekme şeridi
- Şerit parçası taşıyıcı panelin DIŞ yüzüne monte edilir (`yuz` "dis"); kök panel ("kemer") dışarıda görünen kısımdır.
- Kemerin `ust` kenarına `yariktan_gecer` T başı (eni şerit + 6, kemerin üst yarığından içeri girip kilitlenir),
  `alt` kenarına `yariktan_gecer`, `aci` 0 içeri dalan koşu (eni şerit eni; kilit değil kayar geçiş) bağlanır.
  Kemerin y=0 ve y=boyu konumlarına iki kilit_yarigi (genislik sw + ts, hedef taşıyıcı panel).
- Koşunun ucuna `aci` 180, `kivrim_yaricapi` ru = (g − 2*ts)/2 kol bağlanır; kol karşı panelin içinden yükselir.
- Dayanak kemerin ALT yarığıdır: kalkış ≈ alt yarık y − 6 − kart y. Görünürlük ≥ 15 mm için alt yarık ~25 mm'de.
- Kemer arka yüzdeyse altına katlı banknot konur (içerik paneli = kemer): şerit çekildikçe kemer gerilip parayı tutar.
- Kapaklı modelde kapak çıtçıtı önde görünen kemere oturur (içeride orada şerit yoktur); kol arka yüzdeki şerit
  yuvasından dışarı çıkar (bkz. kapaklı çekme şeridi).

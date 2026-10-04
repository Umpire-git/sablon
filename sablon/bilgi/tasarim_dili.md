# Tasarım dili (DSL) kılavuzu

Ürünü JSON tasarım olarak tanımlarsın; motor bunu mm hassasiyetinde açınım kalıbına, 3B modele,
kontrollere ve yapım talimatına çevirir. Geometri çizmezsin — paneller, menteşeler ve özellikler
tanımlarsın. Tüm ölçüler mm, açılar derece. Her alan zorunludur; kullanılmayan metin alanına "" ,
listeye [] yaz.

## Değişkenler ve ifadeler
- Ölçü alanları sayı ya da ifade içeren metindir: "kart_g + 2*bosluk + t".
- Hazır değişkenler: t (tasarım kalınlığı), kart_g = 85.6, kart_y = 53.98, kart_k = 0.76 (tek kart kalınlığı).
- `degiskenler` sırayla hesaplanır; önceki değişkenleri kullanabilir. Fonksiyonlar: min, max, round, abs,
  sqrt, ceil, floor, sin/cos/tan (derece).
- Anahtar ölçüleri (kart adedi, boşluk, yığın kalınlığı, ana genişlik/yükseklik) değişkene bağla ki
  "6 kartlık yap" gibi düzeltmeler tüm bağlı ölçülere yayılsın.

## Parça ve panel
- Bir `parca` tek deriden kesilen bir parçadır; panellerden oluşan bir ağaçtır. Tam olarak bir kök panel
  (ebeveyn "") olur.
- Panel = taban dikdörtgeni: `genislik` (x) × `yukseklik` (y).
- Kök panel yerel koordinatı: sol alt (0,0), x sağa, y yukarı. Çizimde görünen ve +z'ye bakan yüz
  derinin İÇ (süet) yüzüdür.
- Kenar adları her panelde: alt (y=0), ust (y=yukseklik), sol (x=0), sag (x=genislik).
- Çocuk panel, ebeveynin bir kenarına (`kenar`) menteşeyle bağlanır:
  - Çocuğun `alt` kenarı menteşedir; `ust` serbest ucudur; `genislik` menteşe boyuncadır,
    `yukseklik` menteşeden dışa doğrudur.
  - Çocuğun x ekseni: menteşede durup dışa (serbest uca) bakarken soldan sağa artar. Yani çocuğun `sol`u
    o bakışta solda kalır.
  - Çocuk, kenarın ortasına ortalanır; `ofset` ebeveynin +x (yatay kenarlar) veya +y (dikey kenarlar)
    yönünde kaydırır.
  - Alt-olmayan bir çocuğun `alt` kenarı zaten menteşe olduğundan oraya başka panel bağlanamaz.
  - Çocuk, kenardan daha geniş olabilir (ör. kilit dili kafası boyundan geniş); örtüşmeyen kısım kesim olur.
- `aci`: bitmiş üründeki kat açısı. + vadi (iç/süet yüzler birbirine yaklaşır), − dağ. 180 = ebeveynin
  üzerine yatar, 90 = duvar olur, 0 = düz devam (kat yok).
- Panel ölçüleri BİTMİŞ ölçülerdir (iç yüzde kat çizgisinden). Motor kat payını
  (radyan(|açı|)·t/2) kendisi ekler.
- `kat_sirasi`: montajda katlanma sırası (1,2,3...). Aynı anda katlananlar aynı numara.
- `koseler`: sol_alt, sag_alt, sag_ust, sol_ust yarıçapları. Menteşe tarafındaki köşeler (sol_alt, sag_alt)
  çocuk panellerde 0 olmalı.
- `daralma`: serbest uçta her iki yandan içe çekilme (yamuk). Daralan panelin yanına panel bağlanamaz.
- Profiller (yalnızca ust, sol, sag; panel bağlı kenarda profil olmaz):
  - duz; kavis (dışa bombe, olcu = sehim); sivri (zarf ucu, olcu = uç derinliği);
    oyuk (ortada içe yarım daire başparmak oyuğu, olcu = yarıçap); yuvarlak (tam yarım daire uç).
- Açınımda (düz serilmiş hâlde) bir parçanın panelleri ÜST ÜSTE BİNEMEZ. Binecekse ayrı parça yap
  (monte parça).

## Kalınlık ve hacim (çok önemli)
- 180° kat, kalınlığı ancak iki deri kadar olan bir "sandviç" için uygundur (ör. yanları dikilen cep).
- Arasına içerik (kart yığını S = adet·kart_k) girecek bir kapak/gövde için SIRT/KÖRÜK paneli kullan:
  sırt yüksekliği ≈ S + 2t (+1), iki tane 90° kat.
- Dikişli düz cep için çevre kuralı: dikişler arası iç genişlik ≥ içerik genişliği + yığın kalınlığı + 1 mm.
  Yani gövde genişliği ≈ kart_g + S + 2 + 2·kenar_payi.
- Yan duvarlı (körüklü) yapılarda duvar yüksekliği ≥ S.

## Monte parça (cep, astar, takviye)
- `montaj.ana_panel`: üzerine monte edildiği panel; `x`,`y`: bu parçanın kök panelinin sol-alt köşesinin ana
  panel yerelindeki konumu (bitmiş ölçülerle); `yuz`: "ic" veya "dis"; `dikis_kenarlari`: ana panele dikilen
  kenarlar (ör. ["sol","alt","sag"]). Motor dikiş deliklerini HER İKİ parçaya birebir aynı konumda koyar.
- Aynı yüze sırayla monte edilen parçalar üst üste biner (kademeli cepler: önce arka cep, sonra öndeki).

## Özellikler (`ozellikler`)
Ortak alanlar: tip, panel, x, y, genislik, yukseklik, aci, boyut, kenarlar, kenar_payi, hedefler, etiket.
Kullanılmayanlar "" veya [].
- citcit: kaynak panelde merkez (x,y), boyut mini|L20|L24. Karşı parça KATLANINCA otomatik bulunur
  (hedefler boşsa en yakın paralel panel). Şapka kenara ≥ şapka yarıçapı + 2 mm uzak olmalı; kapak, karşı
  panelin üzerine en az ~20 mm binmeli.
- miknatis: citcit gibi, boyut = çap (ör. "12"). İki kat arasına gizlenir.
- dikis: `kenarlar` boyunca, kenardan `kenar_payi` içeride. Katlanınca üst üste gelen panellere aynı
  delikleri koymak için `hedefler` (ör. alttan katlanan ön cebin yanları → hedefler ["arka"]).
- dikis_cizgisi: (x,y)'den `aci` yönünde `genislik` uzunluğunda düz dikiş (ör. cebi ikiye bölen dikiş).
- kilit_yarigi: dikişsiz kilit. Kaynak panelde (genelde dil boynu) tanımlanır; yarık yalnızca katlanınca
  denk geldiği HEDEF panelde kesilir. (x,y) başlangıç, `genislik` = boyun + t, `aci` 0 (x yönü).
  Kilit kafası (boynun ucuna bağlı, aci 0, genişliği boyun + 5) yarıktan ≥ 2 mm geniş olmalı.
- yarik: panelde düz kesik (uçlarına otomatik yırtılma önleyici delik).
- percin / delik: (x,y), boyut = çap.
- oval_delik: kayış/kemer yuvası (genislik × yukseklik, uçları yuvarlak). pencere: köşesi yuvarlak iç kesim.
- logo_alani: damga/gravür kılavuz dikdörtgeni.

## İçerik (`icerikler`)
Kontroller ve 3B için ürünün ne taşıdığını belirt: tip kart|banknot|ozel, adet, panel.
- İçerik, `panel`in iç yüzüne oturur. Panel bir monte cebin kök paneliyse içerik o cebin İÇİNDEDİR.
- x,y boşsa ortalanır/alta oturtulur.

## Kontrol listesi (tasarlarken kendine sor)
1. Kartlar sığıyor mu (çevre kuralı / duvar yüksekliği)? Dolu hâlde kapak kapanıyor mu (sırt)?
2. Kart nasıl çıkıyor (cep ağzı alçak mı, başparmak oyuğu var mı)?
3. Çıtçıt katlanınca bir panele denk geliyor mu, kenardan yeterince uzak mı?
4. Açınımda paneller çakışıyor mu? Çakışıyorsa ayrı parça.
5. Malzemeye uygun mu (crazy horse yumuşak: dikişsiz kilit zayıf; vaketa: kalıplanır, sert)?

## Dikiş deliklerinin ortaklığı (endüstriyel kural)
- Aynı kenara dikilen kademeli parçalarda (üst üste cepler) delikler gövdede ORTAK olmalı, yoksa yan
  yana iki delik deriyi yırtar. Motor uç kenarlarda delikleri sabit zımba adımıyla dizer; bu yüzden
  her monte parçanın yan dikiş boyu = yükseklik − kenar_payi − köşe_yarıçapı (köşe > kenar payıysa)
  zımba adımının (p) katı olmalı. Pratik formül: yukseklik = r + e + n*p (r köşe, e kenar payı).

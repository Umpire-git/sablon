# EBYS Görev Takip — Kurulum

Kalite Koordinatörlüğü için: EBYS'ye sevk edilen yazıları ve hocanın notlarını okur, notta adı
geçen kişiye görev olarak atar, takip panelinde gösterir. Ayrıca yazıyı **mevcut gelen-giden evrak
tablonuza** satır olarak ekler ve PDF'i Drive'da **İş ve İşlemler / Gelen Yazı** ya da
**Giden Yazı** klasörüne koyar.

**Aynı yazı iki kez işlenmez:**
- Sistem işlediği her evrak numarasını kendi **Aktarım Kaydı** sekmesine yazar. Kayıttaki bir evrak
  tablolara bir daha yazılmaz, satırı sonradan silseniz bile.
- Evrak no ya da sayı evrak tablonuzda zaten varsa (örneğin elle girilmişse) satır eklenmez.
- Sistem dolu hiçbir hücrenin, formülün ya da satırın üstüne yazmaz. Yalnızca son kaydın altındaki
  boş satıra yazar.
- Drive'da aynı evrak numarasıyla başlayan bir dosya varsa PDF yeniden yüklenmez.

```
EBYS (tarayıcıda açık)  ──►  Tampermonkey betiği  ──►  Google Sheets + Apps Script  ──►  Takip paneli
 görev listesi + notlar       yeni görevleri okur        Görevler / Personel / Ayarlar      herkes kendi işini görür
                              PDF'i indirir              PDF → Drive klasörü               "Tamamlandı" → PDF hedef klasöre
```

Kurulum tek seferlik, yaklaşık 20 dakika. Kurulumu bir kişi yapar (Sheets'in sahibi). Diğer kişiler
sadece paneli kullanır. Betiği EBYS'ye görev düşen kişinin bilgisayarına kurmak yeterli.

---

## 1. Google Sheets ve kod (bir kez, kurumsal hesapla)

1. Kurumsal Google hesabınızla <https://sheets.new> adresinden yeni bir tablo açın. Adını
   **"EBYS Görev Takip"** koyun. Bu ayrı dosyadır: mevcut evrak tablonuza **hiç sekme eklenmez**,
   oraya yalnızca satır yazılır. Bu dosyayı açan hesabın evrak tablonuzda **düzenleme yetkisi**
   olmalıdır.
2. Menüden **Uzantılar → Apps Script**'i açın.
3. Soldaki `Kod.gs` dosyasının içini silin ve bu klasördeki `apps-script/Kod.gs` dosyasının
   tamamını yapıştırın.
4. Soldaki **+ → HTML** ile yeni bir dosya ekleyin, adını tam olarak **`Panel`** yazın.
   `apps-script/Panel.html` içeriğini yapıştırın.
5. Kaydedin (💾). Sol menüden **Proje ayarları**'nda saat dilimini **(GMT+03:00) İstanbul** yapın.
6. Tabloya dönüp sayfayı yenileyin. Menüde **EBYS Takip → Kurulum / onarım**'ı çalıştırın.
   Google izin isteyecek: hesabınızı seçin, **Gelişmiş → (güvenli değil) sayfasına git → İzin ver**.
   Bu uyarı kodu sizin yazdığınız için çıkar.
   Bunun sonunda **Görevler**, **Personel** ve **Ayarlar** sayfaları oluşur.

## 2. Personel ve Drive klasörleri

**Personel** sayfasına 6 kişiyi yazın:

| Ad Soyad | E-posta | Notta geçen adlar (virgülle) | Rol |
|---|---|---|---|
| Ali DAĞLI | ali.dagli@usak.edu.tr | Ali | Personel |
| Zeynep … | …@usak.edu.tr | Zeynep, Zeynep Hanım | Personel |
| (hoca) | …@usak.edu.tr | | Yönetici |
| Kalite Koordinatörlüğü | kalite@usak.edu.tr | | Ortak |

- Hocanın notlarda yazdığı adları "Notta geçen adlar" sütununa yazın. Ad Soyad'ın ilk kelimesi
  zaten otomatik olarak eklenir. Büyük/küçük harf ve Türkçe karakter fark etmez: "ALI" ve "ali"
  de Ali olarak tanınır.
- Birkaç kişinin kullandığı ortak bir hesap (örn. kalite@usak.edu.tr) varsa onu da **Rol = Ortak** ile
  ekleyin. Bu hesapla panele girildiğinde sağ üstte "Ben:" kutusundan kişi seçilir; seçim o tarayıcıda
  hatırlanır ve yapılan işlemler o kişi adına kaydedilir. Ortak hesap görev atanacak kişiler listesinde
  çıkmaz.
- Aynı adı taşıyan iki kişi varsa, birine farklı bir ad yazın (örn. "Ali K.") ve hocadan notlarda
  o şekilde yazmasını isteyin.

**Drive:** **"İş ve İşlemler"** adında bir klasör açın. Klasörü açınca adres çubuğunda
`…/folders/` sonrasında uzun bir kod görünür. Bu kodu **Ayarlar** sayfasında
`IS_ISLEMLER_KLASOR_ID` satırına yapıştırın. Klasörün içinde **Gelen Yazı** ve **Giden Yazı**
klasörleri yoksa sistem bunları kendisi açar. PDF'ler `[382726] MEDEK Ödemesi Hk..pdf` gibi bir
adla kaydedilir. Klasörü ekiple paylaşın.

**Evrak tablosu:** Ayarlar sayfasında şu değerler hazır gelir:
- `EVRAK_TABLO_ID`: sizin tablonuz.
- `GELEN_SEKME` = `#1192504650` (2026 GELEN YAZILAR), `GIDEN_SEKME` = `#3352743` (2026 GİDEN YAZILAR). Sekme adını da yazabilirsiniz. Yeni yılda yeni sekme açtığınızda bu iki satırı güncelleyin.

Giden yazılar başka bir sekmede tutuluyorsa `GIDEN_SEKME` satırına o sekmenin adını yazın.
Bir tür için tabloya yazma işini kapatmak isterseniz `GELEN_TABLOYA_YAZ` ya da
`GIDEN_TABLOYA_YAZ` satırını `HAYIR` yapın.

Ardından menüden **EBYS Takip → Evrak tablosu sütun eşleşmesini göster**'i çalıştırın. Sistem başlık
satırını ve hangi bilginin hangi sütuna yazılacağını gösterir, örneğin "Konu: G (Konu)". Başlıkları
kendisi tanır: Sıra No, Gelen/Giden, Tarih, Sayı, Evrak/Kayıt No, Geldiği Yer, Konu, Sorumlu,
Dosya/Link, Açıklama.

Eşleşme yanlışsa Ayarlar sayfasına yeni bir satır ekleyin, örneğin `SUTUN_KONU` | `D`. Bu satır iki sekme için de geçerlidir. Yalnızca birini değiştirmek için `SUTUN_GELEN_KONU` ya da `SUTUN_GIDEN_KONU` yazın. "Günlü evrak", "son tarih" ve "termin" sütunları tanınır ama bu sütunlara bir şey yazılmaz.
Bir alanın hiç yazılmamasını istiyorsanız değer olarak `-` yazın. Kullanılabilecek adlar:
`SUTUN_SIRA`, `SUTUN_TUR`, `SUTUN_KAYITNO`, `SUTUN_SAYI`, `SUTUN_EVRAKTARIHI`, `SUTUN_KAYITTARIHI`,
`SUTUN_YER`, `SUTUN_KONU`, `SUTUN_SORUMLU`, `SUTUN_DOSYA`, `SUTUN_ACIKLAMA`, `SUTUN_DOSYAKODU`.

## 3. Web uygulamasını yayınlama

Apps Script'te **Dağıt → Yeni dağıtım → (dişli) Web uygulaması**:

- **Açıklama:** Panel
- **Şu kullanıcı olarak yürüt:** Ben
- **Erişimi olan:** **usak.edu.tr içindeki herkes**

**Dağıt**'a basın ve çıkan `…/exec` adresini kopyalayın. Bu **panel adresi**, ekiple paylaşın ve yer
imlerine ekleyin. Panele yalnızca Personel listesindeki e-postalar girebilir.

Tarayıcı betiği için ikinci bir dağıtım oluşturun (yine **Dağıt → Yeni dağıtım**):

- **Açıklama:** Betik
- **Şu kullanıcı olarak yürüt:** Ben
- **Erişimi olan:** **Herkes**

Çıkan `…/exec` adresi **betik adresi**dir. Betik buraya gizli anahtarla yazar; anahtarı bilmeyen
biri bu adrese veri gönderemez ve panel bu adresten açılmaz.

> Kurum ayarları "Herkes" seçeneğini kapatmış olabilir. O durumda betik için de panel adresini
> kullanın. Betiğin çalıştığı tarayıcıda kurumsal Google hesabının açık olması yeterlidir.

> Kodu sonradan değiştirirseniz: **Dağıt → Dağıtımları yönet → kalem → Sürüm: Yeni sürüm → Dağıt**.
> Böylece adresler değişmez.

## 4. Tarayıcı betiği (EBYS'yi kullanan bilgisayarda)

1. Chrome ya da Edge'e **Tampermonkey** eklentisini kurun (Chrome Web Mağazası'nda "Tampermonkey").
2. Tampermonkey simgesi → **Yeni betik oluştur** seçin. Açılan şablonu silin,
   `tarayici/ebys-takip.user.js` içeriğini yapıştırıp kaydedin (Ctrl+S).
3. Chrome kullanıyorsanız: **Uzantıları yönet → Tampermonkey → Ayrıntılar** sayfasında
   **"Kullanıcı komut dosyalarına izin ver"** seçeneğini açın. Gerekiyorsa
   chrome://extensions sayfasında sağ üstteki **Geliştirici modu**'nu da açın.
4. EBYS'yi açın. Sol altta mavi bir **EBYS Takip** kutusu belirir.
5. Tampermonkey simgesi → **EBYS Görev Takip → Ayarlar** seçin ve şunları girin:
   - betik adresini,
   - gizli anahtarı (Sheets'te **EBYS Takip → Gizli anahtarı göster**),
   - otomatik gönderimi açıp açmamayı,
   - sayfanın kaç dakikada bir yenileneceğini (önerilen 15).
6. **İlk kullanımda:** listede eski görevler varsa ve bunların aktarılmasını istemiyorsanız
   Tampermonkey menüsünden **"Listede görünenleri gönderilmiş say"** komutunu seçin. Bundan sonra
   yalnızca yeni gelen görevler aktarılır.

### Nasıl çalışır?

- **Takip dosyasının sekmeleri:**
  - **Özet:** açık görev, bugün gelen, atanmamış ve bu ay tamamlanan sayıları, kişi bazında durum ve
    açık işlerin listesi (konu, hocanın notu, evrak tarihi). Sayılar her değişiklikte kendiliğinden yenilenir.
  - **Görevler:** açık işler. En yeni görev en üstte durur. Görünen sütunlar: Evrak No, Evrak Tarihi,
    Konu, Hocanın Notu, Sorumlu, Durum, Açıklama, Dosya, Eklenme.
  - **Tamamlananlar:** Durum "Tamamlandı" ya da "İptal" yapılınca görev otomatik olarak buraya taşınır.
    Tekrar "Bekliyor" ya da "Devam Ediyor" yapılırsa Görevler'e geri döner.
    **Toplu tamamlama:** Panelde görevlerin solundaki kutuları işaretleyip **"Seçilenleri tamamla"**ya
    basın ("Listedekilerin tümünü seç" de var). Tabloda ise Görevler sekmesinde satırları seçip
    **EBYS Takip → Seçili satırları tamamla**'yı kullanın ya da Durum hücrelerine toplu olarak
    "Tamamlandı" yapıştırın. Durumu panelden ya da
    doğrudan tablodan değiştirebilirsiniz.
  - Teknik sütunlar (ID, anahtar vb.) gizlidir. Uzun notlar satırı uzatmaz; notun tamamını görmek
    için hücreye tıklayın ya da paneli kullanın.
- **Bütün sayfaların taranması:** Ekrandaki sayfadaki görevlerin hepsi yeniyse betik sonraki sayfaya
  kendisi geçer. Bütün listeyi baştan sona taramak için kutudaki **"Tüm sayfaları tara"** düğmesine
  basın. Görevler 4'erli gruplar halinde gönderilir; tarama yarıda kesilirse gönderilmiş olanlar
  kaybolmaz ve bir sonraki açılışta kaldığı yerden devam edilir.
- EBYS ana sayfası yalnızca **"Kaç Günlük Görevler"** ayarındaki gün sayısı kadar geriye giden görevleri
  gösterir (en fazla 10 gün). Daha eski görevler için o ayarı en yükseğe alın.

- Görev listesi her açıldığında betik yeni görevleri bulur. Her birinin evrak sayfasını arka planda
  açıp **Notlar** bölümünü okur ve takip tablosuna gönderir. Hocanın notu "Ali: … Zeynep: …"
  biçimindeyse her kişiye ayrı görev açılır. Notta kimsenin adı geçmiyorsa görev
  **Genel / atanmamış** sekmesine düşer.
- Yeni bir yazı aynı anda **evrak tablonuza** da satır olarak eklenir. Geldiği yer ana birim düzeyinde yazılır: "… » STR. GEL. DAİ. BAŞ. » Bütçe ve Performans Program Şube Müdürlüğü" yerine "Strateji Geliştirme Daire Başkanlığı". Bunu Ayarlar sayfasındaki `YER_DUZEYI` satırıyla değiştirebilirsiniz: `SON` en alt birimi, `TAM` bütün zinciri yazar. Açılmayan bir kısaltma için Ayarlar sayfasına `KISALTMA ÖZ. BÜR.` | `Özel Kalem` gibi bir satır ekleyin. Satırda tür, evrak no,
  tarih, geldiği yer, konu, dosya kodu, sorumlu ve hocanın notu yer alır; tabloda sütunu olmayan
  bilgi yazılmaz. Sıra numarası bir önceki satırın bir fazlası olarak verilir; o hücrede formül
  varsa ona dokunulmaz.
- **Kendi yazdığınız yazılar:** İmzalanınca ana sayfaya düşen "Hazırlamış Olduğunuz Evrak Onaylanmıştır"
  satırları görev açılmadan **giden** sekmesine yazılır (Sorumlu Kişi = yazıyı hazırlayan) ve PDF'i
  Giden Yazı klasörüne konur. Betik, yazıyı hazırlayan kişinin bilgisayarında kurulu olmalıdır.
- "Gelen Evrak Bilgilerini Güncelleyiniz" görevleri **gelen** sayılır. "Kurum Dışına Gönderilmiş
  Olan Evrak…" görevleri **giden** sayılır.
- PDF, **İş ve İşlemler / Gelen Yazı** (ya da **Giden Yazı**) klasörüne gider. Linki takip
  panelinde görünür ve evrak tablosunda **sistemin eklediği satırın** boş Dosya/Link hücresine
  yazılır. Elle girilmiş satırlara dokunulmaz.
- Bir evrak sayfasını açtığınızda kutuda **"Takibe al + PDF'i Drive'a gönder"** düğmesi çıkar. Bununla
  tek bir evrakı elle de gönderebilirsiniz.
- Ana sayfa açık bırakılırsa ayarladığınız aralıkla yenilenir ve yeni gelenleri kendisi alır.

## Birimin bütün giden yazıları (Evrak Arama ile, diğer kişiler kurulum yapmadan)

Betik, EBYS'deki **Evrak Arama** sonuçlarından birimin **imzalı giden yazılarını** (kim yazmış olursa olsun)
okur: giden sekmesine yazar (Sorumlu Kişi = Oluşturan), PDF'i Giden Yazı klasörüne koyar. Betiğin tek
bir bilgisayarda kurulu olması yeterlidir.

Bir kez yapılacaklar (betiğin kurulu olduğu bilgisayarda):
1. **Evrak Arama**'yı açın ve şunları seçin:
   - **Evrakın Birimi:** Kalite Koordinatörlüğü
   - **Evrak Türü:** Kurum İçi Giden Evrak, Kurum Dışı Giden Evrak (kullandığınız diğer giden türleri de)
   - **Evrak Durumu:** Onaylandı
   - **Tarih:** 7 Gün
2. **Ara**'ya basın.
3. Arama kutusunun sağ üstündeki **Kayıtlı Aramalar** (disket simgesi) → **Aramayı Kaydet** ile aramaya
   bir ad verin, örneğin **"Takip – Giden Yazılar"**. **"Kayıtlı Arama Kısayolu Ekle"** ile kısayollarınıza
   da ekleyin.
4. Bu kayıtlı aramayı kısayoldan açın. Sol alttaki kutuda **"Bu aramayı otomatik takip araması yap"**
   düğmesine basın.

Bundan sonra EBYS ana sayfası açıkken betik **yalnızca bu kayıtlı aramayı** saatte bir arka planda
çalıştırır. Siz Evrak Arama'da istediğiniz başka aramayı yapabilirsiniz; takibi etkilemez. Hemen yaptırmak
için Tampermonkey menüsünden **"Giden yazı aramasını şimdi yap"**ı seçin. Herhangi bir arama sonucundaki
giden yazıları tek seferlik kaydetmek isterseniz kutudaki **"N giden yazıyı tabloya kaydet"** düğmesini
kullanın.

## İlgi (yazılar arası ilişki)

- Bir yazı başka bir yazıya ilgi tutuyorsa ("28.10.2026 tarihli ve 381948 sayılı yazınız") Görevler'de
  **İlgi** sütununda "381948 – konu" görünür; evrak tablosundaki satırın Açıklama'sına da "İlgi: …" yazılır.
- Bir gelen yazıya cevap olarak giden yazı imzalanınca, o gelen yazının görevinin Açıklama'sına
  **"Cevap yazıldı: 383600 (tarih)"** notu düşülür. Ayarlar'da `CEVAP_YAZILINCA_TAMAMLA` = `EVET` yaparsanız
  o görev ayrıca otomatik **Tamamlandı** olur.
- Aktarım Kaydı sekmesinde her evrakın İlgi ve Cevap bilgisi tutulur.

## Bilinmesi gerekenler

- **Okundu işareti:** Betik evrak sayfasını arka planda açtığı için EBYS o görevi "okundu" sayabilir.
  Görev EBYS'de yerinde durur, yalnızca kalın yazısı normale döner.
- **Betik yalnızca EBYS açıkken çalışır.** Bilgisayar kapalıyken gelen görevler, EBYS bir sonraki
  açılışında aktarılır.
- **Gizlilik:** Gizli ya da kişisel veri içeren evrakları Drive'a koymadan önce birim kurallarını
  kontrol edin. Drive klasörlerini yalnızca ekiple paylaşın.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Kutuda "Zaman aşımı" yazıyor | Yeni sürümde görevler küçük gruplar halinde gönderilir. Hata sürerse "Tüm sayfaları tara"ya tekrar basın; gönderilmiş olanlar tekrar yazılmaz. |
| Kutuda "Anahtar hatalı" yazıyor | Ayarlardaki anahtarı Sheets'teki ile karşılaştırın. |
| "Sunucu yanıtı okunamadı" yazıyor | Betik adresinin `/exec` ile bittiğinden ve dağıtımın "Herkes" erişiminde olduğundan emin olun. Olmuyorsa 3. adımdaki nota bakın. |
| Görev geliyor ama PDF gelmiyor | `IS_ISLEMLER_KLASOR_ID` dolu mu kontrol edin. Evrak sayfasında elle gönder düğmesini deneyin. Yine olmazsa tarayıcı konsolundaki `[EBYS Takip]` satırlarını iletin. |
| Notta adı geçen kişi bulunamadı | Personel sayfasındaki "Notta geçen adlar" sütununa o yazılışı ekleyin. Görevi panelden elle atayın. |
| Evrak tablosuna satır gelmiyor | **Aktarım Kaydı** sekmesindeki "Not" sütununa bakın, hata orada yazar. Menüden sütun eşleşmesini kontrol edin. Kurulumu yapan hesabın evrak tablosunda düzenleme yetkisi olmalı. |
| Bir evrakı bilerek yeniden yazdırmak istiyorum | O evrakın satırını **Aktarım Kaydı** sekmesinden silin. Evrak tablonuzda hâlâ varsa yine yazılmaz. |
| Panel "Panele giriş yapılamadı" diyor | Sayfada **algılanan hesap** yazıyorsa o adresi Personel sekmesine birebir yazın. "Adres iletilmedi" yazıyorsa aşağıdaki "Panel açılmıyor" bölümüne bakın. |

## Panel açılmıyor

- **"Dosyayı açamıyoruz" hatası:** Tarayıcıda birden çok Google hesabı açıktır. Adresi
  `https://script.google.com/a/macros/usak.edu.tr/s/…/exec` biçiminde kullanın ya da gizli pencerede
  yalnızca kurumsal hesapla girin.
- **"Adres iletilmedi" uyarısı:** Panelin sahibi kurumsal bir hesap değildir. Tabloyu ve kodu kurumsal
  hesapla yeniden oluşturun. Hızlı çözüm olarak Panel dağıtımında **Şu kullanıcı olarak yürüt** ayarını
  **"Web uygulamasına erişen kullanıcı"** yapın; o zaman paneli kullanacak herkesin takip tablosunda
  düzenleme yetkisi olmalı ve ilk girişte Google'ın izin ekranını onaylaması gerekir. "Betik"
  dağıtımı "Ben" olarak kalmalı.

## Siz olmadan da çalışması için

| Parça | Kime bağlı | Yapılacak |
|---|---|---|
| Takip tablosu, panel, kod | **kalite@usak.edu.tr** (ortak hesap) | Hiçbir şey. Kişiye bağlı değil. |
| Drive klasörleri (İş ve İşlemler) | Klasörün sahibi | Klasörleri **kalite@** hesabında açın ya da bir **ortak Drive**'a taşıyın. Kişisel hesapta kalırsa o kişi ayrılınca erişim sorunu çıkar. |
| Gelen-giden evrak tablosu | Tablonun sahibi | kalite@ hesabının düzenleme yetkisi olmalı. |
| EBYS'yi okuyan betik | Kurulu olduğu bilgisayar ve oradaki EBYS oturumu | 7/24 açık bir bilgisayara kurun: **linux-mint/LINUX-MINT.md**. Yedek olarak bir bilgisayara daha kurun; aynı yazı iki yerden gelse de bir kez işlenir. |

- **Hangi bilgisayarlara kurulmalı:** Hocanın görev sevk ettiği kişilerin bilgisayarlarına. Gelen görevler
  yalnızca sevk edilen kişinin EBYS ana sayfasına düşer. Giden yazılar ise Evrak Arama'dan alındığı için tek
  bilgisayar yeter; yine de yedek olarak ikinci bir bilgisayarda da kayıtlı aramayı seçin.
- **Sağlık kontrolü:** Özet sayfasının üstünde **"Son EBYS aktarımı: tarih (kim)"** yazar. Betik 24 saatten
  uzun süre çalışmazsa (pazartesi için 72 saat) iş günleri sabah 9-10 arasında **yöneticilere ve ortak hesaba**
  uyarı e-postası gider. Başka adresler de almak isterse Ayarlar'daki `UYARI_EPOSTA`'ya yazın.
- **Uyarı gelince:** Betiğin kurulu olduğu bilgisayarlardan birinde EBYS'ye girip ana sayfayı açık bırakmak
  yeterli. Birikmiş görevler kendiliğinden aktarılır, hiçbiri tekrar yazılmaz.
- **Kod ve belgeler:** Bu klasörün (KURULUM.md dahil) bir kopyası kalite@ hesabının Drive'ında dursun. Yeni
  gelen biri kurulumu buradan yapabilir.

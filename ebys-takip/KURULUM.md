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

- Hocanın notlarda yazdığı adları "Notta geçen adlar" sütununa yazın. Ad Soyad'ın ilk kelimesi
  zaten otomatik olarak eklenir. Büyük/küçük harf ve Türkçe karakter fark etmez: "ALI" ve "ali"
  de Ali olarak tanınır.
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

- Görev listesi her açıldığında betik yeni görevleri bulur. Her birinin evrak sayfasını arka planda
  açıp **Notlar** bölümünü okur ve takip tablosuna gönderir. Hocanın notu "Ali: … Zeynep: …"
  biçimindeyse her kişiye ayrı görev açılır. Notta kimsenin adı geçmiyorsa görev
  **Genel / atanmamış** sekmesine düşer.
- Yeni bir yazı aynı anda **evrak tablonuza** da satır olarak eklenir. Geldiği yer ana birim düzeyinde yazılır: "… » STR. GEL. DAİ. BAŞ. » Bütçe ve Performans Program Şube Müdürlüğü" yerine "Strateji Geliştirme Daire Başkanlığı". Bunu Ayarlar sayfasındaki `YER_DUZEYI` satırıyla değiştirebilirsiniz: `SON` en alt birimi, `TAM` bütün zinciri yazar. Açılmayan bir kısaltma için Ayarlar sayfasına `KISALTMA ÖZ. BÜR.` | `Özel Kalem` gibi bir satır ekleyin. Satırda tür, evrak no,
  tarih, geldiği yer, konu, dosya kodu, sorumlu ve hocanın notu yer alır; tabloda sütunu olmayan
  bilgi yazılmaz. Sıra numarası bir önceki satırın bir fazlası olarak verilir; o hücrede formül
  varsa ona dokunulmaz.
- "Gelen Evrak Bilgilerini Güncelleyiniz" görevleri **gelen** sayılır. "Kurum Dışına Gönderilmiş
  Olan Evrak…" görevleri **giden** sayılır.
- PDF, **İş ve İşlemler / Gelen Yazı** (ya da **Giden Yazı**) klasörüne gider. Linki takip
  panelinde görünür ve evrak tablosunda **sistemin eklediği satırın** boş Dosya/Link hücresine
  yazılır. Elle girilmiş satırlara dokunulmaz.
- Bir evrak sayfasını açtığınızda kutuda **"Takibe al + PDF'i Drive'a gönder"** düğmesi çıkar. Bununla
  tek bir evrakı elle de gönderebilirsiniz.
- Ana sayfa açık bırakılırsa ayarladığınız aralıkla yenilenir ve yeni gelenleri kendisi alır.

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
| Kutuda "Anahtar hatalı" yazıyor | Ayarlardaki anahtarı Sheets'teki ile karşılaştırın. |
| "Sunucu yanıtı okunamadı" yazıyor | Betik adresinin `/exec` ile bittiğinden ve dağıtımın "Herkes" erişiminde olduğundan emin olun. Olmuyorsa 3. adımdaki nota bakın. |
| Görev geliyor ama PDF gelmiyor | `IS_ISLEMLER_KLASOR_ID` dolu mu kontrol edin. Evrak sayfasında elle gönder düğmesini deneyin. Yine olmazsa tarayıcı konsolundaki `[EBYS Takip]` satırlarını iletin. |
| Notta adı geçen kişi bulunamadı | Personel sayfasındaki "Notta geçen adlar" sütununa o yazılışı ekleyin. Görevi panelden elle atayın. |
| Evrak tablosuna satır gelmiyor | **Aktarım Kaydı** sekmesindeki "Not" sütununa bakın, hata orada yazar. Menüden sütun eşleşmesini kontrol edin. Kurulumu yapan hesabın evrak tablosunda düzenleme yetkisi olmalı. |
| Bir evrakı bilerek yeniden yazdırmak istiyorum | O evrakın satırını **Aktarım Kaydı** sekmesinden silin. Evrak tablonuzda hâlâ varsa yine yazılmaz. |
| Panel "yetkiniz yok" diyor | Kişinin e-postası Personel sayfasında birebir aynı mı kontrol edin. |

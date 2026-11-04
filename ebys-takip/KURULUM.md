# EBYS Görev Takip — Kurulum

Kalite Koordinatörlüğü için: EBYS'ye sevk edilen yazıları ve hocanın notlarını okur, notta adı
geçen kişiye görev olarak atar, takip panelinde gösterir, PDF'i Drive'a koyar.

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
   **"EBYS Görev Takip"** koyun.
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

**Drive:** iki klasör açın, örneğin **"EBYS – İşlemde"** ve **"EBYS – Tamamlanan"**. Her klasörü
açtığınızda adres çubuğundaki `…/folders/` sonrasındaki uzun kodu **Ayarlar** sayfasında
`ISLEMDE_KLASOR_ID` ve `TAMAMLANAN_KLASOR_ID` satırlarına yapıştırın. Klasörleri ekiple paylaşın.

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
- Evrakın PDF'i **İşlemde** klasörüne `[382726] MEDEK Ödemesi Hk..pdf` gibi bir adla kaydedilir.
- Bir evraka bağlı bütün görevler **Tamamlandı** olunca PDF **Tamamlanan / 2026-11** klasörüne taşınır.
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
- **Gelen-giden evrak** entegrasyonu sonraki adımda yapılacak.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Kutuda "Anahtar hatalı" yazıyor | Ayarlardaki anahtarı Sheets'teki ile karşılaştırın. |
| "Sunucu yanıtı okunamadı" yazıyor | Betik adresinin `/exec` ile bittiğinden ve dağıtımın "Herkes" erişiminde olduğundan emin olun. Olmuyorsa 3. adımdaki nota bakın. |
| Görev geliyor ama PDF gelmiyor | `ISLEMDE_KLASOR_ID` dolu mu kontrol edin. Evrak sayfasında elle gönder düğmesini deneyin. Yine olmazsa tarayıcı konsolundaki `[EBYS Takip]` satırlarını iletin. |
| Notta adı geçen kişi bulunamadı | Personel sayfasındaki "Notta geçen adlar" sütununa o yazılışı ekleyin. Görevi panelden elle atayın. |
| Panel "yetkiniz yok" diyor | Kişinin e-postası Personel sayfasında birebir aynı mı kontrol edin. |

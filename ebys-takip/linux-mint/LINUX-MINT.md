# EBYS Görev Takip — Linux Mint bilgisayarda 7/24 çalıştırma

Bu bilgisayar EBYS ana sayfasını sürekli açık tutar. Üzerindeki betik yeni görevleri, imzalanan giden
yazıları ve kayıtlı aramayı kimse başında olmadan takip tablosuna aktarır. Oturum kapanınca kendisi
yeniden giriş yapar, elektrik kesilip gelince de kendiliğinden ayağa kalkar.

## 1. Ayarları yapan betiği çalıştırın (2 dakika)

1. `ebys-takip` klasörünü bu bilgisayara kopyalayın (zip'i açın).
2. `linux-mint` klasörüne sağ tıklayın → **Terminalde Aç**.
3. Şunu yazıp Enter'a basın:
   ```bash
   bash mint-7-24-kurulum.sh
   ```

Betik şunları yapar (yönetici şifresi istemez):
- Bilgisayarın uykuya geçmesini kapatır. Ekran kararabilir ve kilitlenebilir; tarayıcı arkada çalışmaya devam eder.
- Oturum açılınca Firefox'u EBYS ana sayfasıyla otomatik başlatır.
- Firefox'u her gece 03:30'da yeniden başlatır. Böylece günlerce açık kalan tarayıcı şişmez.

## 2. Firefox'a betiği kurun

1. Firefox'ta **Tampermonkey** eklentisini kurun: addons.mozilla.org'da "Tampermonkey" aratın.
2. Tampermonkey → **Yeni betik oluştur**. Şablonu silin, `tarayici/ebys-takip.user.js` içeriğini yapıştırıp kaydedin.
3. EBYS'ye girin. Tampermonkey menüsünden:
   - **Ayarlar:** betik adresini ve gizli anahtarı girin. Otomatik gönderim için **Tamam**'ı seçin, yenileme süresine **15** yazın.
   - **Otomatik giriş:** bu bilgisayarın kullanacağı EBYS kullanıcı adını ve şifresini girin.
4. Kayıtlı giden aramasını açın ve kutudaki **"Bu aramayı otomatik takip araması yap"** düğmesine basın.
   Ayrıntı: KURULUM.md → "Birimin bütün giden yazıları".
5. Firefox'ta **Ayarlar → Gizlilik ve Güvenlik → Çerezler** bölümünde "Firefox kapanınca çerezleri sil"
   seçeneği **kapalı** olsun.

## 3. Elektrik kesintisi ve yeniden başlatma

- **Otomatik oturum açma:** Menü → **Giriş Penceresi** → **Kullanıcılar** bölümünde bu kullanıcıyı
  "otomatik oturum aç" olarak seçin. Bu adım yönetici şifresi ister.
- **Elektrik gelince açılma:** Bilgisayar açılırken BIOS'a girin (genelde Del ya da F2 tuşu). "Restore on AC
  Power Loss" ya da "After Power Failure" ayarını **Power On** yapın.

## Hangi EBYS hesabı?

- **Gelen görevler** yalnızca hocanın sevk ettiği kişinin EBYS ana sayfasına düşer. Bu bilgisayarda
  görevlerin en çok sevk edildiği kişinin hesabı açık olmalı. Diğer kişilerin görevleri için betiği
  onların bilgisayarlarına da kurmaya devam edin; aynı yazı iki yerden gelse de bir kez işlenir.
- **Giden yazılar** Evrak Arama'dan alındığı için hangi hesap olursa olsun birimin hepsi gelir.

## Güvenlik

- EBYS şifresi yalnızca bu bilgisayarın Firefox'unda, Tampermonkey'in kendi alanında saklanır. Takip
  tablosuna ya da Google'a gönderilmez.
- Bu yüzden bilgisayarın ekran kilidi açık kalsın (kurulum betiği açar) ve bilgisayar kilitli bir odada dursun.
- Otomatik girişin bir hesap tarafından yapılması için **Bilgi İşlem'i bilgilendirin**. Mümkünse bu iş için
  ayrı bir EBYS kullanıcısı isteyin.
- Şifre değişince Tampermonkey menüsünden **Otomatik giriş**'i yeniden girin. Yanlış şifreyle betik saatte
  en fazla 3 kez dener, hesabı kilitletmez.

## Kontrol

- Takip tablosundaki **Özet** sayfasının üstünde "Son EBYS aktarımı: … (kişi)" yazısı en fazla yarım
  saatlik olmalı.
- Aktarım 24 saatten uzun süre durursa yöneticilere ve ortak hesaba e-posta gider.

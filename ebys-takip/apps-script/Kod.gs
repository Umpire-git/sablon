/**
 * Kalite Koordinatörlüğü — EBYS Görev Takip
 * Google Sheets'e bağlı Apps Script. Sayfalar: Görevler, Personel, Ayarlar.
 *  - doGet  : takip paneli (yalnızca Personel listesindeki kurumsal hesaplar)
 *  - doPost : tarayıcı betiğinden gelen EBYS görevleri ve PDF'ler (gizli anahtarla)
 */

var SAYFA = { GOREV: 'Görevler', PERSONEL: 'Personel', AYAR: 'Ayarlar', KAYIT: 'Aktarım Kaydı' };
var KAYIT_SUTUN = ['Evrak No', 'Tür', 'Konu', 'Tabloya yazıldı', 'Tablo satırı', 'Drive dosyası', 'Tarih', 'Not'];

var GOREV_SUTUN = [
  'ID', 'Kaynak', 'Evrak No', 'Konu', 'Gönderen', 'Not Yazan', 'Not Tarihi', 'Hocanın Notu',
  'Görev', 'Sorumlu', 'Durum', 'Son Tarih', 'Ekleyen', 'Eklenme', 'Tamamlanma', 'Tamamlayan',
  'Dosya', 'EBYS Linki', 'Açıklama', 'Anahtar'
];
var PERSONEL_SUTUN = ['Ad Soyad', 'E-posta', 'Notta geçen adlar (virgülle)', 'Rol (Yönetici/Personel)'];
var DURUMLAR = ['Bekliyor', 'Devam Ediyor', 'Tamamlandı', 'İptal'];
var GENEL = 'Genel';

// ---------------------------------------------------------------- kurulum

function onOpen() {
  SpreadsheetApp.getUi().createMenu('EBYS Takip')
    .addItem('Kurulum / onarım', 'kurulum')
    .addItem('Gizli anahtarı göster', 'anahtariGoster')
    .addItem('Evrak tablosu sütun eşleşmesini göster', 'eslesmeyiGoster')
    .addToUi();
}

function kurulum() {
  var ss = SpreadsheetApp.getActive();
  sayfaHazirla_(ss, SAYFA.GOREV, GOREV_SUTUN);
  var p = sayfaHazirla_(ss, SAYFA.PERSONEL, PERSONEL_SUTUN);
  if (p.getLastRow() < 2) {
    p.getRange(2, 1, 1, 4).setValues([[
      'Ali DAĞLI', Session.getEffectiveUser().getEmail(), 'Ali', 'Personel']]);
  }
  var a = sayfaHazirla_(ss, SAYFA.AYAR, ['Ayar', 'Değer', 'Açıklama']);
  var varsayilan = [
    ['GIZLI_ANAHTAR', Utilities.getUuid(), 'Tarayıcı betiğine girilecek anahtar. Kimseyle paylaşmayın.'],
    ['EVRAK_TABLO_ID', '1PbWGU0V8KlrQ6ZEujhvalkxzTdk7gIQPE1dPJXZdYPw', 'Gelen-giden evrak tablonuzun ID\'si (adresteki /d/ ile /edit arası).'],
    ['GELEN_SEKME', '#1192504650', 'Gelen yazıların yazılacağı sekmenin adı. # ile başlarsa adresteki gid numarasıdır.'],
    ['GIDEN_SEKME', '#3352743', 'Giden yazıların yazılacağı sekme (gelenle aynı olabilir).'],
    ['GELEN_TABLOYA_YAZ', 'EVET', 'EVET ise yeni gelen yazılar evrak tablosuna otomatik satır olarak eklenir.'],
    ['GIDEN_TABLOYA_YAZ', 'EVET', 'EVET ise EBYS\'de "Kurum Dışına Gönderilmiş Olan Evrak" görevleri giden olarak eklenir.'],
    ['IS_ISLEMLER_KLASOR_ID', '', '"İş ve İşlemler" Drive klasörünün ID\'si. İçinde "Gelen Yazı" ve "Giden Yazı" klasörleri yoksa açılır.'],
    ['YER_DUZEYI', 'DAIRE', 'Geldiği/gittiği yer nasıl yazılsın: DAIRE = şube/birim atlanır, ana birim yazılır (Strateji Geliştirme Daire Başkanlığı); SON = en alt birim; TAM = bütün zincir.'],
    ['AY_ALT_KLASORU', 'HAYIR', 'EVET ise PDF\'ler Gelen Yazı/2026-11 gibi ay klasörlerine ayrılır.'],
    ['EPOSTA_BILDIRIM', 'EVET', 'EVET ise görev atanınca kişiye e-posta gider.'],
    ['ALAN_ADI', 'usak.edu.tr', 'Panele yalnızca bu alan adındaki hesaplar girebilir.']
  ];
  var mevcut = a.getDataRange().getValues().map(function (r) { return r[0]; });
  varsayilan.forEach(function (v) { if (mevcut.indexOf(v[0]) < 0) a.appendRow(v); });

  sayfaHazirla_(ss, SAYFA.KAYIT, KAYIT_SUTUN);
  var g = ss.getSheetByName(SAYFA.GOREV);
  var durumKurali = SpreadsheetApp.newDataValidation().requireValueInList(DURUMLAR, true).build();
  g.getRange(2, sutun_('Durum'), g.getMaxRows() - 1, 1).setDataValidation(durumKurali);
  SpreadsheetApp.getUi().alert('Kurulum tamam. Şimdi Personel sayfasını doldurun, sonra Dağıt → Yeni dağıtım ile web uygulaması oluşturun.');
}

function anahtariGoster() {
  SpreadsheetApp.getUi().alert('Gizli anahtar:\n\n' + ayar_('GIZLI_ANAHTAR'));
}

function sayfaHazirla_(ss, ad, basliklar) {
  var sh = ss.getSheetByName(ad) || ss.insertSheet(ad);
  sh.getRange(1, 1, 1, basliklar.length).setValues([basliklar]).setFontWeight('bold').setBackground('#e8eef7');
  sh.setFrozenRows(1);
  return sh;
}

// ---------------------------------------------------------------- yardımcılar

function sutun_(ad) { return GOREV_SUTUN.indexOf(ad) + 1; }

function ayar_(ad) {
  var sh = SpreadsheetApp.getActive().getSheetByName(SAYFA.AYAR);
  var v = sh.getDataRange().getValues();
  for (var i = 1; i < v.length; i++) if (v[i][0] === ad) return String(v[i][1]).trim();
  return '';
}

function kucuk_(s) {
  return String(s || '').replace(/I/g, 'ı').replace(/İ/g, 'i').toLowerCase();
}

/** Eşleştirme için: küçük harf + Türkçe karakterler sadeleşir (uzunluk aynı kalır). */
function sade_(s) {
  var tr = { 'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u', 'â': 'a', 'î': 'i', 'û': 'u' };
  return String(s || '').replace(/[İI]/g, 'i').toLowerCase().replace(/[çğıöşüâîû]/g, function (c) { return tr[c]; });
}

function personel_() {
  var v = SpreadsheetApp.getActive().getSheetByName(SAYFA.PERSONEL).getDataRange().getValues();
  var liste = [];
  for (var i = 1; i < v.length; i++) {
    if (!v[i][0]) continue;
    var takma = String(v[i][2] || '').split(',').map(function (x) { return x.trim(); }).filter(String);
    var ilkAd = String(v[i][0]).trim().split(/\s+/)[0];
    if (takma.indexOf(ilkAd) < 0) takma.push(ilkAd);
    liste.push({
      ad: String(v[i][0]).trim(),
      eposta: String(v[i][1] || '').trim().toLowerCase(),
      takma: takma,
      yonetici: /yönetici/i.test(String(v[i][3] || ''))
    });
  }
  return liste;
}

function gorevler_() {
  var sh = SpreadsheetApp.getActive().getSheetByName(SAYFA.GOREV);
  var v = sh.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < v.length; i++) {
    if (!v[i][0]) continue;
    var o = { _satir: i + 1 };
    GOREV_SUTUN.forEach(function (b, j) { o[b] = v[i][j]; });
    out.push(o);
  }
  return out;
}

function tarihYazi_(d) {
  if (!(d instanceof Date)) return d ? String(d) : '';
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
}

function yeniId_() { return 'G' + Utilities.formatDate(new Date(), 'GMT', 'yyMMdd') + '-' + Utilities.getUuid().slice(0, 4); }

/** Kaydı Görevler sayfasına ekler, ID döner. */
function gorevYaz_(o) {
  var sh = SpreadsheetApp.getActive().getSheetByName(SAYFA.GOREV);
  o.ID = o.ID || yeniId_();
  o.Durum = o.Durum || 'Bekliyor';
  o['Eklenme'] = new Date();
  sh.appendRow(GOREV_SUTUN.map(function (b) { return o[b] === undefined ? '' : o[b]; }));
  return o.ID;
}

// ---------------------------------------------------------------- not ayrıştırma

/**
 * "Ali: rapor yazısını hazırla. Zeynep şu tabloyu doldursun" →
 *   [{kisi:'Ali DAĞLI', metin:'rapor yazısını hazırla.'}, {kisi:'Zeynep ...', metin:'şu tabloyu doldursun'}]
 * Notta kimse geçmiyorsa tek parça "Genel" görev döner.
 */
function notuBol(not, personel) {
  personel = personel || personel_();
  var metin = String(not || '').trim();
  var k = sade_(metin);
  var bulunan = [];
  personel.forEach(function (p) {
    p.takma.forEach(function (t) {
      var tk = sade_(t);
      if (!tk) return;
      var re = new RegExp('(^|[^a-z0-9])' + tk.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') +
        '(?=$|[^a-z0-9])', 'g');
      var m;
      while ((m = re.exec(k)) !== null) {
        bulunan.push({ bas: m.index + m[1].length, son: m.index + m[1].length + tk.length, kisi: p.ad });
      }
    });
  });
  bulunan.sort(function (a, b) { return a.bas - b.bas || b.son - a.son; });
  // iç içe eşleşmeleri ele ("ali" ve "ali bey" gibi)
  var temiz = [];
  bulunan.forEach(function (b) {
    var son = temiz[temiz.length - 1];
    if (!son || b.bas >= son.son) temiz.push(b);
  });
  if (!temiz.length) return [{ kisi: GENEL, metin: metin }];

  var once = metin.slice(0, temiz[0].bas).trim();
  var parca = [];
  temiz.forEach(function (b, i) {
    var bitis = i + 1 < temiz.length ? temiz[i + 1].bas : metin.length;
    var t = metin.slice(b.son, bitis)
      .replace(/^\s*(bey|hanım|hn\.?|bey'?in|hanım'?ın)(?=[\s:,]|$)/i, '')
      .replace(/^[\s:,\-–—]+/, '').replace(/^(de|da|ise)\s+/i, '')
      .replace(/(^|[\s,]+)(ve|ile)?[\s,]*$/i, '').trim();
    var onceki = parca.filter(function (x) { return x.kisi === b.kisi; })[0];
    if (onceki) onceki.metin += ' ' + t;
    else parca.push({ kisi: b.kisi, metin: t });
  });
  if (once) parca.forEach(function (p) { p.metin = once + ' ' + p.metin; });
  // "Ali ve Zeynep: ..." gibi boş kalan parçalar ortak metni alır
  var dolu = parca.filter(function (p) { return p.metin; });
  var ortak = dolu.length ? dolu[dolu.length - 1].metin : metin;
  parca.forEach(function (p) { if (!p.metin) p.metin = ortak; });
  return parca;
}

// ---------------------------------------------------------------- tarayıcı betiği (doPost)

function doPost(e) {
  var cevap;
  try {
    var veri = JSON.parse(e.postData.contents);
    if (!veri.anahtar || veri.anahtar !== ayar_('GIZLI_ANAHTAR')) throw new Error('Anahtar hatalı');
    var kilit = LockService.getScriptLock();
    kilit.waitLock(30000);
    try {
      if (veri.islem === 'gorevler') cevap = gorevleriAl_(veri.gorevler || [], veri.kullanici || '');
      else if (veri.islem === 'dosya') cevap = dosyaAl_(veri);
      else if (veri.islem === 'kontrol') cevap = { tamam: true };
      else throw new Error('Bilinmeyen işlem');
    } finally { kilit.releaseLock(); }
  } catch (err) {
    cevap = { hata: String(err.message || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(cevap)).setMimeType(ContentService.MimeType.JSON);
}

/** gorevler: [{evrakNo, konu, gonderen, gorevAdi, link, notlar:[{yazan, tarih, metin}]}] */
function gorevleriAl_(liste, kullanici) {
  var mevcut = {};
  gorevler_().forEach(function (g) { if (g.Anahtar) mevcut[g.Anahtar] = g; });
  var personel = personel_();
  var eklenen = 0, dosyaIstenen = [];

  liste.forEach(function (it) {
    try { if (it.evrak && it.evrakNo) evrakTablosunaYaz_(it); } catch (e) { kayitNotu_(it.evrakNo, 'Tabloya yazılamadı: ' + e.message); }
    var notlar = (it.notlar && it.notlar.length) ? it.notlar : [{ yazan: '', tarih: '', metin: '' }];
    var dosyaVar = false, yeni = false;
    notlar.forEach(function (n) {
      var anahtar = (it.evrakNo || it.link) + '|' + (n.yazan || '') + '|' + (n.tarih || '');
      if (mevcut[anahtar]) { if (mevcut[anahtar].Dosya) dosyaVar = true; return; }
      var parcalar = n.metin ? notuBol(n.metin, personel) : [{ kisi: GENEL, metin: it.gorevAdi || '' }];
      parcalar.forEach(function (p, i) {
        var id = gorevYaz_({
          'Kaynak': 'EBYS', 'Evrak No': it.evrakNo || '', 'Konu': it.konu || '', 'Gönderen': it.gonderen || '',
          'Not Yazan': n.yazan || '', 'Not Tarihi': n.tarih || '', 'Hocanın Notu': n.metin || '',
          'Görev': p.metin, 'Sorumlu': p.kisi, 'Ekleyen': kullanici || 'EBYS betiği',
          'EBYS Linki': it.link || '', 'Anahtar': i === 0 ? anahtar : anahtar + '#' + i
        });
        if (i === 0) mevcut[anahtar] = { Dosya: '' };
        if (p.kisi !== GENEL) bildir_(p.kisi, id, it.konu, p.metin, personel);
        eklenen++;
      });
      yeni = true;
    });
    if (it.evrakNo && !dosyaVar && !kayitBul_(it.evrakNo).dosya) dosyaIstenen.push(it.evrakNo);
  });
  return { tamam: true, eklenen: eklenen, dosyaIstenen: dosyaIstenen };
}

/** veri: {evrakNo, tur, dosyaAdi, mime, base64} — aynı evrak ikinci kez yüklenmez */
function dosyaAl_(veri) {
  var kayit = kayitBul_(veri.evrakNo);
  if (kayit.dosya) return { tamam: true, link: kayit.dosya, zatenVardi: true };
  var tur = veri.tur || kayit.tur || 'Gelen';
  var klasor = turKlasoru_(tur);
  var onEk = '[' + veri.evrakNo + ']';
  var it = klasor.searchFiles('title contains "' + onEk + '" and trashed = false');
  var link;
  if (it.hasNext()) {
    link = it.next().getUrl();
  } else {
    var blob = Utilities.newBlob(Utilities.base64Decode(veri.base64), veri.mime || 'application/pdf',
      onEk + ' ' + (veri.dosyaAdi || 'evrak.pdf'));
    link = klasor.createFile(blob).getUrl();
  }
  kayitYaz_(veri.evrakNo, { 'Drive dosyası': link });

  // Görevler sayfasında boş "Dosya" hücrelerine link
  var sh = SpreadsheetApp.getActive().getSheetByName(SAYFA.GOREV);
  gorevler_().forEach(function (g) {
    if (String(g['Evrak No']) === String(veri.evrakNo) && !g.Dosya) sh.getRange(g._satir, sutun_('Dosya')).setValue(link);
  });
  // Evrak tablosunda yalnızca boş dosya hücresine link
  try { evrakTablosunaLink_(veri.evrakNo, kayit, link); } catch (e) { /* tablo erişilemezse PDF yine Drive'da */ }
  return { tamam: true, link: link };
}

function turKlasoru_(tur) {
  var anaId = ayar_('IS_ISLEMLER_KLASOR_ID');
  if (!anaId) throw new Error('Ayarlar sayfasında IS_ISLEMLER_KLASOR_ID boş');
  var ad = tur === 'Giden' ? 'Giden Yazı' : 'Gelen Yazı';
  var k = altKlasor_(DriveApp.getFolderById(anaId), ad);
  if (ayar_('AY_ALT_KLASORU') === 'EVET') {
    k = altKlasor_(k, Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM'));
  }
  return k;
}

function altKlasor_(ust, ad) {
  var it = ust.getFoldersByName(ad);
  return it.hasNext() ? it.next() : ust.createFolder(ad);
}

function bildir_(kisiAdi, id, konu, metin, personel) {
  if (ayar_('EPOSTA_BILDIRIM') !== 'EVET') return;
  var p = (personel || personel_()).filter(function (x) { return x.ad === kisiAdi; })[0];
  if (!p || !p.eposta) return;
  var url = ScriptApp.getService().getUrl() || '';
  try {
    MailApp.sendEmail(p.eposta, 'Yeni görev: ' + (konu || metin).slice(0, 80),
      'Merhaba ' + p.ad + ',\n\nSize yeni bir görev atandı.\n\nKonu: ' + (konu || '-') +
      '\nGörev: ' + metin + '\nNo: ' + id + '\n\nTakip paneli: ' + url + '\n');
  } catch (e) { /* e-posta kotası dolduysa görev yine kaydedilir */ }
}

// ---------------------------------------------------------------- panel (doGet)

function doGet() {
  var ben = kim_();
  if (!ben) {
    return HtmlService.createHtmlOutput('<p style="font-family:sans-serif;padding:24px">Bu panele yalnızca ' +
      'Personel listesindeki kurumsal hesaplar girebilir. Kurumsal Google hesabınızla oturum açın.</p>');
  }
  return HtmlService.createTemplateFromFile('Panel').evaluate()
    .setTitle('Kalite Koordinatörlüğü — Görev Takip')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function kim_() {
  var eposta = String(Session.getActiveUser().getEmail() || '').toLowerCase();
  if (!eposta) return null;
  var p = personel_().filter(function (x) { return x.eposta === eposta; })[0];
  if (p) return p;
  if (eposta === String(Session.getEffectiveUser().getEmail()).toLowerCase()) {
    return { ad: eposta, eposta: eposta, yonetici: true, takma: [] };
  }
  return null;
}

function yetkiKontrol_() {
  var ben = kim_();
  if (!ben) throw new Error('Yetkiniz yok');
  return ben;
}

function panelVerisi() {
  var ben = yetkiKontrol_();
  var gorevler = gorevler_().map(function (g) {
    var o = {};
    GOREV_SUTUN.forEach(function (b) {
      if (b === 'Anahtar') return;
      o[b] = (g[b] instanceof Date) ? tarihYazi_(g[b]) : String(g[b] === undefined ? '' : g[b]);
    });
    if (g['Son Tarih'] instanceof Date) o['Son Tarih'] = Utilities.formatDate(g['Son Tarih'], Session.getScriptTimeZone(), 'yyyy-MM-dd');
    return o;
  });
  return {
    ben: { ad: ben.ad, yonetici: ben.yonetici },
    personel: personel_().map(function (p) { return p.ad; }),
    durumlar: DURUMLAR,
    gorevler: gorevler
  };
}

/** alanlar: {Durum, Sorumlu, Son Tarih, Açıklama, Görev} */
function gorevGuncelle(id, alanlar) {
  var ben = yetkiKontrol_();
  var kilit = LockService.getScriptLock(); kilit.waitLock(30000);
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(SAYFA.GOREV);
    var g = gorevler_().filter(function (x) { return x.ID === id; })[0];
    if (!g) throw new Error('Görev bulunamadı: ' + id);
    var izinli = ['Durum', 'Sorumlu', 'Son Tarih', 'Açıklama', 'Görev'];
    Object.keys(alanlar).forEach(function (k) {
      if (izinli.indexOf(k) < 0) return;
      var v = alanlar[k];
      if (k === 'Son Tarih' && v) v = new Date(v + 'T00:00:00');
      sh.getRange(g._satir, sutun_(k)).setValue(v);
    });
    if (alanlar.Sorumlu && alanlar.Sorumlu !== g.Sorumlu && alanlar.Sorumlu !== GENEL) {
      bildir_(alanlar.Sorumlu, id, g.Konu, alanlar['Görev'] || g['Görev']);
    }
    if (alanlar.Durum === 'Tamamlandı' && g.Durum !== 'Tamamlandı') {
      sh.getRange(g._satir, sutun_('Tamamlanma')).setValue(new Date());
      sh.getRange(g._satir, sutun_('Tamamlayan')).setValue(ben.ad);
    }
    if (alanlar.Durum && alanlar.Durum !== 'Tamamlandı' && g.Durum === 'Tamamlandı') {
      sh.getRange(g._satir, sutun_('Tamamlanma')).setValue('');
      sh.getRange(g._satir, sutun_('Tamamlayan')).setValue('');
    }
  } finally { kilit.releaseLock(); }
  return panelVerisi();
}

/** o: {Görev, Konu, Sorumlu, Son Tarih, Açıklama} */
function gorevEkle(o) {
  var ben = yetkiKontrol_();
  if (!o || !String(o['Görev'] || '').trim()) throw new Error('Görev metni boş olamaz');
  var kilit = LockService.getScriptLock(); kilit.waitLock(30000);
  try {
    var id = gorevYaz_({
      'Kaynak': 'Elle', 'Konu': o.Konu || '', 'Görev': o['Görev'], 'Sorumlu': o.Sorumlu || GENEL,
      'Son Tarih': o['Son Tarih'] ? new Date(o['Son Tarih'] + 'T00:00:00') : '',
      'Açıklama': o['Açıklama'] || '', 'Ekleyen': ben.ad
    });
    if (o.Sorumlu && o.Sorumlu !== GENEL) bildir_(o.Sorumlu, id, o.Konu, o['Görev']);
  } finally { kilit.releaseLock(); }
  return panelVerisi();
}

// ---------------------------------------------------------------- aktarım kaydı
// Sistemin işlediği her evrak burada tutulur. Kayıtta olan evrak tablolara bir daha yazılmaz,
// satır sonradan silinse ya da değiştirilse bile.

function kayitSayfasi_() {
  var ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(SAYFA.KAYIT) || sayfaHazirla_(ss, SAYFA.KAYIT, KAYIT_SUTUN);
}

function kayitBul_(no) {
  var v = kayitSayfasi_().getDataRange().getValues();
  for (var i = 1; i < v.length; i++) {
    if (String(v[i][0]).trim() === String(no).trim()) {
      return { satir: i + 1, tur: v[i][1], tablo: v[i][3], tabloSatiri: v[i][4], dosya: v[i][5] };
    }
  }
  return {};
}

/** Kayıt yoksa ekler; varsa yalnızca BOŞ hücreleri doldurur (Not sütunu hariç, ona eklenir). */
function kayitYaz_(no, alanlar) {
  var sh = kayitSayfasi_();
  var k = kayitBul_(no);
  if (!k.satir) {
    sh.appendRow(KAYIT_SUTUN.map(function (b) {
      if (b === 'Evrak No') return String(no);
      if (b === 'Tarih') return new Date();
      return alanlar[b] === undefined ? '' : alanlar[b];
    }));
    return;
  }
  Object.keys(alanlar).forEach(function (b) {
    var c = KAYIT_SUTUN.indexOf(b) + 1;
    if (c < 1) return;
    var hucre = sh.getRange(k.satir, c);
    if (b === 'Not') hucre.setValue([hucre.getValue(), alanlar[b]].filter(String).join(' | '));
    else if (hucre.getValue() === '') hucre.setValue(alanlar[b]);
  });
}

function kayitNotu_(no, metin) { if (no) kayitYaz_(no, { 'Not': metin }); }

// ---------------------------------------------------------------- gelen-giden evrak tablosu

var ALANLAR = [
  ['dosyaKodu', /dosya ?(kodu|plani|no)|standart dosya/],
  ['tur', /gelen.{0,3}giden|giden.{0,3}gelen|^turu?$|evrak turu|^tipi?$|cinsi/],
  ['sayi', /sayisi?\b|^sayi/],
  ['kayitNo', /(evrak|kayit|kurum|genel|ebys).*(\bno\b|nosu|numara)|numarator|^kayit$/],
  ['sonTarih', /gunlu|son tarih|termin|suresi?\b|cevap tarih/],
  ['evrakTarihi', /(evrak|yazi|belge).*tarih/],
  ['kayitTarihi', /tarih/],
  ['konu', /konu|ozet|icerik/],
  ['yer', /geldigi|gonderen|kimden|nereden|gittigi|gonderilen|kime|nereye|kurum|birim|makam|muhatap/],
  ['sorumlu', /sorumlu|havale|gorevli|ilgilenen|personel|atanan/],
  ['dosya', /dosya|link|baglanti|pdf|drive/],
  ['aciklama', /aciklama|not|talimat|yapilacak|islem/],
  ['sira', /^(s\.? ?no|sira( no)?|no|#)$/]
];
var ALAN_ADI = {
  dosyaKodu: 'Dosya kodu', tur: 'Gelen/Giden', sayi: 'Sayı', kayitNo: 'Evrak no', evrakTarihi: 'Evrak tarihi',
  kayitTarihi: 'Kayıt tarihi', sonTarih: 'Son tarih / günlü evrak (bu sütuna yazılmaz)', konu: 'Konu', yer: 'Geldiği/gittiği yer', sorumlu: 'Sorumlu', dosya: 'Drive linki',
  aciklama: 'Açıklama (hocanın notu)', sira: 'Sıra no'
};

function hedefSekme_(tur) {
  var ss = SpreadsheetApp.openById(ayar_('EVRAK_TABLO_ID'));
  var ad = ayar_(tur === 'Giden' ? 'GIDEN_SEKME' : 'GELEN_SEKME');
  if (/^#\d+$/.test(ad)) {
    var gid = Number(ad.slice(1));
    var sh = ss.getSheets().filter(function (x) { return x.getSheetId() === gid; })[0];
    if (sh) return sh;
  } else if (ad && ss.getSheetByName(ad)) return ss.getSheetByName(ad);
  throw new Error('Evrak tablosunda sekme bulunamadı: ' + ad);
}

function sutunHarfi_(n) { var s = ''; while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = (n - m - 1) / 26; } return s; }

/** Başlık satırını (ilk 10 satırda en çok eşleşen) ve alan → sütun eşleşmesini bulur. */
function eslesme_(sh, tur) {
  var n = Math.min(10, sh.getLastRow());
  var genislik = sh.getLastColumn();
  if (n < 1 || genislik < 1) throw new Error('Sekme boş: ' + sh.getName());
  var v = sh.getRange(1, 1, n, genislik).getDisplayValues();
  var enIyi = { puan: 0 };
  v.forEach(function (satir, i) {
    var sut = {}, puan = 0;
    satir.forEach(function (h, j) {
      var hs = sade_(h).replace(/\s+/g, ' ').trim();
      if (!hs || hs.length > 40) return;
      for (var a = 0; a < ALANLAR.length; a++) {
        if (sut[ALANLAR[a][0]] === undefined && ALANLAR[a][1].test(hs)) { sut[ALANLAR[a][0]] = j + 1; puan++; break; }
      }
    });
    if (puan > enIyi.puan) enIyi = { puan: puan, basSatir: i + 1, sutunlar: sut, basliklar: satir };
  });
  if (enIyi.puan < 2) throw new Error('"' + sh.getName() + '" sekmesinde başlık satırı tanınamadı');
  // Elle düzeltme: Ayarlar'da SUTUN_KONU = C ya da başlık adı
  Object.keys(ALAN_ADI).forEach(function (alan) {
    var d = ayar_('SUTUN_' + (tur === 'Giden' ? 'GIDEN_' : 'GELEN_') + alan.toUpperCase()) || ayar_('SUTUN_' + alan.toUpperCase());
    if (!d) return;
    if (d === '-') { delete enIyi.sutunlar[alan]; return; }
    if (/^[A-Z]{1,2}$/i.test(d)) {
      var c = 0; d.toUpperCase().split('').forEach(function (h) { c = c * 26 + h.charCodeAt(0) - 64; });
      enIyi.sutunlar[alan] = c;
    } else {
      var j = enIyi.basliklar.map(function (h) { return sade_(h).trim(); }).indexOf(sade_(d).trim());
      if (j >= 0) enIyi.sutunlar[alan] = j + 1;
    }
  });
  return enIyi;
}

function eslesmeyiGoster() {
  var metin = [];
  ['Gelen', 'Giden'].forEach(function (tur) {
    try {
      var sh = hedefSekme_(tur), e = eslesme_(sh, tur);
      metin.push(tur + ' → "' + sh.getName() + '" sekmesi, başlık satırı ' + e.basSatir);
      Object.keys(ALAN_ADI).forEach(function (a) {
        var c = e.sutunlar[a];
        metin.push('   ' + ALAN_ADI[a] + ': ' + (c ? sutunHarfi_(c) + ' (' + e.basliklar[c - 1] + ')' : '—'));
      });
    } catch (err) { metin.push(tur + ': ' + err.message); }
    metin.push('');
  });
  metin.push('— olan alanlar yazılmaz. Yanlış eşleşme varsa Ayarlar sayfasına örn. SUTUN_GELEN_KONU = D (yalnızca gelen),');
  metin.push('SUTUN_GIDEN_KONU = D (yalnızca giden) ya da SUTUN_KONU = D (ikisi için) satırı ekleyin. "-" yazarsanız o alan yazılmaz.');
  SpreadsheetApp.getUi().alert(metin.join('\n'));
}

function hucreBos_(sh, r, c) {
  var h = sh.getRange(r, c);
  return h.getValue() === '' && h.getFormula() === '';
}

function trTarih_(s) {
  var m = String(s || '').match(/(\d{1,2})[./](\d{1,2})[./](\d{4})/);
  return m ? new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1])) : (s || '');
}

// ---------------------------------------------------------------- geldiği / gittiği yer

var KISALTMA_IFADE = {
  'STR. GEL. DAİ. BAŞ.': 'Strateji Geliştirme Daire Başkanlığı',
  'PER. DAİ. BAŞ.': 'Personel Daire Başkanlığı',
  'ÖĞR. İŞL. DAİ. BAŞ.': 'Öğrenci İşleri Daire Başkanlığı',
  'İDA. VE MAL. İŞL. DAİ. BAŞ.': 'İdari ve Mali İşler Daire Başkanlığı',
  'BİL. İŞL. DAİ. BAŞ.': 'Bilgi İşlem Daire Başkanlığı',
  'YAP. İŞL. VE TEK. DAİ. BAŞ.': 'Yapı İşleri ve Teknik Daire Başkanlığı',
  'SAĞ. KÜL. VE SPOR DAİ. BAŞ.': 'Sağlık, Kültür ve Spor Daire Başkanlığı',
  'KÜT. VE DOK. DAİ. BAŞ.': 'Kütüphane ve Dokümantasyon Daire Başkanlığı',
  'YÜK. KUR. BAŞ.': 'Yükseköğretim Kurulu Başkanlığı',
  'YÜK. KAL. KUR.': 'Yükseköğretim Kalite Kurulu',
  'REK. MAK.': 'Rektörlük Makamı',
  'GEN. SEK.': 'Genel Sekreterlik',
  'HUK. MÜŞ.': 'Hukuk Müşavirliği'
};
var KISALTMA_KELIME = {
  'DAİ.': 'Daire', 'BAŞ.': 'Başkanlığı', 'MÜD.': 'Müdürlüğü', 'FAK.': 'Fakültesi', 'DEK.': 'Dekanlığı',
  'ENS.': 'Enstitüsü', 'KOO.': 'Koordinatörlüğü', 'KOOR.': 'Koordinatörlüğü', 'MER.': 'Merkezi',
  'GEN.': 'Genel', 'SEK.': 'Sekreterliği', 'İŞL.': 'İşleri', 'ŞB.': 'Şube', 'ŞUB.': 'Şube',
  'REK.': 'Rektörlüğü', 'YÜKS.': 'Yüksekokulu', 'MYO.': 'Meslek Yüksekokulu', 'UYG.': 'Uygulama',
  'ARŞ.': 'Araştırma', 'MÜŞ.': 'Müşavirliği', 'KUR.': 'Kurulu', 'MAK.': 'Makamı', 'BÖL.': 'Bölümü'
};
var ALT_BIRIM = /(şube müdürlüğü|şb\.? ?müd|birimi$|bürosu$|servisi$|ofisi$|anabilim dalı|bilim dalı|programı$|sekreterliği$)/i;

function kisaltmaAc_(t) {
  t = String(t || '').replace(/\s+/g, ' ').trim();
  // Ayarlar'da "KISALTMA STR. GEL. DAİ. BAŞ." | "Strateji Geliştirme Daire Başkanlığı" gibi ekler önce gelir
  var v = SpreadsheetApp.getActive().getSheetByName(SAYFA.AYAR).getDataRange().getValues();
  for (var i = 1; i < v.length; i++) {
    var k = String(v[i][0]);
    if (/^KISALTMA /i.test(k) && k.slice(9).trim().toUpperCase() === t.toUpperCase()) return String(v[i][1]).trim();
  }
  if (KISALTMA_IFADE[t.toUpperCase()]) return KISALTMA_IFADE[t.toUpperCase()];
  if (!/[A-ZÇĞİÖŞÜ]{2,}\./.test(t)) return t;               // kısaltma yok
  return t.split(' ').map(function (w) { return KISALTMA_KELIME[w.toUpperCase()] || w; }).join(' ');
}

/** "A » B » STR. GEL. DAİ. BAŞ. » Bütçe ... Şube Müdürlüğü" → "Strateji Geliştirme Daire Başkanlığı" */
function yerAdi_(zincirler) {
  var duzey = (ayar_('YER_DUZEYI') || 'DAIRE').toUpperCase();
  return String(zincirler || '').split(' | ').map(function (z) {
    if (duzey === 'TAM') return z.trim();
    var parca = z.split('»').map(function (x) { return x.trim(); }).filter(function (x) { return x && !/^[\d\s.-]+$/.test(x); });
    if (!parca.length) return '';
    var sec = parca[parca.length - 1];
    if (duzey !== 'SON') {
      for (var i = parca.length - 1; i >= 0; i--) {
        var acik = kisaltmaAc_(parca[i]);
        if (!ALT_BIRIM.test(acik)) { sec = parca[i]; break; }
      }
    }
    return kisaltmaAc_(sec);
  }).filter(String).join(', ');
}

/** Bir sütunda evrak numarası var mı (elle girilmiş ya da önceden yazılmış) */
function tablodaVarMi_(sh, e, it) {
  var son = sh.getLastRow();
  if (son <= e.basSatir) return 0;
  var bas = e.basSatir + 1, adet = son - e.basSatir;
  var no = String(it.evrakNo).trim();
  var bak = function (c, esitMi) {
    if (!c) return 0;
    var v = sh.getRange(bas, c, adet, 1).getDisplayValues();
    for (var i = 0; i < v.length; i++) if (esitMi(String(v[i][0]).trim())) return bas + i;
    return 0;
  };
  var r = bak(e.sutunlar.kayitNo, function (x) { return x === no || x.replace(/\D/g, '') === no; });
  if (!r) r = bak(e.sutunlar.sayi, function (x) { return x && (x === no || new RegExp('(^|\\D)' + no + '$').test(x) || (it.evrak.sayi && x === it.evrak.sayi)); });
  if (!r && !e.sutunlar.kayitNo && !e.sutunlar.sayi && e.sutunlar.konu) {
    // Numara sütunu yoksa: aynı konu + aynı tarih
    var tc = e.sutunlar.kayitTarihi || e.sutunlar.evrakTarihi;
    var konu = sade_(it.evrak.konu || it.konu).trim();
    var kv = sh.getRange(bas, e.sutunlar.konu, adet, 1).getDisplayValues();
    var tv = tc ? sh.getRange(bas, tc, adet, 1).getValues() : null;
    var hedefT = trTarih_(it.evrak.kayitTarihi);
    for (var i = 0; i < kv.length; i++) {
      if (sade_(kv[i][0]).trim() !== konu) continue;
      if (!tv || !(hedefT instanceof Date) || (tv[i][0] instanceof Date && tv[i][0].toDateString() === hedefT.toDateString())) return bas + i;
    }
  }
  return r;
}

/** it: betikten gelen görev + it.evrak {tur, konu, kayitTarihi, evrakTarihi, sayi, yer, dosyaKodu} */
function evrakTablosunaYaz_(it) {
  var ev = it.evrak, tur = ev.tur === 'Giden' ? 'Giden' : 'Gelen', no = String(it.evrakNo);
  var kayit = kayitBul_(no);
  if (kayit.tablo) return;                                      // daha önce işlendi: dokunma
  if (ayar_(tur === 'Giden' ? 'GIDEN_TABLOYA_YAZ' : 'GELEN_TABLOYA_YAZ') !== 'EVET') {
    kayitYaz_(no, { 'Tür': tur, 'Konu': ev.konu || it.konu, 'Tabloya yazıldı': 'Hayır (ayar kapalı)' });
    return;
  }
  var sh = hedefSekme_(tur), e = eslesme_(sh, tur), S = e.sutunlar;

  var varOlan = tablodaVarMi_(sh, e, it);
  if (varOlan) {
    kayitYaz_(no, { 'Tür': tur, 'Konu': ev.konu || it.konu, 'Tabloya yazıldı': 'Zaten vardı', 'Tablo satırı': varOlan });
    return;
  }

  // Son dolu satırın altındaki, eşleşen hücreleri tamamen boş ilk satır
  var anaSutunlar = Object.keys(S).map(function (k) { return S[k]; });
  var son = e.basSatir;
  var veriSon = sh.getLastRow();
  if (veriSon > e.basSatir) {
    var v = sh.getRange(e.basSatir + 1, 1, veriSon - e.basSatir, sh.getLastColumn()).getDisplayValues();
    var anahtar = [S.konu, S.kayitNo, S.sayi].filter(Boolean);
    if (!anahtar.length) anahtar = anaSutunlar;
    for (var i = v.length - 1; i >= 0; i--) {
      if (anahtar.some(function (c) { return String(v[i][c - 1]).trim() !== ''; })) { son = e.basSatir + 1 + i; break; }
    }
  }
  var r = son + 1;
  while (!anaSutunlar.every(function (c) { return c === S.sira || hucreBos_(sh, r, c); })) r++;
  if (r > sh.getMaxRows()) sh.insertRowsAfter(sh.getMaxRows(), r - sh.getMaxRows());

  var sorumlular = [];
  (it.notlar || []).forEach(function (n) {
    notuBol(n.metin).forEach(function (p) { if (p.kisi !== GENEL && sorumlular.indexOf(p.kisi) < 0) sorumlular.push(p.kisi); });
  });
  var deger = {
    tur: tur, kayitNo: no, sayi: ev.sayi || '', evrakTarihi: trTarih_(ev.evrakTarihi || (S.kayitTarihi ? '' : ev.kayitTarihi)),
    kayitTarihi: trTarih_(ev.kayitTarihi || ev.evrakTarihi), konu: ev.konu || it.konu, yer: yerAdi_(ev.yer),
    dosyaKodu: ev.dosyaKodu || '', sorumlu: sorumlular.join(', '),
    aciklama: (it.notlar || []).map(function (n) { return n.metin; }).filter(String).join(' / ')
  };
  if (S.sira && hucreBos_(sh, r, S.sira) && r > e.basSatir + 1) {
    var onceki = Number(String(sh.getRange(r - 1, S.sira).getDisplayValue()).replace(/\D/g, ''));
    if (onceki) deger.sira = onceki + 1;
  }
  Object.keys(deger).forEach(function (a) {
    if (!S[a] || deger[a] === '' || deger[a] === undefined) return;
    if (!hucreBos_(sh, r, S[a])) return;                        // hiçbir dolu hücrenin üstüne yazılmaz
    sh.getRange(r, S[a]).setValue(deger[a]);
  });
  kayitYaz_(no, { 'Tür': tur, 'Konu': deger.konu, 'Tabloya yazıldı': 'Evet', 'Tablo satırı': r });
}

/** PDF linki: yalnızca sistemin kendi eklediği satıra ve hücre boşsa */
function evrakTablosunaLink_(no, kayit, link) {
  kayit = kayitBul_(no);
  if (kayit.tablo !== 'Evet' || !kayit.tabloSatiri) return;
  var sh = hedefSekme_(kayit.tur), e = eslesme_(sh, kayit.tur);
  if (!e.sutunlar.dosya) return;
  var r = Number(kayit.tabloSatiri);
  if (e.sutunlar.kayitNo && String(sh.getRange(r, e.sutunlar.kayitNo).getDisplayValue()).trim() !== String(no)) return;
  if (hucreBos_(sh, r, e.sutunlar.dosya)) sh.getRange(r, e.sutunlar.dosya).setValue(link);
}

// ---------------------------------------------------------------- deneme

function notBolmeDenemesi() {
  var p = [
    { ad: 'Ali DAĞLI', takma: ['Ali'] }, { ad: 'Zeynep YILMAZ', takma: ['Zeynep'] }
  ];
  Logger.log(JSON.stringify(notuBol('Ali: ulubey e rapor yazısını ilgi tutup acil yazalım', p)));
  Logger.log(JSON.stringify(notuBol('ali şu tabloyu doldursun, zeynep de toplantı tutanağını hazırlasın', p)));
  Logger.log(JSON.stringify(notuBol('Bilginize, dosyalansın', p)));
}

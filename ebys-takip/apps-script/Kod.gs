/**
 * Kalite Koordinatörlüğü — EBYS Görev Takip
 * Google Sheets'e bağlı Apps Script. Sayfalar: Görevler, Personel, Ayarlar.
 *  - doGet  : takip paneli (yalnızca Personel listesindeki kurumsal hesaplar)
 *  - doPost : tarayıcı betiğinden gelen EBYS görevleri ve PDF'ler (gizli anahtarla)
 */

var SAYFA = { GOREV: 'Görevler', PERSONEL: 'Personel', AYAR: 'Ayarlar' };

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
    ['ISLEMDE_KLASOR_ID', '', 'EBYS PDF\'lerinin ilk konduğu Drive klasörünün ID\'si (adres çubuğundaki /folders/ sonrası).'],
    ['TAMAMLANAN_KLASOR_ID', '', 'Görev tamamlanınca PDF\'in taşınacağı klasör. Boşsa yerinde kalır.'],
    ['AY_ALT_KLASORU', 'EVET', 'EVET ise tamamlananlar 2026-11 gibi ay klasörlerine ayrılır.'],
    ['EPOSTA_BILDIRIM', 'EVET', 'EVET ise görev atanınca kişiye e-posta gider.'],
    ['ALAN_ADI', 'usak.edu.tr', 'Panele yalnızca bu alan adındaki hesaplar girebilir.']
  ];
  var mevcut = a.getDataRange().getValues().map(function (r) { return r[0]; });
  varsayilan.forEach(function (v) { if (mevcut.indexOf(v[0]) < 0) a.appendRow(v); });

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
    if (it.evrakNo && !dosyaVar && (yeni || !evrakDosyasi_(it.evrakNo))) dosyaIstenen.push(it.evrakNo);
  });
  return { tamam: true, eklenen: eklenen, dosyaIstenen: dosyaIstenen };
}

function evrakDosyasi_(evrakNo) {
  var g = gorevler_().filter(function (x) { return String(x['Evrak No']) === String(evrakNo) && x.Dosya; })[0];
  return g ? g.Dosya : '';
}

/** veri: {evrakNo, dosyaAdi, mime, base64} */
function dosyaAl_(veri) {
  var klasorId = ayar_('ISLEMDE_KLASOR_ID');
  if (!klasorId) throw new Error('Ayarlar sayfasında ISLEMDE_KLASOR_ID boş');
  var mevcutLink = evrakDosyasi_(veri.evrakNo);
  if (mevcutLink) return { tamam: true, link: mevcutLink, zatenVardi: true };
  var blob = Utilities.newBlob(Utilities.base64Decode(veri.base64), veri.mime || 'application/pdf',
    '[' + veri.evrakNo + '] ' + (veri.dosyaAdi || 'evrak.pdf'));
  var dosya = DriveApp.getFolderById(klasorId).createFile(blob);
  var link = dosya.getUrl();
  var sh = SpreadsheetApp.getActive().getSheetByName(SAYFA.GOREV);
  gorevler_().forEach(function (g) {
    if (String(g['Evrak No']) === String(veri.evrakNo)) sh.getRange(g._satir, sutun_('Dosya')).setValue(link);
  });
  return { tamam: true, link: link };
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
      dosyayiTasi_(g);
    }
    if (alanlar.Durum && alanlar.Durum !== 'Tamamlandı' && g.Durum === 'Tamamlandı') {
      sh.getRange(g._satir, sutun_('Tamamlanma')).setValue('');
      sh.getRange(g._satir, sutun_('Tamamlayan')).setValue('');
    }
  } finally { kilit.releaseLock(); }
  return panelVerisi();
}

/** Aynı evrakın bütün görevleri tamamlanınca PDF hedef klasöre taşınır. */
function dosyayiTasi_(g) {
  var hedefId = ayar_('TAMAMLANAN_KLASOR_ID');
  if (!hedefId || !g.Dosya || !g['Evrak No']) return;
  var acik = gorevler_().filter(function (x) {
    return String(x['Evrak No']) === String(g['Evrak No']) && x.ID !== g.ID &&
      x.Durum !== 'Tamamlandı' && x.Durum !== 'İptal';
  });
  if (acik.length) return;
  var m = String(g.Dosya).match(/[-\w]{25,}/);
  if (!m) return;
  try {
    var dosya = DriveApp.getFileById(m[0]);
    var hedef = DriveApp.getFolderById(hedefId);
    if (ayar_('AY_ALT_KLASORU') === 'EVET') {
      var ay = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM');
      var it = hedef.getFoldersByName(ay);
      hedef = it.hasNext() ? it.next() : hedef.createFolder(ay);
    }
    dosya.moveTo(hedef);
  } catch (e) { /* dosya silinmiş ya da yetki yoksa görev yine tamamlanır */ }
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

// ---------------------------------------------------------------- deneme

function notBolmeDenemesi() {
  var p = [
    { ad: 'Ali DAĞLI', takma: ['Ali'] }, { ad: 'Zeynep YILMAZ', takma: ['Zeynep'] }
  ];
  Logger.log(JSON.stringify(notuBol('Ali: ulubey e rapor yazısını ilgi tutup acil yazalım', p)));
  Logger.log(JSON.stringify(notuBol('ali şu tabloyu doldursun, zeynep de toplantı tutanağını hazırlasın', p)));
  Logger.log(JSON.stringify(notuBol('Bilginize, dosyalansın', p)));
}

/**
 * Kalite Koordinatörlüğü — EBYS Görev Takip
 * Google Sheets'e bağlı Apps Script. Sayfalar: Görevler, Personel, Ayarlar.
 *  - doGet  : takip paneli (yalnızca Personel listesindeki kurumsal hesaplar)
 *  - doPost : tarayıcı betiğinden gelen EBYS görevleri ve PDF'ler (gizli anahtarla)
 */

var SAYFA = { GOREV: 'Görevler', ARSIV: 'Tamamlananlar', PERSONEL: 'Personel', AYAR: 'Ayarlar', KAYIT: 'Aktarım Kaydı' };
var BITMIS = ['Tamamlandı', 'İptal'];
var KAYIT_SUTUN = ['Evrak No', 'Tür', 'Konu', 'Tabloya yazıldı', 'Tablo satırı', 'Drive dosyası', 'Tarih', 'Not', 'İlgi', 'Cevap'];

var GOREV_SUTUN = [
  // görünen sütunlar
  'Evrak No', 'Evrak Tarihi', 'Konu', 'Hocanın Notu', 'İlgi', 'Sorumlu', 'Durum', 'Açıklama', 'Dosya', 'Eklenme',
  // gizli (sistemin kullandığı) sütunlar
  'ID', 'Kaynak', 'Gönderen', 'Not Yazan', 'Not Tarihi', 'Görev', 'Son Tarih', 'Ekleyen',
  'Tamamlanma', 'Tamamlayan', 'EBYS Linki', 'Anahtar'
];
var GORUNUR = { 'Evrak No': 80, 'Evrak Tarihi': 90, 'Konu': 260, 'Hocanın Notu': 380, 'İlgi': 220, 'Sorumlu': 130,
                'Durum': 110, 'Açıklama': 220, 'Dosya': 70, 'Eklenme': 105 };
var PERSONEL_SUTUN = ['Ad Soyad', 'E-posta', 'Notta geçen adlar (virgülle)', 'Rol (Yönetici/Personel)'];
var DURUMLAR = ['Bekliyor', 'Devam Ediyor', 'Tamamlandı', 'İptal'];
var GENEL = 'Genel';

// ---------------------------------------------------------------- kurulum

function onOpen() {
  ozetGuncelleGuvenli_();
  SpreadsheetApp.getUi().createMenu('EBYS Takip')
    .addItem('Kurulum / onarım', 'kurulum')
    .addItem('Gizli anahtarı göster', 'anahtariGoster')
    .addItem('Evrak tablosu sütun eşleşmesini göster', 'eslesmeyiGoster')
    .addItem('Görünümü düzenle (renkler, gizli sütunlar, özet)', 'gorunumuDuzenle')
    .addItem('Özeti yenile', 'ozetGuncelle_')
    .addSeparator()
    .addItem('Seçili satırları tamamla', 'seciliSatirlariTamamla')
    .addToUi();
}

function kurulum() {
  var ss = SpreadsheetApp.getActive();
  gorevSayfasi_(SAYFA.GOREV);
  gorevSayfasi_(SAYFA.ARSIV);
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
    ['CEVAP_YAZILINCA_TAMAMLA', 'HAYIR', 'EVET ise bir gelen yazıya ilgi tutan giden yazı imzalanınca o gelen yazının görevleri otomatik Tamamlandı yapılır. HAYIR ise sadece Açıklama\'ya "Cevap yazıldı" notu düşülür.'],
    ['EPOSTA_BILDIRIM', 'EVET', 'EVET ise görev atanınca kişiye e-posta gider.'],
    ['ALAN_ADI', 'usak.edu.tr', 'Panele yalnızca bu alan adındaki hesaplar girebilir.']
  ];
  var mevcut = a.getDataRange().getValues().map(function (r) { return r[0]; });
  varsayilan.forEach(function (v) { if (mevcut.indexOf(v[0]) < 0) a.appendRow(v); });

  sayfaHazirla_(ss, SAYFA.KAYIT, KAYIT_SUTUN);
  bitmisleriTasi_();
  konulariEkle_();
  try { evrakTarihleriniDoldur_(); } catch (e) { /* evrak tablosuna erişilemezse geç */ }
  gorunumuDuzenle_();
  SpreadsheetApp.getUi().alert('Kurulum tamam. Şimdi Personel sayfasını doldurun, sonra Dağıt → Yeni dağıtım ile web uygulaması oluşturun.');
}

// ---------------------------------------------------------------- görünüm

function gorunumuDuzenle() {
  gorunumuDuzenle_();
  SpreadsheetApp.getUi().alert('Görünüm düzenlendi. Personel listesi değişince bunu tekrar çalıştırın (Sorumlu açılır listesi güncellenir).');
}

function harf_(ad) { return sutunHarfi_(sutun_(ad)); }

function gorunumuDuzenle_() {
  var ss = SpreadsheetApp.getActive();
  gorevSayfasiBicimle_(gorevSayfasi_(SAYFA.GOREV), '#1f4e8c');
  gorevSayfasiBicimle_(gorevSayfasi_(SAYFA.ARSIV), '#2e7d4f');
  digerSayfalar_(ss);
}

function gorevSayfasiBicimle_(g, renk) {
  var son = g.getMaxRows(), gen = GOREV_SUTUN.length;
  var veri = g.getRange(2, 1, son - 1, gen);

  // Başlık
  g.getRange(1, 1, 1, gen).setBackground('#1f4e8c').setFontColor('#ffffff').setFontWeight('bold')
    .setVerticalAlignment('middle').setWrap(true);
  g.setRowHeight(1, 34);
  g.setFrozenRows(1);

  // Satırlar tek satır kalsın: uzun not taşmaz, tamamı panelde ya da hücreye tıklayınca görünür
  veri.setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP).setVerticalAlignment('middle').setFontSize(10);
  g.setRowHeightsForced(2, son - 1, 24);

  // Sadece gerekli sütunlar görünür
  GOREV_SUTUN.forEach(function (b, i) {
    if (GORUNUR[b]) { g.showColumns(i + 1); g.setColumnWidth(i + 1, GORUNUR[b]); }
    else g.hideColumns(i + 1);
  });
  g.getRange(2, sutun_('Evrak Tarihi'), son - 1, 1).setNumberFormat('dd.mm.yyyy');
  g.getRange(2, sutun_('Eklenme'), son - 1, 1).setNumberFormat('dd.mm.yyyy hh:mm');
  ['Evrak No', 'Evrak Tarihi', 'Durum', 'Eklenme', 'Dosya'].forEach(function (b) {
    g.getRange(1, sutun_(b), son, 1).setHorizontalAlignment('center');
  });

  // Açılır listeler
  g.getRange(2, sutun_('Durum'), son - 1, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(DURUMLAR, true).build());
  var kisiler = [GENEL].concat(personel_().map(function (p) { return p.ad; }));
  g.getRange(2, sutun_('Sorumlu'), son - 1, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(kisiler, true).setAllowInvalid(true).build());

  // Renkler (virgülsüz formüller: Türkçe dil ayarında da çalışır)
  var K = '$' + harf_('Durum') + '2', J = '$' + harf_('Sorumlu') + '2';
  var tumu = g.getRange(2, 1, son - 1, gen);
  var kurallar = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=' + K + '="Tamamlandı"')
      .setBackground('#eef7f0').setFontColor('#7a8a80').setRanges([tumu]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=' + K + '="İptal"')
      .setFontColor('#a0a0a0').setStrikethrough(true).setRanges([tumu]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=' + K + '="Devam Ediyor"')
      .setBackground('#fff6dd').setRanges([g.getRange(2, sutun_('Durum'), son - 1, 1)]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=' + J + '="' + GENEL + '"')
      .setFontColor('#b7791f').setBold(true).setRanges([g.getRange(2, sutun_('Sorumlu'), son - 1, 1)]).build()
  ];
  g.setConditionalFormatRules(kurallar);
  if (!g.getFilter()) g.getRange(1, 1, son, gen).createFilter();
  g.setTabColor(renk);
}

function digerSayfalar_(ss) {
  var a = ss.getSheetByName(SAYFA.AYAR);
  a.setColumnWidth(1, 210); a.setColumnWidth(2, 330); a.setColumnWidth(3, 520);
  a.getRange(1, 1, a.getMaxRows(), 3).setVerticalAlignment('top');
  a.getRange(1, 3, a.getMaxRows(), 1).setWrap(true).setFontColor('#6b7488');
  a.setTabColor('#9aa5b8');
  var p = ss.getSheetByName(SAYFA.PERSONEL);
  [170, 230, 260, 170].forEach(function (w, i) { p.setColumnWidth(i + 1, w); });
  p.setTabColor('#2e7d4f');
  var k = kayitSayfasi_();
  [80, 60, 260, 130, 90, 260, 130, 300].forEach(function (w, i) { k.setColumnWidth(i + 1, w); });
  k.getRange(2, 1, k.getMaxRows() - 1, KAYIT_SUTUN.length).setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);
  k.setTabColor('#9aa5b8');

  ozetSayfasi_(ss);
  // Sıra: Özet, Görevler, Tamamlananlar, Personel, Ayarlar, Aktarım Kaydı
  [ 'Özet', SAYFA.GOREV, SAYFA.ARSIV, SAYFA.PERSONEL, SAYFA.AYAR, SAYFA.KAYIT ].forEach(function (ad, i) {
    var sh = ss.getSheetByName(ad);
    if (sh) { ss.setActiveSheet(sh); ss.moveActiveSheet(i + 1); }
  });
  ss.setActiveSheet(ss.getSheetByName('Özet'));
}

/** Özet sayfasının iskeleti. Sayıları ozetGuncelle_ yazar (formül yok: dil ayarından etkilenmez). */
function ozetSayfasi_(ss) {
  var o = ss.getSheetByName('Özet') || ss.insertSheet('Özet');
  o.getRange(1, 1, o.getMaxRows(), o.getMaxColumns()).breakApart();
  o.clear(); o.clearConditionalFormatRules();
  o.setHiddenGridlines(true);

  o.getRange('A1').setValue('Kalite Koordinatörlüğü · Görev Takip').setFontSize(18).setFontWeight('bold').setFontColor('#1f4e8c');
  var url = ScriptApp.getService().getUrl();
  o.getRange('A2').setValue(url ? 'Günlük kullanım için paneli açın: ' + url : 'Panel adresi: Dağıt → Dağıtımları yönet → Panel')
    .setFontColor('#6b7488');

  // Kartlar: A | B-D | F | G-J (E boşluk sütunu)
  var kartlar = [['Açık görev', '#1f4e8c'], ['Bugün gelen', '#c0392b'], ['Atanmamış', '#b7791f'], ['Bu ay tamamlanan', '#2e7d4f']];
  OZET_KART.forEach(function (y, i) {
    var c = y[0], n = y[1];
    var ust = o.getRange(4, c, 1, n), alt = o.getRange(5, c, 1, n);
    if (n > 1) { ust.merge(); alt.merge(); }
    ust.setValue(kartlar[i][0]).setFontColor('#6b7488').setFontSize(10);
    alt.setFontSize(26).setFontWeight('bold').setFontColor(kartlar[i][1]).setHorizontalAlignment('left');
    o.getRange(4, c, 2, n).setBackground('#f3f6fb').setBorder(true, true, true, true, false, false, '#d6dde8', SpreadsheetApp.BorderStyle.SOLID);
  });
  o.setRowHeight(5, 46);

  o.getRange('A7:D7').setValues([['Kişi', 'Açık', 'Bugün gelen', 'Bu ay biten']])
    .setBackground('#1f4e8c').setFontColor('#ffffff').setFontWeight('bold');
  o.getRange('B7:D40').setHorizontalAlignment('center');
  o.getRange('F7:K7').setValues([['Konu', 'Hocanın notu (açık işler, en yeni üstte)', 'Sorumlu', 'Durum', 'Evrak tarihi', 'Evrak no']])
    .setBackground('#1f4e8c').setFontColor('#ffffff').setFontWeight('bold');
  o.getRange('J8:J40').setNumberFormat('dd.mm.yyyy');
  o.getRange('F8:K40').setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP).setFontSize(10);
  o.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule().whenNumberGreaterThan(0).setFontColor('#c0392b').setBold(true)
      .setRanges([o.getRange('C8:C40')]).build()   // bugün gelen varsa kırmızı
  ]);
  [150, 70, 85, 85, 24, 230, 340, 125, 100, 85, 70].forEach(function (w, i) { o.setColumnWidth(i + 1, w); });
  o.getRange('A1:H3').setWrapStrategy(SpreadsheetApp.WrapStrategy.OVERFLOW);
  o.setTabColor('#c0392b');
  ozetGuncelle_();
}

var OZET_KART = [[1, 1], [2, 3], [6, 1], [7, 4]];

/** Özet sayılarını hesaplayıp yazar. Görev eklenince, değişince ve tablo açılınca çağrılır. */
function ozetGuncelle_() {
  var o = SpreadsheetApp.getActive().getSheetByName('Özet');
  if (!o) return;
  var hepsi = gorevler_();
  var bugun = new Date(); bugun.setHours(0, 0, 0, 0);
  var ayBas = new Date(bugun.getFullYear(), bugun.getMonth(), 1);
  var acikMi = function (g) { return g._sayfa === SAYFA.GOREV && BITMIS.indexOf(String(g.Durum)) < 0; };
  var bugunGelen = function (g) { return acikMi(g) && g['Eklenme'] instanceof Date && g['Eklenme'] >= bugun; };
  var buAy = function (g) { return g.Durum === 'Tamamlandı' && g.Tamamlanma instanceof Date && g.Tamamlanma >= ayBas; };
  var acik = hepsi.filter(acikMi);

  var sayilar = [acik.length, hepsi.filter(bugunGelen).length,
    acik.filter(function (g) { return g.Sorumlu === GENEL; }).length, hepsi.filter(buAy).length];
  OZET_KART.forEach(function (y, i) { o.getRange(5, y[0]).setValue(sayilar[i]); });

  var kisiler = [GENEL].concat(personel_().map(function (p) { return p.ad; }));
  o.getRange('A8:D40').clearContent();
  var satirlar = kisiler.slice(0, 33).map(function (k) {
    var benim = hepsi.filter(function (g) { return g.Sorumlu === k; });
    return [k, benim.filter(acikMi).length, benim.filter(bugunGelen).length, benim.filter(buAy).length];
  });
  if (satirlar.length) o.getRange(8, 1, satirlar.length, 4).setValues(satirlar);

  o.getRange('F8:K40').clearContent();
  var liste = acik.slice().sort(function (a, b) {
    var ta = a['Eklenme'] instanceof Date ? a['Eklenme'].getTime() : 0;
    var tb = b['Eklenme'] instanceof Date ? b['Eklenme'].getTime() : 0;
    return tb - ta;
  }).slice(0, 33).map(function (g) {
    return [g.Konu || konusuzGorev_(g), g['Hocanın Notu'] || konusuzGorev_(g), g.Sorumlu, g.Durum, g['Evrak Tarihi'] || '', g['Evrak No']];
  });
  if (liste.length) o.getRange(8, 6, liste.length, 6).setValues(liste);
  else o.getRange('F8').setValue('Açık iş yok');

  o.getRange('A3').setValue('Son güncelleme: ' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd.MM.yyyy HH:mm'))
    .setFontColor('#9aa5b8').setFontSize(9);
}

function ozetGuncelleGuvenli_() { try { ozetGuncelle_(); } catch (e) { /* özet yenilenemese de iş devam etsin */ } }

function anahtariGoster() {
  SpreadsheetApp.getUi().alert('Gizli anahtar:\n\n' + ayar_('GIZLI_ANAHTAR'));
}

/** Görevler / Tamamlananlar sayfası; sütun sırası eskiyse önce veriyi bozmadan yeni sıraya taşır */
function gorevSayfasi_(ad) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(ad);
  if (!sh) return sayfaHazirla_(ss, ad, GOREV_SUTUN);
  onbellek_('duzen_' + ad, function () { sutunlariDuzenle_(sh); return true; });
  return sh;
}

function sutunlariDuzenle_(sh) {
  var v = sh.getDataRange().getValues();
  var bas = v[0].map(function (x) { return String(x).trim(); });
  if (GOREV_SUTUN.every(function (b, i) { return bas[i] === b; })) return;
  if (sh.getFilter()) sh.getFilter().remove();
  var yeni = v.map(function (r, i) {
    if (i === 0) return GOREV_SUTUN.slice();
    return GOREV_SUTUN.map(function (b) { var j = bas.indexOf(b); return j >= 0 ? r[j] : ''; });
  }).filter(function (r, i) { return i === 0 || r.some(function (x) { return x !== ''; }); });
  if (sh.getMaxColumns() < GOREV_SUTUN.length) sh.insertColumnsAfter(sh.getMaxColumns(), GOREV_SUTUN.length - sh.getMaxColumns());
  var tum = sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns());
  sh.showColumns(1, sh.getMaxColumns());
  tum.clearDataValidations();
  tum.clearContent();
  sh.clearConditionalFormatRules();
  sh.getRange(1, 1, yeni.length, GOREV_SUTUN.length).setValues(yeni);
}

function sayfaHazirla_(ss, ad, basliklar) {
  var sh = ss.getSheetByName(ad) || ss.insertSheet(ad);
  sh.getRange(1, 1, 1, basliklar.length).setValues([basliklar]).setFontWeight('bold').setBackground('#e8eef7');
  sh.setFrozenRows(1);
  return sh;
}

// ---------------------------------------------------------------- yardımcılar

function sutun_(ad) { return GOREV_SUTUN.indexOf(ad) + 1; }

// Bir çalıştırma boyunca aynı sayfayı tekrar tekrar okumamak için
var _ONB = {};
function onbellek_(ad, fn) { if (!(ad in _ONB)) _ONB[ad] = fn(); return _ONB[ad]; }
function onbellekSil_(ad) { delete _ONB[ad]; }

function ayarSatirlari_() {
  return onbellek_('ayar', function () {
    return SpreadsheetApp.getActive().getSheetByName(SAYFA.AYAR).getDataRange().getValues();
  });
}

function ayar_(ad) {
  var v = ayarSatirlari_();
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

function personel_() { return onbellek_('personel', personelOku_); }

function personelOku_() {
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
      yonetici: /yönetici/i.test(String(v[i][3] || '')),
      ortak: /ortak/i.test(String(v[i][3] || ''))          // kalite@ gibi birkaç kişinin kullandığı hesap
    });
  }
  return liste;
}

/** Açık görevler (Görevler) + biten görevler (Tamamlananlar); her kayıt hangi sayfa ve satırda olduğunu bilir */
function gorevler_() {
  var ss = SpreadsheetApp.getActive(), out = [];
  [SAYFA.GOREV, SAYFA.ARSIV].forEach(function (ad) {
    var sh = gorevSayfasi_(ad);
    var v = sh.getDataRange().getValues(), idc = sutun_('ID') - 1;
    for (var i = 1; i < v.length; i++) {
      if (!v[i][idc]) continue;
      var o = { _satir: i + 1, _sayfa: ad };
      GOREV_SUTUN.forEach(function (b, j) { o[b] = v[i][j]; });
      out.push(o);
    }
  });
  return out;
}

/** Satırı 2. satıra (en üste) ekler; biçim ve açılır listeler alttaki satırdan kopyalanır */
function ustSatiraYaz_(sh, degerler) {
  var n = degerler.length;
  sh.insertRowBefore(2);
  if (sh.getMaxRows() >= 3) {
    var kaynak = sh.getRange(3, 1, 1, n), hedef = sh.getRange(2, 1, 1, n);
    kaynak.copyTo(hedef, SpreadsheetApp.CopyPasteType.PASTE_FORMAT, false);
    kaynak.copyTo(hedef, SpreadsheetApp.CopyPasteType.PASTE_DATA_VALIDATION, false);
  }
  sh.getRange(2, 1, 1, n).setValues([degerler]);
}

/** Görevi diğer sayfaya taşır (en üste) */
function tasi_(sayfaAdi, satir, hedefAdi) {
  var ss = SpreadsheetApp.getActive();
  var kaynak = gorevSayfasi_(sayfaAdi), hedef = gorevSayfasi_(hedefAdi);
  var v = kaynak.getRange(satir, 1, 1, GOREV_SUTUN.length).getValues()[0];
  ustSatiraYaz_(hedef, v);
  kaynak.deleteRow(satir);
}

/** Durum değişince: biten görev Tamamlananlar'a, yeniden açılan Görevler'e */
function durumaGoreTasi_(sayfaAdi, satir, durum, kim) {
  var sh = SpreadsheetApp.getActive().getSheetByName(sayfaAdi);
  var bitti = BITMIS.indexOf(durum) >= 0;
  if (sayfaAdi === SAYFA.GOREV && bitti) {
    if (durum === 'Tamamlandı') {
      if (!sh.getRange(satir, sutun_('Tamamlanma')).getValue()) sh.getRange(satir, sutun_('Tamamlanma')).setValue(new Date());
      if (kim && !sh.getRange(satir, sutun_('Tamamlayan')).getValue()) sh.getRange(satir, sutun_('Tamamlayan')).setValue(kim);
    }
    tasi_(sayfaAdi, satir, SAYFA.ARSIV);
  } else if (sayfaAdi === SAYFA.ARSIV && durum && !bitti) {
    sh.getRange(satir, sutun_('Tamamlanma')).setValue('');
    sh.getRange(satir, sutun_('Tamamlayan')).setValue('');
    tasi_(sayfaAdi, satir, SAYFA.GOREV);
  }
}

/** Kurulumda: Görevler'de kalmış biten görevleri arşive taşı */
function bitmisleriTasi_() {
  var sh = gorevSayfasi_(SAYFA.GOREV);
  var v = sh.getDataRange().getValues();
  for (var i = v.length - 1; i >= 1; i--) {
    if (v[i][sutun_('ID') - 1] && BITMIS.indexOf(String(v[i][sutun_('Durum') - 1])) >= 0) tasi_(SAYFA.GOREV, i + 1, SAYFA.ARSIV);
  }
}

/** Tabloda "Durum" elle değiştirilince de taşı */
/** Tabloda "Durum" elle değiştirilince taşı. Birden çok satıra birden yapıştırma da desteklenir. */
function onEdit(e) {
  try {
    var sh = e.range.getSheet(), ad = sh.getName();
    if (ad !== SAYFA.GOREV && ad !== SAYFA.ARSIV) return;
    var dc = sutun_('Durum'), r = e.range;
    if (r.getColumn() > dc || r.getLastColumn() < dc || r.getLastRow() < 2) { ozetGuncelleGuvenli_(); return; }
    var bas = Math.max(2, r.getRow()), n = r.getLastRow() - bas + 1;
    var durumlar = sh.getRange(bas, dc, n, 1).getValues();
    var idler = sh.getRange(bas, sutun_('ID'), n, 1).getValues();
    var kim = kimAdi_();
    for (var i = n - 1; i >= 0; i--) {                         // alttan yukarı: satır silinince üsttekiler kaymaz
      if (idler[i][0]) durumaGoreTasi_(ad, bas + i, String(durumlar[i][0] || ''), kim);
    }
    ozetGuncelleGuvenli_();
  } catch (err) { /* elle düzenlemeyi engellemesin */ }
}

function kimAdi_() {
  var eposta = String(Session.getActiveUser().getEmail() || '').toLowerCase();
  var p = personel_().filter(function (x) { return x.eposta === eposta; })[0];
  return p ? p.ad : eposta;
}

/** Menü: Görevler'de seçili satırları "Tamamlandı" yap ve Tamamlananlar'a taşı */
function seciliSatirlariTamamla() {
  var ss = SpreadsheetApp.getActive(), sh = ss.getActiveSheet(), ui = SpreadsheetApp.getUi();
  if (sh.getName() !== SAYFA.GOREV) { ui.alert('Önce Görevler sekmesinde tamamlanacak satırları seçin.'); return; }
  var satirlar = {};
  var secim = sh.getActiveRangeList() ? sh.getActiveRangeList().getRanges() : [sh.getActiveRange()];
  secim.forEach(function (r) { for (var i = Math.max(2, r.getRow()); i <= r.getLastRow(); i++) satirlar[i] = true; });
  var liste = Object.keys(satirlar).map(Number).filter(function (i) { return sh.getRange(i, sutun_('ID')).getValue(); });
  if (!liste.length) { ui.alert('Seçili satırlarda görev yok.'); return; }
  if (ui.alert(liste.length + ' görev Tamamlandı yapılıp Tamamlananlar sekmesine taşınsın mı?', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var kilit = LockService.getScriptLock(); kilit.waitLock(30000);
  try {
    var kim = kimAdi_();
    liste.sort(function (a, b) { return b - a; }).forEach(function (i) {
      sh.getRange(i, sutun_('Durum')).setValue('Tamamlandı');
      durumaGoreTasi_(SAYFA.GOREV, i, 'Tamamlandı', kim);
    });
    ozetGuncelleGuvenli_();
  } finally { kilit.releaseLock(); }
}

/** Panel: seçilen görevleri topluca tamamla */
function topluTamamla(idler, kimAdi) {
  var ben = islemYapan_(yetkiKontrol_(), kimAdi);
  var kilit = LockService.getScriptLock(); kilit.waitLock(30000);
  try {
    var sec = {}; (idler || []).forEach(function (x) { sec[x] = true; });
    var ss = SpreadsheetApp.getActive();
    gorevler_().filter(function (g) { return sec[g.ID] && g._sayfa === SAYFA.GOREV; })
      .sort(function (a, b) { return b._satir - a._satir; })
      .forEach(function (g) {
        ss.getSheetByName(SAYFA.GOREV).getRange(g._satir, sutun_('Durum')).setValue('Tamamlandı');
        durumaGoreTasi_(SAYFA.GOREV, g._satir, 'Tamamlandı', ben.ad);
      });
    ozetGuncelleGuvenli_();
  } finally { kilit.releaseLock(); }
  return panelVerisi();
}

function tarihYazi_(d) {
  if (!(d instanceof Date)) return d ? String(d) : '';
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
}

var KONU_AYRAC = ' → ';
/** "MEDEK Ödemesi Hk. → acil yazalım" */
function konuluGorev_(konu, metin) {
  konu = String(konu || '').trim(); metin = String(metin || '').trim();
  if (!konu) return metin;
  if (!metin || metin === konu) return konu;
  return metin.indexOf(konu + KONU_AYRAC) === 0 ? metin : konu + KONU_AYRAC + metin;
}
/** Görev metninden baştaki konuyu çıkarır (konu ayrı gösterildiğinde tekrar etmesin) */
function konusuzGorev_(g) {
  var m = String(g['Görev'] || ''), k = String(g.Konu || '');
  return k && m.indexOf(k + KONU_AYRAC) === 0 ? m.slice(k.length + KONU_AYRAC.length) : m;
}

/** Kurulumda: Evrak Tarihi boş olan görevleri gelen-giden evrak tablosundan (evrak no ile) doldur */
function evrakTarihleriniDoldur_() {
  var bos = gorevler_().filter(function (g) { return g['Evrak No'] && !g['Evrak Tarihi']; });
  if (!bos.length) return;
  var tarih = {};
  ['Gelen', 'Giden'].forEach(function (tur) {
    try {
      var sh = hedefSekme_(tur), e = eslesme_(sh, tur), S = e.sutunlar;
      var tc = S.evrakTarihi || S.kayitTarihi;
      if (!S.kayitNo || !tc || sh.getLastRow() <= e.basSatir) return;
      var n = sh.getLastRow() - e.basSatir;
      var nolar = sh.getRange(e.basSatir + 1, S.kayitNo, n, 1).getDisplayValues();
      var tarihler = sh.getRange(e.basSatir + 1, tc, n, 1).getValues();
      nolar.forEach(function (r, i) {
        var no = String(r[0]).trim(), t = tarihler[i][0];
        if (no && !tarih[no]) tarih[no] = t instanceof Date ? t : trTarih_(t);
      });
    } catch (err) { /* o sekme okunamadıysa diğerine geç */ }
  });
  var ss = SpreadsheetApp.getActive();
  bos.forEach(function (g) {
    var t = tarih[String(g['Evrak No']).trim()];
    if (t) ss.getSheetByName(g._sayfa).getRange(g._satir, sutun_('Evrak Tarihi')).setValue(t);
  });
}

/** Kurulumda: eski EBYS görevlerinin metnine konuyu ekle */
function konulariEkle_() {
  var ss = SpreadsheetApp.getActive();
  gorevler_().forEach(function (g) {
    if (g.Kaynak !== 'EBYS' || !g.Konu) return;
    var yeni = konuluGorev_(g.Konu, g['Görev']);
    if (yeni !== g['Görev']) ss.getSheetByName(g._sayfa).getRange(g._satir, sutun_('Görev')).setValue(yeni);
  });
}

function yeniId_() { return 'G' + Utilities.formatDate(new Date(), 'GMT', 'yyMMdd') + '-' + Utilities.getUuid().slice(0, 4); }

/** Kaydı Görevler sayfasına ekler, ID döner. */
function gorevYaz_(o) {
  var sh = gorevSayfasi_(SAYFA.GOREV);
  o.ID = o.ID || yeniId_();
  o.Durum = o.Durum || 'Bekliyor';
  o['Eklenme'] = new Date();
  ustSatiraYaz_(sh, GOREV_SUTUN.map(function (b) { return o[b] === undefined ? '' : o[b]; }));
  return o.ID;
}

// ---------------------------------------------------------------- not ayrıştırma

/** İsimden sonraki metin, ismin görev alan değil sadece adı geçen kişi olduğunu gösteriyor mu */
function bahsediliyor_(sonrasi) {
  if (/^['’`´]\s*[a-z]/.test(sonrasi)) return true;                         // Berker'in, Ali'ye
  return /^\s+(hoca|bey|hanim|hn)(n?in|n?un|y?a|y?e|y?i|y?u|dan|den|tan|ten|yla|yle|la|le|m?in|ma|me|mi|si|su|lar)(?![a-z0-9])/.test(sonrasi);
}

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
  // "berker hocanın işini", "zeynep hanıma sor", "Ali'nin yazısı": kişiden bahsediliyor, görev verilmiyor
  bulunan = bulunan.filter(function (b) { return !bahsediliyor_(k.slice(b.son)); });
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
      .replace(/^\s*(bey|hanım|hn\.?|hoca|hocam)(?=[\s:,]|$)/i, '')
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

  liste.slice().reverse().forEach(function (it) {
    try { if (it.evrak && it.evrakNo) evrakTablosunaYaz_(it); } catch (e) { kayitNotu_(it.evrakNo, 'Tabloya yazılamadı: ' + e.message); }
    var ilgiNo = [];
    try { ilgiNo = ilgiBagla_(it, it.evrak && it.evrak.tur === 'Giden' ? 'Giden' : 'Gelen'); } catch (e) { kayitNotu_(it.evrakNo, 'İlgi bağlanamadı: ' + e.message); }
    if (it.sadeceKayit) {                                   // kendi yazdığımız, imzalanmış yazı: görev açılmaz
      if (it.evrakNo && !kayitBul_(it.evrakNo).dosya) dosyaIstenen.push(it.evrakNo);
      return;
    }
    var konu = (it.evrak && it.evrak.konu) || it.konu || '';
    var notlar = (it.notlar && it.notlar.length) ? it.notlar : [{ yazan: '', tarih: '', metin: '' }];
    var dosyaVar = false, yeni = false;
    notlar.forEach(function (n) {
      var anahtar = (it.evrakNo || it.link) + '|' + (n.yazan || '') + '|' + (n.tarih || '');
      if (mevcut[anahtar]) { if (mevcut[anahtar].Dosya) dosyaVar = true; return; }
      var parcalar = n.metin ? notuBol(n.metin, personel) : [{ kisi: GENEL, metin: it.gorevAdi || '' }];
      parcalar.forEach(function (p, i) {
        var id = gorevYaz_({
          'Kaynak': 'EBYS', 'Evrak No': it.evrakNo || '', 'Konu': konu, 'Gönderen': it.gonderen || '',
          'Evrak Tarihi': it.evrak ? trTarih_(it.evrak.evrakTarihi || it.evrak.kayitTarihi) : '',
          'İlgi': ilgiNo.length ? ilgiYazisi_(ilgiNo) : '',
          'Not Yazan': n.yazan || '', 'Not Tarihi': n.tarih || '', 'Hocanın Notu': n.metin || '',
          'Görev': konuluGorev_(konu, p.metin), 'Sorumlu': p.kisi, 'Ekleyen': kullanici || 'EBYS betiği',
          'EBYS Linki': it.link || '', 'Anahtar': i === 0 ? anahtar : anahtar + '#' + i
        });
        if (i === 0) mevcut[anahtar] = { Dosya: '' };
        if (p.kisi !== GENEL) bildir_(p.kisi, id, konu, p.metin, personel);
        eklenen++;
      });
      yeni = true;
    });
    if (it.evrakNo && !dosyaVar && !kayitBul_(it.evrakNo).dosya) dosyaIstenen.push(it.evrakNo);
  });
  if (eklenen) ozetGuncelleGuvenli_();
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
  var ss = SpreadsheetApp.getActive();
  gorevler_().forEach(function (g) {
    if (String(g['Evrak No']) === String(veri.evrakNo) && !g.Dosya) ss.getSheetByName(g._sayfa).getRange(g._satir, sutun_('Dosya')).setValue(link);
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
    var eposta = String(Session.getActiveUser().getEmail() || '');
    var sahip = String(Session.getEffectiveUser().getEmail() || '');
    var neden = eposta
      ? 'Algılanan hesap: <b>' + eposta + '</b><br>Bu adres Personel sekmesinde yok. Personel sekmesindeki E-posta sütununa ' +
        'bu adresi <b>birebir</b> yazın, sonra bu sayfayı yenileyin.'
      : 'Google, giriş yapan hesabın adresini panele iletmedi.<br>Panelin sahibi: <b>' + sahip + '</b><br>' +
        'Sahip kişisel bir hesapsa (gmail.com) ya da sizinle aynı kurumda değilse bu olur. Çözüm için KURULUM.md → "Panel açılmıyor" bölümüne bakın.';
    return HtmlService.createHtmlOutput('<div style="font-family:sans-serif;padding:24px;line-height:1.6;max-width:640px">' +
      '<h3 style="margin-top:0">Panele giriş yapılamadı</h3>' + neden + '</div>').setTitle('Görev Takip');
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

/** Ortak hesapla girildiyse panelde seçilen kişi adına işlem yapılır */
function islemYapan_(ben, kimAdi) {
  if (ben.ortak && kimAdi && personel_().some(function (p) { return p.ad === kimAdi; })) return { ad: kimAdi, yonetici: false };
  return ben;
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
    if (g['Evrak Tarihi'] instanceof Date) o['Evrak Tarihi'] = Utilities.formatDate(g['Evrak Tarihi'], Session.getScriptTimeZone(), 'dd.MM.yyyy');
    return o;
  });
  return {
    ben: { ad: ben.ad, yonetici: ben.yonetici, ortak: !!ben.ortak },
    kisiler: personel_().filter(function (p) { return !p.ortak; }).map(function (p) { return p.ad; }),
    personel: personel_().filter(function (p) { return !p.ortak; }).map(function (p) { return p.ad; }),
    durumlar: DURUMLAR,
    gorevler: gorevler
  };
}

/** alanlar: {Durum, Sorumlu, Açıklama} */
function gorevGuncelle(id, alanlar, kimAdi) {
  var ben = islemYapan_(yetkiKontrol_(), kimAdi);
  var kilit = LockService.getScriptLock(); kilit.waitLock(30000);
  try {
    var g = gorevler_().filter(function (x) { return x.ID === id; })[0];
    if (!g) throw new Error('Görev bulunamadı: ' + id);
    var sh = SpreadsheetApp.getActive().getSheetByName(g._sayfa);
    var izinli = ['Durum', 'Sorumlu', 'Açıklama'];
    Object.keys(alanlar).forEach(function (k) {
      if (izinli.indexOf(k) < 0) return;
      var v = alanlar[k];
      sh.getRange(g._satir, sutun_(k)).setValue(v);
    });
    if (alanlar.Sorumlu && alanlar.Sorumlu !== g.Sorumlu && alanlar.Sorumlu !== GENEL) {
      bildir_(alanlar.Sorumlu, id, g.Konu, alanlar['Görev'] || g['Görev']);
    }
    if (alanlar.Durum && alanlar.Durum !== g.Durum) durumaGoreTasi_(g._sayfa, g._satir, alanlar.Durum, ben.ad);
    ozetGuncelleGuvenli_();
  } finally { kilit.releaseLock(); }
  return panelVerisi();
}

/** o: {Konu, Not, Sorumlu, Evrak Tarihi, Açıklama} */
function gorevEkle(o) {
  var ben = islemYapan_(yetkiKontrol_(), o && o.kim);
  if (!o || !String(o.Konu || '').trim()) throw new Error('Konu boş olamaz');
  var kilit = LockService.getScriptLock(); kilit.waitLock(30000);
  try {
    var id = gorevYaz_({
      'Kaynak': 'Elle', 'Konu': o.Konu, 'Hocanın Notu': o.Not || '', 'Görev': o.Not || o.Konu,
      'Sorumlu': o.Sorumlu || GENEL,
      'Evrak Tarihi': o['Evrak Tarihi'] ? new Date(o['Evrak Tarihi'] + 'T00:00:00') : '',
      'Açıklama': o['Açıklama'] || '', 'Ekleyen': ben.ad
    });
    if (o.Sorumlu && o.Sorumlu !== GENEL) bildir_(o.Sorumlu, id, o.Konu, o.Not || o.Konu);
    ozetGuncelleGuvenli_();
  } finally { kilit.releaseLock(); }
  return panelVerisi();
}

// ---------------------------------------------------------------- aktarım kaydı
// Sistemin işlediği her evrak burada tutulur. Kayıtta olan evrak tablolara bir daha yazılmaz,
// satır sonradan silinse ya da değiştirilse bile.

function kayitSayfasi_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(SAYFA.KAYIT);
  if (!sh) return sayfaHazirla_(ss, SAYFA.KAYIT, KAYIT_SUTUN);
  onbellek_('kayitBaslik', function () {
    if (sh.getRange(1, KAYIT_SUTUN.length).getValue() !== KAYIT_SUTUN[KAYIT_SUTUN.length - 1]) {
      sh.getRange(1, 1, 1, KAYIT_SUTUN.length).setValues([KAYIT_SUTUN]).setFontWeight('bold').setBackground('#e8eef7');
    }
    return true;
  });
  return sh;
}

function kayitBul_(no) {
  var v = onbellek_('kayit', function () { return kayitSayfasi_().getDataRange().getValues(); });
  for (var i = 1; i < v.length; i++) {
    if (String(v[i][0]).trim() === String(no).trim()) {
      return { satir: i + 1, tur: v[i][1], konu: v[i][2], tablo: v[i][3], tabloSatiri: v[i][4], dosya: v[i][5], ilgi: v[i][8] };
    }
  }
  return {};
}

/** Kayıt yoksa ekler; varsa yalnızca BOŞ hücreleri doldurur (Not sütunu hariç, ona eklenir). */
function kayitYaz_(no, alanlar) {
  var sh = kayitSayfasi_();
  var k = kayitBul_(no);
  onbellekSil_('kayit');
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
    if (b === 'Not' || b === 'Cevap') {
      var eski = String(hucre.getValue());
      if (eski.indexOf(alanlar[b]) < 0) hucre.setValue([eski, alanlar[b]].filter(String).join(' | '));
    }
    else if (hucre.getValue() === '') hucre.setValue(alanlar[b]);
  });
}

function kayitNotu_(no, metin) { if (no) kayitYaz_(no, { 'Not': metin }); }

// ---------------------------------------------------------------- ilgi (yazılar arası ilişki)

/** "28.10.2026 tarihli ve 381948 sayılı yazınız." / "E-88071677-100-382595 sayılı" → ['381948', '382595'] */
function ilgiNolari_(metin, haric) {
  var out = [], re = /(\d{5,7})\s*say[ıi]l[ıi]/gi, m;
  while ((m = re.exec(String(metin || ''))) !== null) {
    if (m[1] !== String(haric || '') && out.indexOf(m[1]) < 0) out.push(m[1]);
  }
  return out;
}

/** ['381948'] → "381948 – Ortak Faaliyet ve PUKÖ Adımları" (konu, sistemde kayıtlıysa) */
function ilgiYazisi_(nolar) {
  return nolar.map(function (n) {
    var k = kayitBul_(n);
    return n + (k.konu ? ' – ' + k.konu : '');
  }).join('; ');
}

/**
 * Yeni gelen/giden yazının ilgilerini işler:
 *  - Aktarım Kaydı'na ilgi yazılır
 *  - Giden yazı bir gelen yazıya cevapsa: o gelen yazının açık görevlerine "Cevap yazıldı" notu
 *    (CEVAP_YAZILINCA_TAMAMLA = EVET ise görev Tamamlandı yapılır)
 */
function ilgiBagla_(it, tur) {
  var nolar = ilgiNolari_(it.evrak && it.evrak.ilgi, it.evrakNo);
  if (!nolar.length || !it.evrakNo) return nolar;
  kayitYaz_(it.evrakNo, { 'İlgi': ilgiYazisi_(nolar) });
  if (tur !== 'Giden') return nolar;
  var not = 'Cevap yazıldı: ' + it.evrakNo + (it.evrak.kayitTarihi ? ' (' + it.evrak.kayitTarihi + ')' : '');
  var tamamla = ayar_('CEVAP_YAZILINCA_TAMAMLA') === 'EVET';
  var ss = SpreadsheetApp.getActive();
  nolar.forEach(function (n) { kayitYaz_(n, { 'Cevap': it.evrakNo }); });
  gorevler_().filter(function (g) {
    return nolar.indexOf(String(g['Evrak No'])) >= 0 && g._sayfa === SAYFA.GOREV;
  }).sort(function (a, b) { return b._satir - a._satir; }).forEach(function (g) {
    var sh = ss.getSheetByName(SAYFA.GOREV);
    var h = sh.getRange(g._satir, sutun_('Açıklama'));
    var eski = String(h.getValue());
    if (eski.indexOf(not) < 0) h.setValue([eski, not].filter(String).join(' | '));
    if (tamamla) {
      sh.getRange(g._satir, sutun_('Durum')).setValue('Tamamlandı');
      durumaGoreTasi_(SAYFA.GOREV, g._satir, 'Tamamlandı', personelAdi_(it.hazirlayan || '') || 'Cevap yazısı');
    }
  });
  return nolar;
}

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

function hedefSekme_(tur) { return onbellek_('sekme_' + tur, function () { return hedefSekmeBul_(tur); }); }

function hedefSekmeBul_(tur) {
  var ss = onbellek_('evrakTablo', function () { return SpreadsheetApp.openById(ayar_('EVRAK_TABLO_ID')); });
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
function eslesme_(sh, tur) { return onbellek_('esl_' + sh.getName() + tur, function () { return eslesmeBul_(sh, tur); }); }

function eslesmeBul_(sh, tur) {
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
  var v = ayarSatirlari_();
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
/** EBYS'deki ad soyadı Personel listesindeki yazılışa çevirir (bulamazsa olduğu gibi bırakır) */
function personelAdi_(ad) {
  var a = sade_(ad).replace(/\s+/g, ' ').trim();
  var p = personel_().filter(function (x) { return sade_(x.ad).replace(/\s+/g, ' ').trim() === a; })[0];
  return p ? p.ad : ad;
}

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
  var bak = anaSutunlar.filter(function (c) { return c !== S.sira; });
  var enSag = Math.max.apply(null, bak.concat([1]));
  for (var tur2 = 0; tur2 < 20; tur2++) {                       // 100'er satırlık bloklarla ara
    var adet = Math.max(0, Math.min(100, sh.getMaxRows() - r + 1));
    if (!adet) break;
    var blok = sh.getRange(r, 1, adet, enSag);
    var deg = blok.getValues(), form = blok.getFormulas(), bulundu = false;
    for (var j = 0; j < adet; j++) {
      if (bak.every(function (c) { return deg[j][c - 1] === '' && form[j][c - 1] === ''; })) { r += j; bulundu = true; break; }
    }
    if (bulundu) break;
    r += adet;
  }
  if (r > sh.getMaxRows()) sh.insertRowsAfter(sh.getMaxRows(), r - sh.getMaxRows());

  var sorumlular = [];
  (it.notlar || []).forEach(function (n) {
    notuBol(n.metin).forEach(function (p) { if (p.kisi !== GENEL && sorumlular.indexOf(p.kisi) < 0) sorumlular.push(p.kisi); });
  });
  if (!sorumlular.length && it.hazirlayan) sorumlular.push(personelAdi_(it.hazirlayan));
  var deger = {
    tur: tur, kayitNo: no, sayi: ev.sayi || '', evrakTarihi: trTarih_(ev.evrakTarihi || (S.kayitTarihi ? '' : ev.kayitTarihi)),
    kayitTarihi: trTarih_(ev.kayitTarihi || ev.evrakTarihi), konu: ev.konu || it.konu, yer: yerAdi_(ev.yer),
    dosyaKodu: ev.dosyaKodu || '', sorumlu: sorumlular.join(', '),
    aciklama: [(it.notlar || []).map(function (n) { return n.metin; }).filter(String).join(' / '),
               (function () { var n = ilgiNolari_(ev.ilgi, no); return n.length ? 'İlgi: ' + ilgiYazisi_(n) : ''; })()]
              .filter(String).join(' | ')
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

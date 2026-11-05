// ==UserScript==
// @name         EBYS Görev Takip (Kalite Koordinatörlüğü)
// @namespace    usak-kalite-koordinatorlugu
// @version      0.3.0
// @description  EBYS görev listesindeki yazıları ve hocanın notlarını Google Sheets takip sistemine aktarır, PDF'i Drive'a gönderir.
// @match        https://ebys.usak.edu.tr/enVision/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @connect      script.google.com
// @connect      script.googleusercontent.com
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // ------------------------------------------------------------ ayarlar
  var A = {
    get url() { return GM_getValue('url', ''); },
    get anahtar() { return GM_getValue('anahtar', ''); },
    get otomatik() { return GM_getValue('otomatik', true); },
    get yenileDk() { return GM_getValue('yenileDk', 15); },
    get gonderilen() { return GM_getValue('gonderilen', {}); }
  };

  GM_registerMenuCommand('Ayarlar: web uygulaması adresi ve anahtar', ayarla);
  GM_registerMenuCommand('Tüm sayfaları tara (bütün görev listesi)', function () { tara(true, true); });
  GM_registerMenuCommand('Listede görünenleri gönderilmiş say (eski işleri atla)', eskileriAtla);
  GM_registerMenuCommand('Gönderilmiş listesini sıfırla', function () {
    if (confirm('Gönderilmiş kayıtlar unutulsun mu? Sonraki taramada listedekiler yeniden gönderilir (aynı not iki kez eklenmez).')) {
      GM_setValue('gonderilen', {}); kutuGuncelle();
    }
  });

  function ayarla() {
    var u = prompt('Apps Script web uygulaması adresi (…/exec ile biter):', A.url);
    if (u === null) return;
    var k = prompt('Gizli anahtar (Sheets → EBYS Takip → Gizli anahtarı göster):', A.anahtar);
    if (k === null) return;
    var o = confirm('Görev listesi açılınca yeni görevler OTOMATİK gönderilsin mi?\n(Tamam = otomatik, İptal = sadece düğmeyle)');
    var d = prompt('Ana sayfa kaç dakikada bir yenilensin? (0 = yenileme yok)', String(A.yenileDk));
    GM_setValue('url', u.trim()); GM_setValue('anahtar', k.trim()); GM_setValue('otomatik', o);
    GM_setValue('yenileDk', Math.max(0, parseInt(d, 10) || 0));
    sunucu({ islem: 'kontrol' }).then(function () { alert('Bağlantı tamam.'); }, function (e) { alert('Bağlantı kurulamadı: ' + e.message); });
    kutuGuncelle();
  }

  // ------------------------------------------------------------ yardımcılar
  function bekle(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function yazi(el) {
    if (!el) return '';
    var c = el.cloneNode(true);
    c.querySelectorAll('br').forEach(function (b) { b.replaceWith('\n'); });
    return c.textContent.replace(/[ \t ]+/g, ' ').replace(/\n\s+/g, '\n').trim();
  }
  function kullanici() {
    var el = document.querySelector('.username, .username-hide-on-mobile, #ctl00_lblUserName');
    return el ? el.textContent.trim() : '';
  }

  function sunucu(veri) {
    return new Promise(function (coz, red) {
      if (!A.url || !A.anahtar) return red(new Error('Önce Tampermonkey menüsünden ayarları girin'));
      veri.anahtar = A.anahtar;
      GM_xmlhttpRequest({
        method: 'POST', url: A.url, data: JSON.stringify(veri),
        headers: { 'Content-Type': 'text/plain;charset=utf-8' }, timeout: 300000,
        onload: function (r) {
          try {
            var j = JSON.parse(r.responseText);
            if (j.hata) red(new Error(j.hata)); else coz(j);
          } catch (e) { red(new Error('Sunucu yanıtı okunamadı (' + r.status + '). Web uygulaması "Herkes" erişimine açık mı?')); }
        },
        onerror: function () { red(new Error('Ağ hatası')); },
        ontimeout: function () { red(new Error('Zaman aşımı')); }
      });
    });
  }

  // ------------------------------------------------------------ görev listesini oku
  /** Ana sayfa / görevler sayfasındaki görev satırları */
  function listeyiOku() {
    var out = [], gor = {};
    document.querySelectorAll('a[href*="DocumentModule/Task.aspx?value="]').forEach(function (a) {
      var li = a.closest('li'); if (!li) return;
      var baslik = a.textContent.replace(/\s+/g, ' ').trim();
      var m = baslik.match(/\[(\d{3,})\]/);
      var evrakNo = m ? m[1] : '';
      var konu = '';
      var p = baslik.indexOf('(');
      if (p >= 0) konu = baslik.slice(p + 1).replace(/\s*\[\d{3,}\][\s\S]*$/, '').trim();
      var gonderenEl = li.querySelector('span[title="Gönderen"]');
      var tarihEl = li.querySelector('.date');
      var o = {
        link: a.href, gorevAdi: p >= 0 ? baslik.slice(0, p).trim() : baslik, konu: konu || baslik, evrakNo: evrakNo,
        gonderen: gonderenEl ? gonderenEl.textContent.trim() : '', listeTarihi: tarihEl ? tarihEl.textContent.trim() : ''
      };
      // "Hazırlamış Olduğunuz Evrak Onaylanmıştır": kişinin kendi yazdığı yazı imzalandı.
      // Görev açılmaz; yalnızca giden tablosuna yazılır ve PDF'i Drive'a gider.
      o.sadeceKayit = /hazırlamış olduğunuz evrak onaylanmıştır/i.test(o.gorevAdi);
      o.anahtar = [o.evrakNo || o.konu, o.listeTarihi, o.gorevAdi].join('|');
      if (gor[o.anahtar]) return; gor[o.anahtar] = 1;
      if (!o.evrakNo && /^evrak sevkedildi/i.test(o.gorevAdi)) return;
      out.push(o);
    });
    return out;
  }

  // ------------------------------------------------------------ görev / evrak sayfasını oku
  /** doc: evrak sayfasının DOM'u (canlı sayfa ya da arka planda indirilmiş) */
  function notlariOku(doc) {
    var kutu = doc.getElementById('ctl00_cp_divNotes');
    if (!kutu) return [];
    var notlar = [];
    kutu.querySelectorAll('span.required').forEach(function (bas) {
      var govde = bas.nextElementSibling;
      while (govde && govde.tagName === 'BR') govde = govde.nextElementSibling;
      if (!govde || !govde.classList.contains('wwrap')) return;
      var c = govde.cloneNode(true);
      var islemEl = c.querySelector('b');
      var islem = islemEl ? islemEl.textContent.trim() : '';
      if (islemEl) islemEl.remove();
      var metin = yazi(c);
      var b = bas.textContent.trim().match(/^(.*?)\s*\(([^)]*)\)\s*$/);
      notlar.push({ yazan: b ? b[1] : bas.textContent.trim(), tarih: b ? b[2] : '', islem: islem, metin: metin });
    });
    return notlar;
  }

  function evrakNoOku(doc) {
    var el = doc.getElementById('ctl00_cp_ucCommonNumerator1_lblGetNumber_label');
    return el ? el.textContent.trim() : '';
  }

  /** Evrak tablosu için: tür, konu, tarih, sayı, geldiği/gittiği yer, dosya kodu */
  function evrakBilgisi(doc, o) {
    o = o || {};
    var statik = function (id) {
      var el = doc.querySelector('#' + id + ' .form-control-static');
      return el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
    };
    var alanlar = {};
    doc.querySelectorAll('.form-control-static').forEach(function (el) {
      var grup = el.closest('.form-group');
      var lbl = grup && grup.querySelector('label');
      var v = el.textContent.replace(/\s+/g, ' ').trim();
      if (lbl && v && !alanlar[lbl.textContent.trim()]) alanlar[lbl.textContent.trim()] = v;
    });
    var bul = function (re) {
      var k = Object.keys(alanlar).filter(function (x) { return re.test(x); })[0];
      return k ? alanlar[k] : '';
    };
    var metin = [o.gorevAdi, o.gonderen, doc.title].join(' ');
    var tur = /gönderilmiş|giden/i.test(metin) && !/gelen evrak/i.test(o.gorevAdi || '') ? 'Giden' : 'Gelen';
    var yerOku = function (onEk) {
      var parca = [];
      doc.querySelectorAll('[id^="' + onEk + '"][id$="_text_spn"], [id^="' + onEk + '"] .form-control-static').forEach(function (el) {
        var t = el.textContent.replace(/\s+/g, ' ').trim();
        if (t && !/^[\d\s.-]+$/.test(t) && parca.indexOf(t) < 0) parca.push(t);
      });
      return parca.join(' | ');   // tam zincir; birim düzeyi sunucuda seçilir
    };
    var kod = doc.getElementById('ctl00_cp_ucClassificationCode_txtControlRhea_text');
    return {
      tur: tur,
      konu: statik('ctl00_cp_txtDocumentSubject') || o.konu || '',
      kayitTarihi: statik('ctl00_cp_txtOrgDocumentDate') || bul(/kayıt tarihi/i),
      evrakTarihi: bul(/^(evrak|yazı|belge) tarihi/i),
      sayi: bul(/sayı/i),
      yer: tur === 'Giden' ? (yerOku('ctl00_cp_ucDocumentTo_') || yerOku('ctl00_cp_ucDocumentFrom_')) : yerOku('ctl00_cp_ucDocumentFrom_'),
      dosyaKodu: kod ? (kod.value || kod.textContent || '').trim() : ''
    };
  }

  function sayfaGetir(url) {
    return fetch(url, { credentials: 'include' }).then(function (r) {
      if (!r.ok) throw new Error('EBYS sayfası açılamadı (' + r.status + ')');
      return r.text().then(function (h) {
        var doc = new DOMParser().parseFromString(h, 'text/html');
        return { doc: doc, html: h, url: r.url };
      });
    });
  }

  // ------------------------------------------------------------ PDF indir
  function blobBase64(blob) {
    return new Promise(function (coz, red) {
      var fr = new FileReader();
      fr.onload = function () { coz(String(fr.result).split(',')[1]); };
      fr.onerror = red; fr.readAsDataURL(blob);
    });
  }
  function pdfMi(r) {
    var t = (r.headers.get('content-type') || '').toLowerCase();
    var d = (r.headers.get('content-disposition') || '').toLowerCase();
    return t.indexOf('pdf') >= 0 || t.indexOf('octet-stream') >= 0 || d.indexOf('attachment') >= 0;
  }

  /** 1) Görüntüleyicinin PDF adresi (hdnSrc)  2) "İndir" düğmesinin isteği */
  function pdfIndir(sayfa) {
    var doc = sayfa.doc, taban = sayfa.url;
    var src = doc.getElementById('ctl00_cp_ucDocumentViewer_hdnSrc');
    var adaylar = [];
    var dosyaAdi = 'evrak.pdf';
    if (src && src.value) {
      var m = src.value.match(/GetFile\.ashx\/([^?]+)/);
      if (m) { try { dosyaAdi = decodeURIComponent(m[1]); } catch (e) { dosyaAdi = m[1]; } }
      adaylar.push(new URL(src.value, taban).href);
      adaylar.push(new URL('/enVision/' + src.value.replace(/^(\.\.\/)+/, ''), taban).href);
    }
    var dene = function (i) {
      if (i >= adaylar.length) return postbackIndir(sayfa);
      return fetch(adaylar[i], { credentials: 'include' }).then(function (r) {
        if (r.ok && pdfMi(r)) return r.blob();
        return dene(i + 1);
      }, function () { return dene(i + 1); });
    };
    return dene(0).then(function (blob) {
      if (!blob || !blob.size) throw new Error('PDF alınamadı');
      return { blob: blob, dosyaAdi: dosyaAdi };
    });
  }

  function postbackIndir(sayfa) {
    var form = sayfa.doc.getElementById('aspnetForm');
    if (!form || !sayfa.doc.getElementById('ctl00_cp_btnView')) return Promise.resolve(null);
    var fd = new FormData();
    form.querySelectorAll('input, select, textarea').forEach(function (el) {
      if (!el.name || el.disabled) return;
      var t = (el.type || '').toLowerCase();
      if (['submit', 'button', 'image', 'file', 'reset'].indexOf(t) >= 0) return;
      if ((t === 'checkbox' || t === 'radio') && !el.checked) return;
      if (el.tagName === 'SELECT') { if (el.value) fd.append(el.name, el.value); return; }
      fd.append(el.name, el.value || '');
    });
    fd.set('__EVENTTARGET', 'ctl00$cp$btnView');
    fd.set('__EVENTARGUMENT', '');
    var hedef = new URL(form.getAttribute('action') || sayfa.url, sayfa.url).href;
    return fetch(hedef, { method: 'POST', body: fd, credentials: 'include' }).then(function (r) {
      if (r.ok && pdfMi(r)) return r.blob();
      // Bazı sürümler dosyayı ayrı bir GetFile adresinden açar: yanıtta yeni çıkan adresi dene
      return r.text().then(function (h) {
        var eski = sayfa.html;
        var yeni = (h.match(/GetFile\.ashx[^"'\s<>)]+/g) || []).filter(function (u) { return eski.indexOf(u) < 0; })[0];
        if (!yeni) return null;
        return fetch(new URL(yeni.replace(/&amp;/g, '&'), r.url).href, { credentials: 'include' })
          .then(function (r2) { return r2.ok && pdfMi(r2) ? r2.blob() : null; });
      });
    });
  }

  function pdfGonder(sayfa, evrakNo, tur) {
    return pdfIndir(sayfa).then(function (p) {
      if (p.blob.size > 40 * 1024 * 1024) throw new Error('PDF 40 MB\'tan büyük');
      return blobBase64(p.blob).then(function (b64) {
        return sunucu({ islem: 'dosya', evrakNo: evrakNo, tur: tur || 'Gelen', dosyaAdi: p.dosyaAdi, mime: p.blob.type || 'application/pdf', base64: b64 });
      });
    });
  }

  // ------------------------------------------------------------ tarama
  // Görevler 4'erli gruplar halinde okunur ve gönderilir; her grup ayrı kaydedilir, böylece
  // yarıda kalsa bile gönderilenler kaybolmaz. Sayfalar EBYS'nin kendi sayfa değiştirme işleviyle gezilir.
  var GRUP = 4;
  var calisiyor = false;

  function sayfalama() {
    var say = document.querySelector('input[id$="_hdnPageCount"]');
    var idx = document.querySelector('input[id$="_hdnPageIndexTaskTree"]');
    return { toplam: say ? (parseInt(say.value, 10) || 1) : 1, idx: idx };
  }
  function listeImza() { return listeyiOku().map(function (o) { return o.anahtar; }).join('#'); }

  /** n. sayfaya geçer; liste değişince true, değişmezse (zaten o sayfadaysa) false döner */
  function sayfayaGit(n) {
    return new Promise(function (coz) {
      var sp = sayfalama();
      var w = (typeof unsafeWindow !== 'undefined') ? unsafeWindow : window;
      if (!sp.idx || !sp.idx.name || typeof w.__doPostBack !== 'function') return coz(false);
      var once = listeImza();
      sp.idx.value = String(n);
      w.__doPostBack(sp.idx.name.replace(/hdnPageIndexTaskTree$/, 'btnPageIndexChangeTaskTree'), String(n));
      var bas = Date.now();
      var t = setInterval(function () {
        var simdi = listeImza();
        if (simdi && simdi !== once) { clearInterval(t); setTimeout(function () { coz(true); }, 800); }
        else if (Date.now() - bas > 15000) { clearInterval(t); coz(false); }
      }, 500);
    });
  }

  function durumKaydet(st) { st.zaman = Date.now(); GM_setValue('tarama', st); }

  /** Ekrandaki sayfanın yeni görevlerini işler */
  async function sayfayiIsle(st, sayfaNo) {
    var liste = listeyiOku();
    var g = A.gonderilen;
    var yeniler = liste.filter(function (o) { return !g[o.anahtar]; });
    for (var i = 0; i < yeniler.length; i += GRUP) {
      var grup = yeniler.slice(i, i + GRUP), paket = [], sayfalar = {};
      for (var k = 0; k < grup.length; k++) {
        var o = grup[k];
        durum((sayfaNo ? 'Sayfa ' + sayfaNo + ' · ' : '') + 'okunuyor ' + (i + k + 1) + '/' + yeniler.length + ': ' + o.konu.slice(0, 35));
        try {
          var s = await sayfaGetir(o.link);
          o.notlar = notlariOku(s.doc);
          o.evrakNo = o.evrakNo || evrakNoOku(s.doc);
          o.link = s.url;
          o.evrak = evrakBilgisi(s.doc, o);
          if (o.sadeceKayit) o.evrak.tur = 'Giden';
          sayfalar[o.evrakNo] = s;
          paket.push(o);
        } catch (e) { console.warn('[EBYS Takip]', o.konu, e); st.okunamayan = (st.okunamayan || 0) + 1; }
        await bekle(500);
      }
      if (!paket.length) continue;
      durum('Takip sistemine gönderiliyor…');
      var c = await sunucu({
        islem: 'gorevler', kullanici: kullanici(),
        gorevler: paket.map(function (o) {
          return { evrakNo: o.evrakNo, konu: o.konu, gonderen: o.gonderen, gorevAdi: o.gorevAdi, link: o.link, notlar: o.notlar,
                   evrak: o.evrak, sadeceKayit: !!o.sadeceKayit, hazirlayan: o.sadeceKayit ? kullanici() : '' };
        })
      });
      var gg = A.gonderilen;
      paket.forEach(function (o) { gg[o.anahtar] = Date.now(); });
      GM_setValue('gonderilen', gg);
      st.eklenen += c.eklenen || 0;
      var istenen = (c.dosyaIstenen || []).filter(function (n) { return sayfalar[n]; });
      for (var j = 0; j < istenen.length; j++) {
        var n = istenen[j];
        var tur = (paket.filter(function (x) { return x.evrakNo === n; })[0] || {}).evrak;
        durum('PDF gönderiliyor (evrak ' + n + ')');
        try { await pdfGonder(sayfalar[n], n, tur && tur.tur); st.pdf++; }
        catch (e) { st.pdfHata++; console.warn('[EBYS Takip] PDF', n, e); }
      }
      durumKaydet(st);
    }
    return { hepsiYeni: liste.length > 0 && yeniler.length === liste.length };
  }

  /**
   * tum = true  : 1. sayfadan son sayfaya kadar hepsini tarar
   * tum = false : ekrandaki sayfayı tarar; sayfadaki görevlerin hepsi yeniyse sonraki sayfaya geçer
   */
  async function tara(elle, tum) {
    if (calisiyor) return;
    calisiyor = true;
    var st = GM_getValue('tarama', null);
    var devam = st && st.aktif && (Date.now() - st.zaman < 10 * 60000);
    if (!devam) st = { aktif: true, tum: !!tum, sonraki: null, eklenen: 0, pdf: 0, pdfHata: 0, okunamayan: 0 };
    durumKaydet(st);
    try {
      var toplam = sayfalama().toplam;
      var r = await sayfayiIsle(st, st.sonraki ? st.sonraki - 1 : null);
      if (st.tum) {
        for (var n = st.sonraki || 1; n <= toplam; n++) {
          st.sonraki = n + 1; durumKaydet(st);
          durum('Sayfa ' + n + '/' + toplam + ' açılıyor…');
          await sayfayaGit(n);
          await sayfayiIsle(st, n);
        }
      } else {
        var m = st.sonraki || 2;
        while (r.hepsiYeni && m <= toplam) {
          st.sonraki = m + 1; durumKaydet(st);
          durum('Sayfa ' + m + '/' + toplam + ' açılıyor (yeni görevler sürüyor)…');
          if (!(await sayfayaGit(m))) break;
          r = await sayfayiIsle(st, m);
          m++;
        }
      }
      var ozet = st.eklenen + ' görev eklendi';
      if (st.pdf || st.pdfHata) ozet += ', ' + st.pdf + ' PDF Drive\'a gitti' + (st.pdfHata ? ' (' + st.pdfHata + ' PDF alınamadı)' : '');
      if (st.okunamayan) ozet += ', ' + st.okunamayan + ' görev okunamadı';
      if (st.eklenen || st.pdf || st.pdfHata || elle) durum(ozet, true);
      else durum(GM_getValue('sonDurum', '') || 'Yeni görev yok');
      st.aktif = false; durumKaydet(st);
    } catch (e) {
      // Kayıt durur, bir sonraki açılışta kaldığı yerden devam edilir; gönderilenler tekrar yazılmaz
      durum('Hata: ' + e.message + ' · tekrar denenecek', true);
      st.aktif = false; durumKaydet(st);
    }
    calisiyor = false;
    kutuGuncelle();
  }

  function eskileriAtla() {
    var g = A.gonderilen;
    var l = listeyiOku();
    l.forEach(function (o) { g[o.anahtar] = Date.now(); });
    GM_setValue('gonderilen', g);
    alert(l.length + ' görev gönderilmiş sayıldı. Bundan sonra yalnızca yeni gelenler aktarılacak.');
    kutuGuncelle();
  }

  // ------------------------------------------------------------ evrak sayfasında tek tık
  function evrakSayfasiDugmesi() {
    if (!document.getElementById('ctl00_cp_divNotes') && !document.getElementById('ctl00_cp_ucDocumentViewer_hdnSrc')) return;
    var b = dugme('Takibe al + PDF\'i Drive\'a gönder', function () {
      var sayfa = { doc: document, html: document.documentElement.outerHTML, url: location.href };
      var evrakNo = evrakNoOku(document);
      var baslik = document.title.trim();
      var ev = evrakBilgisi(document, { gorevAdi: baslik });
      durum('Gönderiliyor…');
      sunucu({
        islem: 'gorevler', kullanici: kullanici(),
        gorevler: [{ evrakNo: evrakNo, konu: ev.konu || baslik, gonderen: '', gorevAdi: baslik, link: location.href, notlar: notlariOku(document), evrak: ev }]
      }).then(function (c) {
        if (!evrakNo || (c.dosyaIstenen || []).indexOf(evrakNo) < 0) return c;
        return pdfGonder(sayfa, evrakNo, ev.tur).then(function () { return c; });
      }).then(function (c) { durum((c.eklenen || 0) + ' yeni görev; evrak daha önce işlendiyse tekrar yazılmadı', true); },
        function (e) { durum('Hata: ' + e.message, true); });
    });
    kutu().appendChild(b);
  }

  // ------------------------------------------------------------ arayüz
  var _kutu;
  function kutu() {
    if (_kutu) return _kutu;
    _kutu = document.createElement('div');
    _kutu.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:99999;background:#1f4e8c;color:#fff;' +
      'font:13px system-ui,sans-serif;padding:8px 10px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.25);max-width:340px;display:grid;gap:6px';
    _kutu.innerHTML = '<b>EBYS Takip</b><span id="ebysTakipDurum" style="opacity:.9"></span>';
    document.body.appendChild(_kutu);
    return _kutu;
  }
  function dugme(etiket, fn) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = etiket;
    b.style.cssText = 'border:0;border-radius:6px;padding:6px 10px;background:#fff;color:#1f4e8c;cursor:pointer;font:inherit';
    b.onclick = function (e) { e.preventDefault(); fn(); };
    return b;
  }
  function durum(m, kalici) {
    kutu();
    var el = document.getElementById('ebysTakipDurum');
    if (el) el.textContent = m;
    if (kalici) GM_setValue('sonDurum', new Date().toLocaleTimeString('tr-TR') + ' · ' + m);
  }
  var _taraDugme;
  function kutuGuncelle() {
    var l = listeyiOku();
    if (!l.length) return;
    var g = A.gonderilen;
    var yeni = l.filter(function (o) { return !g[o.anahtar]; }).length;
    if (!_taraDugme) {
      _taraDugme = dugme('', function () { tara(true, false); }); kutu().appendChild(_taraDugme);
      if (sayfalama().toplam > 1) kutu().appendChild(dugme('Tüm sayfaları tara (' + sayfalama().toplam + ' sayfa)', function () { tara(true, true); }));
    }
    _taraDugme.textContent = yeni ? yeni + ' yeni görevi takibe gönder' : 'Yeni görev yok · tekrar tara';
    if (!A.url) durum('Ayarlar girilmemiş: Tampermonkey menüsü → Ayarlar');
    else if (!calisiyor) durum(GM_getValue('sonDurum', '') || (A.otomatik ? 'Otomatik gönderim açık' : 'Elle gönderim'));
  }

  // ------------------------------------------------------------ başlat
  function basla() {
    // Görev listesi değişince (sayfa değişimi, sonradan yükleme) yeniden bak.
    // Sayfadaki saat gibi sürekli değişen öğeler yüzünden yalnızca liste gerçekten değişince çalışır.
    var sonImza = listeImza(), bekliyor = false;
    new MutationObserver(function (kayitlar) {
      if (bekliyor) return;
      if (!kayitlar.some(function (k) { return !_kutu || !_kutu.contains(k.target); })) return;
      bekliyor = true;
      setTimeout(function () {
        bekliyor = false;
        var imza = listeImza();
        if (imza === sonImza || calisiyor || !imza) return;
        sonImza = imza;
        kutuGuncelle();
        if (A.otomatik && A.url && A.anahtar) tara(false, false);
      }, 1500);
    }).observe(document.body, { childList: true, subtree: true });

    if (listeyiOku().length) {
      kutuGuncelle();
      var st = GM_getValue('tarama', null);
      var yarim = st && st.aktif && (Date.now() - st.zaman < 10 * 60000);
      if (A.url && A.anahtar && (yarim || A.otomatik)) tara(false, yarim ? st.tum : false);
      if (/Portal_Rhea\.aspx/i.test(location.pathname) && A.yenileDk > 0) {
        setTimeout(function yenile() { if (calisiyor) return setTimeout(yenile, 60000); location.href = location.origin + location.pathname; }, A.yenileDk * 60000);
      }
    }
    evrakSayfasiDugmesi();
  }
  if (window.top === window.self) basla();
})();

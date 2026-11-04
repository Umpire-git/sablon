// ==UserScript==
// @name         EBYS Görev Takip (Kalite Koordinatörlüğü)
// @namespace    usak-kalite-koordinatorlugu
// @version      0.1.0
// @description  EBYS görev listesindeki yazıları ve hocanın notlarını Google Sheets takip sistemine aktarır, PDF'i Drive'a gönderir.
// @match        https://ebys.usak.edu.tr/enVision/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
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
        headers: { 'Content-Type': 'text/plain;charset=utf-8' }, timeout: 120000,
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
      o.anahtar = [o.evrakNo || o.konu, o.listeTarihi, o.gorevAdi].join('|');
      if (gor[o.anahtar]) return; gor[o.anahtar] = 1;
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
      return parca.map(function (t) { return t.split('»').pop().trim(); }).join(', ');
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
  var calisiyor = false;
  function tara(elle) {
    if (calisiyor) return; calisiyor = true;
    var liste = listeyiOku();
    var gonderilen = A.gonderilen;
    var yeniler = liste.filter(function (o) { return !gonderilen[o.anahtar]; });
    if (!yeniler.length) { calisiyor = false; if (elle) durum('Yeni görev yok'); return; }
    var sayfalar = {};
    var paket = [];
    var i = 0;
    var sonraki = function () {
      if (i >= yeniler.length) return Promise.resolve();
      var o = yeniler[i++];
      durum('Okunuyor ' + i + '/' + yeniler.length + ': ' + o.konu.slice(0, 40));
      return sayfaGetir(o.link).then(function (s) {
        o.notlar = notlariOku(s.doc);
        o.evrakNo = o.evrakNo || evrakNoOku(s.doc);
        o.link = s.url;
        o.evrak = evrakBilgisi(s.doc, o);
        sayfalar[o.evrakNo] = s;
        paket.push(o);
      }, function (e) { console.warn('[EBYS Takip]', o.konu, e); })
        .then(function () { return bekle(700); }).then(sonraki);
    };
    sonraki().then(function () {
      if (!paket.length) throw new Error('Görev sayfaları okunamadı');
      durum('Takip sistemine gönderiliyor…');
      return sunucu({
        islem: 'gorevler', kullanici: kullanici(),
        gorevler: paket.map(function (o) {
          return { evrakNo: o.evrakNo, konu: o.konu, gonderen: o.gonderen, gorevAdi: o.gorevAdi, link: o.link, notlar: o.notlar, evrak: o.evrak };
        })
      });
    }).then(function (c) {
      var g = A.gonderilen;
      paket.forEach(function (o) { g[o.anahtar] = Date.now(); });
      GM_setValue('gonderilen', g);
      var istenen = (c.dosyaIstenen || []).filter(function (n) { return sayfalar[n]; });
      var turu = {}; paket.forEach(function (o) { turu[o.evrakNo] = o.evrak && o.evrak.tur; });
      var j = 0, hatali = 0;
      var dosya = function () {
        if (j >= istenen.length) return Promise.resolve();
        var n = istenen[j++];
        durum('PDF gönderiliyor ' + j + '/' + istenen.length + ' (evrak ' + n + ')');
        return pdfGonder(sayfalar[n], n, turu[n]).catch(function (e) { hatali++; console.warn('[EBYS Takip] PDF', n, e); }).then(dosya);
      };
      return dosya().then(function () {
        durum(c.eklenen + ' görev eklendi' + (istenen.length ? ', ' + (istenen.length - hatali) + '/' + istenen.length + ' PDF Drive\'a gitti' : ''), true);
      });
    }).catch(function (e) {
      durum('Hata: ' + e.message, true);
    }).then(function () { calisiyor = false; kutuGuncelle(); });
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
    if (!_taraDugme) { _taraDugme = dugme('', function () { tara(true); }); kutu().appendChild(_taraDugme); }
    _taraDugme.textContent = yeni ? yeni + ' yeni görevi takibe gönder' : 'Yeni görev yok · tekrar tara';
    if (!A.url) durum('Ayarlar girilmemiş: Tampermonkey menüsü → Ayarlar');
    else if (!calisiyor) durum(GM_getValue('sonDurum', '') || (A.otomatik ? 'Otomatik gönderim açık' : 'Elle gönderim'));
  }

  // ------------------------------------------------------------ başlat
  function basla() {
    // Görev listesi sayfalanınca ya da sonradan yüklenince yeniden say
    var t;
    new MutationObserver(function (kayitlar) {
      var disarida = kayitlar.some(function (k) { return !_kutu || !_kutu.contains(k.target); });
      if (!disarida) return;
      clearTimeout(t);
      t = setTimeout(function () {
        if (calisiyor || !listeyiOku().length) return;
        kutuGuncelle();
        if (A.otomatik && A.url && A.anahtar) tara(false);
      }, 1500);
    }).observe(document.body, { childList: true, subtree: true });

    var liste = listeyiOku();
    if (liste.length) {
      kutuGuncelle();
      if (A.otomatik && A.url && A.anahtar) tara(false);
      if (/Portal_Rhea\.aspx/i.test(location.pathname) && A.yenileDk > 0) {
        setTimeout(function () { if (!calisiyor) location.reload(); }, A.yenileDk * 60000);
      }
    }
    evrakSayfasiDugmesi();
  }
  if (window.top === window.self) basla();
})();

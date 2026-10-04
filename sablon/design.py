"""Tasarım dili (DSL).

DİKİŞSİZ deri ürünler içindir. Bir ürün; paneller (dikdörtgen tabanlı, profilli, köşeleri
yuvarlatılabilir), paneller arasındaki menteşeler (katlama açısıyla), üst üste monte edilen
parçalar ve özelliklerden (kilit yarığı, çıtçıt, perçin, şikago vidası, yarık, delik...)
oluşur. Birleştirme yalnızca kat, dil-yarık kilidi, çıtçıt, perçin ve vidayla yapılır. Ölçüler sayı ya da değişken
içeren ifadedir. Bu yapı hem JSON proje dosyası hem de Claude'un yapılandırılmış
çıktısıdır; Claude geometri çizmez, bu dili kullanarak *tasarlar*, motor ise
mm hassasiyetinde geometriyi, 3B modeli ve kontrolleri üretir.

Panel yerel koordinatı: x menteşe kenarı boyunca (0..genislik), y menteşeden uzağa
(0..yukseklik). Kök panelde sol alt köşe (0,0). Kenar adları: alt (y=0, menteşe),
ust (y=yukseklik, serbest uç), sol (x=0), sag (x=genislik).
"""
from __future__ import annotations

import copy
from typing import Literal

from pydantic import BaseModel, Field

Kenar = Literal["alt", "sag", "ust", "sol"]


class Degisken(BaseModel):
    ad: str = Field(description="Python tanımlayıcısı gibi (ör. kart_adet, bosluk)")
    deger: str = Field(description="Sayı veya önceki değişkenleri kullanan ifade")
    aciklama: str


class Koseler(BaseModel):
    sol_alt: str
    sag_alt: str
    sag_ust: str
    sol_ust: str


class Profil(BaseModel):
    tip: Literal["duz", "kavis", "sivri", "oyuk", "yuvarlak"] = Field(
        description="duz; kavis=dışa bombe (olcu=sehim); sivri=zarf ucu (olcu=uç derinliği); "
                    "oyuk=ortada içe yarım daire başparmak oyuğu (olcu=yarıçap); yuvarlak=tam yarım daire uç")
    olcu: str


class Panel(BaseModel):
    id: str = Field(description="Tüm tasarımda benzersiz kısa kimlik")
    ad: str
    ebeveyn: str = Field(description="Bağlı olduğu panelin id'si; parçanın kök paneli için boş")
    kenar: Literal["alt", "sag", "ust", "sol", ""] = Field(description="Ebeveynin hangi kenarına bağlı (kökte boş)")
    ofset: str = Field(description="Ebeveyn kenarının ortasına göre kaydırma (+x / +y yönünde), genelde 0")
    genislik: str = Field(description="Menteşe kenarı boyunca bitmiş ölçü (mm)")
    yukseklik: str = Field(description="Menteşeden serbest uca bitmiş ölçü (mm), iç yüzde kat çizgisinden ölçülür")
    aci: str = Field(description="Bitmiş üründe katlama açısı; + vadi (iç yüzler birbirine döner), - dağ; 0 düz")
    kat_sirasi: int = Field(description="Montajda katlanma sırası (1,2,3...); kökte veya katlanmayanlarda 0")
    kivrim_yaricapi: str = Field(description="Kıvrım iç yarıçapını elle ver (mm); boşsa deriye göre otomatik. Çekme "
                                             "şeridinin kartları U şeklinde sarması için kullanılır")
    yariktan_gecer: bool = Field(description="Kilit kafası: ebeveyni (dil boynu) bir kilit_yarigi'ndan geçerken bu panel "
                                             "yarıktan içeri girip hedef panelin öbür yüzüne geçer")
    koseler: Koseler
    daralma: str = Field(description="Serbest uçta her iki yandan içe çekilme (yamuk/şev), genelde 0")
    profil_ust: Profil
    profil_sol: Profil
    profil_sag: Profil


class Montaj(BaseModel):
    ana_panel: str = Field(description="Bu parçanın üzerine monte edildiği panel id'si; bağımsız parçada boş")
    x: str = Field(description="Bu parçanın kök panelinin sol-alt köşesinin ana paneldeki x konumu")
    y: str
    yuz: Literal["ic", "dis"] = Field(description="Ana panelin iç (süet, katlamada içe bakan) veya dış yüzü")


class Parca(BaseModel):
    id: str
    ad: str
    adet: int
    malzeme: str = Field(description="Malzeme anahtarı; tasarımın varsayılanı için boş")
    kalinlik: str = Field(description="mm; tasarım varsayılanı için boş")
    montaj: Montaj
    paneller: list[Panel]


class Ozellik(BaseModel):
    tip: Literal["kilit_yarigi", "citcit", "percin", "vida", "yarik", "delik", "oval_delik", "pencere", "logo_alani"] = Field(
        description="kilit_yarigi: yalnızca HEDEF panelde kesilen yarık (dil boynu geçişi; kaynakta tanımlanır); "
                    "citcit: katlanınca hedefte karşılığı otomatik konur; percin/vida: katlanınca üst üste gelen tüm "
                    "hedef panellerden geçen delik (katları birleştirir); yarik: panelde düz kesik (kart yuvası vb.); "
                    "delik: anahtar halkası vb.; oval_delik: kayış yuvası; pencere: iç kesim; logo_alani: damga alanı")
    panel: str
    x: str = Field(description="Merkez (yarik/kilit_yarigi için başlangıç noktası) x")
    y: str
    genislik: str = Field(description="oval_delik/pencere/logo genişliği, yarık uzunluğu; yoksa boş")
    yukseklik: str = Field(description="oval_delik/pencere/logo yüksekliği; yoksa boş")
    aci: str = Field(description="Yarık/oval açısı (derece, 0 = +x); yoksa boş")
    boyut: str = Field(description="citcit: mini|L20|L24; percin/vida/delik: delik çapı mm (boşsa standart)")
    hedefler: list[str] = Field(description="Katlanınca üst üste gelen ve aynı deliği/yarığı alacak panel id'leri")
    etiket: str


class Icerik(BaseModel):
    tip: Literal["kart", "banknot", "ozel"]
    adet: int
    panel: str = Field(description="İçeriğin oturduğu panel (cep parçasının kök paneli veya cep tabanı)")
    x: str = Field(description="İçeriğin sol-alt köşesi (panel yerel), boşsa ortalanır")
    y: str
    genislik: str = Field(description="ozel için; diğerlerinde boş")
    yukseklik: str
    kalinlik: str


class Tasarim(BaseModel):
    ad: str = Field(description="Satışa uygun kısa ürün adı")
    konsept: str = Field(description="Tasarım fikri, neyi farklı yaptığı, kime hitap ettiği (2-4 cümle)")
    kategori: str = Field(description="kartlik, cuzdan, anahtarlik, kilif, kutu...")
    malzeme: Literal["vaketa", "crazy_horse"]
    kalinlik: str = Field(description="Deri kalınlığı (mm)")
    renk: str = Field(description="Deri rengi (#rrggbb), 3B ön izleme için")
    degiskenler: list[Degisken]
    parcalar: list[Parca]
    ozellikler: list[Ozellik]
    icerikler: list[Icerik]


# --- elle yazılmış JSON'lar için varsayılan doldurma ------------------------------
_DUZ = {"tip": "duz", "olcu": "0"}
_DEFAULTS = {
    "Panel": {"ebeveyn": "", "kenar": "", "ofset": "0", "aci": "0", "kat_sirasi": 0, "daralma": "0", "yariktan_gecer": False,
              "kivrim_yaricapi": "",
              "koseler": {"sol_alt": "0", "sag_alt": "0", "sag_ust": "0", "sol_ust": "0"},
              "profil_ust": _DUZ, "profil_sol": _DUZ, "profil_sag": _DUZ, "ad": ""},
    "Montaj": {"ana_panel": "", "x": "0", "y": "0", "yuz": "ic"},
    "Parca": {"adet": 1, "malzeme": "", "kalinlik": "", "ad": ""},
    "Ozellik": {"x": "", "y": "", "genislik": "", "yukseklik": "", "aci": "", "boyut": "", "hedefler": [], "etiket": ""},
    "Icerik": {"x": "", "y": "", "genislik": "", "yukseklik": "", "kalinlik": "", "adet": 1},
    "Tasarim": {"konsept": "", "kategori": "", "renk": "", "degiskenler": [], "ozellikler": [], "icerikler": [],
                "malzeme": "vaketa", "kalinlik": "1.6"},
}


def _fill(d: dict, kind: str) -> dict:
    out = copy.deepcopy(_DEFAULTS.get(kind, {}))
    out.update(d)
    for k, v in list(out.items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("adet", "kat_sirasi"):
            out[k] = str(v)
    return out


_LEGACY = {"Tasarim": ("dikis_araligi", "kenar_payi"), "Montaj": ("dikis_kenarlari",), "Ozellik": ("kenarlar", "kenar_payi")}


def from_dict(data: dict) -> Tasarim:
    data = {k: v for k, v in data.items() if k not in _LEGACY["Tasarim"] and k != "gecmis"}
    d = _fill(data, "Tasarim")
    d["degiskenler"] = [{**v, "deger": str(v["deger"]), "aciklama": v.get("aciklama", "")} for v in d["degiskenler"]]
    parcalar = []
    for p in d["parcalar"]:
        p = _fill(p, "Parca")
        p["montaj"] = _fill({k: v for k, v in p.get("montaj", {}).items() if k not in _LEGACY["Montaj"]}, "Montaj")
        pans = []
        for pn in p["paneller"]:
            pn = _fill(pn, "Panel")
            pn["koseler"] = {k: str(v) for k, v in {**_DEFAULTS["Panel"]["koseler"], **pn["koseler"]}.items()}
            for pk in ("profil_ust", "profil_sol", "profil_sag"):
                pn[pk] = {"tip": pn[pk].get("tip", "duz"), "olcu": str(pn[pk].get("olcu", "0"))}
            pans.append(pn)
        p["paneller"] = pans
        parcalar.append(p)
    d["parcalar"] = parcalar
    d["ozellikler"] = [_fill({k: v for k, v in o.items() if k not in _LEGACY["Ozellik"]}, "Ozellik") for o in d["ozellikler"]]
    d["icerikler"] = [_fill(i, "Icerik") for i in d["icerikler"]]
    return Tasarim.model_validate(d)


def to_dict(t: Tasarim) -> dict:
    return t.model_dump()

"""Tasarım dili (DSL).

Bir ürün; paneller (dikdörtgen tabanlı, profilli, köşeleri yuvarlatılabilir), paneller
arasındaki menteşeler (katlama açısıyla), üst üste monte edilen parçalar (cep vb.) ve
özelliklerden (çıtçıt, dikiş, yarık, delik...) oluşur. Ölçüler sayı ya da değişken
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
    dikis_kenarlari: list[Kenar] = Field(description="Ana panele dikilen kenarlar (ör. sol, alt, sag)")


class Parca(BaseModel):
    id: str
    ad: str
    adet: int
    malzeme: str = Field(description="Malzeme anahtarı; tasarımın varsayılanı için boş")
    kalinlik: str = Field(description="mm; tasarım varsayılanı için boş")
    montaj: Montaj
    paneller: list[Panel]


class Ozellik(BaseModel):
    tip: Literal["citcit", "miknatis", "percin", "delik", "yarik", "oval_delik", "pencere", "dikis",
                 "dikis_cizgisi", "kilit_yarigi", "logo_alani"] = Field(
        description="citcit/miknatis: katlanınca hedefte karşılığı otomatik konur; dikis: panel kenarları boyunca; "
                    "dikis_cizgisi: (x,y)'den aci yönünde genislik uzunluğunda düz dikiş; kilit_yarigi: yalnızca "
                    "HEDEF panellerde kesilen yarık (dil geçişi için, kaynakta tanımlanır)")
    panel: str
    x: str = Field(description="Merkez (yarik/dikis_cizgisi için başlangıç) x; dikiş kenarı için boş")
    y: str
    genislik: str = Field(description="oval_delik/pencere/logo genişliği, yarık/dikiş çizgisi uzunluğu; yoksa boş")
    yukseklik: str = Field(description="oval_delik/pencere/logo yüksekliği; yoksa boş")
    aci: str = Field(description="Yarık/oval/dikiş çizgisi açısı (derece, 0 = +x); yoksa boş")
    boyut: str = Field(description="citcit: mini|L20|L24; miknatis: çap; delik/percin: çap; diğerleri boş")
    kenarlar: list[Kenar] = Field(description="dikis için panelin dikilen kenarları; diğerlerinde boş liste")
    kenar_payi: str = Field(description="dikis: kenara uzaklık (mm); boşsa tasarım varsayılanı")
    hedefler: list[str] = Field(description="Katlanınca üst üste gelen ve aynı deliği/dikişi alacak panel id'leri")
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
    malzeme: str = Field(description="vaketa | crazy_horse | krom_nappa | karton")
    kalinlik: str = Field(description="Varsayılan malzeme kalınlığı (mm)")
    renk: str = Field(description="3B ön izleme rengi (#rrggbb)")
    dikis_araligi: str = Field(description="Zımba adımı, ör. 3.85")
    kenar_payi: str = Field(description="Varsayılan dikiş kenar payı, ör. 3.5")
    degiskenler: list[Degisken]
    parcalar: list[Parca]
    ozellikler: list[Ozellik]
    icerikler: list[Icerik]


# --- elle yazılmış JSON'lar için varsayılan doldurma ------------------------------
_DUZ = {"tip": "duz", "olcu": "0"}
_DEFAULTS = {
    "Panel": {"ebeveyn": "", "kenar": "", "ofset": "0", "aci": "0", "kat_sirasi": 0, "daralma": "0",
              "koseler": {"sol_alt": "0", "sag_alt": "0", "sag_ust": "0", "sol_ust": "0"},
              "profil_ust": _DUZ, "profil_sol": _DUZ, "profil_sag": _DUZ, "ad": ""},
    "Montaj": {"ana_panel": "", "x": "0", "y": "0", "yuz": "ic", "dikis_kenarlari": []},
    "Parca": {"adet": 1, "malzeme": "", "kalinlik": "", "ad": ""},
    "Ozellik": {"x": "", "y": "", "genislik": "", "yukseklik": "", "aci": "", "boyut": "", "kenarlar": [],
                "kenar_payi": "", "hedefler": [], "etiket": ""},
    "Icerik": {"x": "", "y": "", "genislik": "", "yukseklik": "", "kalinlik": "", "adet": 1},
    "Tasarim": {"konsept": "", "kategori": "", "renk": "", "dikis_araligi": "3.85", "kenar_payi": "3.5",
                "degiskenler": [], "ozellikler": [], "icerikler": [], "malzeme": "vaketa", "kalinlik": "1.4"},
}


def _fill(d: dict, kind: str) -> dict:
    out = copy.deepcopy(_DEFAULTS.get(kind, {}))
    out.update(d)
    for k, v in list(out.items()):
        if isinstance(v, (int, float)) and k not in ("adet", "kat_sirasi"):
            out[k] = str(v)
    return out


def from_dict(data: dict) -> Tasarim:
    d = _fill(data, "Tasarim")
    d["degiskenler"] = [{**v, "deger": str(v["deger"]), "aciklama": v.get("aciklama", "")} for v in d["degiskenler"]]
    parcalar = []
    for p in d["parcalar"]:
        p = _fill(p, "Parca")
        p["montaj"] = _fill(p.get("montaj", {}), "Montaj")
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
    d["ozellikler"] = [_fill(o, "Ozellik") for o in d["ozellikler"]]
    d["icerikler"] = [_fill(i, "Icerik") for i in d["icerikler"]]
    return Tasarim.model_validate(d)


def to_dict(t: Tasarim) -> dict:
    return t.model_dump()

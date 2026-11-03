"""Kilit parçaları: kanca (dil), dil çifti, yarık — ve bunların sayısal kilit kontrolü.

Terimler (PDF'teki "words used" ile aynı):
  neck  (boyun) : yarıktan geçen dar kısım
  head  (baş)   : yarığın arkasında kalan geniş kısım
  shoulder (omuz): başın boyundan taşan kısmı; yarığın iki yanına tutunur
  tongue pair   : orta kesikle ikiye ayrılmış dil; yarıktan teker teker geçer
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Polygon

from .geom import PUNCH, Hole, Slit


@dataclass
class Tongue:
    """Bir kenardan dışarı çıkan dil. Yerel eksen: u dışarı doğru, v kenar boyunca."""
    base: tuple[float, float]  # kökün ortası (kenar üzerinde)
    angle: float  # dışarı yön, derece
    neck_w: float
    neck_len: float
    head_w: float
    head_len: float
    tip_w: float = 0.0  # 0 → head_w * 0.45 (sivri uç kolay girer)
    pair: bool = False  # True → ortadan kesilmiş dil çifti
    label: str = ""

    def _P(self, u, v):
        a = math.radians(self.angle)
        bx, by = self.base
        return (bx + u * math.cos(a) - v * math.sin(a), by + u * math.sin(a) + v * math.cos(a))

    def polygon(self) -> Polygon:
        nw, hw = self.neck_w / 2, self.head_w / 2
        tw = (self.tip_w or self.head_w * 0.45) / 2
        u1 = self.neck_len
        u2 = u1 + self.head_len * 0.5
        u3 = u1 + self.head_len
        pts = [(-1.0, -nw), (u1, -nw), (u1, -hw), (u2, -hw), (u3, -tw), (u3, tw), (u2, hw), (u1, hw), (u1, nw), (-1.0, nw)]
        return Polygon([self._P(u, v) for u, v in pts])

    def cuts(self) -> list[list[tuple[float, float]]]:
        if not self.pair:
            return []
        return [[self._P(self.neck_len + self.head_len + 0.5, 0), self._P(self.root_u(), 0)]]

    def root_u(self) -> float:
        return -PUNCH / 2  # orta kesik deliğin merkezinde biter

    def holes(self) -> list[Hole]:
        if not self.pair:
            return []
        return [Hole(self._P(self.root_u(), 0), PUNCH, self.label, True)]

    def tip(self):
        return self._P(self.neck_len + self.head_len, 0)


@dataclass
class LockCase:
    """Tek bir en kötü durum kombinasyonu."""
    t: float = 1.6  # deri kalınlığı
    wrap: float = 0.0  # gevşek sarım (+1 mm bükülme)
    fold: float = 0.0  # kat çizgisi kayması (±1)
    slit_off: float = 0.0  # yarık işaret kayması (±0.7)
    slit_long: float = 0.0  # yarık fazla kesilmiş (0 / 0.6)
    punch: float = PUNCH  # kullanılan zımba (1.5 / 2 / 3)
    mirror: bool = False  # şablon ters çizilmiş

    def short(self) -> str:
        return (f"t={self.t:g} sarım+{self.wrap:g} kat{self.fold:+g} yarık{self.slit_off:+g}"
                f"{' uzun' if self.slit_long else ''} Ø{self.punch:g}{' ayna' if self.mirror else ''}")


def effective_opening(slit: Slit, case: LockCase) -> float:
    """Müşterinin kestiği gerçek açıklık: zımba büyükse ve yarık uzun kesildiyse büyür."""
    return slit.opening + case.slit_long + max(0.0, case.punch - slit.d)


def check_tongue_slit(tg: Tongue, slit: Slit, case: LockCase, reach: float, min_shoulder=1.5, neck_margin=3.0,
                      pass_margin=0.5) -> list[str]:
    """Bir dilin bir yarıkta kilitlenip kilitlenmediğini sınar.

    reach: bu durumda dil kökünden yarığa kadar olan uzaklık (ürün modülü hesaplar;
           sarım kayması ~1.3·t, kat hatası, yarık kayması burada hesaba katılır).
    """
    errs = []
    opening = effective_opening(slit, case)
    if tg.neck_w > slit.opening - neck_margin + 1e-9:
        errs.append(f"{tg.label}: boyun {tg.neck_w:.1f} mm, yarık açıklığından ({slit.opening:.1f}) en az "
                    f"{neck_margin:g} mm dar olmalı")
    shoulder = (tg.head_w - opening) / 2 - abs(case.slit_off)
    if shoulder < min_shoulder - 1e-9:
        errs.append(f"{tg.label}: omuz {shoulder:.2f} mm < {min_shoulder:g} mm (baş kayar) [{case.short()}]")
    single = tg.head_w / 2 if tg.pair else tg.head_w * 0.45
    if single > opening - 0.5 and tg.pair:
        errs.append(f"{tg.label}: dil çiftinin tek başı ({single:.1f}) yarıktan ({opening:.1f}) geçmez")
    through = tg.neck_len - reach
    if through < case.t + pass_margin - 1e-9:
        errs.append(f"{tg.label}: baş yarığı tam geçmiyor (boyun {tg.neck_len:.1f}, gerekli "
                    f"{reach + case.t + pass_margin:.1f}) [{case.short()}]")
    if reach < -0.01:
        errs.append(f"{tg.label}: dil kökü yarığı geçiyor (aşırı bol) [{case.short()}]")
    return errs

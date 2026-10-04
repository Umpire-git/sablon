"""Şablon veri modeli: parçalar, çizgi türleri, etiketler, yerleşim."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .geometry import Circle, Primitive, merge_bounds


class Kind(str, Enum):
    CUT = "cut"          # dış kesim çizgisi
    SLIT = "slit"        # iç yarık / kesik
    HOLE = "hole"        # zımba deliği (yırtılma önleyici vb.)
    FOLD = "fold"        # katlama çizgisi
    GUIDE = "guide"      # yardımcı çizgi (çıtçıt/vida başı, logo alanı)
    GRAIN = "grain"      # deri omurga yönü oku


KIND_LABEL_TR = {
    Kind.CUT: "Kesim çizgisi",
    Kind.SLIT: "Yarık (iç kesim)",
    Kind.HOLE: "Zımba deliği",
    Kind.FOLD: "Katlama çizgisi",
    Kind.GUIDE: "Yardımcı çizgi (çıtçıt / vida başı, logo)",
    Kind.GRAIN: "Deri omurga yönü",
}


@dataclass
class Text:
    x: float
    y: float
    text: str
    size: float = 3.5  # mm
    angle: float = 0.0
    anchor: str = "middle"  # start | middle | end


@dataclass
class Piece:
    name: str
    quantity: int = 1
    note: str = ""
    items: list[tuple[Kind, Primitive]] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)

    def add(self, kind: Kind, *prims: Primitive) -> "Piece":
        for p in prims:
            self.items.append((kind, p))
        return self

    def add_all(self, kind: Kind, prims) -> "Piece":
        return self.add(kind, *prims)

    def label(self, x: float, y: float, text: str, size: float = 3.5, angle: float = 0.0, anchor: str = "middle") -> "Piece":
        self.texts.append(Text(x, y, text, size, angle, anchor))
        return self

    def bounds(self, kinds: set[Kind] | None = None) -> tuple[float, float, float, float]:
        return merge_bounds(p.bounds() for k, p in self.items if kinds is None or k in kinds)

    def cut_bounds(self) -> tuple[float, float, float, float]:
        return self.bounds({Kind.CUT})

    def size(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.cut_bounds()
        return (x1 - x0, y1 - y0)

    def moved(self, dx: float, dy: float) -> "Piece":
        p = Piece(self.name, self.quantity, self.note)
        p.items = [(k, prim.moved(dx, dy)) for k, prim in self.items]
        p.texts = [Text(t.x + dx, t.y + dy, t.text, t.size, t.angle, t.anchor) for t in self.texts]
        return p

    def count(self, kind: Kind) -> int:
        return sum(1 for k, _ in self.items if k == kind)


@dataclass
class Pattern:
    title: str
    pieces: list[Piece]
    gap: float = 12.0  # parçalar arası boşluk (mm)

    def layout(self, max_width: float = 400.0) -> list[Piece]:
        """Parçaları raf yöntemiyle (soldan sağa, alttan üste) yerleştirir.

        Dönen parçalar, sol alt köşe (0, 0) olacak şekilde ötelenmiş kopyalardır.
        """
        placed: list[Piece] = []
        x = y = row_h = 0.0
        for piece in self.pieces:
            for _ in range(1):  # adet bilgisi etikette; kalıp bir kez basılır
                bx0, by0, bx1, by1 = piece.bounds()
                w, h = bx1 - bx0, by1 - by0
                if x > 0 and x + w > max_width:
                    x, y, row_h = 0.0, y + row_h + self.gap, 0.0
                placed.append(piece.moved(x - bx0, y - by0))
                x += w + self.gap
                row_h = max(row_h, h)
        return placed

    @staticmethod
    def extent(placed: list[Piece]) -> tuple[float, float, float, float]:
        return merge_bounds(p.bounds() for p in placed)


def relief_holes(x0: float, y0: float, x1: float, y1: float, d: float) -> list[Circle]:
    """Yarık uçlarına yırtılma önleyici delikler."""
    return [Circle(x0, y0, d / 2), Circle(x1, y1, d / 2)]

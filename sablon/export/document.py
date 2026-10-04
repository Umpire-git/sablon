"""Bir tasarımın tüm çıktılarını tek yerde toplayan belge nesnesi."""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import materials as M
from ..checks import run_checks
from ..design import Tasarim
from ..engine import Built, Finding, build
from ..instructions import Instructions, make
from ..pattern import Piece


@dataclass
class Document:
    design: Tasarim
    built: Built
    pieces: list[Piece]
    findings: list[Finding]
    instructions: Instructions
    size: tuple
    images: dict = field(default_factory=dict)

    @property
    def material(self):
        return M.material(self.design.malzeme)

    @property
    def t(self):
        return self.built.env["t"]


def make_document(design: Tasarim, images: bool = True, quick: bool = False) -> Document:
    b = build(design)
    doc = Document(design, b, b.pieces(), run_checks(b), make(b), b.finished_size())
    if images:
        render_images(doc, quick=quick)
    return doc


def render_images(doc: Document, quick: bool = False):
    from ..render3d import render
    b = doc.built
    big = (900, 650) if quick else (1400, 1000)
    small = (700, 460) if quick else (1000, 660)
    ss = 1 if quick else 2
    doc.images["hero"] = render(b, fold=1.0, az=-35, el=30, size=big, ss=ss)
    doc.images["flat"] = render(b, fold=0.0, az=0, el=89.9, size=small, ss=ss, show_contents=False)
    for i, st in enumerate(doc.instructions.steps, 1):
        if not st.image:
            continue
        if st.image.get("view") == "flat":
            continue
        fold = st.image["fold"]
        pull = st.image.get("pull", 0.0)
        doc.images[f"step{i}"] = render(b, fold=fold, az=160 if pull else -30, el=32 if pull else 38, size=small,
                                        ss=ss, show_contents=(fold == 1.0), pull=pull)

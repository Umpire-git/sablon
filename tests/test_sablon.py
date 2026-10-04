import math
from collections import Counter

import pytest
from pypdf import PdfReader

from sablon.ai import Revision, ParamChange, DesignChoice, ParamValue, autofix, design_from_description, revise
from sablon.cli import main
from sablon.export.pdf import MM, write_pdf
from sablon.geometry import Arc, Line, path_length, points_along, rounded_rect
from sablon.pattern import Kind, Pattern
from sablon.project import Change, Project
from sablon.templates import REGISTRY
from sablon.templates.dikissiz_kartlik import DikissizKartlik
from sablon.templates.dikisli_kartlik import DikisliKartlik
from sablon.templates.kutu import TuckKutu


def endpoints(seg):
    if isinstance(seg, Line):
        return [(seg.x0, seg.y0), (seg.x1, seg.y1)]
    return [seg.start, seg.end]


def assert_closed(segs):
    """Her uç nokta çift sayıda segmentte bulunmalı → kesim hattı kapalı, boşluk yok."""
    cnt = Counter((round(x, 6), round(y, 6)) for s in segs for (x, y) in endpoints(s))
    odd = [p for p, n in cnt.items() if n % 2]
    assert not odd, f"açık uçlar: {odd[:4]}"


# --- geometri -----------------------------------------------------------------
def test_rounded_rect_perimeter():
    segs = rounded_rect(0, 0, 100, 50, 5)
    assert path_length(segs) == pytest.approx(2 * (100 + 50) - 8 * 5 + 2 * math.pi * 5)
    assert_closed(segs)


def test_points_along_hits_both_ends():
    segs = [Line(0, 0, 100, 0)]
    pts, step = points_along(segs, 3.85)
    assert pts[0] == (0, 0)
    assert pts[-1] == pytest.approx((100, 0))
    assert step == pytest.approx(100 / round(100 / 3.85))


# --- tüm şablonlar --------------------------------------------------------------
@pytest.mark.parametrize("key", list(REGISTRY))
def test_defaults_have_no_errors_and_closed_outline(key):
    t = REGISTRY[key]()
    assert not [f for f in t.checks() if f.level == "hata"]
    for piece in t.build().pieces:
        assert_closed([p for k, p in piece.items if k == Kind.CUT])
    assert t.assembly()
    assert t.preview_svg().startswith("<svg")


@pytest.mark.parametrize("key", list(REGISTRY))
def test_params_are_clamped(key):
    T = REGISTRY[key]
    p = T.params[0]
    assert T.resolve({p.name: p.max * 10})[p.name] == p.max
    with pytest.raises(KeyError):
        T.resolve({"olmayan_parametre": 1})


# --- dikişsiz kartlık --------------------------------------------------------------
@pytest.mark.parametrize("n,t", [(1, 1.0), (4, 1.4), (8, 2.0)])
def test_stitchless_slits_align_with_tabs_when_folded(n, t):
    k = DikissizKartlik({"kart_sayisi": n, "deri_kalinligi": t})
    d = k.dims()
    piece = k.build().pieces[0]
    slits = [p for kind, p in piece.items if kind == Kind.SLIT]
    assert len(slits) == 2
    yb = d["Hf"] + d["g"]
    for s in slits:
        center = (s.y0 + s.y1) / 2
        # katlanınca: ön panelde dilin alt kıvrımdan yüksekliği == yarığın arka paneldeki yüksekliği
        assert center - yb == pytest.approx(d["Hf"] - d["yc"])
        assert abs(s.y1 - s.y0) == pytest.approx(d["hn"] + t)
        assert yb < min(s.y0, s.y1) and max(s.y0, s.y1) < yb + d["Hb"]
    assert sorted(s.x0 for s in slits) == pytest.approx([d["Ln"], d["W"] - d["Ln"]])
    # tam açık ölçü = panel + 2*(körük + dil)
    w, h = piece.size()
    assert w == pytest.approx(d["W"] + 2 * (d["g"] + d["Ln"] + d["Lh"]))
    assert h == pytest.approx(d["Hf"] + d["g"] + d["Hb"])


def test_stitchless_inner_width_fits_iso_card():
    m = DikissizKartlik().measures()
    assert m["ic_genislik"].value == pytest.approx(85.6 + 3.0)


def test_stitchless_detects_problems():
    codes = {f.code for f in DikissizKartlik({"bosluk": 0.2, "kilit_payi": 0.5, "dil_genislik": 6}).checks()}
    assert {"sikisik_kart", "kilit_tutmaz", "dar_dil"} <= codes


# --- dikişli kartlık ---------------------------------------------------------------
def test_stitch_holes_line_up_across_pieces():
    k = DikisliKartlik()
    pieces = k.build().pieces
    holes = [{(round(c.cx, 6), round(c.cy, 6)) for kind, c in p.items if kind == Kind.STITCH} for p in pieces]
    body, back, front = holes
    assert front <= back <= body  # her cep deliği gövdede aynı yerde
    assert len(front) < len(back)
    pts, step = k.holes()
    path = k.stitch_path()
    assert pts[0] == pytest.approx((path[0].x0, path[0].y0))
    assert pts[-1] == pytest.approx((path[-1].x1, path[-1].y1))


def test_nonstandard_iron_warning():
    codes = {f.code for f in DikisliKartlik({"dikis_araligi": 3.6}).checks()}
    assert "standart_disi_zimba" in codes


# --- kutu -----------------------------------------------------------------------
def test_box_fold_lines():
    folds = [p for k, p in TuckKutu().build().pieces[0].items if k == Kind.FOLD]
    # 4 gövde dikey + üst(kapak, dil, 2 toz) + alt(kapak, dil, 2 toz)
    assert len(folds) == 12


def test_box_dust_flap_collision():
    codes = {f.code for f in TuckKutu({"uzunluk": 40, "toz_kapak": 30}).checks()}
    assert "toz_cakisma" in codes


# --- PDF ölçek doğruluğu ----------------------------------------------------------------
@pytest.mark.parametrize("paper,size", [("A4", (210, 297)), ("Letter", (215.9, 279.4))])
def test_tiled_pdf_page_size(tmp_path, paper, size):
    out = tmp_path / "k.pdf"
    write_pdf(DikissizKartlik(), str(out), paper)
    r = PdfReader(str(out))
    for page in r.pages:
        assert float(page.mediabox.width) == pytest.approx(size[0] * MM, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(size[1] * MM, abs=0.01)


def test_full_size_pdf_matches_pattern_extent(tmp_path):
    t = TuckKutu()
    out = tmp_path / "k.pdf"
    write_pdf(t, str(out), "full", include_info=False)
    placed = t.build().layout(600)
    x0, y0, x1, y1 = Pattern.extent(placed)
    page = PdfReader(str(out)).pages[0]
    assert float(page.mediabox.width) / MM == pytest.approx(x1 - x0 + 30, abs=0.01)
    assert float(page.mediabox.height) / MM == pytest.approx(y1 - y0 + 8 + 30 + 12, abs=0.01)


def test_large_pattern_tiles_over_pages(tmp_path):
    t = TuckKutu({"uzunluk": 150, "genislik": 80, "yukseklik": 200, "toz_kapak": 40, "dil_boyu": 25})
    info = write_pdf(t, str(tmp_path / "b.pdf"), "A4")
    assert info["pages"] > 1


# --- proje / düzeltme ------------------------------------------------------------
def test_project_roundtrip_and_autofix(tmp_path):
    p = Project("dikissiz_kartlik")
    p.apply([Change("bosluk", 0, 0.2), Change("kilit_payi", 0, 0.5)], source="test")
    assert any(f.level == "hata" for f in p.instance().checks())
    fixed = autofix(p)
    assert fixed
    assert not any(f.level == "hata" for f in p.instance().checks())
    path = tmp_path / "p.json"
    p.save(str(path))
    q = Project.load(str(path))
    assert q.params == p.params and len(q.history) == len(p.history)


class FakeResp:
    def __init__(self, parsed):
        self.parsed_output = parsed
        self.stop_reason = "end_turn"


class FakeClient:
    def __init__(self, parsed):
        self.calls = []
        outer = self

        class _M:
            def parse(self, **kw):
                outer.calls.append(kw)
                return FakeResp(parsed)

        class _B:
            messages = _M()

        self.beta = _B()


def test_ai_design_and_revision_use_params_only():
    choice = DesignChoice(supported=True, template="dikissiz_kartlik", name="Minimal Kartlık",
                          params=[ParamValue(name="kart_sayisi", value=6), ParamValue(name="uydurma", value=3)],
                          assumptions=["ISO kart"], missing_capability="")
    fc = FakeClient(choice)
    proj, _ = design_from_description("6 kartlık dikişsiz cüzdan", client=fc)
    assert proj.params["kart_sayisi"] == 6
    assert "uydurma" not in proj.params
    assert fc.calls[0]["model"] == "claude-opus-5-5"

    rev = Revision(understood_as="ön panel uzun", question="",
                   changes=[ParamChange(name="on_panel_orani", new_value=5.0, reason="kısalt")])
    _, applied = revise(proj, "ön panel çok uzun olmuş", client=FakeClient(rev))
    assert applied[0].new == 1.0  # sınırlara kırpıldı
    assert proj.history[-1]["request"] == "ön panel çok uzun olmuş"


def test_cli_end_to_end(tmp_path, capsys):
    pj = str(tmp_path / "p.json")
    main(["yeni", "dikisli_kartlik", "kademe=10", "-o", pj])
    main(["ayarla", pj, "kenar_payi=4"])
    main(["cikti", pj, "-d", str(tmp_path / "out")])
    files = sorted(f.name for f in (tmp_path / "out").iterdir())
    assert files == ["p.dxf", "p.svg", "p_A4.pdf", "p_Letter.pdf", "p_onizleme.svg", "p_tam_boy.pdf"]
    dxf = (tmp_path / "out" / "p.dxf").read_text()
    assert "STITCH" in dxf and dxf.strip().endswith("EOF")

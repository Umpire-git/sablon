import copy
import json
import math
import os
from collections import Counter

import numpy as np
import pytest
from pypdf import PdfReader

from sablon import ai
from sablon import project as P
from sablon.checks import run_checks
from sablon.cli import main
from sablon.design import from_dict
from sablon.engine import BuildError, build
from sablon.export.document import make_document
from sablon.export.pdf import MM, write_pdf
from sablon.expr import ExprError, evaluate
from sablon.geometry import Arc, Line, arc_from_3pts, fillet, path_length, points_along, rounded_rect, triangulate
from sablon.pattern import Kind, Pattern

ROOT = os.path.dirname(os.path.dirname(__file__))
EXAMPLES = sorted(f[:-5] for f in os.listdir(os.path.join(ROOT, "ornekler")) if f.endswith(".json"))


def load(name, **changes):
    with open(os.path.join(ROOT, "ornekler", name + ".json"), encoding="utf-8") as f:
        d = json.load(f)
    return d


def design(name):
    return from_dict(load(name))


def endpoints(seg):
    if isinstance(seg, Line):
        return [(seg.x0, seg.y0), (seg.x1, seg.y1)]
    return [seg.start, seg.end]


def assert_closed(segs):
    """Her uç nokta çift sayıda segmentte → kesim hattı kapalı (açık uç yok)."""
    cnt = Counter((round(x, 4), round(y, 4)) for s in segs for (x, y) in endpoints(s))
    odd = [p for p, n in cnt.items() if n % 2]
    assert not odd, f"açık uçlar: {odd[:4]}"


# --- geometri / ifade ------------------------------------------------------------
def test_geometry_helpers():
    assert path_length(rounded_rect(0, 0, 100, 50, 5)) == pytest.approx(300 - 40 + 2 * math.pi * 5)
    a = arc_from_3pts((0, 0), (5, 5), (10, 0))
    assert (a.cx, a.cy, a.r) == pytest.approx((5, 0, 5))
    t1, arc, t2 = fillet((0, 10), (0, 0), (10, 0), 3)
    assert t1 == pytest.approx((0, 3)) and t2 == pytest.approx((3, 0))
    assert len(triangulate([(0, 0), (10, 0), (10, 10), (5, 4), (0, 10)])) == 3
    pts, step = points_along([Line(0, 0, 100, 0)], 3.85)
    assert pts[0] == (0, 0) and pts[-1] == pytest.approx((100, 0))


def test_expressions():
    assert evaluate("kart_g + 2*b", {"kart_g": 85.6, "b": 1.5}) == pytest.approx(88.6)
    assert evaluate("12,5", {}) == 12.5
    with pytest.raises(ExprError):
        evaluate("__import__('os')", {})
    with pytest.raises(ExprError):
        evaluate("x + 1", {})


# --- tüm örnekler ------------------------------------------------------------------
@pytest.mark.parametrize("name", EXAMPLES)
def test_examples_build_clean(name):
    b = build(design(name))
    errs = [f for f in run_checks(b) if f.level == "hata"]
    assert not errs, errs
    for piece in b.pieces():
        assert_closed([p for k, p in piece.items if k == Kind.CUT])


@pytest.mark.parametrize("name", EXAMPLES)
def test_flat_pieces_have_fold_allowance(name):
    b = build(design(name))
    for p in b.panels.values():
        if p.parent:
            assert p.allow == pytest.approx(math.radians(abs(p.angle)) * p.t / 2)


def test_folded_box_is_closed_box():
    b = build(design("karton_kutu"))
    w, h, d = b.finished_size()
    t = b.env["t"]
    assert sorted((w, h, d)) == pytest.approx(sorted((120 + 2 * t + t, 80 + t + t, 40 + t + t)), abs=1.5)


# --- katlama-farkındalıklı özellikler ------------------------------------------------
def test_snap_counterpart_lands_on_front_pocket_when_folded():
    b = build(design("kapakli_citcitli_kartlik"))
    s = b.snaps[0]
    assert s.src == "kapak" and s.dst == "on"
    w_src = b.world("kapak", s.src_xy)
    w_dst = b.world("on", s.dst_xy)
    assert np.allclose(w_src[:2], w_dst[:2], atol=1e-6)  # katlı hâlde üst üste
    assert s.gap > 0


def test_side_stitch_holes_match_through_fold():
    b = build(design("kapakli_citcitli_kartlik"))
    on = [m.prim for m in b.panels["on"].marks if m.kind == Kind.STITCH]
    arka = [m.prim for m in b.panels["arka"].marks if m.kind == Kind.STITCH]
    assert len(on) == len(arka) > 10
    W = [tuple(np.round(b.world("on", (c.cx, c.cy))[:2], 6)) for c in on]
    A = [tuple(np.round(b.world("arka", (c.cx, c.cy))[:2], 6)) for c in arka]
    assert sorted(W) == sorted(A)


def test_lock_slits_cut_on_back_panel_only():
    b = build(design("dikissiz_kilitli_kartlik"))
    slits_back = [m for m in b.panels["arka"].marks if m.kind == Kind.SLIT]
    slits_neck = [m for m in b.panels["boyun_sol"].marks if m.kind == Kind.SLIT]
    assert len(slits_back) == 2 and not slits_neck
    for m in slits_back:
        assert 0 < m.prim.y0 < b.panels["arka"].h


def test_tiered_pockets_share_holes():
    b = build(design("kademeli_cepli_kartlik"))
    body = [(m.prim.cx, m.prim.cy) for m in b.panels["govde_p"].marks if m.kind == Kind.STITCH]
    for i in range(len(body)):
        for j in range(i + 1, len(body)):
            assert math.dist(body[i], body[j]) > 0.6 * 3.85 - 1e-6
    front = [(m.prim.cx, m.prim.cy) for m in b.panels["cep_on_p"].marks if m.kind == Kind.STITCH]
    assert all(any(math.dist(q, p) < 0.01 for p in body) for q in front)


# --- kontroller ----------------------------------------------------------------------
def test_narrow_pocket_is_error():
    d = load("kapakli_citcitli_kartlik")
    for v in d["degiskenler"]:
        if v["ad"] == "W":
            v["deger"] = "kart_g + 2*e + 1"
    codes = {f.code for f in run_checks(build(from_dict(d)))}
    assert "cep_dar" in codes


def test_snap_into_void_is_error():
    d = load("kapakli_citcitli_kartlik")
    d["parcalar"][0]["paneller"][3]["yukseklik"] = "H*1.6"  # gövdeden uzun kapak
    d["ozellikler"][1]["y"] = "H*1.5"  # çıtçıt, kapanınca gövdenin dışına (boşluğa) düşer
    with pytest.raises(BuildError) as e:
        build(from_dict(d))
    assert any(f.code == "karsilik_yok" for f in e.value.findings)


def test_flat_overlap_detected():
    d = load("kapakli_citcitli_kartlik")
    d["parcalar"][0]["paneller"].append({"id": "kapak2", "ad": "ikinci kapak", "ebeveyn": "sirt", "kenar": "ust",
                                         "genislik": "30", "ofset": "10", "yukseklik": "20", "aci": "90"})
    with pytest.raises(BuildError) as e:
        build(from_dict(d))
    assert any(f.code == "acinim_cakisma" for f in e.value.findings)


def test_snap_gap_warning():
    d = load("kapakli_citcitli_kartlik")
    d["ozellikler"][1]["y"] = "4"  # menteşeye yakın: altında sırt boşluğu var, kapanmaz
    assert "citcit_bosluk" in {f.code for f in run_checks(build(from_dict(d)))}


def test_soft_leather_lock_warning():
    d = load("dikissiz_kilitli_kartlik")
    d["malzeme"] = "crazy_horse"
    assert "kilit_yumusak" in {f.code for f in run_checks(build(from_dict(d)))}


def test_tiered_pocket_hole_conflict_warning():
    d = load("kademeli_cepli_kartlik")
    for v in d["degiskenler"]:
        if v["ad"] == "h2":
            v["deger"] = "r + e + 7*p + 1.5"
    assert "delik_cakisma" in {f.code for f in run_checks(build(from_dict(d)))}


# --- çıktı --------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def doc():
    return make_document(design("kapakli_citcitli_kartlik"), quick=True)


@pytest.mark.parametrize("paper,size", [("A4", (210, 297)), ("Letter", (215.9, 279.4))])
def test_pdf_page_sizes(tmp_path, doc, paper, size):
    out = tmp_path / "k.pdf"
    write_pdf(doc, str(out), paper)
    r = PdfReader(str(out))
    assert len(r.pages) >= 5
    for page in r.pages:
        assert float(page.mediabox.width) == pytest.approx(size[0] * MM, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(size[1] * MM, abs=0.01)
    text = "".join(p.extract_text() for p in r.pages)
    assert "Yapım aşamaları" in text and "Malzeme listesi" in text


def test_full_pdf_is_true_scale(tmp_path, doc):
    out = tmp_path / "k.pdf"
    write_pdf(doc, str(out), "full", include_info=False)
    x0, y0, x1, y1 = Pattern.extent(Pattern("t", doc.pieces).layout(600))
    page = PdfReader(str(out)).pages[0]
    assert float(page.mediabox.width) / MM == pytest.approx(x1 - x0 + 30, abs=0.01)


def test_instructions_order(doc):
    titles = [s.title for s in doc.instructions.steps]
    assert titles.index("Donanım (çıtçıt / mıknatıs)") < titles.index("Katlama 1") < titles.index("Katlı hâlde dikiş (1)")


# --- proje / CLI -----------------------------------------------------------------------
def test_cli_flow(tmp_path, capsys):
    pj = str(tmp_path / "p.json")
    main(["yeni", "kademeli_cepli_kartlik", "-o", pj])
    main(["ayarla", pj, "e=4", "govde_p.kose.sol_alt=8"])
    d, hist = P.load(pj)
    assert any(v.ad == "e" and v.deger == "4" for v in d.degiskenler)
    assert len(hist) == 2
    main(["cikti", pj, "-d", str(tmp_path / "o"), "--bicim", "svg,dxf,3b", "--hizli"])
    files = sorted(os.listdir(tmp_path / "o"))
    assert files == ["p.dxf", "p.svg", "p_3B.html"]
    html = (tmp_path / "o" / "p_3B.html").read_text(encoding="utf-8")
    assert "three" in html and "govde_p" in html


# --- Claude akışı (sahte istemci) ------------------------------------------------------------
class _Msg:
    def __init__(self, parsed):
        self.parsed_output = parsed
        self.stop_reason = "end_turn"
        self.content = []


class FakeClient:
    """Sırayla verilen yanıtları döndüren, gönderilen istekleri kaydeden istemci."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
        outer = self

        class _Stream:
            def __init__(self, parsed):
                self.parsed = parsed

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return _Msg(self.parsed)

        class _Messages:
            def stream(self, **kw):
                outer.calls.append(kw)
                return _Stream(outer.answers.pop(0))

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()


def test_ideas_validate_and_repair():
    good = design("kapakli_citcitli_kartlik")
    broken = copy.deepcopy(design("dikissiz_kilitli_kartlik"))
    broken.ozellikler[0].hedefler = ["yok_boyle_panel"]
    fixed = design("dikissiz_kilitli_kartlik")
    fc = FakeClient(ai.Fikirler(tasarimlar=[good, broken]), ai.Onarim(tasarim=fixed, aciklama="hedef düzeltildi"))
    res = ai.ideas("kapaklı çıtçıtlı kartlık", n=2, client=fc, seed=1, log=lambda *_: None)
    assert len(res) == 2
    assert all(not [f for f in fs if f.level == "hata"] for _, fs in res)
    assert len(fc.calls) == 2  # 1 fikir + 1 onarım
    kw = fc.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "tasarim_dili" not in kw["messages"][0]["content"]  # bilgi bankası sistemde
    assert "Doğrulanmış örnek tasarımlar" in kw["system"][0]["text"]


def test_ideas_prompt_varies_with_seed():
    a = ai._moves(4, __import__("random").Random(1))
    b = ai._moves(4, __import__("random").Random(2))
    assert a != b


def test_revise_returns_diffable_design():
    d = design("kapakli_citcitli_kartlik")
    new = copy.deepcopy(d)
    for v in new.degiskenler:
        if v.ad == "kart_adet":
            v.deger = "4"
    new.icerikler[0].adet = 4
    rev = ai.Revizyon(anlasilan="daha ince", degisiklikler=["kart 4"], soru="", tasarim=new)
    r, out, findings = ai.revise(d, "biraz daha ince olsun", client=FakeClient(rev))
    assert "~ değişken kart_adet: 6 → 4" in P.diff(d, out)
    assert not [f for f in findings if f.level == "hata"]

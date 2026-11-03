import math
import os
import sys
import zipfile

from shapely.geometry import box

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dagli import cutfiles, seo  # noqa: E402
from dagli.booklet import Booklet, plan_template, write_fullsize  # noqa: E402
from dagli.checks import Report, geometry_checks, sweep  # noqa: E402
from dagli.fold3d import Scene  # noqa: E402
from dagli.geom import Part, Slit, fillet_inner, union  # noqa: E402
from dagli.locks import LockCase, Tongue, check_tongue_slit  # noqa: E402
from dagli.pipeline import check_product, produce, trial  # noqa: E402
from dagli.product import Meta, Product, Seo, Step, load  # noqa: E402

PEN = os.path.join(ROOT, "urunler", "round_pen_cup.py")


class Sleeve(Product):
    """Test ürünü: tek sayfalık kart kılıfı (gövde + kapak dili + yarık)."""
    meta = Meta(name="Test Card Sleeve", slug="Test_Card_Sleeve", sku="T-1", version="0.9",
                finished_size="9 × 6 cm", t_test=(0.2, 2.4))
    seo = Seo(primary="leather card sleeve pattern", keywords=["no sew card holder", "card sleeve template"])

    def __init__(self, head_w=23.0, neck=12.0):
        self.head_w, self.neck = head_w, neck

    def tongue(self):
        return Tongue((45, 130), 90, self.neck, 10.0, self.head_w, 8.0, label="H1")

    def slit(self):
        return Slit((45, 20), 0, 16.0, "S1")

    def parts(self):
        body = box(0, 0, 90, 130)
        poly = fillet_inner(union(body, self.tongue().polygon()), 1.0)
        return [Part("Body", poly, folds=[[(0, 65), (90, 65)]], slits=[self.slit()])]

    def scene(self, t=None):
        sc = Scene(t or 1.6)
        p = self.parts()[0]
        low = sc.panel("low", p.outline.intersection(box(-1, -1, 91, 65)))
        sc.panel("up", p.outline.intersection(box(-1, 65, 91, 200)), parent=low, hinge=((90, 65), (0, 65)), angle=170)
        return sc

    def steps(self):
        return [Step("Print.", "print"), Step("Trace.", "trace"), Step("Punch.", "punch"), Step("Slit.", "slits"),
                Step("Cut.", "outline"), Step("Fold.", "fold", fold=0.5), Step("Done.", "done")]

    def lock_check(self, case):
        reach = 3.0 + 1.3 * case.t + case.fold + case.slit_off
        return check_tongue_slit(self.tongue(), self.slit(), case, reach)


def test_pen_cup_passes_all_checks():
    rep = check_product(load(PEN))
    assert rep.ok, rep.text()
    assert rep.sweep_total == 2592 and rep.sweep_failed == 0


def test_sweep_catches_narrow_head():
    rep = Report()
    sweep(Sleeve(head_w=19.0).lock_check, rep)  # omuz yetersiz
    assert rep.sweep_failed > 0 and any("omuz" in e for e in rep.errors)


def test_neck_must_be_3mm_narrower_than_slit():
    errs = check_tongue_slit(Tongue((0, 0), 0, 14.0, 10, 23, 8), Slit((0, 0), 0, 16.0), LockCase(), 1.0)
    assert any("boyun" in e for e in errs)


def test_stop_hole_near_edge_is_error():
    p = Part("P", box(0, 0, 50, 50), slits=[Slit((25, 3), 0, 16)])
    rep = Report()
    geometry_checks([p], rep)
    assert any("kenara" in e for e in rep.errors)


def test_slit_opening_constant_when_punch_changes():
    s = Slit((0, 0), 0, 16.0)
    for d in (1.5, 2.0, 3.0):
        a, b = s.ends(d)
        assert math.isclose(abs(b[0] - a[0]) + d, 16.0)


def test_overlap_detected():
    rep = Report()
    geometry_checks([Part("A", box(0, 0, 10, 10)), Part("B", box(5, 5, 15, 15))], rep)
    assert any("üst üste" in e for e in rep.errors)


def test_single_page_template_and_booklet(tmp_path):
    prod = Sleeve()
    assert plan_template(prod, "A4").single and plan_template(prod, "Letter").single
    from pypdf import PdfReader
    for paper, size in (("A4", {(595, 842), (842, 595)}), ("Letter", {(612, 792), (792, 612)})):
        path = tmp_path / f"s_{paper}.pdf"
        n = Booklet(prod, paper).write(str(path))
        r = PdfReader(str(path))
        assert len(r.pages) == n
        assert "TEMPLATE 1:1" in r.pages[0].extract_text()
        for pg in r.pages:
            assert (round(float(pg.mediabox.width)), round(float(pg.mediabox.height))) in size


def test_cut_files_are_1to1(tmp_path):
    prod = Sleeve()
    z = cutfiles.write_all(prod, str(tmp_path))
    with zipfile.ZipFile(z) as zz:
        svg = zz.read("Test_Card_Sleeve.svg").decode()
        dxf = zz.read("Test_Card_Sleeve.dxf").decode()
        cri = zz.read("Test_Card_Sleeve_Cricut.svg").decode()
    x0, y0, x1, y1 = prod.layout()[0].bounds()
    assert f'width="{x1 - x0 + 10:.3f}mm"' in svg
    assert "AC1009" in dxf and "\nFOLD\n" in dxf and "\nCUT\n" in dxf
    assert cri.count("<path") > svg.count("<path") - 1  # yarıklar kapalı şekil


def test_fullsize_scale(tmp_path):
    from pypdf import PdfReader
    prod = Sleeve()
    p = tmp_path / "full.pdf"
    write_fullsize(prod, str(p))
    x0, _, x1, _ = prod.layout()[0].bounds()
    w = float(PdfReader(str(p)).pages[0].mediabox.width) / 72 * 25.4
    assert abs(w - (x1 - x0 + 30)) < 0.1


def test_seo_rules():
    L = seo.listing(load(PEN), None, ["FullSize", "CutFiles"])
    assert not L["lint"], L["lint"]
    assert len(L["tags"]) == 13 and all(len(t) <= 20 for t in L["tags"])
    assert len(L["title"]) <= 140 and L["description"].startswith("DIGITAL PATTERN")
    assert L["attributes"]["Content"] == "With an AI generator"


def test_market_analysis_from_csv(tmp_path):
    from dagli import market
    p = tmp_path / "c.csv"
    p.write_text("title,price,tags,favorites\n"
                 "Leather Pen Holder Pattern PDF stitched,8.50,pen holder;leather pattern,120\n"
                 "No sew pen cup template SVG,6.00,no sew;pen cup,40\n"
                 "Desk organizer leather pattern snaps,12,desk organizer;leather pattern,300\n", encoding="utf-8")
    an = market.analyze(market.from_csv(str(p)), "pen holder")
    assert an["price"]["median"] == 8.5
    assert an["features"]["no-sew"] == 1 and an["features"]["stitched"] == 1 and an["features"]["snap"] == 1
    assert dict(an["tags"])["leather pattern"] == 2
    assert "Rakip taraması" in market.report_md(an)


def test_trial_and_produce(tmp_path):
    prod = load(PEN)
    made = trial(prod, str(tmp_path / "deneme"), log=lambda *_: None)
    assert any(m.endswith("_konsept.pdf") for m in made)
    folder = produce(prod, str(tmp_path / "teslim"), None, log=lambda *_: None)
    for f in ("LISTING.md", "OZET.md", "ai/PROMPTS.md", "ai/ai_referans.png", "etsy_gorselleri/01_hero.png",
              "etsy_gorselleri/03_steps.png", f"UPLOAD_TO_ETSY_{prod.meta.slug}.zip"):
        assert os.path.exists(os.path.join(folder, f)), f
    from PIL import Image
    assert Image.open(os.path.join(folder, "etsy_gorselleri/02_what_you_get.png")).size == (2000, 2000)
    ozet = open(os.path.join(folder, "OZET.md"), encoding="utf-8").read()
    assert "0 hata" in ozet and "temiz" in ozet
    pr = open(os.path.join(folder, "ai/PROMPTS.md"), encoding="utf-8").read()
    assert "Türkçesi" in pr and "MUST NOT APPEAR" in pr


def test_design_loop_repairs(tmp_path, monkeypatch):
    """Sahte Claude: önce bozuk modül, sonra doğru modül → döngü onarır."""
    from dagli import ai
    good = open(PEN, encoding="utf-8").read()
    bad = good.replace("HEAD_W, HEAD_L = 12.0, 23.0, 9.0", "HEAD_W, HEAD_L = 12.0, 17.0, 9.0")
    replies = iter([bad, good])
    seen = []

    class R:
        content = []

    def fake(msgs, system, **kw):
        seen.append(msgs[-1]["content"])
        return f"```python\n{next(replies)}```", R()

    monkeypatch.setattr(ai, "_stream_text", fake)
    ok, rep = ai.design("round pen cup", str(tmp_path / "x.py"), rounds=3, log=lambda *_: None)
    assert ok and len(seen) == 2 and "omuz" in seen[1]

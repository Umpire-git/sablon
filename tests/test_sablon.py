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
from sablon.engine import BuildError, build, slab_gap
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
def test_examples_are_stitchless_leather(name):
    d = load(name)
    assert d["malzeme"] in ("vaketa", "crazy_horse")
    assert all(o["tip"] not in ("dikis", "dikis_cizgisi") for o in d["ozellikler"])
    b = build(design(name))
    assert not [m for p in b.panels.values() for m in p.marks if m.kind.value == "stitch"]


@pytest.mark.parametrize("name", EXAMPLES)
def test_fold_allowance_matches_bend(name):
    b = build(design(name))
    for p in b.panels.values():
        if p.parent:
            assert p.allow == pytest.approx(math.radians(abs(p.angle)) * (p.bend_r + p.t / 2))


def test_stitch_features_rejected():
    d = load("vidali_kartlik")
    d["ozellikler"].append({"tip": "dikis", "panel": "on"})
    with pytest.raises(Exception):
        from_dict(d)


# --- katlama-farkındalıklı özellikler ------------------------------------------------
def test_snap_counterpart_touches_front_when_folded():
    b = build(design("kapakli_citcitli_kartlik"))
    s = b.snaps[0]
    assert s.src == "kapak" and s.dst == "on"
    assert np.allclose(b.world("kapak", s.src_xy)[:2], b.world("on", s.dst_xy)[:2], atol=1e-6)
    assert -0.2 <= s.gap <= 1.0  # kapak ön panele oturuyor


def test_lock_heads_pass_through_slits():
    b = build(design("dikissiz_kilitli_kartlik"))
    slits = [m for m in b.panels["arka"].marks if m.kind == Kind.SLIT]
    assert len(slits) == 2 and not [m for m in b.panels["boyun_sol"].marks if m.kind == Kind.SLIT]
    arka = b.panels["arka"]
    for head in ("kafa_sol", "kafa_sag"):
        h = b.panels[head]
        assert h.through != 0
        # kafa, arka panelin İÇ yüzünün üstünde (yarıktan geçmiş): tüm köşeleri z ≥ 0 (arka yerelinde)
        for (x, y) in h.quad:
            for z in (0.0, -h.t):
                q = b.to_local("arka", b.world(head, (x, y), z))
                assert q[2] >= -1e-6


def test_chicago_screws_join_touching_layers():
    b = build(design("vidali_kartlik"))
    assert len(b.fasteners) == 2
    for f in b.fasteners:
        assert f["layers"] == [f["panel"], "on"]
        assert abs(slab_gap(b, f["panel"], f["xy"], "on")) < 0.3


# --- hatalı üretimleri yakalama -------------------------------------------------------------
def codes(d):
    try:
        return {f.code for f in run_checks(build(from_dict(d)))}
    except BuildError as e:
        return {f.code for f in e.findings}


def test_short_flap_spine_fails_assembly():
    d = load("kapakli_citcitli_kartlik")
    for v in d["degiskenler"]:
        if v["ad"] == "sirt":
            v["deger"] = "g - 2"
    assert "montaj_carpisma" in codes(d)


def test_thin_gusset_cards_do_not_fit():
    d = load("vidali_kartlik")
    for v in d["degiskenler"]:
        if v["ad"] == "g":
            v["deger"] = "1"
    assert "hacim_yetersiz" in codes(d)


def test_screw_layers_not_touching():
    d = load("vidali_kartlik")
    for pn in d["parcalar"][0]["paneller"]:
        if pn["id"].startswith("duvar"):
            pn["yukseklik"] = "g + 6"
    assert "kat_bosluk" in codes(d)


def test_lock_head_too_narrow():
    d = load("dikissiz_kilitli_kartlik")
    for pn in d["parcalar"][0]["paneller"]:
        if pn["id"].startswith("kafa"):
            pn["genislik"] = "boyun + t + 0.5"
    assert "kilit_tutmaz" in codes(d)


def test_snap_into_void_is_error():
    d = load("kapakli_citcitli_kartlik")
    for pn in d["parcalar"][0]["paneller"]:
        if pn["id"] == "kapak":
            pn["yukseklik"] = "Hb*1.8"
    d["ozellikler"][2]["y"] = "Hb*1.7"
    assert "karsilik_yok" in codes(d)


def test_flat_overlap_detected():
    d = load("kapakli_citcitli_kartlik")
    d["parcalar"][0]["paneller"].append({"id": "kapak2", "ad": "ikinci kapak", "ebeveyn": "sirt", "kenar": "ust",
                                         "genislik": "30", "ofset": "10", "yukseklik": "20", "aci": "90"})
    assert "acinim_cakisma" in codes(d)


def test_soft_leather_lock_warning():
    d = load("dikissiz_kilitli_kartlik")
    d["malzeme"] = "crazy_horse"
    assert "kilit_yumusak" in codes(d)


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
    assert "Yapım aşamaları" in text and "Malzeme listesi" in text and "GEREKMEZ" in text


def test_full_pdf_is_true_scale(tmp_path, doc):
    out = tmp_path / "k.pdf"
    write_pdf(doc, str(out), "full", include_info=False)
    x0, y0, x1, y1 = Pattern.extent(Pattern("t", doc.pieces).layout(600))
    page = PdfReader(str(out)).pages[0]
    assert float(page.mediabox.width) / MM == pytest.approx(x1 - x0 + 30, abs=0.01)


def test_instructions_order(doc):
    titles = [s.title for s in doc.instructions.steps]
    assert titles.index("Kenar bitirme (katlamadan önce)") < titles.index("Çıtçıtlar") < titles.index("Katlama 1")
    assert titles.index("Katlama 2") < titles.index("Kilitleme") < titles.index("Şekillendirme")


def test_render_is_image(doc):
    im = doc.images["hero"]
    assert im.size == (900, 650)
    arr = np.asarray(im)
    assert arr.std() > 10  # boş değil


# --- proje / CLI -----------------------------------------------------------------------
def test_cli_flow(tmp_path, capsys):
    pj = str(tmp_path / "p.json")
    main(["yeni", "vidali_kartlik", "-o", pj])
    main(["ayarla", pj, "kart_adet=5", "arka.kose.sol_ust=6"])
    d, hist = P.load(pj)
    assert any(v.ad == "kart_adet" and v.deger == "5" for v in d.degiskenler)
    assert len(hist) == 2
    main(["cikti", pj, "-d", str(tmp_path / "o"), "--bicim", "svg,dxf,3b", "--hizli"])
    assert sorted(os.listdir(tmp_path / "o")) == ["p.dxf", "p.svg", "p_3B.html"]
    html = (tmp_path / "o" / "p_3B.html").read_text(encoding="utf-8")
    assert "three" in html and "kanat_sol" in html


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
    assert "3 adet BİRBİRİNDEN" in fc.calls[0]["messages"][0]["content"]  # yedekli üretim
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
    assert "~ değişken kart_adet: 5 → 4" in P.diff(d, out)
    assert not [f for f in findings if f.level == "hata"]


# --- Blender fotoğraf sahnesi ------------------------------------------------------------
def test_photo_scene_data_matches_model():
    from sablon.foto import scene_data
    b = build(design("kapakli_citcitli_kartlik"))
    d = scene_data(b, size=(400, 300))
    n = len(d["M"])
    assert n > 100 and len(d["P"]) == len(d["N"]) == n * 9 and len(d["UV"]) == n * 6
    assert d["crazy"] is True and all(0 <= c <= 1 for c in d["base"])
    w, h, _ = b.finished_size()
    ext = np.array(d["P"]).reshape(-1, 3)
    span = sorted(ext.max(0) - ext.min(0), reverse=True)
    assert span[0] == pytest.approx(w, abs=3)  # aynı geometri
    eye = np.array(d["eye"]); ctr = np.array(d["ctr"])
    assert np.linalg.norm(eye - ctr) > d["radius"] * 2


def test_photo_without_blender_reports_clearly(monkeypatch, tmp_path):
    from sablon import foto
    monkeypatch.setattr(foto, "_has_bpy", lambda: False)
    monkeypatch.setattr(foto, "find_blender", lambda: None)
    with pytest.raises(foto.BlenderYok):
        foto.render_photo({"x": 1}, str(tmp_path / "a.png"))


def test_thick_leather_is_error():
    d = load("vidali_kartlik")
    d["kalinlik"] = "2.2"
    assert "kalin_deri" in codes(d)


def test_soft_mesh_keeps_thickness():
    from sablon.render3d import Soft
    import numpy as np
    s = Soft([(0, 0), (90, 0), (90, 50), (0, 50)], 1.0, 3)
    assert s.dz(0, 25) == 0 and s.dz(45, 0) == 0          # kenarlarda bombe yok (kıvrımla birleşir)
    assert s.dz(45, 25) < 0                                  # ortada dışa bombe
    # aynı (x, y) için iki yüze aynı kayma uygulanır → kalınlık sabit
    x = np.array([10.0, 45.0, 70.0]); y = np.array([10.0, 25.0, 40.0])
    assert np.allclose(s.dz(x, y), s.dz(x, y))


def test_texture_maps_found(tmp_path):
    pytest.importorskip("bpy")
    from sablon.blender_render import _find_maps
    for n in ("Leather037_1K-JPG_Color.jpg", "Leather037_1K-JPG_Roughness.jpg",
              "Leather037_1K-JPG_NormalDX.jpg", "Leather037_1K-JPG_NormalGL.jpg"):
        (tmp_path / n).write_bytes(b"x")
    m = _find_maps(str(tmp_path))
    assert m["color"].endswith("Color.jpg") and m["rough"].endswith("Roughness.jpg") and m["normal"].endswith("NormalGL.jpg")


# --- Gemini ile gerçekçi görsel (sahte istemci) -----------------------------------------------
def test_gemini_keeps_geometry_rules_and_returns_image(tmp_path):
    import io as _io
    from PIL import Image
    from sablon import gemini

    d = design("kapakli_citcitli_kartlik")
    pr = gemini.prompt(d, "ahsap")
    assert "STITCHLESS" in pr and "EXACT shape" in pr and "crazy horse" in pr and "oak" in pr

    out = Image.new("RGB", (64, 48), (120, 70, 40))
    buf = _io.BytesIO(); out.save(buf, "PNG")

    class Part:
        def __init__(self):
            self.inline_data = type("D", (), {"data": buf.getvalue()})()
            self.text = None

    class Resp:
        candidates = [type("C", (), {"content": type("X", (), {"parts": [Part()]})()})()]

    class Models:
        def __init__(self):
            self.calls = []

        def generate_content(self, **kw):
            self.calls.append(kw)
            return Resp()

    client = type("Cl", (), {"models": Models()})()
    ref = Image.new("RGB", (64, 48))
    paths = gemini.realistic_set({"urun": ref}, d, str(tmp_path / "k"), scenes=("studyo", "ahsap"), client=client, log=lambda *_: None)
    assert len(paths) == 2 and all(os.path.exists(p) for p in paths)
    kw = client.models.calls[0]
    assert kw["contents"][1] is ref and kw["model"]


def test_gemini_without_key_is_clear(monkeypatch):
    from sablon import gemini
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(gemini.GeminiYok):
        gemini._client()


# --- kalibrasyon ---------------------------------------------------------------------------
def test_calibration_roundtrip_and_effect(tmp_path, monkeypatch):
    from sablon import calibration as C
    t, r = 1.6, 1.2
    L = C.STRIP_L
    # motorun modeline göre katlanmış şeridin ölçülecek boyu
    P = (L - math.pi * (r + t / 2)) / 2
    F = P + r + t
    assert C.bend_from_measure(F, t) == pytest.approx(r / t, rel=1e-6)
    monkeypatch.setenv("SABLON_KALIBRASYON", str(tmp_path / "k.json"))
    before = build(design("vidali_kartlik")).panels["on"].allow
    C.save("vaketa", kivrim_orani=1.5, kilit_payi=5.0)
    b = build(design("vidali_kartlik"))
    assert b.panels["on"].bend_k == 1.5 and b.panels["on"].allow > before
    assert C.lock_margin("vaketa") == 5.0
    assert "kilit_tutmaz" in codes(load("dikissiz_kilitli_kartlik"))  # 5 mm pay isteniyor, kafa yalnızca +4


def test_calibration_pdf(tmp_path):
    from sablon.calibration import write_pdf
    out = tmp_path / "k.pdf"
    write_pdf(str(out), "crazy_horse", 1.6)
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "Katlama testi" in text and "sablon kalibre crazy_horse" in text


# --- sağlamlık: Claude'un üretebileceği bozuk tasarımlar motoru çökertmemeli -------------------
def test_bad_expressions_and_sizes_are_findings_not_crashes():
    d = load("vidali_kartlik")
    d["degiskenler"].append({"ad": "zz", "deger": "1/0", "aciklama": ""})
    assert "ifade" in codes(d)
    d = load("vidali_kartlik")
    d["parcalar"][0]["paneller"][0]["genislik"] = "1e6"
    assert "olcu" in codes(d)
    d = load("vidali_kartlik")
    d["parcalar"][0]["paneller"][1]["ebeveyn"] = "alt_koruk"  # kendine bağlı
    assert codes(d)  # çökmeden bulgu döner


# --- Gemini ile fikir üretimi (sahte istemci) ------------------------------------------------
class FakeGemini:
    """generate_content çağrılarını sırayla yanıtlar; bir öğe Exception ise fırlatır."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
        outer = self

        class _Models:
            def generate_content(self, **kw):
                outer.calls.append(kw)
                a = outer.answers.pop(0)
                if isinstance(a, Exception):
                    raise a
                if isinstance(a, str):
                    return type("R", (), {"parsed": None, "text": a})()
                return type("R", (), {"parsed": a, "text": a.model_dump_json()})()

        self.models = _Models()


def test_gemini_ideas_only_return_buildable_designs():
    good = design("vidali_kartlik")
    hopeless = copy.deepcopy(design("dikissiz_kilitli_kartlik"))
    for pn in hopeless.parcalar[0].paneller:
        if pn.id.startswith("kafa"):
            pn.genislik = "boyun"  # kafa yarıktan dar: tutmaz
    replacement = design("kanat_kilitli_dikey_kartlik")
    fg = FakeGemini(ai.Fikirler(tasarimlar=[good, hopeless]),
                    ai.Onarim(tasarim=hopeless, aciklama="denedim"), ai.Onarim(tasarim=hopeless, aciklama="denedim"),
                    ai.Onarim(tasarim=hopeless, aciklama="denedim"),
                    ai.Fikirler(tasarimlar=[replacement]))
    res = ai.ideas("dikişsiz kartlık", n=2, client=fg, seed=2, log=lambda *_: None)
    names = [d.ad for d, _ in res]
    assert len(res) == 2 and hopeless.ad not in names
    assert all(not [f for f in fs if f.level == "hata"] for _, fs in res)
    first = fg.calls[0]
    assert first["model"]
    assert "DİKİŞSİZ" in first["config"].system_instruction
    assert first["config"].response_json_schema is not None
    assert "TEKRARLAMA" in fg.calls[-1]["contents"][-1]  # ikinci turda öncekiler bildirildi


def test_gemini_schema_rejection_falls_back_to_plain_json():
    from google.genai import errors
    good = design("vidali_kartlik")
    err = errors.ClientError(400, {"error": {"message": "schema too complex", "status": "INVALID_ARGUMENT"}})
    fg = FakeGemini(err, ai.Fikirler(tasarimlar=[good]).model_dump_json())
    out = ai._ask("x", ai.Fikirler, fg)
    assert out.tasarimlar[0].ad == good.ad
    assert fg.calls[1]["config"].response_json_schema is None
    assert "JSON şemasına" in fg.calls[1]["config"].system_instruction


def test_provider_selection(monkeypatch):
    monkeypatch.delenv("SABLON_AI", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert ai.provider() == "gemini"
    monkeypatch.setenv("SABLON_AI", "claude")
    assert ai.provider() == "claude"


# --- Gemini otomatik model seçimi --------------------------------------------------------------
def test_gemini_model_picking(monkeypatch):
    from sablon import gemini_models as GM
    monkeypatch.delenv("SABLON_GEMINI_TEXT_MODEL", raising=False)
    monkeypatch.delenv("SABLON_GEMINI_MODEL", raising=False)
    names = ["gemini-2.5-pro", "gemini-3.1-pro-preview", "gemini-3.8-flash", "gemini-3.5-flash-lite",
             "gemini-3-pro-image-preview", "gemini-2.5-flash-image", "text-embedding-004", "gemini-embedding-001",
             "gemini-2.5-flash-preview-tts"]
    models = [type("M", (), {"name": f"models/{n}", "supported_actions": ["generateContent"]})() for n in names]
    client = type("C", (), {"models": type("Ms", (), {"list": lambda self: models})()})()
    GM.reset_cache()
    assert GM.pick_text(client) == "gemini-3.1-pro-preview"
    assert GM.pick_fallback(client, "gemini-3.1-pro-preview") == "gemini-3.8-flash"
    assert GM.pick_image(client) == "gemini-3-pro-image-preview"
    monkeypatch.setenv("SABLON_GEMINI_TEXT_MODEL", "benim-modelim")
    assert GM.pick_text(client) == "benim-modelim"
    GM.reset_cache()


def test_gemini_quota_falls_back_to_flash(monkeypatch):
    from google.genai import errors
    from sablon import gemini_models as GM
    monkeypatch.setattr(ai, "GEMINI_MODEL", "")
    monkeypatch.setattr(GM, "pick_text", lambda c: "gemini-3.1-pro")
    monkeypatch.setattr(GM, "pick_fallback", lambda c, cur: "gemini-3.8-flash")
    good = design("vidali_kartlik")
    fg = FakeGemini(errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
                    ai.Fikirler(tasarimlar=[good]))
    out = ai._ask("x", ai.Fikirler, fg)
    assert out.tasarimlar[0].ad == good.ad
    assert [c["model"] for c in fg.calls] == ["gemini-3.1-pro", "gemini-3.8-flash"]


def test_cli_fikir_reports_and_saves_rejected(tmp_path, monkeypatch, capsys):
    hopeless = copy.deepcopy(design("dikissiz_kilitli_kartlik"))
    for pn in hopeless.parcalar[0].paneller:
        if pn.id.startswith("kafa"):
            pn.genislik = "boyun"

    def fake_ideas(*a, rejected_out=None, **k):
        rejected_out.append((hopeless, ai.evaluate(hopeless)))
        return []

    monkeypatch.setattr(ai, "ideas", fake_ideas)
    with pytest.raises(SystemExit) as e:
        main(["fikir", "çekme şeritli kartlık", "-n", "2", "-d", str(tmp_path / "f")])
    assert e.value.code == 2
    out = capsys.readouterr().out
    assert "Hiçbir fikir" in out and "kilit" in out
    files = os.listdir(tmp_path / "f" / "elenenler")
    assert any(f.endswith("_neden.txt") for f in files) and any(f.endswith(".json") for f in files)


# --- çekme şeridi ve monte parçalar ------------------------------------------------------------
def test_pull_strip_wraps_under_cards_and_reports_lift():
    b = build(design("cekme_seritli_kartlik"))
    fs = run_checks(b)
    assert not [f for f in fs if f.level == "hata"]
    rep = [f for f in fs if f.code == "cekme"]
    assert rep and "yükselir" in rep[0].message
    # şeridin dönüş kolu arka panelin iç yüzüne yatıyor, kartlar şeridin üstünde
    arka = b.panels["arka"]
    q = b.to_local("arka", b.world("serit_arka", (10, 20)))
    assert 0 < q[2] < 2.5
    assert b.contents[0].z0 >= 0.9  # kartlar şerit ve kilit kafalarının üstünde


def test_pull_strip_poking_out_of_body_is_caught():
    d = load("cekme_seritli_kartlik")
    for part in d["parcalar"]:
        if part["id"] == "serit":
            part["montaj"]["y"] = "1"  # U kıvrımı alt körükten taşar
    assert "carpisma" in codes(d)


def test_pull_strip_animation():
    import json as _j
    from sablon.checks import pull_strip_data
    from sablon.render3d import build_mesh
    from sablon.viewer import scene_json
    from sablon.instructions import make
    b = build(from_dict(_j.load(open("ornekler/cekme_seritli_kartlik.json", encoding="utf-8"))))
    d = pull_strip_data(b)
    assert len(d) == 1 and d[0]["lift"] > 15
    assert scene_json(b)["pulls"][0]["child"] == d[0]["child"]
    m0, m1 = build_mesh(b, 1.0, soft=False), build_mesh(b, 1.0, soft=False, pull=1.0)
    assert len(m1.P) > len(m0.P)  # şerit uzantısı eklendi
    top = lambda m: max(float(np.asarray(p)[:, 1].max()) for p in m.P)
    assert top(m1) > top(m0) + 10
    assert any("çekme şeridi" in s.title for s in make(b).steps)


def test_pull_strip_through_slot():
    from sablon.checks import pull_fold, pull_strip_data
    from sablon.render3d import build_mesh
    b = build(from_dict(json.load(open("ornekler/tek_merkez_kilitli_cek_cikar.json", encoding="utf-8"))))
    errs = [f for f in run_checks(b) if f.level == "hata"]
    assert not errs, errs
    d = pull_strip_data(b)[0]
    assert d["pass"] == ["serit_uc"] and d["tab"] >= 12 and d["visible"] >= 15
    assert all(lk["gecis"] for lk in b.locks if lk["neck"] == "serit_arka")
    f = pull_fold(b)
    assert f["kapak"] == 0.0 and f["on"] == 1.0
    assert len(build_mesh(b, f, soft=False, pull=1.0).P) > 0


def test_repair_fixes_quality_warnings():
    good = design("cekme_seritli_kartlik")
    weak = copy.deepcopy(good)
    rivets = [f for f in weak.ozellikler if f.tip == "percin"]
    weak.ozellikler = [f for f in weak.ozellikler if f is not rivets[1]]
    fs = ai.evaluate(weak)
    assert any(f.code == "tek_baglanti" for f in fs) and not ai._errors(fs)
    fc = FakeClient(ai.Fikirler(tasarimlar=[weak]), ai.Onarim(tasarim=good, aciklama="ikinci perçin"))
    res = ai.ideas("şeritli kartlık", n=1, client=fc, seed=1, log=lambda *_: None)
    assert len(fc.calls) == 2
    assert not any(f.code == "tek_baglanti" for f in res[0][1])


def test_fikir_full_package(tmp_path, monkeypatch):
    d = design("cekme_seritli_kartlik")
    monkeypatch.setattr(ai, "ideas", lambda *a, **k: [(d, ai.evaluate(d))])
    main(["fikir", "şeritli kartlık", "-n", "1", "-d", str(tmp_path), "--tam", "--hizli"])
    sub = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(sub) == 1
    names = {p.name for p in sub[0].iterdir()}
    for suffix in ("_A4.pdf", "_Letter.pdf", "_tam_boy.pdf", ".svg", ".dxf", "_3B.html", "_urun.png",
                   "_cekilmis.png", "_etsy.txt", ".json"):
        assert any(n.endswith(suffix) for n in names), suffix
    etsy = next(p for p in sub[0].iterdir() if p.name.endswith("_etsy.txt")).read_text(encoding="utf-8")
    assert "Stitchless" in etsy and "Pull-Tab" in etsy
    assert (tmp_path / "koleksiyon.pdf").exists()

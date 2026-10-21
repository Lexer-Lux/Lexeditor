"""Maps selection panel layout: coordinates first, values fully shown.

The selection panel squeezed its record title (sixty-pixel header buttons),
listed Position/Rotation/Scale under separate headers below the Placement
group, and clipped coordinate values: each vector row split a narrow panel
into three tiny inputs with a help bubble per axis, and float32 tails
(179.99998 for 180 degrees) overflowed the boxes. Coordinates now come
first with no header above them, one help bubble serves each row,
rotations show at sensible precision, and header controls are compact.
"""
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from msb_fixture import build_msb  # noqa: E402
from plugins.ds1.msb import MsbDocument  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MAP = "m10_00_00_00.msb"
# A number input's spinner counts toward scrollWidth, so a fully visible
# value can still read a few pixels over. Genuine clipping (float tails
# in tiny boxes) overflowed by twenty pixels or more.
SPINNER_SLOP = 16


@contextmanager
def selection_page(width, height):
    raw = make_archive()
    vanilla = build_msb(parts=(("enemy", 2, 0, 0, 120000, (-170.125, -100.5, 30.25)),
                              ("player", 4, 0, 1, None)))
    doc = MsbDocument(vanilla, MAP)
    doc.edit((2, 0), "rotY", 179.99998474121094)
    vanilla = bytes(doc.plain)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-selection-') as temp:
        game, mod = Path(temp) / 'game', Path(temp) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / "map" / "MapStudio").mkdir(parents=True)
        (game / "map" / "MapStudio" / MAP).write_bytes(vanilla)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0',
                              'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': width, 'height': height})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function(
                        "state.tab==='maps' && state.mapView && state.rows.length>0",
                        timeout=60000)
                    page.locator('[data-tabstrip-id="selection"]').click()
                    page.wait_for_timeout(600)
                    yield page
                finally:
                    browser.close()
        finally:
            session.stop()


def vector_inputs(page):
    return page.locator("[data-maps-side] .lex-multi-number input").evaluate_all(
        "nodes=>nodes.map(n=>({key:n.getAttribute('data-field-key'),value:n.value,"
        "w:n.clientWidth,sw:n.scrollWidth}))")


def test_selection_vectors_show_full_value():
    with selection_page(1600, 900) as page:
        shown = vector_inputs(page)
        assert len(shown) == 9, shown
        for box in shown:
            assert box["sw"] <= box["w"] + SPINNER_SLOP, box
        assert page.locator("[data-maps-side] [data-field-key='rotY']").input_value() == "180"
        page.set_viewport_size({"width": 1100, "height": 800})
        page.wait_for_timeout(500)
        for box in vector_inputs(page):
            assert box["sw"] <= box["w"] + SPINNER_SLOP, box


def test_selection_vectors_come_first_without_headers():
    with selection_page(1600, 900) as page:
        sections = page.locator(
            "[data-maps-side] .lex-detail-section-title-text").evaluate_all(
            "nodes=>nodes.map(n=>n.textContent)")
        assert sections == ["Placement"], sections
        order = page.locator("[data-maps-side] .lex-detail-panel-body").evaluate(
            """n => [...n.querySelectorAll('.lex-detail-field-label-text,'
              + ' .lex-detail-section-title-text')].map(e => e.textContent.trim())""")
        assert order[:4] == ["Position", "Rotation", "Scale", "Placement"], order
        assert page.locator(
            "[data-maps-side] .lex-multi-number .lex-info-help").count() == 0
        assert page.locator(
            "[data-maps-side] .lex-detail-field:has(.lex-multi-number) > "
            ".lex-detail-field-label .lex-info-help").count() == 3
        header = page.locator("[data-maps-side] .lex-detail-panel-heading").evaluate(
            """n => {
              const buttons = [...n.querySelectorAll('.lex-detail-panel-actions'
                + ' .lex-header-icon:not(.lex-detail-add-header)')].map(b => {
                  const r = b.getBoundingClientRect(); return {w: r.width, h: r.height}; });
              const meta = n.querySelector('.lex-detail-panel-meta');
              return {buttons, metaText: meta ? meta.textContent : null,
                metaClipped: meta ? meta.scrollWidth > meta.clientWidth + 1 : null};
            }""")
        assert len(header["buttons"]) == 3, header
        for button in header["buttons"]:
            assert abs(button["w"] - 28) <= 1, header
            assert abs(button["h"] - 28) <= 1, header
        assert header["metaClipped"] is False, header

"""DS1 animations tab on the shared viewer: transport, shortcuts, menu.

The DS1 viewer keeps its textured Havok-mapped playback and gains the shared
transport row, arrow/space bindings and context-filtered shortcuts menu.
Synthetic fixtures only; read-only with no mod.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd, build_tae
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

LABELS = ["Go to animation start", "Back one frame", "Play or pause",
          "Forward one frame", "Go to animation end"]
ANIM_IDS = ["anim-start", "anim-prev", "anim-play", "anim-next", "anim-end"]


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-anim-viewer-") as folder:
        temp = Path(folder)
        game = temp / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "chr").mkdir(parents=True)
        tag = build_tag0()
        red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
        tpf = make_tpf([("tex0", red)])
        cid = "c1200"
        members = {"Skeleton.hkx": tag, "a87.tae": build_tae()}
        for m in range(3):
            members[f"a87_{3300 + m}.hkx"] = tag
        (game / "chr" / f"{cid}.anibnd.dcx").write_bytes(build_anibnd(members))
        (game / "chr" / f"{cid}.chrbnd.dcx").write_bytes(
            make_chrbnd(build_flver(), cid, [(f"{cid}.tpf", tpf)]))
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1",
                              "LEXEDITOR_MOD_READ_ONLY": "1"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="animations"]').click()
                    page.wait_for_function('state.tab === "animations" && !state.error')
                    page.wait_for_selector("[data-anim-host][data-ready='true']", timeout=30000)
                    assert page.evaluate("typeof LexeditorUI.animationViewer") == "function"
                    assert page.evaluate(
                        "!!document.querySelector('[data-anim-host]')._animViewer")
                    modes = page.locator(
                        "[data-anim-host] .lex-model-view-modes button:not([data-anim-follow])")
                    assert modes.count() == 3
                    assert [modes.nth(index).get_attribute("aria-label")
                            for index in range(3)] == ["Regular", "Fullbright", "Wireframe"]
                    status = page.locator("[data-anim-status]").inner_text()
                    assert status.strip() == "", status
                    assert "Root motion" not in page.locator("[data-anim-timeline]").inner_text()
                    assert page.locator("[data-anim-timeline] .lex-anim-marker").count() >= 1
                    buttons = page.locator("[data-anim-timeline] [data-anim-transport] button")
                    assert buttons.count() == 5
                    assert [buttons.nth(index).get_attribute("aria-label")
                            for index in range(5)] == LABELS
                    follow = page.locator(
                        "[data-anim-host] .lex-model-view-modes [data-anim-follow]")
                    assert follow.count() == 1
                    assert follow.get_attribute("aria-label") == "Root motion"
                    assert follow.locator("svg").count() == 1
                    assert follow.inner_text().strip() == ""
                    assert follow.get_attribute("aria-pressed") == "false"
                    assert page.evaluate(
                        "document.querySelector('[data-anim-host]')"
                        "._animViewer.follow") is False
                    follow.click()
                    assert follow.get_attribute("aria-pressed") == "true"
                    assert page.evaluate(
                        "document.querySelector('[data-anim-host]')"
                        "._animViewer.follow") is True
                    follow.click()
                    assert follow.get_attribute("aria-pressed") == "false"
                    overflow = page.evaluate(
                        """() => { const host = document.querySelector(
                            '[data-anim-host]');
                            return {sw: host.scrollWidth, cw: host.clientWidth,
                                    sh: host.scrollHeight, ch: host.clientHeight}; }""")
                    assert overflow["sw"] <= overflow["cw"] + 1, overflow
                    assert overflow["sh"] <= overflow["ch"] + 1, overflow
                    for index in range(5):
                        box = buttons.nth(index).bounding_box()
                        assert abs(box["width"] - box["height"]) < 1, (index, box)
                    scrub = page.locator("[data-anim-timeline] .lex-anim-scrub").bounding_box()
                    bar = page.locator("[data-anim-timeline] [data-anim-transport]").bounding_box()
                    assert bar["y"] >= scrub["y"] + scrub["height"] - 1, (scrub, bar)
                    last = page.locator("[data-anim-timeline] input[type='range']").get_attribute("max")
                    readout = lambda: page.locator("[data-anim-readout]").text_content()
                    by_label = {label: buttons.nth(index) for index, label in enumerate(LABELS)}
                    by_label["Play or pause"].click()
                    by_label["Go to animation end"].click()
                    assert readout().startswith(f"{float(last):.1f}"), readout()
                    by_label["Go to animation start"].click()
                    assert readout().startswith("0.0"), readout()
                    by_label["Forward one frame"].click()
                    assert readout().startswith("1.0"), readout()
                    by_label["Back one frame"].click()
                    assert readout().startswith("0.0"), readout()
                    page.evaluate("document.activeElement?.blur()")
                    page.keyboard.press("ArrowRight")
                    assert readout().startswith("1.0"), readout()
                    page.keyboard.press("ArrowLeft")
                    assert readout().startswith("0.0"), readout()
                    page.keyboard.press("Shift+ArrowRight")
                    assert readout().startswith(f"{float(last):.1f}"), readout()
                    page.keyboard.press("Shift+ArrowLeft")
                    assert readout().startswith("0.0"), readout()
                    glyph = lambda: page.locator(
                        "[data-anim-timeline] [aria-label='Play or pause']").text_content()
                    paused_glyph = glyph()
                    page.keyboard.press("Space")
                    assert glyph() != paused_glyph
                    if output:
                        page.wait_for_timeout(300)
                        page.screenshot(path=str(output / "ds1-anim-viewer.png"))
                        page.locator("[data-anim-host] .lex-model-view-modes").screenshot(
                            path=str(output / "ds1-anim-viewmodes.png"))
                        page.locator("[data-anim-timeline]").screenshot(
                            path=str(output / "ds1-anim-transport.png"))
                    opener = page.locator("#lexeditor-shortcuts")
                    opener.click()
                    found = page.locator("[data-lex-shortcut^='anim-']").evaluate_all(
                        "rows => rows.map(row => row.dataset.lexShortcut)")
                    assert found == ANIM_IDS, found
                    if output:
                        page.screenshot(path=str(output / "ds1-shortcuts-in-anim.png"))
                    page.keyboard.press("Escape")
                    page.locator('button[data-tab="items"]').click()
                    page.wait_for_function('state.tab === "items"')
                    page.wait_for_timeout(500)
                    opener.click()
                    assert page.locator('[data-lex-shortcut^="anim-"]').count() == 0
                    assert page.locator('[data-lex-shortcut="save"]').count() == 1
                    if output:
                        page.screenshot(path=str(output / "ds1-shortcuts-outside.png"))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 animation viewer passed.")


if __name__ == "__main__":
    main()

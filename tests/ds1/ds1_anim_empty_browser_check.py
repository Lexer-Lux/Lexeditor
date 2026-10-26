"""A character with no animations: grayed tab, bind pose in the viewport.

The Animations tab disables itself with its reason, and the viewport
holds the model's bind pose instead of playback: ready, finite bones,
no motion, an empty status line. Synthetic binders only.
"""
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-anim-empty-") as folder:
        temp = Path(folder)
        game = temp / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "chr").mkdir(parents=True)
        (game / "chr" / "c1200.anibnd.dcx").write_bytes(
            build_anibnd({"Skeleton.hkx": build_tag0()}))
        (game / "chr" / "c1200.chrbnd.dcx").write_bytes(
            make_chrbnd(build_flver(), "c1200"))
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
                    page.wait_for_selector("[data-anim-chars] .lex-list-row")
                    page.locator("[data-anim-chars] .lex-list-row").first.click()
                    page.wait_for_function("state.animCharId && state.animView")
                    tab = page.locator('[data-anim-left] [data-tabstrip-id="anims"]')
                    assert tab.get_attribute("aria-disabled") == "true"
                    assert tab.get_attribute("aria-description") == "This character has no animations."
                    assert page.evaluate("state.animLeftTab") != "anims"
                    page.wait_for_selector("[data-anim-host][data-ready='true']", timeout=30000)
                    posed = page.evaluate(
                        "document.querySelector('[data-anim-host]')._animBones()")
                    assert posed, "bind pose mounted no bones"
                    assert all(isinstance(bone["peak"], (int, float)) and
                               all(math.isfinite(v) for v in bone["pos"])
                               for bone in posed), posed
                    assert page.evaluate(
                        "document.querySelector('[data-anim-host]')._animViewer.toEvent") is None
                    assert page.locator("[data-anim-status]").inner_text().strip() == ""
                    skeleton = page.locator(
                        "[data-anim-host] .lex-model-view-modes [data-anim-skeleton]")
                    assert skeleton.count() == 1
                    assert skeleton.get_attribute("aria-pressed") == "true"
                    assert page.evaluate(
                        "document.querySelector('[data-anim-host]')._animSkeletonShown()") is True
                    if output:
                        page.screenshot(path=str(output / "ds1-anim-empty.png"))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 empty animations passed.")


if __name__ == "__main__":
    main()

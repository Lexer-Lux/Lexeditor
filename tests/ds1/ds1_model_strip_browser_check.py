"""DS1 Models strip shows companion-archive textures, not just embedded ones.

A character binder names its maps; the game keeps them in a sibling
character's binder. The strip resolves and shows those tiles inline.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from playwright.sync_api import sync_playwright
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import RELATIVE
from test_ds1_assets import make_tpf, make_uncompressed_dds


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-model-strip-") as temporary:
        game = Path(temporary) / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "chr").mkdir(parents=True)
        (game / "chr" / "c1200.chrbnd.dcx").write_bytes(
            make_chrbnd(build_flver(tex_name="c9999_cloak.tga"), stem="c1200"))
        (game / "chr" / "c9999.chrbnd.dcx").write_bytes(make_chrbnd(
            build_flver(), stem="c9999",
            extra=[("c9999.tpf", make_tpf([("c9999_cloak", make_uncompressed_dds(8, 4))]))]))
        with DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                         "LEXEDITOR_NO_MOD": "1"}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1600, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate('navigate("models", "files", "Asset:chr/c1200.chrbnd.dcx")')
                    page.wait_for_selector(".ds1-texture-tile img", timeout=120000)
                    tiles = page.locator(".ds1-texture-tile")
                    assert tiles.count() == 1, tiles.count()
                    assert tiles.nth(0).locator(".ds1-texture-name").inner_text() == "c9999_cloak"
                    assert tiles.nth(0).locator("img").get_attribute("src").startswith("data:image/png")
                finally:
                    browser.close()
    assert not errors, errors
    print("Models strip shows companion textures inline.")


if __name__ == "__main__":
    main()

"""Animation load failures stay where they happen: no alerts while browsing.

A character without a skeleton, an unreadable motion list and failing
event rows each explain themselves inline - in the viewport, the
animations pane and the events pane - and never raise the alert dialog.
Synthetic binders only; the server answers from fixtures, and the
unreachable paths are stubbed at the HTTP layer with the backend's own
messages.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from tae_fixture import build_anibnd, build_tae
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-anim-errors-") as folder:
        temp = Path(folder)
        game = temp / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "chr").mkdir(parents=True)
        (game / "chr" / "c9999.anibnd.dcx").write_bytes(build_anibnd({"a00.tae": build_tae()}))
        (game / "chr" / "c9998.anibnd.dcx").write_bytes(build_anibnd({"a00.tae": build_tae()}))
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1",
                              "LEXEDITOR_MOD_READ_ONLY": "1"})
        errors = []
        mode = {"list": "stub-motion", "events": "live"}
        try:
            session.start()

            def router(route):
                url = route.request.url
                if "/api/anim/list" in url and mode["list"] == "stub-motion":
                    route.fulfill(status=200, content_type="application/json",
                                  body=('{"chr":"c9999","skeleton":false,"anims":['
                                        '{"file":"a00_3300.hkx","binder":"c9999.anibnd.dcx","bank":"a00",'
                                        '"id":3300,"duration":2.0,"frames":48,"tae":"a00.tae","taeIndex":0}]}'))
                elif "/api/anim/list" in url and mode["list"] == "fail":
                    route.fulfill(status=400, content_type="application/json",
                                  body='{"error":"Cannot open c9999.anibnd.dcx: not a Havok file"}')
                elif "scope=events" in url and mode["events"] == "fail":
                    route.fulfill(status=400, content_type="application/json",
                                  body='{"error":"Cannot open c9999.anibnd.dcx: not a Havok file"}')
                else:
                    route.fallback()

            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.route("**/api/**", router)
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="animations"]').click()
                    page.wait_for_function('state.tab === "animations" && !state.error')
                    page.wait_for_selector("[data-anim-host]")

                    def no_alert():
                        assert page.locator(".lex-important-dialog").count() == 0
                        assert page.locator(".lex-important-backdrop").count() == 0

                    # A motion whose skeleton is missing explains itself in
                    # the viewport; the backend's own message names the cause.
                    page.locator("[data-anim-chars] .lex-list-row").first.click()
                    page.wait_for_function("state.animCharId && state.rows.length>0")
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.locator("[data-anim-list] .lex-list-row").first.click()
                    page.wait_for_selector("[data-anim-host] .lex-notice")
                    notice = page.locator("[data-anim-host] .lex-notice").inner_text()
                    assert "No skeleton is installed" in notice, notice
                    assert page.locator("[data-anim-status]").inner_text().strip() != ""
                    no_alert()

                    # An unreadable motion list fills the animations pane.
                    mode["list"] = "fail"
                    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
                    page.locator("[data-anim-chars] .lex-list-row").nth(1).click()
                    page.wait_for_function("state.animListError")
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_selector("[data-anim-left] .lex-notice")
                    notice = page.locator("[data-anim-left] .lex-notice").inner_text()
                    assert "Cannot open c9999.anibnd.dcx" in notice, notice
                    no_alert()

                    # Failing event rows fill the events pane the same way.
                    mode["list"] = "stub-motion"
                    mode["events"] = "fail"
                    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
                    page.locator("[data-anim-chars] .lex-list-row").first.click()
                    page.wait_for_function("state.animCharId && state.rows.length>0")
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_selector("[data-anim-list] [data-anim-events]")
                    page.locator("[data-anim-list] [data-anim-events]").first.click()
                    page.wait_for_selector("[data-anim-left] .lex-notice")
                    notice = page.locator("[data-anim-left] .lex-notice").inner_text()
                    assert "Cannot open c9999.anibnd.dcx" in notice, notice
                    no_alert()
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 animation load failures stay inline without alerts.")


if __name__ == "__main__":
    main()

"""The Names page: the game's own name list, edited and saved end to end."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8.plugin import FF8Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def api(url: str, path: str) -> dict:
    with urlopen(url + path, timeout=120) as response:
        return json.load(response)


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-namedic-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 950})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                page.evaluate("()=>navigate('names')")
                page.wait_for_selector(".ff8-name-detail", timeout=60000)
                # The list pages at fifteen; the whole list is what this checks.
                page.evaluate("()=>{state.pageSizes.names=40;render()}")
                page.wait_for_selector(".ff8-name-detail", timeout=60000)
                rows = page.locator(".ff8-record-list .lex-list-row").count()
                assert rows == 32, rows
                field = page.locator('input[aria-label="Name 0"]')
                assert field.input_value() == "Galbadia"
                # The labels are drawn in the game's bitmap font, so the page's
                # own state, not the painted text, is what this reads.
                assert page.evaluate("()=>[state.data.names.count,state.data.names.bytes]") == [32, None]
                assert page.evaluate("()=>state.data.names.path").endswith("namedic.bin")
                field.fill("Galbadia Test")
                page.wait_for_function("()=>dirtyCount()>0", timeout=20000)
                page.evaluate("()=>document.querySelector('#global-save').click()")
                page.wait_for_function(
                    "()=>dirtyCount()===0&&document.querySelector('#global-save').disabled",
                    timeout=120000)
                stored = api(session.url, "/api/namedic?dataset=current")
                assert stored["rows"][0]["text"] == "Galbadia Test", stored["rows"][0]
                assert stored["rows"][1]["text"] == "Esthar", stored["rows"][1]
                assert api(session.url, "/api/namedic?dataset=vanilla")["rows"][0]["text"] == "Galbadia"
                assert not errors, errors
                print(json.dumps({"names": stored["count"], "edited": stored["rows"][0]["text"],
                                  "untouched": stored["rows"][1]["text"],
                                  "vanillaKept": True}, ensure_ascii=True))
                browser.close()
        return 0
    finally:
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

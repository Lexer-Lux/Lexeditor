"""The Archives page: the game's own archives, listed and searched."""
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
    project = tempfile.TemporaryDirectory(prefix="lexeditor-archives-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            listing = api(session.url, "/api/archives")
            available = [row for row in listing["rows"] if row["available"]]
            assert available, listing
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 950})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                page.evaluate("()=>{state.tab='archives';render()}")
                page.wait_for_selector(".ff8-archive-list", timeout=60000)
                page.wait_for_function(
                    "()=>document.querySelectorAll('.ff8-archive-list .lex-list-row').length>0",
                    timeout=60000)
                rows = page.locator(".ff8-archive-list .lex-list-row").count()
                assert rows >= 5, rows
                # The archive picker lists every archive, and the search reaches
                # an entry by its stored name.
                options = page.locator(".ff8-archive-panel select option").count()
                assert options == len(listing["rows"]), options
                page.locator(".ff8-archive-panel select").select_option("main")
                page.wait_for_function(
                    "()=>document.querySelectorAll('.ff8-archive-list .lex-list-row').length>0",
                    timeout=60000)
                searched = page.evaluate("""async ()=>{const response=await fetch('/api/archive?'+
                  new URLSearchParams({name:'main',query:'namedic',page:'0',pageSize:'10'}));
                  return response.json()}""")
                assert searched["matched"] == 1, searched
                assert searched["rows"][0]["basename"] == "namedic.bin", searched["rows"][0]
                # The detail panel copies one entry into the project.
                page.locator(".ff8-archive-list .lex-list-row").first.click()
                button = page.get_by_role("button", name="Extract copy")
                assert button.count() == 1, button.count()
                button.click()
                # The written path is shown in a field the game's bitmap font
                # draws, so the proof is the file itself.
                extracted = []
                for _ in range(120):
                    extracted = sorted((Path(project.name) / "extracted" / "main").glob("*"))
                    if extracted:
                        break
                    page.wait_for_timeout(500)
                assert extracted and extracted[0].stat().st_size > 0, extracted
                assert not errors, errors
                print(json.dumps({"archivesListed": options, "available": len(available),
                                  "visibleRows": rows, "namedic": searched["rows"][0]["name"],
                                  "extracted": extracted[0].name,
                                  "totals": {row["name"]: row["entries"] for row in available}},
                                 ensure_ascii=True))
                browser.close()
        return 0
    finally:
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

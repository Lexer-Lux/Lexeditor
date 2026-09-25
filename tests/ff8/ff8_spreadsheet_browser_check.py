"""The Data Map's spreadsheet bar: export a table, edit it, import it back."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8.plugin import FF8Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"} if payload is not None else {})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-spreadsheet-ui-",
                                          ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 1000},
                                        accept_downloads=True)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                page.evaluate("()=>{state.tab='datamap';render()}")
                page.wait_for_selector(".ff8-spreadsheet-bar", timeout=60000)
                page.wait_for_function(
                    "()=>document.querySelectorAll('.ff8-spreadsheet-bar select option').length>0",
                    timeout=60000)
                options = page.locator(".ff8-spreadsheet-bar select option").count()
                assert options == len(api(session.url, "/api/tables")["rows"]), options
                # Export hands the browser a CSV of the chosen table.
                with page.expect_download(timeout=60000) as download:
                    page.get_by_role("button", name="Export CSV").click()
                path = download.value.path()
                text = Path(path).read_text(encoding="utf-8")
                header = next(csv.reader(io.StringIO(text)))
                assert header[0] == "id" and "buyPrice" in header, header
                # Import the same sheet with one price raised.
                rows = list(csv.DictReader(io.StringIO(text)))
                before = api(session.url, "/api/items?dataset=current")["rows"][1]["buyPrice"]
                rows[1]["buyPrice"] = str(int(rows[1]["buyPrice"]) + 10)
                buffer = io.StringIO()
                writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
                edited = Path(project.name).parent / "edited.csv"
                edited.write_text(buffer.getvalue(), encoding="utf-8")
                page.set_input_files(".ff8-spreadsheet-bar input[type=file]", str(edited))
                page.wait_for_function(
                    "()=>/row/.test(document.querySelector('.ff8-spreadsheet-bar').innerText)",
                    timeout=120000)
                after = api(session.url, "/api/items?dataset=current")["rows"][1]["buyPrice"]
                assert after == before + 10, (before, after)
                assert not errors, errors
                print(json.dumps({"tables": options, "header": header[:3],
                                  "priceBefore": before, "priceAfter": after}, ensure_ascii=True))
                browser.close()
        return 0
    finally:
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

"""What a world draw point gives: shown, edited and saved as a Hext patch.

Lexer asked to "edit the amount and spell on the draw points" through Hext,
the way Irvine's shots per turn are. The magic, refill and high-yield bits live
in FF8_EN.exe's DrawPointData table (codex/ff8/world-draw-points.md); a save
writes only the changed bytes to the project's own Hext patch, and the page
reads them back from it.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import draw_point_data  # noqa: E402
from plugins.ff8.plugin import FF8Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def api(url: str, path: str) -> dict:
    with urlopen(url + path, timeout=120) as response:
        return json.load(response)


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-draw-gives-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            vanilla = api(session.url, "/api/draw-point-data?dataset=vanilla")
            assert not vanilla.get("error"), vanilla
            first = next(row for row in vanilla["rows"] if row["id"] == 129)
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=["--mute-audio"])
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                page.evaluate("()=>{state.worldTab='drawPoints';state.selected.world=0;navigate('world')}")
                section = page.locator("section[aria-label='WHAT IT GIVES']")
                section.wait_for(timeout=60000)
                magic = page.evaluate("id=>state.data.magic.rows.find(r=>Number(r.id)===id)?.name", first["magicId"])
                assert magic and magic in section.inner_text(), (magic, section.inner_text())
                high = page.get_by_label("Draw Point 129 high yield", exact=True)
                refill = page.get_by_label("Draw Point 129 refill", exact=True)
                assert high.is_checked() == first["highYield"] and refill.is_checked() == first["refill"]
                high.click()
                refill.click()
                page.wait_for_function("()=>dirtyCount()>0", timeout=20000)
                page.evaluate("()=>document.querySelector('#global-save').click()")
                page.wait_for_function("()=>dirtyCount()===0", timeout=120000)
                assert not errors, errors
                browser.close()
            patch = Path(project.name) / "hext" / "ff8" / "en_nv" / draw_point_data.PATCH_NAME
            assert patch.is_file(), patch
            lines = [line for line in patch.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
            expected = first["magicId"] | (0 if first["refill"] else 0x40) | (0 if first["highYield"] else 0x80)
            assert lines == [f"{draw_point_data.TABLE_ADDRESS + 128:X} = {expected:02X}  # draw ID 129"], lines
            current = next(row for row in api(session.url, "/api/draw-point-data?dataset=current")["rows"] if row["id"] == 129)
            assert current == {**first, "refill": not first["refill"], "highYield": not first["highYield"]}, current
            print(json.dumps({"drawId": 129, "magic": first["magicId"], "patch": lines}))
    finally:
        project.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The World to Field page: the table read, edited and saved end to end."""
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
    project = tempfile.TemporaryDirectory(prefix="lexeditor-wm2field-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 950})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                page.wait_for_function("()=>!!(state.data&&state.data.wm2field)", timeout=180000)
                assert not page.evaluate("()=>!!state.bootFailed"), \
                    page.locator("#main").inner_text()[:200]
                # Set the tab directly: navigate() is async and can re-render
                # after this evaluate, which left the list on its default page.
                page.evaluate("""()=>{state.tab='world';state.worldTab='worldToField';
                  state.pageSizes.wm2field=80;state.pages.wm2field=0;state.selected.wm2field=0;render()}""")
                page.wait_for_selector(".world-to-field", timeout=60000)
                rows = page.locator(".ff8-record-list .lex-list-row").count()
                # The list fits its pane, so the visible count is not the table's
                # size; the data and the row content are what matter here.
                assert rows >= 10, rows
                assert page.evaluate("()=>state.data.wm2field.count") == 72
                assert page.evaluate("()=>state.data.wm2field.path").endswith("wm2field.tbl")
                # The list names the field each position leads to, from the
                # Field page's own list, not just the bare ID.
                named = page.evaluate("""()=>{const row=state.data.wm2field.rows[0];
                  const field=state.data.fields.rows.find(entry=>Number(entry.mapId)===Number(row.fieldId));
                  return field?field.name:''}""")
                assert named and named in page.locator(".ff8-record-list .lex-list-row").first.inner_text(), named
                # The detail is the entry's arrival in the field: the field's
                # name as a link on top, and its picture with the point drawn
                # (Lexer, 2026-09-27).
                title = page.locator(".world-to-field .lex-detail-panel-title .lex-hoverable[data-hover-target-type='fields']")
                assert title.inner_text().strip() == named, title.inner_text()
                page.wait_for_function(
                    "()=>{const s=document.querySelector('.world-to-field-picture');"
                    "return s&&s.style.visibility!=='hidden'&&s.querySelector('img').naturalWidth>0}", timeout=120000)
                marked = page.evaluate(
                    "()=>{const c=document.querySelector('.world-to-field-picture canvas');"
                    "const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;"
                    "for(let i=3;i<d.length;i+=4)if(d[i])return true;return false}")
                assert marked, "the arrival point is not drawn"
                bound = page.evaluate("()=>document.querySelector('input[aria-label=\"World to field 0 Z\"]').max")
                triangles = page.evaluate(
                    "name=>state.data.fields.rows.find(r=>r.name===name).walkmesh.triangles.length", named)
                assert int(bound) == triangles - 1, (bound, triangles)
                x_field = page.locator('input[aria-label="World to field 0 X"]')
                field_field = page.locator('input[aria-label="World to field 0 field ID"]')
                before = api(session.url, "/api/wm2field?dataset=current")["rows"]
                before_x = before[0]["x"]
                x_field.fill(str(before_x + 5))
                x_field.dispatch_event("change")
                field_field.fill("160")
                field_field.dispatch_event("change")
                page.wait_for_function("()=>dirtyCount()>0", timeout=20000)
                page.evaluate("()=>document.querySelector('#global-save').click()")
                page.wait_for_function(
                    "()=>dirtyCount()===0&&document.querySelector('#global-save').disabled",
                    timeout=120000)
                stored = api(session.url, "/api/wm2field?dataset=current")
                assert stored["rows"][0]["x"] == before_x + 5, stored["rows"][0]
                assert stored["rows"][0]["fieldId"] == 160, stored["rows"][0]
                assert stored["rows"][1] == before[1], (before[1], stored["rows"][1])
                vanilla = api(session.url, "/api/wm2field?dataset=vanilla")
                assert vanilla["rows"][0]["fieldId"] != 160, vanilla["rows"][0]
                assert not errors, errors
                print(json.dumps({"entries": stored["count"], "editedX": stored["rows"][0]["x"],
                                  "editedField": stored["rows"][0]["fieldId"],
                                  "nextEntryField": stored["rows"][1]["fieldId"],
                                  "vanillaField": vanilla["rows"][0]["fieldId"]}, ensure_ascii=True))
                browser.close()
        return 0
    finally:
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

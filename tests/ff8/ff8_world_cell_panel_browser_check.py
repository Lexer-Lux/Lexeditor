"""A world-map cell has one panel, on the Map page and on the Cells page.

Lexer, 2026-09-27: "the details panel for a region should also list the sky
colors, draw points, field->world, world->field, ground types, enemy
encounters", and the Map's panel should be the thing's own details panel.
World -> Field is left out: that table stores no world position
(codex/ff8/wm2field.md).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8.plugin import FF8Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PANEL = """()=>{const panel=document.querySelector('.world-segment-detail');return {
  sections:[...panel.querySelectorAll('.lex-detail-section-title')].map(n=>n.textContent.replace(/[?]\\s*$/,'').trim()),
  links:[...panel.querySelectorAll('.world-cell-links .lex-hoverable')].map(n=>n.textContent.trim()),
  rules:panel.querySelectorAll("[aria-label^='Encounter rules for cell'] .lex-column-list-row").length}}"""


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-cell-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=["--mute-audio"])
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                # The cell that holds the first placed draw point.
                cell, expected_rules = page.evaluate("""()=>{const rows=state.data.world.rows;
                  const point=rows.find(r=>r.kind==='drawPoint'&&(r.x||r.y));const at=worldDrawPosition(point);
                  const cell=Math.floor(at.y/4)*32+Math.floor(at.x/4);
                  const region=rows.find(r=>r.kind==='region'&&r.id===cell).regionId;
                  const grounds=rows.find(r=>r.kind==='worldSegment'&&r.id===cell).groundTypes;
                  return [cell,region===255?0:rows.filter(r=>r.kind==='helper'&&r.regionId===region&&grounds.includes(r.groundId)).length]}""")
                page.evaluate(f"()=>{{state.worldTab='map';state.worldMapPoint=null;state.worldMapSky=null;state.selected.world={cell};navigate('world')}}")
                page.wait_for_selector(".world-segment-detail .world-cell-links", timeout=60000)
                on_map = page.evaluate(PANEL)
                page.evaluate(f"()=>{{state.worldTab='regions';state.selected.world={cell};state.pages.world=0;state.filters.world='';renderWorldMap()}}")
                page.wait_for_function(f"()=>document.querySelector('.world-segment-detail .lex-detail-panel-title')?.textContent.includes('CELL {cell}')&&state.worldTab==='regions'", timeout=60000)
                on_cells = page.evaluate(PANEL)
                assert on_map == on_cells, (on_map, on_cells)
                assert on_map["sections"][:5] == ["WORLD MAP", "CELL", "IN THIS CELL", "ENCOUNTERS", "BLOCKS"], on_map
                assert any(link.startswith("Draw Point ") for link in on_map["links"]), on_map
                assert on_map["rules"] == expected_rules, (on_map, expected_rules)
                # A link opens the record's own page.
                page.locator(".world-cell-links .lex-hoverable", has_text="Draw Point").first.click()
                page.wait_for_function("()=>state.worldTab==='drawPoints'", timeout=20000)
                assert not errors, errors
                print(json.dumps({"cell": cell, **on_map}))
                browser.close()
    finally:
        project.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

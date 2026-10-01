"""A GF's ability slots link to the ability's record and have a thing finder.

Lexer, 2026-09-27: "gfs -> right panel -> abilites: shouldn't this be a
hoverable + thing finder?" The slot was a plain dropdown. It now shows the
ability as a hoverable that opens its category page, and a finder that picks
from any category because ability IDs are global.
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

SLOT_VALUES = "()=>state.data.gfs.rows.find(r=>r.id===state.selected.gfs).fields.filter(f=>/^ability[0-9]+$/.test(f.field)).map(f=>f.value)"


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-gf-ability-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=["--mute-audio"])
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                page.evaluate("()=>navigate('gfs')")
                table = page.locator("[data-gf-abilities='true']")
                table.wait_for(timeout=60000)
                rows = table.locator(".lex-column-list-row")
                finders = table.locator("button[aria-label^='Choose an ability']")
                assert finders.count() == rows.count() > 0, (finders.count(), rows.count())
                assert table.locator(".lex-column-list-cell[data-column-key='ability'] select").count() == 0, "the ability is still a dropdown"

                # The first row's name opens that ability on its category page.
                link = table.locator(".lex-hoverable[data-hover-target-type^='ability']").first
                assert link.count(), "the ability name is not a hoverable"
                first = [link.get_attribute("data-hover-target-type"), link.get_attribute("data-hover-target-id")]
                link.click()
                page.wait_for_function("()=>state.tab==='abilities'", timeout=20000)
                opened = page.evaluate("view=>[state.abilityTab,String(state.selected[view])]", first[0])
                assert opened == ["gfAbilities",first[1]], (opened, first)
                assert page.evaluate("view=>state.selected.gfAbilities===state.data[view].rows.find(r=>String(r.id)===String(state.selected[view])).abilityId", first[0])
                page.evaluate("()=>navigate('gfs')")
                table.wait_for(timeout=20000)
                before = page.evaluate(SLOT_VALUES)

                # Pick an ability from another category with the finder.
                finders.first.click()
                page.wait_for_function("()=>state.tab==='abilities'", timeout=20000)
                page.evaluate("state.filters.gfAbilities=state.data.abilityMenu.rows[5].name;state.pages.gfAbilities=0;renderAbilities()")
                candidate = page.locator(".ff8-record-list .lex-column-list-row").first
                candidate.wait_for(timeout=20000)
                picked = candidate.locator(".lex-column-list-cell[data-column-key='name']").inner_text().strip()
                box = candidate.bounding_box()
                page.mouse.move(box["x"] + 40, box["y"] + box["height"] / 2)
                page.mouse.down()
                page.wait_for_timeout(1500)
                page.mouse.up()
                page.wait_for_function("()=>state.tab==='gfs'", timeout=20000)
                after = page.evaluate(SLOT_VALUES)
                changed = [index for index, (old, new) in enumerate(zip(before, after)) if old != new]
                assert len(changed) == 1, (before, after)
                name = page.evaluate(
                    "value=>state.data.abilityMenu.rows.find(r=>Number(r.abilityId)===Number(value))?.name",
                    after[changed[0]])
                assert name == picked, (name, picked)
                assert picked in table.inner_text()
                assert not errors, errors
                print(json.dumps({"slots": rows.count(), "link": first, "picked": picked}))
                browser.close()
    finally:
        project.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

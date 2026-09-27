"""Exercise the production Encounter pages with synthetic data in a headless browser.

Checks Rules matrix coverage, shared eight-formation group details, common
record cards, actual group/formation/enemy finder selection and return, extra
enabled slots, group usage, and the World map surface's layout.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import re
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

ENEMIES = [
    {"id": 0, "name": "Bite Bug"},
    {"id": 1, "name": "Caterchipillar"},
    {"id": 2, "name": "Geezard"},
    {"id": 3, "name": "Funguar"},
]
for enemy in ENEMIES:
    enemy.update(available=True,fields=[])


def slot(index, enemy_id, enabled, level):
    return {"slot": index, "enemyId": enemy_id,
            "enemyName": ENEMIES[enemy_id]["name"] if enemy_id < len(ENEMIES) else f"Enemy {enemy_id}",
            "enabled": enabled, "visible": True, "loaded": True, "targetable": True,
            "x": 0, "y": 0, "z": 0, "level": level,
            "levelRule": {"mode": "fixed", "value": level, "raw": level}}


def formation(identifier, enabled_slots):
    """enabled_slots: {slot index: (enemy id, stored level byte)}."""
    slots = []
    for index in range(8):
        enemy_id, level = enabled_slots.get(index, (0, 1))
        slots.append(slot(index, enemy_id, index in enabled_slots, level))
    return {"id": identifier, "stageId": identifier, "flags": 0,
            "cameraMain": 0, "cameraSecondary": 0, "slots": slots}


FORMATIONS = [
    formation(0, {0: (0, 7), 1: (1, 12), 2: (2, 120)}),
    formation(1, {0: (3, 9), 6: (2, 30)}),           # a stored seventh slot
    formation(2, {0: (1, 4)}),
    formation(3, {0: (2, 255)}),
    formation(4, {0: (3, 6)}),
    formation(5, {0: (0, 252)}),
]

# region x ground -> group. Region 2 with ground 0 deliberately holds two rules
# so the clash marking can be measured; region 3 with ground 0 is terrain the
# map really uses with no rule at all.
RULES = [
    {"id": 0, "kind": "helper", "regionId": 1, "groundId": 0, "encounterGroup": 0},
    {"id": 1, "kind": "helper", "regionId": 1, "groundId": 2, "encounterGroup": 1},
    {"id": 2, "kind": "helper", "regionId": 2, "groundId": 0, "encounterGroup": 1},
    {"id": 3, "kind": "helper", "regionId": 2, "groundId": 0, "encounterGroup": 2},
    {"id": 4, "kind": "helper", "regionId": 3, "groundId": 2, "encounterGroup": 0},
]
GROUPS = [
    {"id": 0, "kind": "group", "encounters": [0, 1, 2, 3, 4, 5, 0, 1]},
    {"id": 1, "kind": "group", "encounters": [1, 1, 1, 1, 1, 1, 1, 1]},
    {"id": 2, "kind": "group", "encounters": [2, 2, 2, 2, 2, 2, 2, 2]},
    {"id": 3, "kind": "group", "encounters": [3, 3, 3, 3, 3, 3, 3, 3]},  # no rule reaches it
]
REGION_CELLS = [
    {"id": 0, "kind": "region", "x": 0, "y": 0, "regionId": 1},
    {"id": 1, "kind": "region", "x": 1, "y": 0, "regionId": 2},
    {"id": 2, "kind": "region", "x": 2, "y": 0, "regionId": 3},
]
SEGMENTS = [
    {"id": 0, "kind": "worldSegment", "x": 0, "y": 0, "groupId": 0, "polygonCount": 4,
     "groundTypes": [0, 2], "blocks": [{"id": 0, "polygonCount": 4, "vertexCount": 8}]},
    {"id": 1, "kind": "worldSegment", "x": 1, "y": 0, "groupId": 0, "polygonCount": 4,
     "groundTypes": [0], "blocks": [{"id": 0, "polygonCount": 4, "vertexCount": 8}]},
    {"id": 2, "kind": "worldSegment", "x": 2, "y": 0, "groupId": 0, "polygonCount": 4,
     "groundTypes": [0, 2], "blocks": [{"id": 0, "polygonCount": 4, "vertexCount": 8}]},
]
MODELS = [
    {"id": 0, "file": "c0m000.dat", "name": "Bite Bug", "modelKind": "monster", "enemyId": 0,
     "vertices": 100, "timCount": 1, "tims": [{"index": 0, "paletteCount": 1}],
     "sections": [], "counts": None, "editor": "models"},
]

WORLD = {"rows": RULES + REGION_CELLS + GROUPS + SEGMENTS,
         "helpers": RULES, "regions": REGION_CELLS, "groups": GROUPS, "segments": SEGMENTS,
         "drawPoints": [], "fieldReturns": [], "skyColors": [], "tracks": [], "textures": [],
         "width": 32, "height": 24, "sha256": "fixture"}

EMPTY = {"rows": []}
PAYLOADS = {
    "/api/dashboard": {"runtime": {"installed": False}, "baseline": {"root": "fixture"},
                       "game": {}, "themeSounds": {}},
    "/api/datamap": {"rows": []},
    "/api/editor-settings": {"showNewGame": False},
    "/api/settings": {"sections": []},
    "/api/references": {"rows": []},
    "/api/platform-config": {"sections": []},
    "/api/mods": {"rows": [], "composition": {}},
    "/api/encounters": {"rows": FORMATIONS},
    "/api/world-map": WORLD,
    "/api/enemies": {"rows": ENEMIES},
    "/api/models": {"rows": MODELS},
    "/api/init": {"general": {"fields": []}, "config": {"fields": []},
                  "characters": {"rows": []}, "inventory": {"rows": []},
                  "choices": {"magic": [], "items": []}},
    "/api/refine": {"rows": [], "tables": [], "choices": {}},
    "/api/fields": {"rows": []},
}


def payload(path: str):
    base = path.split("?", 1)[0]
    if base in PAYLOADS:
        return json.loads(json.dumps(PAYLOADS[base]))
    return json.loads(json.dumps(EMPTY))


def serve(route, request):
    url = request.url
    path = re.sub(r"^https?://[^/]+", "", url)
    base = path.split("?", 1)[0]
    if base.startswith("/api/"):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload(path)))
        return
    if base.startswith("/shared/"):
        target = ROOT / "ui" / base.rsplit("/", 1)[-1]
    elif base.endswith(".js") or base.endswith(".css") or base.endswith(".html"):
        target = ROOT / "plugins" / "ff8" / base.lstrip("/")
    else:
        route.fulfill(status=200, content_type="image/png", body=PNG)
        return
    if not target.is_file():
        route.fulfill(status=404, body="")
        return
    kind = {"js": "text/javascript", "css": "text/css", "html": "text/html"}[target.suffix[1:]]
    route.fulfill(status=200, content_type=f"{kind}; charset=utf-8",
                  body=target.read_text(encoding="utf-8"))


def text_of(locator):
    return " ".join(locator.all_inner_texts())


def main():
    failures = []
    shots = Path(tempfile.gettempdir()) / "lexeditor-dev"
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 950})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        shot = lambda name: page.screenshot(path=str(shots / f"ff8-encounters-{name}.png"))
        page.route("**/*", serve)
        page.goto("http://ff8.fixture/editor.html")
        page.wait_for_selector("nav button[data-tab='encounters']", timeout=20000)
        page.wait_for_function("() => typeof state !== 'undefined' && state.booting === false",
                               timeout=20000)
        page.wait_for_timeout(400)

        # ---- Encounters: three subtabs -----------------------------------
        page.click("nav button[data-tab='encounters']")
        page.wait_for_selector(".ff8-encounter-tabs", timeout=10000)
        tabs = page.locator(".ff8-encounter-tabs [role=tab]")
        labels = [value.strip().title() for value in
                  tabs.locator(".lex-tab-label-text").all_inner_texts()]
        assert labels == ["Formations", "Rules", "Groups"], labels
        helped = tabs.locator(".lex-info-help").count()
        assert helped == 3, f"every subtab needs its own help, found {helped}"
        assert page.locator(".lex-column-list-row").count() > 0, "Formations lost its list"
        page.click(".lex-column-list-row >> nth=0")
        page.wait_for_timeout(200)
        assert page.get_by_label("Slot 1 enabled", exact=True).count() == 1, \
            "Formations no longer shows the eight-slot formation editor"

        # ---- Rules: the axes ---------------------------------------------
        tabs.nth(1).click()
        page.wait_for_selector(".ff8-encounter-rule-table", timeout=10000)
        table = page.locator(".ff8-encounter-rule-table")
        headers = [value.strip() for value in
                   table.locator(".lex-column-list-header:not(.lex-matrix-column-axis) > .lex-column-list-head-cell").all_inner_texts()]
        assert headers[0] == "", headers
        assert [value.split("\n")[0].strip() for value in headers[1:]] == ["0", "2"], headers
        assert table.locator(".lex-matrix-row-axis .lex-matrix-axis-text").inner_text() == "REGION"
        assert table.locator(".lex-matrix-column-axis .lex-matrix-axis-text").inner_text() == "TERRAIN"
        assert table.locator(".lex-info-help").count() == 2
        assert table.locator('[role="rowheader"]').count() == 3
        axes = table.evaluate("""table => {
            const row = table.querySelector('.lex-matrix-row-axis').getBoundingClientRect();
            const column = table.querySelector('.lex-matrix-column-axis').getBoundingClientRect();
            const first = table.querySelector('.lex-column-list-row [data-column-key="ground:0"]').getBoundingClientRect();
            return {rowRight:row.right, columnLeft:column.left, columnBottom:column.bottom,
                    cellLeft:first.left, cellTop:first.top};
        }""")
        assert axes['rowRight'] < axes['cellLeft'], axes
        assert abs(axes['columnLeft'] - axes['cellLeft']) <= 1, axes
        assert axes['columnBottom'] < axes['cellTop'], axes
        region_column = [value.strip().lstrip("#").strip() for value in table.locator(
            ".lex-column-list-row > [data-column-key='regionId']").all_inner_texts()]
        assert region_column == ["1", "2", "3"], region_column
        # Rules uses the shared table fill behavior at different panel heights.
        for height in (950, 720):
            page.set_viewport_size({"width": 1500, "height": height})
            page.wait_for_timeout(100)
            bounds = table.evaluate("""table => {
                const last = table.querySelector('.lex-column-list-row:last-child');
                return {bottom: last.getBoundingClientRect().bottom,
                        panelBottom: table.getBoundingClientRect().top + table.clientHeight};
            }""")
            assert abs(bounds["bottom"] - bounds["panelBottom"]) <= 4, bounds
        page.set_viewport_size({"width": 1500, "height": 950})

        # A dense two-axis table must retain alignment while scrolling sideways.
        page.evaluate("""() => {
            window.savedRuleRows = state.data.world.rows;
            state.data.world.rows = [
                ...state.data.world.rows.filter(row => row.kind !== 'helper'),
                ...Array.from({length:20 * 32}, (_, id) => ({id, kind:'helper',
                    regionId:Math.floor(id / 32), groundId:id % 32, encounterGroup:0}))];
            renderEncounters();
        }""")
        page.wait_for_timeout(150)
        assert table.evaluate("table => table.scrollWidth > table.clientWidth")
        shot("matrix")
        table.evaluate("table => { table.scrollLeft = table.scrollWidth; }")
        alignment = table.evaluate("""table => {
            const head = table.querySelector('.lex-column-list-head-cell[data-column-key="ground:31"]').getBoundingClientRect();
            const cell = table.querySelector('.lex-column-list-row [data-column-key="ground:31"]').getBoundingClientRect();
            return Math.abs(head.left - cell.left) + Math.abs(head.right - cell.right);
        }""")
        assert alignment <= 2, alignment
        axis_visible = table.evaluate("""table => {
            const label = table.querySelector('.lex-matrix-column-axis .lex-matrix-axis-label').getBoundingClientRect();
            const panel = table.getBoundingClientRect();
            return label.left >= panel.left && label.right <= panel.right;
        }""")
        assert axis_visible, "the column axis label scrolled out of view"
        page.evaluate("""() => {
            state.data.world.rows = window.savedRuleRows;
            delete window.savedRuleRows;
            renderEncounters();
        }""")

        # A group finder edits only the chosen rule, then restores Rules.
        page.evaluate("state.activeSource='mine';renderEncounters();shell.refresh()")
        cell=page.get_by_label('Region 1 ground 0 encounter group',exact=True)
        assert cell.inner_text()=='0'
        cell.click()
        page.wait_for_selector('.lex-searcher-bar')
        candidate=page.locator("[aria-label='FF8 encounterGroups'] .lex-search-candidate").nth(2)
        candidate.dispatch_event('pointerdown',{'button':0,'pointerId':1})
        page.wait_for_timeout(900)
        page.wait_for_selector('.ff8-encounter-rule-table')
        assert page.evaluate("state.data.world.rows.find(r=>r.kind==='helper'&&r.id===0).encounterGroup")==2

        # ---- Rules: what exists, what is missing, what clashes ------------
        blanks = page.locator('[data-lex-rule-cell="blank"]')
        # Two cells have nothing stored; one of them is a pair the terrain
        # really uses, and that is the one the next line calls out.
        assert blanks.count() == 1, blanks.count()
        missing = page.locator('[data-lex-rule-cell="missing"]')
        assert missing.count() == 1, "the reachable pair with no rule is not called out"
        for status in (blanks.first, missing.first):
            assert status.is_disabled()
            fit = status.evaluate("""control => {
                const box = control.getBoundingClientRect();
                const cell = control.closest('.lex-column-list-cell').getBoundingClientRect();
                return {width:box.width / cell.width, height:box.height / cell.height};
            }""")
            assert fit['width'] > .95 and fit['height'] > .95, fit
        # The shared framework moves every title onto data-lex-title and
        # aria-description, so the explanation is read from there.
        assert "no rule is stored for it" in (missing.first.get_attribute("data-lex-title") or "")
        clash = page.locator('[data-lex-rule-cell="clash"]')
        assert clash.count() == 1, clash.count()
        assert clash.first.locator(".ff8-encounter-rule-input").count() == 2, "both clashing rules must stay editable"
        assert "Only one of them can decide" in (
            clash.first.locator(".lex-badge").get_attribute("data-lex-title") or "")
        shot("rules")
        assert table.locator('.lex-detail-panel-heading').count()==0
        assert table.locator('.ff8-encounter-rule-input').count()==len(RULES)
        preview=page.locator('.ff8-encounter-group-preview')
        assert preview.locator('.lex-detail-panel-name').inner_text().strip()=='Encounter group'
        rows=preview.locator('.ff8-encounter-formation-row')
        assert rows.count()==8
        assert preview.locator('select').count()==0
        assert rows.first.locator('[data-lex-battle-position]').count()==6
        assert rows.first.locator('.lex-record-card-title').first.inner_text()=='Caterchipillar'
        assert rows.first.locator('.lex-record-card-body').first.inner_text()=='Level 4'
        assert ''.join(rows.first.locator('.ff8-encounter-formation-link').inner_text().split())=='#2'
        assert rows.first.locator('.ff8-encounter-formation-link').evaluate("e=>getComputedStyle(e).writingMode")=='horizontal-tb'
        empty = preview.locator('[data-lex-empty-position]').first
        assert empty.locator('.lex-record-card-title').inner_text() == 'Empty'
        assert empty.locator('.lex-record-card-body').count() == 0
        shot('rules')
        page.evaluate("state.encountersTab='groups';state.selected.encounterGroups=2;renderEncounters()")
        page.wait_for_selector('.ff8-encounter-group-detail')

        # ---- Groups: list, finder, previews, reachability -----------------
        master = page.locator("[aria-label='FF8 encounterGroups']")
        master_headers = [value.strip().splitlines()[-2].strip()
                          for value in master.locator(".lex-column-list-head-cell").all_inner_texts()]
        assert master_headers == ["GROUP", "FORMATIONS", "ENEMIES", "RULES"], master_headers
        rule_counts = [value.strip() for value in master.locator(
            ".lex-column-list-row > [data-column-key='ruleCount']").all_inner_texts()]
        # Group 0 started with two rules; the cell edit above moved one of them
        # to group 2, and the list counts what the data now says.
        assert rule_counts == ["1", "2", "2", "none"], rule_counts
        identities = ["".join(value.split()) for value in master.locator(
            ".lex-column-list-row > [data-column-key='id']").all_inner_texts()]
        assert identities == ["#0", "#1", "#2", "#3"], identities
        detail = page.locator(".ff8-encounter-group-detail")
        assert "Encounter group" in detail.locator(".lex-detail-panel-title").inner_text()
        finders = detail.get_by_label(re.compile(r"^Choose the battle formation for group 2"))
        assert finders.count() == 8, f"eight battle slots, {finders.count()} finders"
        detail.locator('.ff8-encounter-formation-row').first.hover()
        finders.first.click()
        page.wait_for_timeout(200)
        assert page.locator(".lex-searcher-bar").count() == 1, \
            "the shared Searcher did not open for a formation slot"
        assert page.evaluate("() => state.encountersTab") == "formations"
        target=page.locator("[aria-label='FF8 encounters'] .lex-search-candidate").filter(has=page.locator('[data-column-key="id"]',has_text='#5'))
        assert target.count()==1,page.locator("[aria-label='FF8 encounters'] .lex-search-candidate").all_text_contents()
        target.hover()
        page.mouse.down()
        page.wait_for_timeout(900)
        page.mouse.up()
        actual=page.evaluate("state.data.world.rows.find(r=>r.kind==='group'&&r.id===2).encounters")
        assert actual==[5,2,2,2,2,2,2,2],actual

        page.evaluate("() => { state.encountersTab='groups'; state.selected.encounterGroups=3;"
                      " renderEncounters(); }")
        page.wait_for_selector(".ff8-encounter-group-detail", timeout=10000)
        unused = text_of(page.locator(".ff8-encounter-group-detail .lex-notice"))
        assert "never starts these battles" in unused, unused

        page.evaluate("() => { state.selected.encounterGroups=0; state.encounterBattleSlot=1;"
                      " renderEncounters(); }")
        page.wait_for_timeout(200)
        shot("groups")
        assert page.locator('.ff8-encounter-group-detail').get_by_text('Special level', exact=True).count() == 1
        assert 'Level byte' not in page.locator('.ff8-encounter-group-detail').inner_text()
        page.locator('.ff8-encounter-group-detail').get_by_text('Special level', exact=True).scroll_into_view_if_needed()
        shot('special-level')
        rows=page.locator('.ff8-encounter-group-detail .ff8-encounter-formation-row')
        assert rows.count()==8
        assert rows.nth(1).locator('[data-lex-battle-position]').count()==7
        bounds=page.evaluate("""() => {
          const rows=[...document.querySelectorAll('.ff8-encounter-group-detail .ff8-encounter-formation-row')];
          const usage=document.querySelector('.ff8-encounter-group-detail section[aria-label="WHERE THIS GROUP IS USED"]');
          return {bottom:rows.at(-1).getBoundingClientRect().bottom,usage:usage.getBoundingClientRect().top};
        }""")
        assert bounds['bottom']<=bounds['usage'],bounds
        # An enemy cell invokes the enemy finder, including previously empty cells.
        rows.first.locator('.lex-record-card').nth(3).hover()
        rows.first.get_by_label('Choose enemy for formation 0 slot 4',exact=True).click()
        page.wait_for_selector('.lex-searcher-bar')
        assert page.evaluate('state.tab')=='enemies'
        target=page.locator("[aria-label='FF8 enemies'] .lex-search-candidate").filter(has=page.locator('[data-column-key="id"]',has_text='#2'))
        target.hover()
        page.mouse.down()
        page.wait_for_timeout(900)
        page.mouse.up()
        page.wait_for_selector('.ff8-encounter-group-detail')
        assert page.evaluate("[state.data.encounters.rows[0].slots[3].enemyId,state.data.encounters.rows[0].slots[3].enabled]")==[2,True]

        # ---- World: the map panel is only the map -------------------------
        page.click("nav button[data-tab='world']")
        page.wait_for_selector(".ff8-world-map-panel", timeout=10000)
        panel = page.locator(".ff8-world-map-panel")
        assert panel.locator("h2").count() == 0, "the map panel still has a heading band"
        assert "World map" not in panel.inner_text(), panel.inner_text()[:200]
        world_tabs = [value.strip() for value in page.locator(
            ".ff8-world-tabs .lex-tab-label-text").all_inner_texts()]
        assert "Encounter Rules" not in world_tabs and "Encounter Groups" not in world_tabs, world_tabs
        panel_box = panel.bounding_box()
        # The map surface fills the pane; the image stage keeps its 4:3 ratio
        # and can letterbox without shrinking the interactive map container.
        stage = panel.locator(".lex-image-map").bounding_box()
        share = stage["height"] / panel_box["height"]
        assert share > 0.9, f"the map covers only {share:.0%} of its panel"

        shot("world-map")
        assert not errors, errors
        browser.close()
    if failures:
        raise SystemExit("\n".join(failures))
    print('PASS FF8 encounter matrix and group finder; shared eight-formation layouts, enemy cards, finder controls, usage and World map')


if __name__ == "__main__":
    main()

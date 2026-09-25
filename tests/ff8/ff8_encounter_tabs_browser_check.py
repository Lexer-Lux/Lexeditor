"""What this check measures, in its own words.

It loads the real FF8 editor page - `plugins/ff8/editor.html` and every module
it names, the shared framework, and the plugin stylesheet - in a headless
browser, with every `/api/...` call answered from a small hand-built FF8 data
fixture instead of an installed game. Nothing here reads game files.

It then opens the screens and measures:

  * the Encounters tab has three subtabs, Formations, Rules and Groups, each
    with its own question-mark help, and Formations still shows the eight-slot
    formation editor it always did;
  * the Rules subtab draws one axis of region codes and one axis of ground
    codes, and the value in a cell is the encounter group. Typing in a cell
    writes to the rule the game looks up, and only to that rule;
  * a region and ground pair with no stored rule reads as such, a pair the
    world terrain actually uses with no rule is called out separately, and a
    pair with two stored rules is marked as a clash. No control can add a rule,
    because the file cannot hold one;
  * the group preview shows the group's name in its heading as a hoverable that
    opens the Groups subtab at that group, and six preview boxes, each with the
    enemy's name above the box and the level it fights at below;
  * a formation that switches on a seventh slot gets a seventh box, so the
    six-box layout hides nothing that is stored;
  * the Groups subtab is a master list plus detail, its formation slots use the
    shared record finder (the same press-and-hold Searcher as the rest of FF8),
    and it says which rules reach a group and when none do;
  * the World tab's Map page is only the map: the panel has no heading band and
    the words "World map" appear nowhere on it, while the map fills the panel.

It prints what it proved and exits non-zero on the first failure.
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
    formation(3, {0: (2, 5)}),
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
                   table.locator(".lex-column-list-head-cell").all_inner_texts()]
        assert headers[0].startswith("REGION"), headers
        assert [value.split("\n")[0].strip() for value in headers[1:]] == ["GROUND 0", "GROUND 2"], headers
        region_column = [value.strip().lstrip("#").strip() for value in table.locator(
            ".lex-column-list-row > [data-column-key='regionId']").all_inner_texts()]
        assert region_column == ["1", "2", "3"], region_column

        # ---- Rules: a cell is the group, and editing it edits the lookup --
        cell = page.get_by_label("Region 1 ground 0 encounter group", exact=True)
        assert cell.input_value() == "0", cell.input_value()
        cell.fill("2")
        cell.dispatch_event("input")
        page.wait_for_timeout(150)
        stored = page.evaluate(
            "() => state.data.world.rows.filter(r=>r.kind==='helper').map(r=>"
            "[r.regionId,r.groundId,r.encounterGroup])")
        assert stored == [[1, 0, 2], [1, 2, 1], [2, 0, 1], [2, 0, 2], [3, 2, 0]], stored

        # ---- Rules: what exists, what is missing, what clashes ------------
        blanks = page.locator('[data-lex-rule-cell="blank"]')
        # Two cells have nothing stored; one of them is a pair the terrain
        # really uses, and that is the one the next line calls out.
        assert blanks.count() == 1, blanks.count()
        missing = page.locator('[data-lex-rule-cell="missing"]')
        assert missing.count() == 1, "the reachable pair with no rule is not called out"
        # The shared framework moves every title onto data-lex-title and
        # aria-description, so the explanation is read from there.
        assert "no rule is stored for it" in (missing.first.get_attribute("data-lex-title") or "")
        clash = page.locator('[data-lex-rule-cell="clash"]')
        assert clash.count() == 1, clash.count()
        assert clash.first.locator("input").count() == 2, "both clashing rules must stay editable"
        assert "Only one of them can decide" in (
            clash.first.locator(".lex-badge").get_attribute("data-lex-title") or "")
        shot("rules")
        summary = text_of(page.locator(".ff8-encounter-rules-panel .lex-detail-note"))
        assert "5 stored rules" in summary and "have no rule" in summary, summary
        # No control invents a rule: every input in the table belongs to a
        # stored rule, and there are exactly as many as the file holds.
        inputs = page.locator(".ff8-encounter-rule-table input[type=number]").count()
        assert inputs == len(RULES), f"{inputs} cell editors for {len(RULES)} stored rules"
        assert page.locator(".ff8-encounter-rules-panel button:has-text('Add')").count() == 0

        # ---- Rules: the group preview ------------------------------------
        preview = page.locator(".ff8-encounter-group-preview")
        heading = preview.locator(".lex-detail-panel-title .lex-hoverable")
        assert heading.count() == 1, "the group name is not a hoverable"
        assert heading.inner_text().strip() == "ENCOUNTER GROUP 2", heading.inner_text()
        boxes = preview.locator("[data-lex-battle-position]")
        assert boxes.count() == 6, f"expected six preview boxes, found {boxes.count()}"
        first = boxes.nth(0)
        assert first.locator("figcaption").inner_text().strip() == "Caterchipillar"
        assert first.locator(".lex-figure-footer").inner_text().strip() == "Level 4"
        widths = [round(boxes.nth(i).locator(".lex-icon-slot").bounding_box()["width"])
                  for i in range(6)]
        assert max(widths) - min(widths) <= 2, f"the six boxes are not one size: {widths}"
        name_top = first.locator("figcaption").bounding_box()["y"]
        box_top = first.locator(".lex-icon-slot").bounding_box()["y"]
        level_top = first.locator(".lex-figure-footer").bounding_box()["y"]
        assert name_top < box_top < level_top, (name_top, box_top, level_top)

        # ---- The hoverable goes to that group on the Groups subtab --------
        heading.click()
        page.wait_for_selector(".ff8-encounter-group-detail", timeout=10000)
        assert page.evaluate("() => state.encountersTab") == "groups"
        assert page.evaluate("() => state.selected.encounterGroups") == 2

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
        assert "ENCOUNTER GROUP 2" in detail.locator(".lex-detail-panel-title").inner_text()
        finders = detail.get_by_label(re.compile(r"^Choose the battle formation for group 2"))
        assert finders.count() == 8, f"eight battle slots, {finders.count()} finders"
        finders.first.click()
        page.wait_for_timeout(200)
        assert page.locator(".lex-searcher-bar").count() == 1, \
            "the shared Searcher did not open for a formation slot"
        assert page.evaluate("() => state.encountersTab") == "formations"
        page.locator(".lex-searcher-cancel").click()
        page.wait_for_timeout(200)

        page.evaluate("() => { state.encountersTab='groups'; state.selected.encounterGroups=3;"
                      " renderEncounters(); }")
        page.wait_for_selector(".ff8-encounter-group-detail", timeout=10000)
        unused = text_of(page.locator(".ff8-encounter-group-detail .lex-notice"))
        assert "never starts these battles" in unused, unused

        page.evaluate("() => { state.selected.encounterGroups=0; state.encounterBattleSlot=1;"
                      " renderEncounters(); }")
        page.wait_for_timeout(200)
        shot("groups")
        seventh = page.locator(".ff8-encounter-group-detail [data-lex-battle-position]")
        assert seventh.count() == 7, \
            f"a formation with a stored seventh slot must show it, found {seventh.count()}"

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
        stage = page.locator(".lex-image-map-stage").first.bounding_box()
        share = stage["height"] / panel_box["height"]
        assert share > 0.9, f"the map covers only {share:.0%} of its panel"

        shot("world-map")
        assert not errors, errors
        browser.close()
    if failures:
        raise SystemExit("\n".join(failures))
    print("FF8 Encounters: Formations/Rules/Groups subtabs each carry help; the rules table "
          "shows region codes 1-3 down one axis and ground codes 0 and 2 across the other, with "
          "the encounter group as the cell value; typing in a cell changed only that stored rule; "
          "a pair the terrain uses with no rule is flagged, an unused empty pair reads as a dash, "
          "and the pair with two stored rules is marked a clash with both still editable; no "
          "control can add a rule; the group preview heads with a hoverable group name that opened "
          "Groups at that group and drew six boxes with the enemy name above and its level below, "
          "growing to seven when a seventh slot is stored; a group with no rule says so; the "
          "formation slots open the shared Searcher; and the World map panel has no heading band, "
          "never says \"World map\", and the map covers over 90% of it.")


if __name__ == "__main__":
    main()

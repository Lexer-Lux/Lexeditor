"""Real rendered placement controls: list, edit, enemy select, save and reload."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1.formats import ItemDocument
from plugins.ds1.msb import MsbDocument
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright

MAP = "m10_00_00_00.msb"


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    root = os.environ.get("LEXEDITOR_DS1_ACCEPTANCE_ROOT")
    if root:
        raw = (Path(root) / RELATIVE).read_bytes()
        game_maps = sorted((Path(root) / "map" / "MapStudio").glob("*.msb"))
        assert game_maps, "Acceptance root has no maps"
        source_map = game_maps[0]
        vanilla_map = source_map.read_bytes()
        map_name = source_map.name
    else:
        raw = make_archive()
        vanilla_map = build_msb(parts=(("enemy", 2, 0, 0, 120000), ("enemy", 2, 1, 0, 120100),
                                       ("player", 4, 0, 1, None), ("piece", 0, 0, 1, None),
                                       ("chest", 1, 0, 1, None)))
        map_name = MAP
    digest = hashlib.sha256(raw).hexdigest()
    map_digest = hashlib.sha256(vanilla_map).hexdigest()
    npc_ids = sorted(row.row_id for row in ItemDocument(raw).params["NpcParam"].rows)
    placements = MsbDocument(vanilla_map, map_name).placements()
    enemy = next(p for p in placements if p["type"] == 2)
    other_npc = next(n for n in npc_ids if n != enemy["npc"])
    exact = lambda value: struct.unpack("<f", struct.pack("<f", value))[0]
    new_pos, new_rot = exact(enemy["pos"][0] + 2.5), exact(enemy["rot"][1] + 45.0)
    key = f"{enemy['type']}:{enemy['partId']}"
    chest = next((p for p in placements if p["type"] in (1, 9)), None)
    chest_pos = exact(chest["pos"][0] + 2.5) if chest else None
    chest_key = f"{chest['type']}:{chest['partId']}" if chest else None
    expected_options = len(npc_ids) + (0 if enemy["npc"] in npc_ids else 1)
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-maps-") as temp:
        game, mod = Path(temp) / "game", Path(temp) / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / "map" / "MapStudio").mkdir(parents=True)
        (game / "map" / "MapStudio" / map_name).write_bytes(vanilla_map)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1100, "height": 800})
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function("(n) => state.tab==='maps' && state.mapView && state.rows.length===n", arg=len(placements))
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    page.wait_for_selector('[data-maps-dir] .lex-column-list.lex-list-fill',
                                           timeout=30000)
                    assert page.locator('[data-maps-dir] .lex-column-list.lex-list-fill').count() == 1
                    assert page.locator('.lex-collapsible-handle').count() == 0
                    width = page.evaluate(
                        "() => document.querySelector('[data-maps-side]')"
                        ".getBoundingClientRect().width")
                    assert round(width) == 300, width
                    counts = page.evaluate('(name) => state.mapList.find(r=>r.id===name).values', arg=map_name)
                    assert set(counts) == {'npcs', 'drops', 'enemies'}, counts
                    if not root:
                        assert (counts['npcs'], counts['drops'], counts['enemies']) == (0, 0, 2), counts
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    assert page.locator('[data-maps-side] .lex-column-list.lex-list-fill').count() == 1
                    if not root:
                        titled = ["Rat", "Small Rat", "piece0",
                                  "chest0", "player0"]
                        assert sorted(page.evaluate("state.rows.map(r=>r.name)")) == sorted(titled)
                    else:
                        assert page.evaluate("state.rows.length") > 0
                    page.get_by_role("searchbox", name="Search placements").fill(enemy["name"])
                    if not root:
                        page.wait_for_function("(e) => state.selected.endsWith(e.key) && state.row?.name===e.name",
                                               arg={"key": ":" + key.split(":")[1], "name": "Rat"})
                    else:
                        page.wait_for_function("(e) => state.selected.endsWith(e.key) && state.row?.table===e.map",
                                               arg={"key": ":" + key.split(":")[1], "map": map_name})
                    title = page.locator(".lex-detail-panel-title").inner_text()
                    if not root:
                        assert title.strip() == "Rat", title
                    else:
                        assert map_name not in title and title.strip(), title
                    goto = page.locator('[data-maps-detail] [data-row-action="goto"]')
                    assert goto.count() == 1
                    assert "lex-header-icon" in (goto.first.get_attribute("class") or "")
                    assert page.locator("[data-maps-detail] .lex-multi-number").count() == 3
                    vectors = page.locator("[data-maps-detail] .lex-detail-field:has(.lex-multi-number) .lex-detail-field-label-text").evaluate_all("nodes=>nodes.map(n=>n.textContent)")
                    assert vectors == ["Position", "Rotation", "Scale"], vectors
                    rows = page.locator("[data-maps-detail] .lex-multi-number").evaluate_all(
                        "nodes=>nodes.map(n=>[...n.querySelectorAll('input')].map("
                        "i=>{const r=i.getBoundingClientRect();"
                        "return [r.left+r.width/2,r.top+r.height/2]}))")
                    for axes in rows:
                        assert len(axes) == 3, axes
                        assert max(y for _, y in axes) - min(y for _, y in axes) < 4, axes
                        assert max(x for x, _ in axes) - min(x for x, _ in axes) > 20, axes
                    units = page.locator("[data-maps-detail] .lex-unit").evaluate_all(
                        "nodes=>nodes.map(n=>n.textContent)")
                    assert units == ["m", "m", "m", "\u00b0", "\u00b0", "\u00b0", "\u00d7", "\u00d7", "\u00d7"], units
                    assert page.get_by_text(f"model {enemy['model']}", exact=False).count() >= 1
                    if output:
                        page.wait_for_timeout(250)
                        page.screenshot(path=str(output / "maps-list.png"))
                    field = page.locator('[data-field-key="posX"]:visible')
                    assert field.evaluate("n=>n.tagName") == "INPUT" and field.get_attribute("step") == "any"
                    assert field.get_attribute("min") is None and field.get_attribute("max") is None
                    field.fill(str(new_pos))
                    field.press("Tab")
                    page.wait_for_function("(x) => state.pending===0 && state.row.fields.find(f=>f.key==='posX').value===x", arg=new_pos)
                    rot = page.locator('[data-field-key="rotY"]:visible')
                    rot.fill(str(new_rot))
                    rot.press("Tab")
                    page.wait_for_function("(x) => state.pending===0 && state.row.fields.find(f=>f.key==='rotY').value===x", arg=new_rot)
                    npc = page.locator('[data-field-key="npcId"]:visible')
                    assert npc.evaluate("n=>n.tagName") == "SELECT"
                    assert npc.locator("option").count() == expected_options
                    npc.select_option(str(other_npc))
                    page.wait_for_function("(x) => state.pending===0 && state.row.fields.find(f=>f.key==='npcId').value===x", arg=other_npc)
                    if chest is not None:
                        page.locator('[data-tabstrip-id="placements"]').click()
                        box = page.get_by_role("searchbox", name="Search placements")
                        box.click(); box.press("ControlOrMeta+a"); box.press("Backspace"); box.fill(chest["name"])
                        if not root:
                            page.wait_for_function("(c) => state.selected.endsWith(':'+c.partId) && state.row?.name===c.name",
                                                   arg={"partId": chest["partId"], "name": "chest0"})
                        else:
                            page.wait_for_function("(c) => state.selected.endsWith(':'+c.partId) && state.row?.table===c.map",
                                                   arg={"partId": chest["partId"], "map": map_name})
                            assert page.locator('[data-field-key="npcId"]:visible').count() == 0
                        field = page.locator('[data-field-key="posX"]:visible')
                        field.fill(str(chest_pos))
                        field.press("Tab")
                        page.wait_for_function("(x) => state.pending===0 && state.row.fields.find(f=>f.key==='posX').value===x", arg=chest_pos)
                        if output:
                            page.screenshot(path=str(output / "maps-object.png"))
                    if output:
                        page.screenshot(path=str(output / "maps-detail.png"))
                    page.set_viewport_size({"width": 1000, "height": 700})
                    page.wait_for_timeout(400)
                    shown = page.locator("[data-maps-detail] .lex-multi-number input").evaluate_all(
                        "nodes=>nodes.map(n=>({w:n.clientWidth,sw:n.scrollWidth,value:n.value}))")
                    assert shown, "no coordinate inputs rendered"
                    for box in shown:
                        assert box["sw"] <= box["w"] + 1, box
                    if output:
                        page.screenshot(path=str(output / "maps-small.png"))
                    page.set_viewport_size({"width": 1100, "height": 800})
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    saved = MsbDocument((mod / "map" / "MapStudio" / map_name).read_bytes(), map_name)
                    got = {(p["type"], p["partId"]): p for p in saved.placements()}[(enemy["type"], enemy["partId"])]
                    assert (got["pos"][0], got["rot"][1], got["npc"]) == (new_pos, new_rot, other_npc)
                    if chest is not None:
                        moved = {(p["type"], p["partId"]): p for p in saved.placements()}[(chest["type"], chest["partId"])]
                        assert moved["pos"][0] == chest_pos
                    for field, value in (("npcId", 999999999), ("npcId", 2 ** 31), ("think", 1), ("posX", "far")):
                        try:
                            request_json(session.url + "api/edit", {"table": map_name, "id": key, "field": field, "value": value})
                            raise AssertionError("Invalid placement edit accepted")
                        except HTTPError as error:
                            assert error.code == 400
                    try:
                        request_json(session.url + "api/edit", {"table": "m99_00_00_00.msb", "id": key, "field": "posX", "value": 1.0})
                        raise AssertionError("Unknown map edit accepted")
                    except HTTPError as error:
                        assert error.code == 400
                    if chest is not None:
                        try:
                            request_json(session.url + "api/edit", {"table": map_name, "id": chest_key, "field": "npcId", "value": 120000})
                            raise AssertionError("Object enemy-swap accepted")
                        except HTTPError as error:
                            assert error.code == 400
                    session.stop()
                    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                                          "LEXEDITOR_NO_MOD": "1", "LEXEDITOR_MOD_READ_ONLY": "1"})
                    session.start()
                    page.goto(session.url + "?lexNoMod=1")
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function("state.tab==='maps' && state.rows.length>0 && !!state.row")
                    control = page.locator('[data-field-key="posX"]:visible')
                    assert control.is_disabled()
                    control.click(force=True)
                    page.get_by_text("Create a mod to edit?", exact=True).wait_for()
                    if output:
                        page.screenshot(path=str(output / "maps-vanilla-prompt.png"))
                    page.get_by_role("button", name="Cancel", exact=True).click()
                    try:
                        request_json(session.url + "api/edit", {"table": map_name, "id": key, "field": "posX", "value": 1.0})
                        raise AssertionError("Vanilla placement edit accepted")
                    except HTTPError as error:
                        assert error.code == 403
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
        assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == digest
        assert hashlib.sha256((game / "map" / "MapStudio" / map_name).read_bytes()).hexdigest() == map_digest
    print(json.dumps({"placements": len(placements), "enemySelectOptions": len(npc_ids),
                      "fieldsSavedReloaded": 3, "objectMoved": chest is not None,
                      "vanillaCreateModPrompt": True,
                      "originalUnchanged": True, "browserErrors": errors}))


if __name__ == "__main__":
    main()

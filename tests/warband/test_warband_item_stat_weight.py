"""Editing the non-weight stat rows must retain the separate weight property."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/shared"))
from test_shared_ui_feedback import page, framework
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_items_editor import SOURCE
from plugins.warband import server


def test_item_stat_edit_remove_add_preserves_weight_and_reloads(page, tmp_path, record_service):
    source = tmp_path / "module_items.py"
    source.write_text(SOURCE, encoding="utf-8")
    original = server.item_data()
    sent = []

    def api(route):
        path = route.request.url.split("http://fixture", 1)[1]
        if path in ("/api/items", "/api/items/save"):
            body = route.request.post_data_json if route.request.method == "POST" else None
            if body is not None:
                sent.append(body)
            status, result = record_service(path[len("/api/items"):], body, "/api/items")
            route.fulfill(status=status, json=result)
        elif path == "/api/build/start":
            route.fulfill(json={"started": True})
        elif path.startswith("/api/build/status"):
            route.fulfill(json={"running": False, "returnCode": 0, "cursor": 1, "lines": ["Build verified: fixture"]})
        else:
            route.fulfill(status=400, json={"error": "No model preview in this fixture"})

    framework(page)
    page.route("http://fixture/api/**", api)
    page.add_style_tag(path=str(ROOT / "plugins/warband/editor.css"))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    for script in ("field_controls.js", "editor.js", "troop_editor.js"):
        page.add_script_tag(path=str(ROOT / "plugins/warband" / script))
    page.add_script_tag(content="const shell={refresh(){},history:{clear(){}}};")
    page.evaluate("""data=>{
      state.items=data;state.activeSource='mine';state.tab='items';state.selectedItem='0';state.booting=false;
      moduleRecords={preflight(){},dirtyCount:()=>0,saveAll:async()=>({saved:0,files:[]})};renderItems();
    }""", original)
    weight = page.locator('[data-lex-property="weight"] input')
    weight.fill("3.25")
    weight.dispatch_event("change")
    speed = page.get_by_label("spd_rtng value 1", exact=True)
    speed.fill("100")
    speed.dispatch_event("change")
    assert weight.input_value() == "3.25"
    assert page.evaluate("effectiveItemField(state.items.rows[0],'stats')") == "weight(3.25)|spd_rtng(100)|weapon_length(90)"
    page.get_by_role("button", name="Remove the spd_rtng stat", exact=True).click()
    page.get_by_role("button", name="Remove the weapon_length stat", exact=True).click()
    assert page.evaluate("effectiveItemField(state.items.rows[0],'stats')") == "weight(3.25)"
    assert weight.input_value() == "3.25"
    page.get_by_label("Stat to add", exact=True).select_option("weapon_length")
    page.get_by_role("button", name="Add stat", exact=True).click()
    length = page.get_by_label("weapon_length value 1", exact=True)
    length.fill("125")
    length.dispatch_event("change")
    assert weight.input_value() == "3.25"
    page.evaluate("saveAll()")
    assert page.evaluate("state.status") == "Saved and build verified"
    assert len(sent) == 1
    reopened = server.item_data()
    assert reopened["rows"][0]["fields"]["stats"] == "weight(3.25)|weapon_length(125)"
    assert reopened["rows"][0]["weight"] == "3.25"
    assert reopened["rows"][1]["fields"] == original["rows"][1]["fields"]
    for key, value in original["rows"][0]["fields"].items():
        if key != "stats":
            assert reopened["rows"][0]["fields"][key] == value
    assert page.evaluate("dirtyCount()") == 0
    page.evaluate("async()=>{state.items=await api('/api/items');renderItems()}")
    assert weight.input_value() == "3.25"
    assert length.input_value() == "125"
    if destination := os.environ.get("LEXEDITOR_UI_SCREENSHOT_DIR"):
        Path(destination).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(destination) / "warband-item-stats.png"))

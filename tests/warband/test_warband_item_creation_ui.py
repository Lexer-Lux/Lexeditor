"""Shared Add writes a real temporary item source; only the compiler is mocked."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tests/shared"))
from test_shared_ui_feedback import page, framework
from test_warband_items_editor import SOURCE
from plugins.warband import server


def test_item_creation_from_shared_add(page, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "MODULE_SYSTEM", tmp_path)
    source = tmp_path / "module_items.py"
    source.write_text(SOURCE, encoding="utf-8")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    builds = []

    def api(route):
        path = route.request.url.split("http://fixture", 1)[1]
        try:
            if path == "/api/items/create":
                body = route.request.post_data_json
                result = server.create_item(body["recordIndex"], body["originalId"], body["id"], body["name"], body["sha256"])
            elif path == "/api/items":
                result = server.item_data()
            elif path == "/api/build/start":
                builds.append(True)
                result = {"started": True}
            elif path.startswith("/api/build/status"):
                result = {"running": False, "returnCode": 0, "cursor": 1, "lines": ["Build verified: fixture"]}
            else:
                result = {"error": "No preview in fixture"}
            route.fulfill(json=result)
        except Exception as error:
            route.fulfill(status=400, json={"error": str(error)})

    page.route("http://fixture/api/**", api)
    framework(page)
    page.add_style_tag(path=str(ROOT / "plugins/warband/editor.css"))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    page.add_script_tag(path=str(ROOT / "plugins/warband/field_controls.js"))
    page.add_script_tag(path=str(ROOT / "plugins/warband/editor.js"))
    page.add_script_tag(content="const shell={refresh(){},history:{clear(){}}};")
    page.evaluate("data=>{state.items=data;state.booting=false;renderItems();}", server.item_data())
    page.locator(".lex-table-add").click(force=True)
    page.get_by_label("New item ID", exact=True).fill("new_sword")
    page.get_by_label("New item name", exact=True).fill("New Sword")
    page.get_by_label("Copy from item", exact=True).select_option("0")
    destination = os.environ.get("LEXEDITOR_UI_SCREENSHOT_DIR")
    if destination:
        Path(destination).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(destination) / "warband-create-item.png"))
    page.get_by_role("button", name="Create and build", exact=True).click()
    page.wait_for_function("state.status === 'Saved and build verified'")
    assert builds == [True]
    assert server.item_rows()[-1]["id"] == "new_sword"
    assert page.evaluate("state.selectedItem") == "2"
    assert page.evaluate("state.items.rows.at(-1).name") == "New Sword"
    assert not errors, errors
    # Reload from disk, then verify pending edits disable creation.
    page.evaluate("async()=>{state.items=await api('/api/items');renderItems();}")
    assert page.locator(".warband-record-list").get_by_text("New Sword", exact=True).count() == 1
    page.evaluate("state.itemEdits={'0':{fields:{value:'123'}}};renderItems()")
    assert page.locator(".lex-table-add").get_attribute("aria-disabled") == "true"

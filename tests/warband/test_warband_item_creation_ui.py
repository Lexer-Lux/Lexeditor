"""Shared Add writes a real temporary item source; only the compiler is mocked."""
from pathlib import Path
import os
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tests/shared"))
from test_shared_ui_feedback import page, framework
from test_warband_items_editor import SOURCE
from test_warband_troop_editor import SOURCE as TROOP_SOURCE
from plugins.warband import server


@pytest.mark.parametrize('kind',['item','troop'])
def test_item_creation_from_shared_add(page, tmp_path, monkeypatch,kind):
    monkeypatch.setattr(server, "MODULE_SYSTEM", tmp_path)
    monkeypatch.setattr(server, "CREATED_LEDGER", tmp_path / ".lexeditor-created.json")
    view=kind+'s'
    source = tmp_path / f"module_{view}.py"
    source.write_text(SOURCE if kind=='item' else TROOP_SOURCE, encoding="utf-8")
    read_data=lambda:server.item_data() if kind=='item' else server.troop_data(tmp_path)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    builds = []

    def api(route):
        path = route.request.url.split("http://fixture", 1)[1]
        try:
            if path == "/api/items/create":
                body = route.request.post_data_json
                result = server.create_with_origin("items", body["id"], server.create_item,
                    body["recordIndex"], body["originalId"], body["id"], body["name"], body["sha256"])
            elif path == "/api/items":
                result = server.mark_created("items", server.item_data())
            elif path == '/api/troops/create':
                body=route.request.post_data_json
                result=server.create_with_origin('troops',body['id'],server.create_troop,tmp_path,
                    body['sha256'],body['recordIndex'],body['originalId'],body['id'],body['name'],body['plural'])
            elif path == '/api/troops':
                result=server.mark_created('troops',server.troop_data(tmp_path))
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
    page.add_script_tag(path=str(ROOT / "plugins/warband/troop_editor.js"))
    page.add_script_tag(content="const shell={refresh(){},history:{clear(){}}};")
    page.evaluate("({data,view})=>{state[view]=data;state.tab=view;state.booting=false;render();}", {'data':read_data(),'view':view})
    page.locator(".lex-table-add").click(force=True)
    page.get_by_label(f"New {kind} ID", exact=True).fill("new_copy")
    page.get_by_label(f"New {kind} name", exact=True).fill("New Copy")
    page.get_by_label(f"Copy from {kind}", exact=True).select_option("0")
    if kind=='troop':page.get_by_label('New troop plural name',exact=True).fill('New Copies')
    destination = os.environ.get("LEXEDITOR_UI_SCREENSHOT_DIR")
    if destination:
        Path(destination).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(destination) / f"warband-create-{kind}.png"))
    page.get_by_role("button", name="Create and build", exact=True).click()
    page.wait_for_function("state.status === 'Saved and build verified'")
    assert builds == [True]
    created=next(row for row in read_data()['rows'] if row['id']=='new_copy')
    assert created['name']=='New Copy'
    selected='selectedItem' if kind=='item' else 'selectedTroop'
    assert page.evaluate('key=>state[key]',selected)==str(created['recordIndex'])
    assert not errors, errors
    # Reload from disk, then verify pending edits disable creation.
    page.evaluate("async view=>{state[view]=await api('/api/'+view);render();}",view)
    assert page.locator(".warband-record-list").get_by_text("New Copy", exact=True).count() == 1
    # The created record carries the created-in-mod pen; the one it was copied
    # from does not.
    pens = page.locator(".warband-record-list .lex-column-list-row").filter(
        has=page.locator('[aria-label="Created in this mod"]'))
    assert pens.count() == 1 and "New Copy" in pens.first.inner_text(), pens.count()
    if destination:
        page.screenshot(path=str(Path(destination) / f"warband-created-pen-{kind}.png"))
    page.evaluate("state.itemEdits={'0':{fields:{value:'123'}}};render()")
    assert page.locator(".lex-table-add").get_attribute("aria-disabled") == "true"

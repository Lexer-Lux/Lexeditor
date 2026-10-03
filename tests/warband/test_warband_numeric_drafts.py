"""Hidden scalar/vector drafts must block all writers and survive navigation."""
from pathlib import Path
import sys
import os

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/shared"))
from test_shared_ui_feedback import page, framework
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_module_records import FIXTURES
from plugins.warband.module_records import SCHEMAS, dataset_data


@pytest.mark.parametrize("dataset,field,label,correct", [
    ("skills", "maxLevel", "Maximum level", "12"),
    ("postfx", "params1", "HDR parameters", "1.125"),
])
def test_hidden_numeric_draft_precedes_global_writers(page, tmp_path, record_service,
                                                    dataset, field, label, correct):
    source = tmp_path / SCHEMAS[dataset]["filename"]
    source.write_text(FIXTURES[source.name], encoding="utf-8")
    data = dataset_data(tmp_path, dataset)
    status, _ = record_service("/create", {"dataset": dataset, "sha256": data["sha256"],
        "recordIndex": 0, "originalId": data["rows"][0]["id"], "id": "copy"})
    assert status == 200
    posts = []
    writes = []
    page.on("request", lambda request: writes.append(request.url) if request.method == "POST" else None)

    def api(route):
        path = route.request.url.split("http://fixture/api/module-records", 1)[1]
        body = route.request.post_data_json if route.request.method == "POST" else None
        if body is not None:
            posts.append(body)
        status, result = record_service(path, body)
        route.fulfill(status=status, json=result)

    framework(page)
    page.route("http://fixture/api/module-records**", api)
    page.add_style_tag(path=str(ROOT / "plugins/warband/editor.css"))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    for script in ("field_controls.js", "editor.js", "module_records.js"):
        page.add_script_tag(path=str(ROOT / "plugins/warband" / script))
    page.evaluate("""({dataset,filename})=>{
      window.dataset=dataset;state.activeSource='mine';
      moduleRecords=WarbandModuleRecords.create({state,api,main:()=>document.querySelector('main'),
        toolbar:()=>document.querySelector('#toolbar'),refreshShell(){},renderApp:()=>moduleRecords.render(dataset),
        setStatus(){},hasPendingEdits:()=>false,dataMapRows:()=>[{dataset,filename,recordLabel:dataset}],sourceDraft:()=>false});
      moduleRecords.render(dataset);
    }""", {"dataset": dataset, "filename": source.name})
    control = page.locator(".lex-detail-field").filter(has_text=label).locator("input").first
    control.wait_for()
    before = source.read_bytes()
    for invalid in (("", "-1", "1.5") if dataset == "skills" else ("",)):
        control.fill(invalid)
        assert page.evaluate("moduleRecords.dirtyCount()") == 1
        assert page.evaluate("filename=>moduleRecords.fileHasEdits(filename)", source.name)
        saved = page.evaluate("moduleRecords.snapshot()")
        page.evaluate("moduleRecords.openRecord(dataset,1)")
        rejection = page.evaluate("async()=>{try{await moduleRecords.saveAll();return ''}catch(error){return error.message}}")
        assert any(message in rejection for message in ("finite number", "at least", "whole number"))
        page.evaluate("state.settingEdits={2:'0'};saveAll()")
        page.get_by_role("button", name="Confirm and Close", exact=True).click()
        assert page.evaluate("state.settingEdits[2]") == "0"
        assert not posts
        assert not writes
        assert source.read_bytes() == before
        page.evaluate("value=>{moduleRecords.restore(value);moduleRecords.render(dataset)}", saved)
        assert control.input_value() == invalid
        assert not control.evaluate("n=>n.checkValidity()")
    control.fill(correct)
    page.evaluate("moduleRecords.render(dataset)")
    assert control.input_value() == correct
    assert control.evaluate("n=>n.checkValidity()")
    external = before + b"\n# external source edit\n"
    source.write_bytes(external)
    rejection = page.evaluate("async()=>{try{await moduleRecords.saveAll();return ''}catch(error){return error.message}}")
    assert rejection
    assert source.read_bytes() == external
    assert page.evaluate("moduleRecords.dirtyCount()") == 1
    assert control.input_value() == correct
    page.evaluate("moduleRecords.load(dataset,true)")
    assert control.input_value() == correct
    page.evaluate("moduleRecords.saveAll()")
    assert len(posts) == len(writes) == 2
    assert posts[0]["edits"] == posts[1]["edits"]
    actual = dataset_data(tmp_path, dataset)["rows"][0]["fields"][field]
    assert (actual[0] if isinstance(actual, list) else actual) == float(correct)
    assert page.evaluate("moduleRecords.dirtyCount()") == 0
    assert dataset_data(tmp_path, dataset)["rows"][1]["fields"][field] == data["rows"][0]["fields"][field]
    if destination := os.environ.get("LEXEDITOR_UI_SCREENSHOT_DIR"):
        Path(destination).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(destination) / f"warband-numeric-{dataset}.png"))

"""All structured Module System lists can append a byte-preserving template."""
import os
from pathlib import Path
import sys
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/shared"))
from test_shared_ui_feedback import framework, page
from tests.warband import test_warband_module_records as fixtures
from plugins.warband import server
from plugins.warband.module_records import SCHEMAS, create_dataset_record, dataset_data, save_dataset


@pytest.fixture
def record_service(tmp_path, monkeypatch):
    """Exercise the production routes against isolated Module System files."""
    monkeypatch.setattr(server, "MODULE_SYSTEM", tmp_path)
    monkeypatch.setattr(server, "CREATED_LEDGER", tmp_path / ".lexeditor-created.json")
    monkeypatch.setenv("LEXEDITOR_MOD_READ_ONLY", "0")
    monkeypatch.setenv("LEXEDITOR_NO_MOD", "0")
    service = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    worker = threading.Thread(target=service.serve_forever, daemon=True)
    worker.start()

    def request(path, body=None):
        url = f"http://127.0.0.1:{service.server_port}/api/module-records{path}"
        payload = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    try:
        yield request
    finally:
        service.shutdown()
        service.server_close()
        worker.join(timeout=5)


@pytest.mark.parametrize("dataset", list(SCHEMAS))
def test_each_dataset_copies_template_then_saves_and_reloads(tmp_path, dataset, record_service):
    schema = SCHEMAS[dataset]
    path = tmp_path / schema["filename"]
    path.write_text(fixtures.FIXTURES[path.name], encoding="utf-8")
    original = path.read_bytes()
    before = dataset_data(tmp_path, dataset)
    template = before["rows"][0]
    for index, old_id, new_id, digest in [
        (True, template["id"], "copied_record", before["sha256"]),
        (0.5, template["id"], "copied_record", before["sha256"]),
        (0, "wrong", "copied_record", before["sha256"]),
        (0, template["id"], template["id"], before["sha256"]),
        (0, template["id"], "invalid id", before["sha256"]),
        (0, template["id"], "copied_record", "stale"),
    ]:
        status, rejected = record_service("/create", {"dataset": dataset, "sha256": digest,
            "recordIndex": index, "originalId": old_id, "id": new_id})
        assert status == 400 and rejected["error"]
        assert path.read_bytes() == original
        assert not path.with_name(path.name + ".lexeditor.bak").exists()
        assert server.created_ids(dataset) == set()
    status, result = record_service("/create", {"dataset": dataset, "sha256": before["sha256"],
        "recordIndex": 0, "originalId": template["id"], "id": "copied_record"})
    assert status == 200
    status, after = record_service("?dataset=" + dataset)
    assert status == 200
    # A protected field's AST error includes a process-local object address.
    # Its diagnostic keys and every source/value field must stay unchanged.
    for old, current in zip(before["rows"], after["rows"][:-1]):
        assert not current.get("created", False)
        assert {k: v for k, v in current.items() if k not in {"fieldProblems", "created"}} == {
            k: v for k, v in old.items() if k != "fieldProblems"}
        assert set(current.get("fieldProblems", {})) == set(old.get("fieldProblems", {}))
    assert result["recordIndex"] == len(before["rows"])
    assert after["rows"][-1]["fields"] == {**template["fields"], "id": "copied_record"}
    assert after["rows"][-1]["created"]
    assert Path(result["backup"]).read_bytes() == original
    compile(path.read_bytes(), str(path), "exec")
    # This copy remains a normal editable record, including opaque expressions.
    spec = next(spec for spec in schema["fields"] if spec["key"] != "id")
    value = after["rows"][-1]["fields"][spec["key"]]
    if spec["kind"] in {"string", "text"}:
        value = "Edited copy"
    elif spec["kind"] in {"integer", "number"}:
        value = 1
    else:
        value = f"({value})"
    created_source = path.read_bytes()
    status, saved = record_service("/save", {"dataset": dataset, "sha256": after["sha256"],
        "edits": [{"recordIndex": result["recordIndex"], "originalId": "copied_record",
            "fields": {spec["key"]: value}}]})
    assert status == 200, saved
    status, reopened = record_service("?dataset=" + dataset)
    assert status == 200
    assert reopened["rows"][-1]["fields"][spec["key"]] == value
    assert reopened["rows"][-1]["created"]
    assert Path(result["backup"]).read_bytes() == created_source
    saved_source = path.read_bytes()
    status, rejected = record_service("/create", {"dataset": dataset, "sha256": reopened["sha256"],
        "recordIndex": 0, "originalId": template["id"], "id": "copied_record"})
    assert status == 400 and "already exists" in rejected["error"]
    assert path.read_bytes() == saved_source
    assert server.created_ids(dataset) == {"copied_record"}


@pytest.mark.parametrize("dataset", ["skills", "quests"])
def test_dataset_add_reopens_created_record_and_sends_source_to_build(page, tmp_path, monkeypatch, dataset):
    schema = SCHEMAS[dataset]
    source = tmp_path / schema["filename"]
    source.write_text(fixtures.FIXTURES[source.name], encoding="utf-8")
    monkeypatch.setattr(server, "CREATED_LEDGER", tmp_path / ".lexeditor-created.json")

    def api(route):
        if route.request.method == "POST":
            body = route.request.post_data_json
            assert body["dataset"] == dataset
            if route.request.url.endswith("/save"):
                result = save_dataset(tmp_path, dataset, body["sha256"], body["edits"])
            else:
                result = server.note_created(dataset, create_dataset_record(tmp_path, dataset,
                    body["sha256"], body["recordIndex"], body["originalId"], body["id"]))
        else:
            result = server.mark_created(dataset, dataset_data(tmp_path, dataset))
        route.fulfill(json=result)

    framework(page)
    page.route("http://fixture/api/**", api)
    page.add_style_tag(path=str(ROOT / "plugins/warband/editor.css"))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    for script in ("field_controls.js", "editor.js", "module_records.js"):
        page.add_script_tag(path=str(ROOT / "plugins/warband" / script))
    page.evaluate("""dataset=>{
      window.dataset=dataset;window.built=[];
      state.activeSource='mine';
      moduleRecords=WarbandModuleRecords.create({state,api:async(url,options)=>{
        const response=await fetch(url,options);return response.json();},main:()=>document.querySelector('main'),
        toolbar:()=>document.querySelector('#toolbar'),refreshShell(){},renderApp:()=>moduleRecords.render(dataset),
        setStatus(){},hasPendingEdits:()=>false,onCreated:async filename=>built.push(filename),
        dataMapRows:()=>[{dataset,recordLabel:dataset}],sourceDraft:()=>false});
      moduleRecords.render(dataset);
    }""", dataset)
    page.locator(".lex-table-add").wait_for(state="attached")
    page.locator(".warband-record-list").hover()
    page.locator(".lex-table-add").click()
    page.get_by_role("textbox", name="New record ID").fill("copied_record")
    page.get_by_role("button", name="Create and build", exact=True).click()
    page.wait_for_function("built.length===1")
    assert page.evaluate("built") == [source.name]
    assert server.created_ids(dataset) == {"copied_record"}
    assert dataset_data(tmp_path, dataset)["rows"][-1]["id"] == "copied_record"
    assert page.locator(".lex-record-source").count() == 1
    if dataset == "skills":
        before = source.read_bytes()
        level = page.locator(".lex-detail-field").filter(has_text="Maximum level").locator("input")
        for invalid in ("1.5", "-1", ""):
            level.fill(invalid)
            level.evaluate("n=>{n.dispatchEvent(new Event('change',{bubbles:true}));n.blur();}")
            page.wait_for_timeout(50)
            assert level.input_value() == invalid
            assert not level.evaluate("n=>n.checkValidity()")
            assert page.evaluate("moduleRecords.dirtyCount()") == 1
            assert source.read_bytes() == before
        level.fill("12")
        assert level.evaluate("n=>n.checkValidity()")
        assert page.evaluate("moduleRecords.dirtyCount()") == 1
        page.evaluate("moduleRecords.saveAll()")
        assert dataset_data(tmp_path, dataset)["rows"][-1]["fields"]["maxLevel"] == 12
        assert dataset_data(tmp_path, dataset)["rows"][0]["fields"]["maxLevel"] == 10
    destination = os.environ.get("LEXEDITOR_UI_SCREENSHOT_DIR")
    if destination:
        Path(destination).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(destination) / f"warband-created-{dataset}.png"))

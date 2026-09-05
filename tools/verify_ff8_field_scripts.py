"""Verify FF8 field JSM structure, source compilation, API, and rendered save."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import field_data, field_scripts  # noqa: E402
from games.ff8.fs_archive import FsArchive  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def require_error(action, phrase: str) -> None:
    try:
        action()
    except ValueError as error:
        assert phrase.casefold() in str(error).casefold(), error
    else:
        raise AssertionError(f"Expected error containing {phrase!r}")


def corpus_identity() -> dict:
    archive = FsArchive(field_data._prefix())
    groups = field_data._outer_groups(archive)
    map_count = method_count = instruction_count = editable_count = 0
    for key, group in groups.items():
        nested_fs = archive.extract(group["entries"][".fs"])
        entries = field_data._memory_entries(
            archive.extract(group["entries"][".fi"]),
            archive.extract(group["entries"][".fl"]))
        jsm = next((entry for entry in entries if entry["basename"].endswith(".jsm")), None)
        sym = next((entry for entry in entries if entry["basename"].endswith(".sym")), None)
        if jsm is None:
            continue
        raw = field_data._memory_extract(nested_fs, entries, jsm["basename"])
        sym_raw = field_data._memory_extract(
            nested_fs, entries, sym["basename"]) if sym else b""
        document = field_scripts.read(raw, sym_raw)
        rebuilt, changed = field_scripts.rebuild(raw, sym_raw, [])
        assert rebuilt == raw and changed == 0, key
        map_count += 1
        method_count += len(document["methods"])
        instruction_count += sum(method["instructionCount"]
                                 for method in document["methods"])
        editable_count += sum(method["editable"] for method in document["methods"])
    assert (map_count, method_count, instruction_count, editable_count) == (
        882, 87218, 1439792, 87197)
    assert len(field_scripts.OPCODE_NAMES) == 376
    return {"maps": map_count, "methods": method_count,
            "instructions": instruction_count, "editableMethods": editable_count,
            "opcodeNames": len(field_scripts.OPCODE_NAMES)}


def mutation_and_validation() -> dict:
    jsm_path, sym_path = field_data._source_paths("bg/bghall_1", "vanilla")
    raw, sym = jsm_path.read_bytes(), sym_path.read_bytes()
    before = field_scripts.read(raw, sym)
    method = next(value for value in before["methods"]
                  if value["editable"] and "TARGET_0:\nRET" in value["source"])
    replacement = method["source"].replace(
        "TARGET_0:\nRET", "NOP\nTARGET_0:\nRET", 1)
    rebuilt, changed = field_scripts.rebuild(
        raw, sym, [{"id": method["id"], "source": replacement}])
    after = field_scripts.read(rebuilt, sym)
    changed_method = after["methods"][method["id"]]
    assert changed == 1 and changed_method["source"] == replacement
    assert changed_method["instructionCount"] == method["instructionCount"] + 1
    for current, original in zip(after["methods"], before["methods"]):
        if current["id"] != method["id"]:
            assert current["raw"] == original["raw"]
    # The JPF still resolves to the named target after insertion.
    words = field_scripts.compile_source(replacement, method["id"], method["labelId"])
    branch_index = next(index for index, word in enumerate(words)
                        if field_scripts._decode_word(word)[0] ==
                        field_scripts.OPCODE_IDS["JPF"])
    _, relative = field_scripts._decode_word(words[branch_index])
    assert field_scripts._decode_word(words[branch_index + relative])[0] == \
        field_scripts.OPCODE_IDS["RET"]

    require_error(lambda: field_scripts.compile_source(
        replacement.replace("TARGET_0", "MISSING", 1), method["id"], method["labelId"]),
        "undefined")
    first_line, remainder = replacement.split("\n", 1)
    require_error(lambda: field_scripts.compile_source(
        f"LBL {method['labelId'] + 1}\n{remainder}",
        method["id"], method["labelId"]),
        "retain")
    require_error(lambda: field_scripts.compile_source(
        replacement + "\nNOT_AN_OPCODE", method["id"], method["labelId"]), "invalid")
    require_error(lambda: field_scripts.compile_source(
        replacement + "\nMES 1", method["id"], method["labelId"]), "cannot have")
    require_error(lambda: field_scripts.rebuild(raw, sym, [
        {"id": method["id"], "source": replacement},
        {"id": method["id"], "source": replacement}]), "duplicate")
    return {"map": "bg/bghall_1", "method": method["id"],
            "beforeWords": method["instructionCount"],
            "afterWords": changed_method["instructionCount"]}


def api_and_render() -> dict:
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-field-jsm-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            detail = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            method = next(value for value in detail["scripts"]["methods"]
                          if value["editable"] and "TARGET_0:\nRET" in value["source"])
            replacement = method["source"].replace(
                "TARGET_0:\nRET", "NOP\nTARGET_0:\nRET", 1)
            saved = api(session.url, "/api/field/save", {"edits": [{
                "type": "script", "map": "bg/bghall_1",
                "method": method["id"], "source": replacement,
            }]})
            assert saved == {"saved": 1, "maps": 1}
            current = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert current["scripts"]["methods"][method["id"]]["source"] == replacement

            profile, browser, cdp = browser_session()
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            target = next(row for row in api(session.url, "/api/fields")["rows"]
                          if row["key"] == "bg/bghall_1")
            cdp.eval(f"state.selected.fields={target['id']};navigate('fields')")
            wait_eval(cdp, "document.querySelector('.field-script-editor')!==null", 45)
            rendered = cdp.eval("""(()=>{const area=document.querySelector('.field-script-editor'),panel=document.querySelector('.field-map-detail'),source=area.closest('.lex-source-control'),style=getComputedStyle(area),picker=getComputedStyle(document.querySelector('.field-script-picker select'));return{method:Number(document.querySelector('.field-script-picker select').value),value:area.value,vanilla:source?.lexVanillaValue?.(),refs:source?.querySelectorAll('.lex-reference-value').length||0,readOnly:area.readOnly,color:style.color,background:style.backgroundColor,pickerBackground:picker.backgroundColor,pickerColor:picker.color,overflow:panel.scrollWidth>panel.clientWidth+1}})()""")
            assert rendered["method"] == method["id"] and rendered["value"] == replacement, rendered
            assert rendered["vanilla"] == method["source"] and rendered["refs"] >= 1, rendered
            assert not rendered["readOnly"] and not rendered["overflow"], rendered
            assert rendered["color"] == "rgb(255, 255, 255)" and rendered["background"] != "rgb(255, 255, 255)", rendered
            assert rendered["pickerColor"] == "rgb(255, 255, 255)" and rendered["pickerBackground"] != "rgb(255, 255, 255)", rendered
            cdp.eval("""(()=>{const area=document.querySelector('.field-script-editor');area.scrollIntoView({block:'center'});area.value=area.value.replace('TARGET_0:\\nRET','NOP\\nTARGET_0:\\nRET');area.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            card = cdp.eval("""(()=>{const input=document.querySelector('.field-card-table input[inputmode="decimal"]'),before=Number(input.value.replaceAll(',','')),after=before+1;input.value=String(after);input.dispatchEvent(new Event('input',{bubbles:true}));return{before,after}})()""")
            assert cdp.eval("dirtyCount()") >= 1
            cdp.eval("saveAll()", True)
            persisted = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert persisted["scripts"]["methods"][method["id"]]["instructionCount"] == \
                method["instructionCount"] + 2
            assert persisted["players"][0]["params"][0]["value"] == card["after"]
            rendered["uiSavePersisted"] = True
            rendered["combinedCardSave"] = card
            wait_eval(cdp, "document.querySelector('.field-script-editor')!==null", 30)
            cdp.eval("""(()=>{const area=document.querySelector('.field-script-editor'),panel=document.querySelector('.field-map-detail'),owner=area.closest('.lex-detail-section');for(const section of panel.querySelectorAll('.lex-detail-section'))if(section!==owner)section.hidden=true;const boundary=panel.querySelector('.field-boundary');if(boundary)boundary.hidden=true;for(let node=area.parentElement;node;node=node.parentElement)node.scrollTop=0})()""")
            cdp.eval("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))", True)
            rendered["screenshot"] = str(screenshot(cdp, "goal-ff8-field-scripts.png"))
            return rendered
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "fieldScriptsSection" in source and 'type:"script"' in source
    print({"corpus": corpus_identity(), "mutation": mutation_and_validation(),
           "rendered": api_and_render()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

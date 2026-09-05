"""Verify FF8 field MSD corpus, mutation, API, provenance, and unified save."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import field_data, field_dialogue, paths  # noqa: E402
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


def corpus_and_binary() -> dict:
    archive = FsArchive(field_data._prefix())
    groups = field_data._outer_groups(archive)
    maps_with_dialogue = lines = 0
    example = None
    for key, group in groups.items():
        nested_fs = archive.extract(group["entries"][".fs"])
        nested_fi = archive.extract(group["entries"][".fi"])
        nested_fl = archive.extract(group["entries"][".fl"])
        entries = field_data._memory_entries(nested_fi, nested_fl)
        msds = [entry for entry in entries if entry["basename"].endswith(".msd")]
        assert len(msds) <= 1, (key, msds)
        for entry in msds:
            raw = field_data._memory_extract(nested_fs, entries, entry["basename"])
            document = field_dialogue.read(raw)
            identity, changed = field_dialogue.apply_edits(raw, [
                {"id": line["id"], "text": line["text"]}
                for line in document["lines"]
            ])
            assert identity == raw and changed == 0
            maps_with_dialogue += 1
            lines += len(document["lines"])
            if example is None and document["lines"]:
                example = (key, raw, document)
    assert len(groups) == 896 and maps_with_dialogue == 883
    assert lines == 22392 and example is not None

    key, raw, before = example
    line = before["lines"][0]
    replacement = line["text"] + "!"
    rebuilt, changed = field_dialogue.apply_edits(
        raw, [{"id": line["id"], "text": replacement}])
    after = field_dialogue.read(rebuilt)
    assert changed == 1 and after["lines"][0]["text"] == replacement
    assert [value["rawText"] for value in after["lines"][1:]] == [
        value["rawText"] for value in before["lines"][1:]
    ]
    assert len(after["lines"]) == len(before["lines"])

    require_error(lambda: field_dialogue.read(b"\x03\0\0\0"), "first offset")
    malformed = bytearray(raw)
    struct.pack_into("<I", malformed, 4, len(raw) + 1)
    require_error(lambda: field_dialogue.read(bytes(malformed)), "monotonic")
    require_error(lambda: field_dialogue.apply_edits(raw, [
        {"id": 0, "text": "one"}, {"id": 0, "text": "two"}]), "duplicate")
    require_error(lambda: field_dialogue.apply_edits(
        raw, [{"id": 0, "text": "cannot encode ☃"}]), "not available")
    require_error(lambda: field_dialogue.apply_edits(
        raw, [{"id": 999999, "text": "bad"}]), "invalid")
    return {"maps": len(groups), "withDialogue": maps_with_dialogue,
            "lines": lines, "mutatedMap": key}


def api_and_render() -> dict:
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-field-dialogue-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            detail = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert detail["dialogue"] and detail["dialogueSource"].endswith("bghall_1.msd")
            original = detail["dialogue"][0]["text"]
            saved = api(session.url, "/api/field/save", {"edits": [{
                "type": "dialogue", "map": "bg/bghall_1", "line": 0,
                "text": original + "!",
            }]})
            assert saved == {"saved": 1, "maps": 1}
            current = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert current["dialogue"][0]["text"] == original + "!"
            destination = (Path(project.name) /
                           "direct/field/mapdata/bg/bghall_1/bghall_1.msd")
            assert destination.is_file()

            profile, browser, cdp = browser_session()
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            target = next(row for row in api(session.url, "/api/fields")["rows"]
                          if row["key"] == "bg/bghall_1")
            cdp.eval(f"state.selected.fields={target['id']};navigate('fields')")
            wait_eval(cdp, "document.querySelector('.field-dialogue-line textarea')!==null", 45)
            rendered = cdp.eval("""(()=>{const panel=document.querySelector('.field-map-detail'),area=document.querySelector('.field-dialogue-line textarea'),source=area.closest('.lex-source-control'),row=state.data.fields.rows.find(value=>value.key==='bg/bghall_1');return{activeSource:state.activeSource,stateValue:row?.dialogue?.[0]?.text,lines:document.querySelectorAll('.field-dialogue-line').length,value:area.value,vanilla:source?.lexVanillaValue?.(),refs:source?.querySelectorAll('.lex-reference-value').length||0,overflow:panel.scrollWidth>panel.clientWidth+1}})()""")
            assert rendered["lines"] == len(current["dialogue"]), rendered
            assert rendered["value"] == original + "!" and rendered["vanilla"] == original, rendered
            assert rendered["refs"] >= 1 and not rendered["overflow"], rendered
            cdp.eval("""(()=>{const area=document.querySelector('.field-dialogue-line textarea');area.value+='?';area.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            assert cdp.eval("dirtyCount()") >= 1
            cdp.eval("saveAll()", True)
            persisted = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert persisted["dialogue"][0]["text"] == original + "!?"
            rendered["uiSavePersisted"] = True
            rendered["screenshot"] = str(screenshot(cdp, "goal-ff8-field-dialogue.png"))
            return rendered
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "fieldDialogueSection" in source and 'type:"dialogue"' in source
    print({"binary": corpus_and_binary(), "rendered": api_and_render()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

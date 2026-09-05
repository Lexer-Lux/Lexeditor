"""Exact-byte, API, and rendered checks for the FF8 enemy AI operand editor."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import enemy_ai, paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def api(url: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = Request(url + path, data=data,
                      headers={"Content-Type": "application/json"} if data else {})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def editable_operand(parsed: dict) -> tuple[dict, dict, dict]:
    for script in parsed["scripts"]:
        for instruction in script["instructions"]:
            for operand in instruction["operands"]:
                if operand["control"] == "number" and operand["type"] != "jump16":
                    return script, instruction, operand
    raise AssertionError("No editable numeric enemy AI operand was found")


def main() -> int:
    corpus = []
    for path in sorted((paths.BASELINE_ROOT / "battle").glob("c0m*.dat")):
        decoded = enemy_ai.read(path.read_bytes())
        if decoded["available"]:
            corpus.append(decoded)
    instructions = [instruction for decoded in corpus for script in decoded["scripts"]
                    for instruction in script["instructions"]]
    assert len(instructions) == 11763
    assert not [instruction for instruction in instructions if not instruction["editable"]]
    branches = [instruction for instruction in instructions if "targetValid" in instruction]
    assert len(branches) == 3879 and all(instruction["targetValid"] for instruction in branches)

    # A full no-op rebuild must preserve every one of the 144 decoded DATs.
    for path in sorted((paths.BASELINE_ROOT / "battle").glob("c0m*.dat")):
        raw = path.read_bytes()
        document = enemy_ai.read(raw)
        if not document["available"]:
            continue
        identity, _ = enemy_ai.rebuild_scripts(raw, document["scripts"])
        assert identity == raw, path

    baseline_path = paths.BASELINE_ROOT / "battle" / "c0m000.dat"
    baseline = baseline_path.read_bytes()
    parsed = enemy_ai.read(baseline)
    assert parsed["available"] and [row["name"] for row in parsed["scripts"]] == [
        "Init", "Turn", "Counter", "Death", "Pre-hit"]
    assert all(row.get("targetValid", True) for script in parsed["scripts"]
               for row in script["instructions"])
    script, instruction, operand = editable_operand(parsed)
    replacement = operand["value"] + 1 if operand["value"] < operand["maximum"] else operand["value"] - 1
    edit = {"script": script["id"], "offset": instruction["offset"],
            "operand": operand["index"], "value": replacement}
    rebuilt, changed = enemy_ai.apply_edits(baseline, [edit])
    differences = [index for index, pair in enumerate(zip(baseline, rebuilt)) if pair[0] != pair[1]]
    encoded = replacement.to_bytes(operand["size"], "little")
    expected = [operand["offset"] + index for index, pair in enumerate(
        zip(baseline[operand["offset"]:operand["offset"] + operand["size"]], encoded))
        if pair[0] != pair[1]]
    assert changed == 1 and len(rebuilt) == len(baseline) and differences == expected
    reread = enemy_ai.read(rebuilt)
    value = reread["scripts"][script["id"]]["instructions"][
        next(index for index, row in enumerate(script["instructions"])
             if row["offset"] == instruction["offset"])]
    assert value["operands"][operand["index"]]["value"] == replacement

    # Structural compilation can insert and remove instructions while keeping
    # the battle-text payload and every later section byte-identical.
    structural = enemy_ai.read(baseline)
    old_section_start, old_section_end = enemy_ai._section(baseline)
    old_section = baseline[old_section_start:old_section_end]
    old_text = int.from_bytes(old_section[8:12], "little")
    structural["scripts"][0]["instructions"].insert(0, {
        "key": "test-insert", "opcode": 13, "operands": [{"value": 7}],
        "editable": True,
    })
    inserted, _ = enemy_ai.rebuild_scripts(baseline, structural["scripts"])
    inserted_parsed = enemy_ai.read(inserted)
    assert inserted_parsed["scripts"][0]["instructions"][0]["opcode"] == 13
    assert inserted_parsed["scripts"][0]["instructions"][0]["operands"][0]["value"] == 7
    new_section_start, new_section_end = enemy_ai._section(inserted)
    new_section = inserted[new_section_start:new_section_end]
    new_text = int.from_bytes(new_section[8:12], "little")
    assert old_section[old_text:] == new_section[new_text:]
    assert baseline[old_section_end:] == inserted[new_section_end:]

    section_start = parsed["sectionOffset"]
    unknown = bytearray(baseline)
    unknown[script["offset"] + instruction["offset"]] = 0xFE
    unknown_parsed = enemy_ai.read(bytes(unknown))
    tail = next(row for row in unknown_parsed["scripts"][script["id"]]["instructions"]
                if not row["editable"])
    assert tail["name"] == "Unsupported raw tail" and tail["raw"].startswith("FE")
    try:
        enemy_ai.apply_edits(bytes(unknown), [edit])
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("An edit inside an unsupported raw tail was accepted")

    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "goal-ff8-enemy-ai.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-ai-project-", ignore_cleanup_errors=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-ai-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/enemy-ai?id=0&dataset=current")
            assert len(payload["rows"]) == 1 and payload["rows"][0]["available"]
            saved = api(session.url, "/api/enemy-ai/save", {"edits": [{"id": 0, **edit}]})
            assert saved["saved"] == 1
            current = api(session.url, "/api/enemy-ai?id=0&dataset=current")["rows"][0]
            current_instruction = next(row for row in current["scripts"][script["id"]]["instructions"]
                                       if row["offset"] == instruction["offset"])
            assert current_instruction["operands"][operand["index"]]["value"] == replacement
            output_file = Path(project.name) / "direct" / "battle" / "c0m000.dat"
            written = output_file.read_bytes()
            assert len(written) == len(baseline)
            assert [index for index, pair in enumerate(zip(baseline, written)) if pair[0] != pair[1]] == expected

            document = current
            document["scripts"][0]["instructions"].insert(0, {
                "key": "api-insert", "opcode": 13, "operands": [{"value": 9}],
                "editable": True,
            })
            structural_saved = api(session.url, "/api/enemy-ai/save", {
                "documents": [{"id": 0, "scripts": document["scripts"]}],
            })
            assert structural_saved["saved"] > 0
            structurally_current = api(
                session.url, "/api/enemy-ai?id=0&dataset=current")["rows"][0]
            assert structurally_current["scripts"][0]["instructions"][0]["opcode"] == 13
            assert structurally_current["scripts"][0]["instructions"][0]["operands"][0]["value"] == 9

            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(!String(event.message).includes('ResizeObserver loop'))window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("state.selected.enemies=0;state.enemyPanelTab='ai';navigate('enemies');renderEnemies()")
            wait_eval(cdp, "document.querySelectorAll('.enemy-ai-script').length===5", 45)
            rendered = cdp.eval("({sections:[...document.querySelectorAll('.enemy-ai-script>.lex-detail-section-title')].map(node=>node.textContent.trim()),inputs:document.querySelectorAll('.enemy-ai-operands input,.enemy-ai-operands select').length,opcodes:document.querySelectorAll('.enemy-ai-opcode').length,actions:document.querySelectorAll('.enemy-ai-action').length,branches:document.querySelectorAll('.enemy-ai-branch').length,actionHelp:document.querySelector('.enemy-action-definitions>.lex-detail-section-title .lex-info-help')?.getAttribute('aria-label')||'',boundary:document.querySelector('.enemy-ai-boundary')?.textContent||'',errors:window.__testErrors})")
            assert rendered["sections"] == ["INIT", "TURN", "COUNTER", "DEATH", "PRE-HIT"]
            assert rendered["inputs"] > 0 and rendered["branches"] > 0
            assert rendered["opcodes"] > 0 and rendered["actions"] == rendered["opcodes"] * 4
            assert "not the conditional AI program" in rendered["actionHelp"]
            assert "replace, insert, delete, and reorder" in rendered["boundary"]
            assert not rendered["errors"], rendered
            before_insert = rendered["opcodes"]
            cdp.eval("document.querySelector('.enemy-ai-action[title=\"Insert instruction after\"]').click()")
            wait_eval(cdp, f"document.querySelectorAll('.enemy-ai-opcode').length==={before_insert + 1}", 5)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 15)
            after_ui_save = api(
                session.url, "/api/enemy-ai?id=0&dataset=current")["rows"][0]
            # The compiler also adds the required Stop padding to the next
            # four-byte boundary, so the decoded row count can grow by more
            # than the one semantic instruction inserted in the UI.
            assert sum(len(script["instructions"]) for script in after_ui_save["scripts"]) >= before_insert + 1
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True})
            output.write_bytes(base64.b64decode(shot["data"]))
            print(json.dumps({"scripts": rendered["sections"], "inputs": rendered["inputs"],
                              "branches": rendered["branches"], "saved": saved["saved"],
                              "structuralSaved": structural_saved["saved"],
                              "changedBytes": differences, "screenshot": str(output)}))
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        project.cleanup()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

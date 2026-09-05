"""Verify strict FF8 enemy-AI source parsing, saving, and rendered editing."""

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


def expect_error(call, text: str) -> None:
    try:
        call()
    except ValueError as error:
        assert text.lower() in str(error).lower(), error
    else:
        raise AssertionError(f"Expected a source error containing {text!r}")


def main() -> int:
    count = 0
    line_count = 0
    for path in sorted((paths.BASELINE_ROOT / "battle").glob("c0m*.dat")):
        raw = path.read_bytes()
        document = enemy_ai.read(raw)
        if not document["available"]:
            continue
        sources = [{"id": script["id"], "source": script["source"]}
                   for script in document["scripts"]]
        parsed = enemy_ai.compile_sources(sources)
        rebuilt, _ = enemy_ai.rebuild_scripts(raw, parsed)
        assert rebuilt == raw, path
        assert all(line and ": " in line and "[" in line
                   for script in sources for line in script["source"].splitlines())
        count += 1
        line_count += sum(len(script["instructions"]) for script in document["scripts"])
    assert count == 144 and line_count == 11763

    baseline = (paths.BASELINE_ROOT / "battle" / "c0m000.dat").read_bytes()
    document = enemy_ai.read(baseline)
    sources = [{"id": script["id"], "source": script["source"]}
               for script in document["scripts"]]
    sample = sources[0]["source"].splitlines()[0]
    expect_error(lambda: enemy_ai.parse_script("BAD SOURCE"), "syntax")
    expect_error(lambda: enemy_ai.parse_script(sample.replace("[", "_WRONG[", 1)), "mnemonic")
    expect_error(lambda: enemy_ai.parse_script("A: UNUSED[254]"), "unsupported opcode")
    expect_error(lambda: enemy_ai.parse_script("A: STOP[0]\nA: STOP[0]"), "duplicate")
    expect_error(lambda: enemy_ai.parse_script("A: JUMP[35] jump16=@MISSING"), "does not exist")
    expect_error(lambda: enemy_ai.parse_script("A: PREVENT_ESCAPE[23] bool=1"), "true or false")
    expect_error(lambda: enemy_ai.parse_script("A: NO_OP[13] u8=256"), "must be")
    expect_error(lambda: enemy_ai.parse_script("A: NO_OP[13] value16=1"), "expected u8")

    # A typed source edit compiles through the structural compiler and changes
    # only the operand bytes when instruction sizes are unchanged.
    target_script = target_instruction = target_operand = None
    for script in document["scripts"]:
        for instruction in script["instructions"]:
            for operand in instruction["operands"]:
                if operand["type"] not in {"jump16", "skip16", "bool"} \
                        and operand["value"] < operand["maximum"]:
                    target_script, target_instruction, target_operand = script, instruction, operand
                    break
            if target_operand:
                break
        if target_operand:
            break
    assert target_script and target_instruction and target_operand
    replacement = target_operand["value"] + 1
    old_token = f"{target_operand['type']}={target_operand['value']}"
    new_token = f"{target_operand['type']}={replacement}"
    source_entry = sources[target_script["id"]]
    source_entry["source"] = source_entry["source"].replace(old_token, new_token, 1)
    compiled = enemy_ai.compile_sources(sources)
    rebuilt, _ = enemy_ai.rebuild_scripts(baseline, compiled)
    expected = bytearray(baseline)
    start = int(target_operand["offset"])
    size = int(target_operand["size"])
    expected[start:start + size] = replacement.to_bytes(size, "little")
    assert rebuilt == bytes(expected)

    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "goal-ff8-enemy-ai-source.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-ai-source-project-",
                                          ignore_cleanup_errors=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-ai-source-edge-",
                                          ignore_cleanup_errors=True)
    browser = None
    cdp = None
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    port = free_port()
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            checked = api(session.url, "/api/enemy-ai/source/compile", {"sources": sources})
            assert len(checked["scripts"]) == 5
            saved = api(session.url, "/api/enemy-ai/save", {
                "documents": [{"id": 0, "sources": sources}],
            })
            assert saved["saved"] == 1
            assert (Path(project.name) / "direct" / "battle" / "c0m000.dat").read_bytes() == bytes(expected)

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
            cdp.eval("state.selected.enemies=0;state.enemyPanelTab='ai';state.enemyAiView='source';navigate('enemies');renderEnemies()")
            wait_eval(cdp, "document.querySelectorAll('.enemy-ai-source-editor').length===5", 45)
            rendered = cdp.eval("({tabs:[...document.querySelectorAll('.enemy-ai-view-tabs button')].map(node=>node.textContent.trim()),editors:document.querySelectorAll('.enemy-ai-source-editor').length,apply:document.querySelector('.enemy-ai-source-apply')?.textContent.trim(),dark:getComputedStyle(document.querySelector('.enemy-ai-source-editor')).backgroundColor,boundary:document.querySelector('.enemy-ai-boundary')?.textContent||'',errors:window.__testErrors})")
            assert [value.rstrip("12") for value in rendered["tabs"]] == ["Structure", "Source"]
            assert rendered["editors"] == 5 and rendered["apply"] == "Apply Source"
            assert rendered["dark"] in {"rgb(41, 41, 41)", "rgb(59, 59, 59)"}
            assert "typed operands" in rendered["boundary"] and not rendered["errors"]
            cdp.eval("(()=>{const input=document.querySelector('.enemy-ai-source-editor');input.value+='\\nCUSTOM: NO_OP[13] u8=7';input.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('.enemy-ai-source-apply').click()})()")
            wait_eval(cdp, "state.status.startsWith('Compiled')", 15)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 30)
            current = api(session.url, "/api/enemy-ai?id=0&dataset=current")["rows"][0]
            assert any(row["opcode"] == 13 and row["operands"][0]["value"] == 7
                       for row in current["scripts"][0]["instructions"])
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True})
            output.write_bytes(base64.b64decode(shot["data"]))
            print(json.dumps({"files": count, "lines": line_count, "saved": saved["saved"],
                              "tabs": rendered["tabs"], "screenshot": str(output)}))
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

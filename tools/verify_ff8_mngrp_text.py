"""Round-trip, API, and headless rendered checks for FF8 mngrp.bin text."""

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

from games.ff8 import mngrp_text, paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def api(url: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = Request(url + path, data=data,
                      headers={"Content-Type": "application/json"} if data else {})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    baseline_path = paths.BASELINE_ROOT / "menu" / "mngrp.bin"
    baseline = baseline_path.read_bytes()
    parsed = mngrp_text.rows(baseline)
    assert len(parsed["sections"]) == 45 and len(parsed["rows"]) == 755
    target = next(row for row in parsed["rows"] if row["sectionId"] == 39)
    replacement = target["value"] + "A"
    rebuilt, changed = mngrp_text.apply_edits(baseline, [{
        "source": "mngrp", "sectionId": target["sectionId"],
        "recordId": target["recordId"], "value": replacement,
    }])
    section = mngrp_text.BY_ID[39]
    assert changed == 1 and len(rebuilt) == len(baseline)
    assert rebuilt[:section.offset] == baseline[:section.offset]
    assert rebuilt[section.offset + section.size:] == baseline[section.offset + section.size:]
    changed_row = next(row for row in mngrp_text.rows(rebuilt)["rows"]
                       if row["sectionId"] == 39 and row["recordId"] == target["recordId"])
    assert changed_row["value"] == replacement
    seed = next(row for row in parsed["rows"] if row["sectionId"] == 42)
    seed_section = mngrp_text.BY_ID[42]
    old_seed = baseline[seed_section.offset:seed_section.offset + seed_section.size]
    old_seed_offset = int.from_bytes(old_seed[2:4], "little")
    seeded, seed_changed = mngrp_text.apply_edits(baseline, [{
        "source": "mngrp", "sectionId": 42, "recordId": seed["recordId"],
        "value": seed["value"] + "A",
    }])
    new_seed = seeded[seed_section.offset:seed_section.offset + seed_section.size]
    new_seed_offset = int.from_bytes(new_seed[2:4], "little")
    assert seed_changed == 1 and new_seed[new_seed_offset] == old_seed[old_seed_offset]
    try:
        mngrp_text.apply_edits(baseline, [{
            "source": "mngrp", "sectionId": 39, "recordId": 0,
            "value": "A" * section.size,
        }])
    except ValueError as error:
        assert "fixed" in str(error)
    else:
        raise AssertionError("mngrp.bin section overflow was accepted")
    try:
        mngrp_text.apply_edits(baseline, [{
            "source": "mngrp", "sectionId": 75, "recordId": 0, "value": "A",
        }])
    except ValueError as error:
        assert "Invalid" in str(error)
    else:
        raise AssertionError("unsupported mngrp.bin text-box section was accepted")

    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "goal-ff8-mngrp-text.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mngrp-project-", ignore_cleanup_errors=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mngrp-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/text?dataset=current")
            assert {row["source"] for row in payload["rows"]} == {
                "kernel", "mngrp", "exe_card_names", "exe_draw_point", "exe_card_texts",
            }
            assert len({row["id"] for row in payload["rows"]}) == len(payload["rows"])
            menu = next(row for row in payload["rows"] if row["source"] == "mngrp" and row["sectionId"] == 39)
            value = menu["value"] + "A"
            saved = api(session.url, "/api/text/save", {"edits": [{
                "source": "mngrp", "sectionId": menu["sectionId"],
                "recordId": menu["recordId"], "slot": menu["slot"], "value": value,
            }]})
            assert saved["saved"] == 1 and saved["files"][0].endswith("menu\\mngrp.bin")
            current = api(session.url, "/api/text?dataset=current")
            reread = next(row for row in current["rows"] if row["id"] == menu["id"])
            assert reread["value"] == value
            output_file = Path(project.name) / "direct" / "menu" / "mngrp.bin"
            assert output_file.stat().st_size == baseline_path.stat().st_size

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
                "width": 1500, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(!String(event.message).includes('ResizeObserver loop'))window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('text');state.filters.text='Menu text';state.selected.text=null;renderText()")
            wait_eval(cdp, "document.querySelector('.lex-column-list-row')?.textContent.includes('Menu text')", 30)
            rendered = cdp.eval("({sources:[...document.querySelectorAll('.lex-column-list-row')].map(row=>row.textContent),headers:[...document.querySelectorAll('.lex-column-list-head-cell')].map(node=>({key:node.dataset.columnKey,text:node.textContent.trim(),left:node.getBoundingClientRect().left,width:node.getBoundingClientRect().width})),detail:document.querySelector('.lex-detail')?.textContent||'',help:document.querySelector('.kernel-text-editor .lex-info-help')?.getAttribute('aria-label')||'',errors:window.__testErrors,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth})")
            assert rendered["sources"] and all("Menu text" in row for row in rendered["sources"])
            assert "fixed-size mngrp.bin section" in rendered["help"]
            assert not rendered["errors"] and not rendered["overflow"], rendered
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            print(json.dumps({
                "menuRows": sum(row["source"] == "mngrp" for row in payload["rows"]),
                "sections": len(parsed["sections"]), "saved": saved["saved"],
                "headers": rendered["headers"],
                "screenshot": str(output),
            }))
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

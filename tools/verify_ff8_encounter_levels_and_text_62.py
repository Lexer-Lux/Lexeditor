"""Focused binary and hidden-render checks for GOAL item 62."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import encounters  # noqa: E402
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
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def verify_level_binary() -> dict:
    assert encounters.decode_level(1)["mode"] == "fixed"
    assert encounters.decode_level(100)["value"] == 100
    assert encounters.decode_level(101) == {"mode": "maximum", "value": 1, "raw": 101}
    assert encounters.decode_level(200)["value"] == 100
    assert encounters.decode_level(252) == {"mode": "ultimecia", "value": None, "raw": 252}
    assert encounters.decode_level(215)["mode"] == "special"
    assert encounters.encode_level("fixed", 37) == 37
    assert encounters.encode_level("maximum", 37) == 137
    assert encounters.encode_level("ultimecia") == 252
    for mode, value in (("fixed", 0), ("maximum", 101), ("special", 1)):
        try:
            encounters.encode_level(mode, value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe encounter level accepted: {mode} {value}")

    before = bytearray(encounters.RECORD_SIZE)
    before[0x38] = encounters.ENEMY_ID_BASE
    before[0x78] = 20
    row = encounters.read_rows(bytes(before), {0: "Test Enemy"})["rows"][0]
    slot = dict(row["slots"][0])
    slot.update({"id": 0, "level": encounters.encode_level("maximum", 37)})
    after, changed = encounters.apply_edits(bytes(before), [slot], {0})
    offsets = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
    assert changed == 1 and offsets == [0x78], offsets
    assert encounters.read_rows(after, {0: "Test Enemy"})["rows"][0]["slots"][0]["levelRule"] == {
        "mode": "maximum", "value": 37, "raw": 137,
    }
    return {"changedOffset": offsets[0], "storedMaximum": after[0x78]}


def verify_rendered() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-goal62-render-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            rows = api(session.url, "/api/encounters?dataset=current")["rows"]
            target = next(row for row in rows if any(
                slot["enabled"] and slot["levelRule"]["mode"] in {"fixed", "maximum"}
                for slot in row["slots"]))
            target_slot = next(slot for slot in target["slots"] if
                               slot["enabled"] and slot["levelRule"]["mode"] in {"fixed", "maximum"})
            stored_level = encounters.encode_level("maximum", 37)
            edit = {key: target_slot[key] for key in (
                "slot", "enemyId", "enabled", "visible", "loaded", "targetable", "x", "y", "z")}
            edit.update({"id": target["id"], "level": stored_level})
            assert api(session.url, "/api/encounters/save", {"edits": [edit]})["saved"] == 1
            current_target = api(session.url, "/api/encounters?dataset=current")["rows"][target["id"]]
            assert current_target["slots"][target_slot["slot"]]["levelRule"] == {
                "mode": "maximum", "value": 37, "raw": stored_level,
            }

            text_rows = api(session.url, "/api/text?dataset=current")["rows"]
            text_target = text_rows[0]
            replacement = text_target["value"] + "!"
            assert api(session.url, "/api/text/save", {"edits": [{
                "sectionId": text_target["sectionId"], "recordId": text_target["recordId"],
                "slot": text_target["slot"], "value": replacement,
            }]})["saved"] == 1
            assert api(session.url, "/api/text?dataset=current")["rows"][0]["value"] == replacement
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval(f"state.selected.encounters={target['id']};navigate('encounters')")
            wait_eval(cdp, "document.querySelector('.encounter-level-control')!==null", 30)
            encounter_result = cdp.eval("""(()=>{const control=[...document.querySelectorAll('.encounter-level-control')].find(node=>!node.closest('.encounter-slot-disabled'));const input=control?.querySelector('input[inputmode=decimal]'),select=control?.querySelector('select'),uc=control?.querySelector('input[type=checkbox]'),table=document.querySelector('.encounter-slot-table');if(!control||!input)return null;const before=Number(input.value);input.focus();input.value=String(Math.min(100,before+1));input.dispatchEvent(new Event('input',{bubbles:true}));return{header:table.querySelector('[data-column-key=level]')?.textContent.trim(),hasUc:!!uc,modes:[...select.options].map(option=>option.textContent),min:input.dataset.min,max:input.dataset.max,focusStayed:document.activeElement===input,overflow:table.scrollWidth>table.clientWidth+1}})()""")
            assert encounter_result and encounter_result["hasUc"], encounter_result
            assert encounter_result["modes"][:2] == ["Fixed", "Maximum"], encounter_result
            assert encounter_result["min"] == "1" and encounter_result["max"] == "100", encounter_result
            assert encounter_result["focusStayed"] and not encounter_result["overflow"], encounter_result
            encounter_result["screenshot"] = str(screenshot(cdp, "goal-62-ff8-encounter-level-rule.png"))

            cdp.eval("navigate('text')")
            wait_eval(cdp, "document.querySelector('.kernel-text-editor textarea')!==null", 30)
            text_result = cdp.eval("""(()=>{const area=document.querySelector('.kernel-text-editor textarea'),panel=document.querySelector('.kernel-text-editor');const before=area.value;area.value=before+'!';area.dispatchEvent(new Event('input',{bubbles:true}));return{rows:state.data.text.rows.length,kernelRows:state.data.text.rows.filter(row=>row.source==='kernel').length,menuRows:state.data.text.rows.filter(row=>row.source==='mngrp').length,editable:!area.readOnly&&area.value===before+'!',modelUpdated:state.data.text.rows.find(row=>row.id===state.selected.text)?.value===area.value,overflow:panel.scrollWidth>panel.clientWidth+1}})()""")
            assert text_result["kernelRows"] == 1322 and text_result["menuRows"] == 755 and text_result["editable"], text_result
            assert text_result["modelUpdated"], text_result
            assert not text_result["overflow"], text_result
            text_result["screenshot"] = str(screenshot(cdp, "goal-62-ff8-text.png"))

            cdp.eval("navigate('settings')")
            wait_eval(cdp, "document.querySelector('input[aria-label=\"Fast Start\"]')!==null", 30)
            fast_start = cdp.eval("""(()=>{const input=document.querySelector('input[aria-label="Fast Start"]'),row=input.closest('.setting-row');return{checked:input.checked,text:row.textContent.replace(/\\s+/g,' ').trim()}})()""")
            assert fast_start["checked"] is False, fast_start
            assert "opening credits" in fast_start["text"] and "normal transition" in fast_start["text"] and "main-menu initialization" in fast_start["text"], fast_start
            return {"encounter": encounter_result, "text": text_result, "fastStart": fast_start}
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "encounterLevelControl" in source and "Level rule" in source
    assert "renderText" in source and "/api/text/save" in source
    assert "fastStart:state.data.settings.fastStart" in source
    print({"binary": verify_level_binary(), "rendered": verify_rendered()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

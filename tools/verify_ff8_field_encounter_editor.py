"""Verify FF8 field encounter API, Maps UI, Save, refs, and runtime merge."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import field_data, field_encounters, runtime_layout  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


FIELD_KEY = "bg/bghall_1"
LOGICAL_ROOT = "direct/field/mapdata/bg/bghall_1/bghall_1"


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def different(value: int, high: int) -> int:
    return value + 1 if value < high else value - 1


def runtime_merge() -> dict:
    mrt_source, rat_source = field_data._encounter_source_paths(FIELD_KEY, "vanilla")
    assert mrt_source is not None and rat_source is not None
    mrt, rat = mrt_source.read_bytes(), rat_source.read_bytes()
    formations = field_encounters.read_mrt(mrt)["formations"]
    rate = field_encounters.read_rat(rat)["rate"]
    next_first = different(formations[0], 0xFFFF)
    next_second = different(formations[1], 0xFFFF)
    first = field_encounters.apply_mrt_edits(
        mrt, [{"slot": 0, "formation": next_first}])[0]
    second = field_encounters.apply_mrt_edits(
        mrt, [{"slot": 1, "formation": next_second}])[0]
    next_rate = different(rate, 0xFF)
    rate_mod = field_encounters.apply_rat_edit(rat, next_rate)[0]
    with tempfile.TemporaryDirectory(prefix="lexeditor-field-encounter-baseline-") as folder:
        baseline = Path(folder)
        root = baseline / "field/mapdata/bg/bghall_1"
        root.mkdir(parents=True)
        (root / "bghall_1.mrt").write_bytes(mrt)
        (root / "bghall_1.rat").write_bytes(rat)
        merged_mrt, mrt_mode, mrt_conflicts = runtime_layout._compose_logical_payload(
            LOGICAL_ROOT + ".mrt", [("first", first), ("second", second)],
            baseline, None, None)
        merged_rat, rat_mode, rat_conflicts = runtime_layout._compose_logical_payload(
            LOGICAL_ROOT + ".rat", [("rate", rate_mod)], baseline, None, None)
    assert merged_mrt is not None and mrt_mode == "semantic merge" and not mrt_conflicts
    assert merged_rat is not None and rat_mode == "semantic merge" and not rat_conflicts
    assert field_encounters.read_mrt(merged_mrt)["formations"][:2] == [
        next_first, next_second]
    assert field_encounters.read_rat(merged_rat)["rate"] == next_rate
    return {"mrtMode": mrt_mode, "ratMode": rat_mode,
            "formations": [next_first, next_second], "rate": next_rate}


def api_and_render() -> dict:
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-field-encounter-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            vanilla = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=vanilla")
            encounters = vanilla["randomEncounters"]
            assert len(encounters["formations"]) == 4
            next_formation = different(encounters["formations"][0], 0xFFFF)
            next_rate = different(encounters["rate"], 0xFF)
            saved = api(session.url, "/api/field/save", {"edits": [
                {"type": "fieldEncounter", "map": FIELD_KEY, "kind": "formation",
                 "slot": 0, "value": next_formation},
                {"type": "fieldEncounter", "map": FIELD_KEY, "kind": "rate",
                 "value": next_rate},
            ]})
            assert saved == {"saved": 2, "maps": 1}, saved
            current = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert current["randomEncounters"]["formations"][0] == next_formation
            assert current["randomEncounters"]["rate"] == next_rate
            mrt = Path(current["encounterMrtSource"]).read_bytes()
            rat = Path(current["encounterRatSource"]).read_bytes()
            vanilla_mrt = Path(vanilla["encounterMrtSource"]).read_bytes()
            assert mrt[2:] == vanilla_mrt[2:] and rat == bytes((next_rate,)) * 4

            profile, browser, cdp = browser_session()
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            target = next(row for row in api(session.url, "/api/fields")["rows"]
                          if row["key"] == FIELD_KEY)
            cdp.eval(
                f"state.mapsTab='field';state.selected.fields={target['id']};navigate('maps')")
            wait_eval(cdp, "document.querySelector('.field-encounter-section')!==null", 60)
            cdp.eval(
                "new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))",
                True)
            rendered = cdp.eval("""(()=>{const section=document.querySelector('.field-encounter-section'),row=section.querySelector('.field-encounter-row'),formation=[...section.querySelectorAll('select[aria-label*="random encounter formation"]')],rate=section.querySelector('input[aria-label$="random encounter rate"]'),source=rate.closest('.lex-source-control'),maps=[...document.querySelectorAll('.ff8-maps-tabs [role="tab"]')];return{fields:formation.length+Number(!!rate),formation:Number(formation[0].value),rate:Number(rate.value.replaceAll(',','')),vanilla:source?.lexVanillaValue?.(),refs:source?.querySelectorAll('.lex-reference-value').length||0,columns:getComputedStyle(row).gridTemplateColumns.split(' ').length,mapTabs:maps.map(tab=>tab.textContent.trim()),active:maps.find(tab=>tab.getAttribute('aria-selected')==='true')?.textContent.trim(),rowWidth:row.clientWidth,rowScrollWidth:row.scrollWidth,childWidths:[...row.children].map(node=>({client:node.clientWidth,scroll:node.scrollWidth,min:getComputedStyle(node).minWidth})),overflow:row.scrollWidth>row.clientWidth+1}})()""")
            assert rendered["fields"] == 5 and rendered["formation"] == next_formation
            assert rendered["rate"] == next_rate and rendered["vanilla"] == encounters["rate"]
            assert rendered["refs"] >= 1 and rendered["columns"] == 5, rendered
            assert len(rendered["mapTabs"]) == 2
            assert rendered["mapTabs"][0].startswith("Field")
            assert rendered["mapTabs"][1].startswith("World")
            assert rendered["active"].startswith("Field"), rendered
            assert not rendered["overflow"], rendered

            ui_rate = different(next_rate, 0xFF)
            cdp.eval(f"""(()=>{{const input=document.querySelector('input[aria-label$="random encounter rate"]');input.value={ui_rate};input.dispatchEvent(new Event('input',{{bubbles:true}}))}})()""")
            assert cdp.eval("dirtyCount()") >= 1
            cdp.eval("saveAll()", True)
            persisted = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert persisted["randomEncounters"]["rate"] == ui_rate
            assert Path(persisted["encounterRatSource"]).read_bytes() == bytes((ui_rate,)) * 4
            wait_eval(cdp, "document.querySelector('.field-encounter-section')!==null", 60)
            rendered["uiSavePersisted"] = True
            rendered["screenshot"] = str(screenshot(
                cdp, "goal-ff8-field-encounters.png"))
            return rendered
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "fieldEncounterSection" in source and 'type:"fieldEncounter"' in source
    print({"runtime": runtime_merge(), "rendered": api_and_render()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

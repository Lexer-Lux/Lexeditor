"""Verify FF8 field encounter API, Maps UI, Save, refs, and runtime merge."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from plugins.ff8 import field_data, field_encounters, runtime_layout  # noqa: E402
from plugins.ff8.plugin import FF8Session  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tests.shared.verify_panel_layout_visual_46 import (  # noqa: E402
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
                f"state.selected.fields={target['id']};navigate('fields')")
            # The field panel is tabbed now. The random-encounter controls and
            # the card-player table live under Misc, with the other field data
            # that has no tab of its own.
            wait_eval(cdp, "document.querySelector('#main .lex-subtab-button')!==null", 60)
            cdp.eval("""(()=>{const tab=[...document.querySelectorAll('#main .lex-subtab-button')]
              .find(node=>node.textContent.trim().replace(/[.?]+$/,'')==='Misc');tab.click()})()""")
            wait_eval(cdp, "document.querySelector('.field-encounter-section')!==null", 60)
            cdp.eval(
                "new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))",
                True)
            rendered = cdp.eval("""(()=>{const section=document.querySelector('.field-encounter-section'),formation=[...section.querySelectorAll('select[aria-label*="random encounter formation"]')],rate=section.querySelector('input[aria-label$="random encounter rate"]'),source=rate.closest('.lex-source-control'),maps=[...document.querySelectorAll('nav button[data-tab]')],label=node=>node.querySelector('.lex-tab-label-text')?.textContent.trim()||'';return{fields:formation.length+Number(!!rate),formation:Number(formation[0].value),rate:Number(rate.value.replaceAll(',','')),vanilla:source?.lexVanillaValue?.(),refs:source?.querySelectorAll('.lex-reference-value').length||0,mapTabs:maps.map(label),active:label(maps.find(node=>node.classList.contains('active'))||document.createElement('span')),sectionWidth:section.clientWidth,sectionScrollWidth:section.scrollWidth,overflow:section.scrollWidth>section.clientWidth+1}})()""")
            assert rendered["fields"] == 5 and rendered["formation"] == next_formation
            assert rendered["rate"] == next_rate and rendered["vanilla"] == encounters["rate"]
            assert rendered["refs"] >= 1, rendered
            # Field and World are main tabs now, not two halves of a Maps tab.
            assert "Field" in rendered["mapTabs"] and "Maps" not in rendered["mapTabs"], rendered
            assert rendered["active"].startswith("Field"), rendered
            assert not rendered["overflow"], rendered

            # A misc tab is written with its full stop and sorts last, after
            # every named area, and the INF variant and byte count belong with
            # the range explanation rather than as a line of numbers above the
            # fields it is supposed to explain.
            # A sub-tab's text carries its help glyph as a trailing question
            # mark, so the name is read with the glyph and any full stop removed.
            shape = cdp.eval("""(()=>{const name=node=>node.textContent.trim().replace(/[.?]+$/,''),
              buttons=[...document.querySelectorAll('#main .lex-subtab-button')];
              return{labels:buttons.map(name),
                miscRaw:(buttons.find(node=>name(node)==='Misc')||{textContent:''}).textContent,
                ranges:buttons.some(node=>name(node)==='Camera Ranges')}})()""")
            assert shape["labels"] and shape["labels"][-1] == "Misc", shape
            assert shape["miscRaw"].startswith("Misc."), shape
            assert shape["ranges"], shape
            cdp.eval("""(()=>{const name=node=>node.textContent.trim().replace(/[.?]+$/,''),
              tab=[...document.querySelectorAll('#main .lex-subtab-button')]
              .find(node=>name(node)==='Camera Ranges');tab.click()})()""")
            wait_eval(cdp, "(()=>{const name=node=>node.textContent.trim().replace(/[.?]+$/,''),"
                           "tab=[...document.querySelectorAll('#main .lex-subtab-button')]"
                           ".find(node=>name(node)==='Camera Ranges');"
                           "return !!tab&&tab.classList.contains('active')})()", 60)
            ranges = cdp.eval("""(()=>{const notes=[...document.querySelectorAll('#main .lex-detail-note')]
                .map(node=>node.textContent.trim()).join(' | ');
              const helps=[...document.querySelectorAll('#main .lex-info-help')]
                .map(node=>node.getAttribute('aria-label')||'');
              return{note:notes,help:helps.find(text=>text.includes('.inf header'))||''}})()""")
            assert "INF variant" not in ranges["note"], ranges
            assert ranges["help"], ranges
            # The rate edit below belongs to the Misc tab, so come back to it.
            cdp.eval("""(()=>{const name=node=>node.textContent.trim().replace(/[.?]+$/,''),
              tab=[...document.querySelectorAll('#main .lex-subtab-button')]
              .find(node=>name(node)==='Misc');tab.click()})()""")
            wait_eval(cdp, "document.querySelector('input[aria-label$=\"random encounter rate\"]')!==null", 60)

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


def plugin_source() -> str:
    """Every script the page loads, not the HTML shell alone.

    The plugin is one file per page now, so editor.html holds script tags and
    no editor code. Reading the shell alone made this check fail on a plugin
    that works, which hides real breakage instead of reporting it.
    """
    folder = ROOT / "plugins/ff8"
    shell = (folder / "editor.html").read_text(encoding="utf-8")
    loaded = [folder / name for name in re.findall(r'<script src="([^"/]+)"', shell)]
    return "\n".join([shell] + [path.read_text(encoding="utf-8") for path in loaded])


def main() -> int:
    source = plugin_source()
    assert "fieldEncounterSection" in source and 'type:"fieldEncounter"' in source
    print({"runtime": runtime_merge(), "rendered": api_and_render()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

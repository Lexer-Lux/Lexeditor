"""Round-trip, API, and hidden rendered checks for the FF8 world-map slice."""

from __future__ import annotations

import json
import struct
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import paths, world_map  # noqa: E402
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


def verify_binary() -> dict:
    original_roots = (paths.DATA_ROOT, paths.BASELINE_ROOT, paths.PROJECT_ROOT, paths.DIRECT_ROOT)
    with tempfile.TemporaryDirectory(prefix="lexeditor-world-binary-") as name:
        root = Path(name)
        try:
            paths.DATA_ROOT = root / "data"
            paths.BASELINE_ROOT = paths.DATA_ROOT / "baseline" / "en"
            paths.PROJECT_ROOT = root / "project"
            paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"
            baseline = world_map.ensure_baseline()
            cached = sorted(path.relative_to(paths.BASELINE_ROOT).as_posix()
                            for path in paths.BASELINE_ROOT.rglob("*") if path.is_file())
            rail_baseline = world_map.ensure_rail_baseline()
            cached = sorted(path.relative_to(paths.BASELINE_ROOT).as_posix()
                            for path in paths.BASELINE_ROOT.rglob("*") if path.is_file())
            assert cached == ["world/rail.obj", "world/rail.obj.source.json",
                              "world/wmsetus.obj", "world/wmsetus.obj.source.json"], cached
            before = baseline.read_bytes()
            parsed = world_map.parse(before)
            assert (len(parsed["helpers"]), len(parsed["regions"]), len(parsed["groups"]),
                    len(parsed["drawPoints"])) == (96, 768, 84, 128)
            legacy_reference = paths.PROJECT_ROOT / "references" / "wmset-only" / "world" / "dat"
            legacy_reference.mkdir(parents=True)
            (legacy_reference / "wmsetus.obj").write_bytes(before)
            inherited = world_map.rows("reference:wmset-only")
            assert len(inherited["tracks"]) == 14
            assert Path(inherited["railSource"]) == rail_baseline
            edit = {"kind": "region", "id": 0,
                    "regionId": (parsed["regions"][0]["regionId"] + 1) % 256}
            world_map.save([edit])
            after = (paths.DIRECT_ROOT / world_map.DIRECT_RELATIVE).read_bytes()
            changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
            section2 = world_map._pointers(before)[1]
            assert changed == [section2], changed
            assert len(after) == len(before)
            assert world_map.parse(after)["regions"][0]["regionId"] == edit["regionId"]
            rail_before = rail_baseline.read_bytes()
            rail = world_map.parse_rail(rail_before)
            assert len(rail["tracks"]) == 14, len(rail["tracks"])
            assert all(track["pointCount"] == len(track["points"])
                       for track in rail["tracks"])
            assert world_map.apply_rail_edits(
                rail_before, [rail["tracks"][0]]) == rail_before
            track = json.loads(json.dumps(rail["tracks"][0]))
            track["trainStop1"] ^= 1
            for key in ("x", "y", "z"):
                track["points"][0][key] ^= 1
            rail_after = world_map.apply_rail_edits(rail_before, [track])
            rail_changed = [index for index, pair in enumerate(zip(rail_before, rail_after))
                            if pair[0] != pair[1]]
            assert rail_changed == [4, 12, 16, 20], rail_changed
            assert rail_after[24:world_map.RAIL_BLOCK_SIZE] == rail_before[24:world_map.RAIL_BLOCK_SIZE]
            assert rail_after[world_map.RAIL_BLOCK_SIZE:] == rail_before[world_map.RAIL_BLOCK_SIZE:]
            assert struct.unpack_from("<i", rail_after, 24)[0] == struct.unpack_from("<i", rail_before, 24)[0]
            reparsed_track = world_map.parse_rail(rail_after)["tracks"][0]
            assert reparsed_track["trainStop1"] == track["trainStop1"]
            assert reparsed_track["points"][0] == track["points"][0]
            for bad_edit, message in (
                ({**track, "trainStop1": track["pointCount"]}, "invalid stop"),
                ({**track, "points": track["points"][:-1]}, "short point list"),
                ({**track, "points": [{**track["points"][0], "id": 1},
                                       *track["points"][1:]]}, "reordered point"),
                ({**track, "points": [{**track["points"][0], "x": 2 ** 31},
                                       *track["points"][1:]]}, "out-of-range coordinate"),
            ):
                try:
                    world_map.apply_rail_edits(rail_before, [bad_edit])
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"rail writer accepted {message}")
            return {"helpers": 96, "regions": 768, "groups": 84,
                    "tracks": 14, "railPoints": sum(value["pointCount"] for value in rail["tracks"]),
                    "changedOffsets": changed, "railChangedOffsets": rail_changed}
        finally:
            paths.DATA_ROOT, paths.BASELINE_ROOT, paths.PROJECT_ROOT, paths.DIRECT_ROOT = original_roots


def verify_rendered() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-render-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/world-map?dataset=vanilla")
            assert len(payload["regions"]) == 768 and len(payload["helpers"]) == 96
            assert len(payload["tracks"]) == 14
            next_region = (payload["regions"][1]["regionId"] + 1) % 256
            saved = api(session.url, "/api/world-map/save", {
                "edits": [{"kind": "region", "id": 1, "regionId": next_region}],
            })
            assert saved["saved"] == 1
            assert api(session.url, "/api/world-map?dataset=current")["regions"][1]["regionId"] == next_region
            track = payload["tracks"][0]
            track["points"][0]["x"] ^= 1
            rail_saved = api(session.url, "/api/world-map/save", {
                "edits": [track],
            })
            assert rail_saved["saved"] == 1 and rail_saved["files"][0].endswith("rail.obj"), rail_saved
            current_track = api(session.url, "/api/world-map?dataset=current")["tracks"][0]
            assert current_track["points"][0]["x"] == track["points"][0]["x"]
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('world')")
            wait_eval(cdp, "document.querySelectorAll('.world-map-tabs [role=tab]').length===9", 30)
            first = cdp.eval("document.querySelector('.world-map-detail input')?.value")
            cdp.eval("[...document.querySelectorAll('.world-map-tabs [role=tab]')].find(n=>n.textContent.includes('Encounter Rules')).click()")
            wait_eval(cdp, "document.querySelector('.world-map-detail input[aria-label=\"Encounter rule region ID\"]')!==null", 20)
            result = cdp.eval("""(()=>{const root=document.querySelector('.world-map-view'),panel=document.querySelector('.world-map-detail');return{
              tabs:[...document.querySelectorAll('.world-map-tabs [role=tab]')].map(n=>n.textContent.trim().replace(/\\d+$/,'')),
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              inputs:panel.querySelectorAll('input').length,
              overflow:root.scrollWidth>root.clientWidth+1,
              panelHeight:panel.getBoundingClientRect().height,
            }})()""")
            assert first is not None, "Region ID is not editable"
            assert result["tabs"] == ["Map", "Regions", "Encounter Rules", "Encounter Groups", "Field → World", "Draw Points", "Sky Colours", "Train Tracks", "World Textures"], result
            assert result["active"] == "Encounter Rules" and result["inputs"] == 3, result
            assert not result["overflow"] and result["panelHeight"] > 200, result
            cdp.eval("[...document.querySelectorAll('.world-map-tabs [role=tab]')].find(n=>n.textContent.includes('Train Tracks')).click()")
            wait_eval(cdp, "document.querySelector('.world-map-detail.world-rail')!==null", 20)
            rail_view = cdp.eval("""(()=>{const panel=document.querySelector('.world-map-detail.world-rail'),table=panel?.querySelector('.rail-point-table');return{
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              stopSelectors:panel?.querySelectorAll('select[aria-label^="Train stop"]').length,
              coordinateInputs:table?.querySelectorAll('input[aria-label^="Track "]').length,
              headers:[...table.querySelectorAll('.lex-column-list-header')].map(node=>node.textContent.trim()),
              overflow:document.querySelector('.world-map-view').scrollWidth>document.querySelector('.world-map-view').clientWidth+1,
            }})()""")
            assert rail_view["active"] == "Train Tracks" and rail_view["stopSelectors"] == 2, rail_view
            assert rail_view["coordinateInputs"] >= 3, rail_view
            assert not rail_view["overflow"], rail_view
            result["rail"] = rail_view
            result["screenshot"] = str(screenshot(cdp, "goal-61-64-ff8-world-map-rail.png"))
            cdp.eval("navigate('settings')")
            wait_eval(cdp, "document.querySelector('input[aria-label=\"Remove Damage Limit\"]')!==null", 20)
            tweaks = cdp.eval("""(()=>{const damage=document.querySelector('input[aria-label="Remove Damage Limit"]'),card=document.querySelector('input[aria-label="Better Card"]');return{damage:!!damage,card:!!card,damageChecked:damage?.checked,cardChecked:card?.checked}})()""")
            assert tweaks == {"damage": True, "card": True,
                              "damageChecked": False, "cardChecked": False}, tweaks
            result["tweaks"] = tweaks
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    print(json.dumps({"binary": verify_binary(), "rendered": verify_rendered()},
                     ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

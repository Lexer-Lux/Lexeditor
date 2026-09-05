"""Archive, API, round-trip, and hidden-render checks for the FF8 Field slice."""

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

from games.ff8 import field_data, paths  # noqa: E402
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


def verify_archive_and_binary() -> dict:
    previous = (paths.DATA_ROOT, paths.BASELINE_ROOT, paths.PROJECT_ROOT, paths.DIRECT_ROOT)
    with tempfile.TemporaryDirectory(prefix="lexeditor-field-binary-") as name:
        try:
            root = Path(name)
            paths.DATA_ROOT = root / "data"
            paths.BASELINE_ROOT = paths.DATA_ROOT / "baseline/en"
            paths.PROJECT_ROOT = root / "project"
            paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"
            index = field_data.index_rows("vanilla")
            assert len(index["rows"]) == 896, len(index["rows"])
            assert index["listedCount"] == 982, index["listedCount"]
            assert len({row["key"] for row in index["rows"]}) == len(index["rows"])
            assert [path.relative_to(paths.BASELINE_ROOT).as_posix() for path in
                    paths.BASELINE_ROOT.rglob("*") if path.is_file()] == ["field/index.json"]
            selected = next(row for row in index["rows"] if row["key"] == "bg/bghall_1")
            parsed = field_data.map_rows(selected["key"], "vanilla")
            assert len(parsed["players"]) == 4
            assert parsed["walkmesh"]["triangleCount"] == 382
            assert parsed["players"][0]["entity"] == "seito6"
            assert len(parsed["players"][0]["params"]) == 7
            cached = sorted(path.relative_to(paths.BASELINE_ROOT).as_posix() for path in
                            paths.BASELINE_ROOT.rglob("*") if path.is_file())
            selected_root = "field/mapdata/bg/bghall_1"
            metadata_path = paths.BASELINE_ROOT / selected_root / ".source.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            assert metadata["version"] == 5
            assert {"jsm", "sym", "inf", "msd", "id", "map", "mim", "mrt", "rat"} <= set(
                metadata["assets"]), metadata["assets"]
            expected_cache = {"field/index.json", f"{selected_root}/.source.json"}
            expected_cache.update(
                f"{selected_root}/bghall_1.{extension}"
                for extension in metadata["assets"])
            assert set(cached) == expected_cache, cached
            assert all(path == "field/index.json" or path.startswith(selected_root + "/")
                       for path in cached), cached
            before_path, _ = field_data._source_paths(selected["key"], "vanilla")
            before = before_path.read_bytes()
            param = parsed["players"][0]["params"][0]
            replacement = param["value"] + 1
            result = field_data.save([{"map": selected["key"], "player": 0,
                                       "param": 0, "value": replacement}])
            destination = paths.DIRECT_ROOT / "field/mapdata/bg/bghall_1/bghall_1.jsm"
            after = destination.read_bytes()
            changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
            assert result == {"saved": 1, "maps": 1}
            assert changed == [param["offset"]], changed
            assert field_data.map_rows(selected["key"])["players"][0]["params"][0]["value"] == replacement
            inf_before = (paths.BASELINE_ROOT /
                          "field/mapdata/bg/bghall_1/bghall_1.inf").read_bytes()
            entrances = field_data.map_rows(selected["key"], "vanilla")["entrances"]
            assert entrances["size"] == 676 and len(entrances["gateways"]) == 12
            assert len(entrances["triggers"]) == 12
            gateway = entrances["gateways"][0]
            x_replacement = gateway["destination"]["x"] + 1
            result = field_data.save([{"type": "entrance", "map": selected["key"],
                                       "kind": "gateway", "slot": 0,
                                       "field": "destination", "axis": "x",
                                       "value": x_replacement}])
            inf_destination = (paths.DIRECT_ROOT /
                               "field/mapdata/bg/bghall_1/bghall_1.inf")
            inf_after = inf_destination.read_bytes()
            inf_changed = [index for index, pair in enumerate(zip(inf_before, inf_after))
                           if pair[0] != pair[1]]
            assert result == {"saved": 1, "maps": 1}
            assert inf_changed == [gateway["destination"]["offset"]], inf_changed
            current = field_data.map_rows(selected["key"])
            assert current["entrances"]["gateways"][0]["destination"]["x"] == x_replacement
            assert current["players"][0]["params"][0]["value"] == replacement
            stable = inf_destination.read_bytes()
            invalid_batches = [
                [{"type": "entrance", "map": selected["key"], "kind": "gateway",
                  "slot": 0, "field": "destination", "axis": "q", "value": 1}],
                [{"type": "entrance", "map": selected["key"], "kind": "trigger",
                  "slot": 12, "field": "doorId", "value": 1}],
                [{"type": "entrance", "map": selected["key"], "kind": "gateway",
                  "slot": 0, "field": "fieldId", "value": 32768}],
                [{"type": "entrance", "map": selected["key"], "kind": "trigger",
                  "slot": 0, "field": "doorId", "value": 1},
                 {"type": "entrance", "map": selected["key"], "kind": "trigger",
                  "slot": 0, "field": "doorId", "value": 2}],
            ]
            for bad in invalid_batches:
                try:
                    field_data.save(bad)
                    raise AssertionError(f"accepted invalid entrance edits: {bad}")
                except ValueError:
                    pass
                assert inf_destination.read_bytes() == stable
            sparse = field_data.map_rows("fe/felast2", "vanilla")
            assert sparse["players"] == [] and sparse["entrances"]["gateways"] == []
            assert sparse["source"] is None and sparse["infSource"] is None
        finally:
            paths.DATA_ROOT, paths.BASELINE_ROOT, paths.PROJECT_ROOT, paths.DIRECT_ROOT = previous
    return {"maps": len(index["rows"]), "maplistEntries": index["listedCount"],
            "cardPlayers": len(parsed["players"]), "changedOffset": param["offset"],
            "infChangedOffset": gateway["destination"]["offset"],
            "sparseMap": "fe/felast2"}


def verify_inf_variants_and_rejections() -> dict:
    layouts = {676: (100, 32, 484), 672: (96, 32, 480),
               576: (96, 24, 384), 504: (24, 24, 312)}
    checked = []
    for size, (gateway_offset, gateway_size, trigger_offset) in layouts.items():
        raw = bytearray(size)
        for slot in range(12):
            offset = gateway_offset + slot * gateway_size
            for vertex in range(3):
                values = (slot * 10 + vertex, -(slot * 10 + vertex), 300 + vertex)
                struct.pack_into("<hhh", raw, offset + vertex * 6, *values)
            struct.pack_into("<H", raw, offset + 18, 0x7FFF if slot == 11 else slot + 20)
            offset = trigger_offset + slot * 16
            struct.pack_into("<hhh", raw, offset, slot, slot + 1, slot + 2)
            struct.pack_into("<hhh", raw, offset + 6, -slot, -(slot + 1), -(slot + 2))
            raw[offset + 12] = 0xFF if slot == 11 else slot
        parsed = field_data._parse_inf(raw)
        assert parsed["size"] == size and len(parsed["gateways"]) == 12
        assert parsed["gateways"][5]["exitB"] == {
            "x": 51, "y": -51, "z": 301,
            "offset": gateway_offset + 5 * gateway_size + 6,
        }
        assert not parsed["gateways"][11]["active"]
        assert not parsed["triggers"][11]["active"]
        edits = [
            {"kind": "gateway", "slot": 3, "field": "destination",
             "axis": "y", "value": -30000},
            {"kind": "gateway", "slot": 4, "field": "fieldId", "value": 321},
            {"kind": "trigger", "slot": 5, "field": "lineB",
             "axis": "z", "value": 22222},
            {"kind": "trigger", "slot": 6, "field": "doorId", "value": 42},
        ]
        mutated = field_data._edit_inf_bytes(bytes(raw), edits)
        target_ranges = [
            set(range(gateway_offset + 3 * gateway_size + 14,
                      gateway_offset + 3 * gateway_size + 16)),
            set(range(gateway_offset + 4 * gateway_size + 18,
                      gateway_offset + 4 * gateway_size + 20)),
            set(range(trigger_offset + 5 * 16 + 10, trigger_offset + 5 * 16 + 12)),
            {trigger_offset + 6 * 16 + 12},
        ]
        changed = {index for index, pair in enumerate(zip(raw, mutated))
                   if pair[0] != pair[1]}
        assert changed and changed <= set().union(*target_ranges), changed
        assert all(changed & target for target in target_ranges), (size, changed)
        reparsed = field_data._parse_inf(mutated)
        assert reparsed["gateways"][3]["destination"]["y"] == -30000
        assert reparsed["gateways"][4]["fieldId"] == 321
        assert reparsed["triggers"][5]["lineB"]["z"] == 22222
        assert reparsed["triggers"][6]["doorId"] == 42
        checked.append(parsed["variant"])
    for size in (0, 503, 505, 575, 577, 671, 673, 675, 677):
        try:
            field_data._parse_inf(bytes(size))
            raise AssertionError(f"accepted unsupported INF size {size}")
        except ValueError:
            pass
    return {"variants": checked, "rejectedSizes": 9}


def verify_api_and_render() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-field-render-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            index = api(session.url, "/api/fields?dataset=current")
            assert len(index["rows"]) == 896
            detail = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            param = detail["players"][0]["params"][0]
            replacement = param["value"] + 1
            saved = api(session.url, "/api/field/save", {"edits": [{
                "map": "bg/bghall_1", "player": 0, "param": 0, "value": replacement,
            }]})
            assert saved == {"saved": 1, "maps": 1}
            assert api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")["players"][0]["params"][0]["value"] == replacement
            entrance = detail["entrances"]["triggers"][0]
            door_replacement = 1 if entrance["doorId"] != 1 else 2
            saved = api(session.url, "/api/field/save", {"edits": [{
                "type": "entrance", "map": "bg/bghall_1", "kind": "trigger",
                "slot": 0, "field": "doorId", "value": door_replacement,
            }]})
            assert saved == {"saved": 1, "maps": 1}
            assert api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")["entrances"]["triggers"][0]["doorId"] == door_replacement

            target = next(row for row in index["rows"] if row["key"] == "bg/bghall_1")
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval(f"state.selected.fields={target['id']};navigate('fields')")
            wait_eval(cdp, "document.querySelector('.field-card-table')!==null&&document.querySelector('.field-gateway-table')!==null", 30)
            result = cdp.eval("""(()=>{const table=document.querySelector('.field-card-table'),gateway=document.querySelector('.field-gateway-table'),trigger=document.querySelector('.field-trigger-table'),input=gateway.querySelector('input[aria-label*="destination x"]'),panel=document.querySelector('.field-map-detail'),unsupported=[...panel.querySelectorAll('.lex-detail-section-title')].find(node=>node.textContent.includes('NOT YET EDITABLE'))?.parentElement.textContent;const before=Number(input.value.replaceAll(',',''));input.focus();input.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',bubbles:true}));return{maps:state.data.fields.rows.length,rows:table.querySelectorAll('.lex-column-list-row').length,gateways:gateway.querySelectorAll('.lex-column-list-row').length,triggers:trigger.querySelectorAll('.lex-column-list-row').length,value:Number(input.value.replaceAll(',','')),before,focusStayed:document.activeElement===input,overflow:panel.scrollWidth>panel.clientWidth+1,unsupported,help:gateway.querySelectorAll('.lex-info-help').length+trigger.querySelectorAll('.lex-info-help').length}})()""")
            result["mapIdStyled"] = cdp.eval("""(()=>{const cell=document.querySelector('.lex-column-list-cell[data-column-key="mapId"]');return cell?.classList.contains('lex-numbered-id-cell')&&!!cell.querySelector('.lex-record-id')})()""")
            assert result["maps"] == 896 and result["rows"] == 28, result
            assert result["gateways"] == 12 and result["triggers"] == 12, result
            assert result["value"] == result["before"] + 1 and result["focusStayed"], result
            assert result["mapIdStyled"], result
            assert not result["overflow"] and "General JSM instructions" not in result["unsupported"], result
            assert "Background" not in result["unsupported"], result
            assert result["help"] >= 7, result
            assert cdp.eval("dirtyCount()") >= 1
            cdp.eval("saveAll()", True)
            persisted = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert persisted["entrances"]["gateways"][0]["destination"]["x"] == result["value"]
            result["uiSavePersisted"] = True
            result["screenshot"] = str(screenshot(cdp, "goal-62-ff8-fields.png"))
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    server = (ROOT / "games/ff8/server.py").read_text(encoding="utf-8")
    assert 'function renderFields()' in source and '["maps","Maps"]' in source
    assert 'tabs:[{id:"field",label:"Field"},{id:"world",label:"World"}]' in source
    assert '["fields","Field"]' not in source and '["world","World Map"]' not in source
    assert '"/api/fields"' in server and '"/api/field/save"' in server
    print({"binary": verify_archive_and_binary(),
           "infVariants": verify_inf_variants_and_rejections(),
           "rendered": verify_api_and_render()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

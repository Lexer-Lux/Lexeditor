"""Verify FF8 field-background API, UI, persistence, and runtime composition."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import field_background, field_data, paths, runtime_layout  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


FIELD_KEY = "bg/bghall_1"
RELATIVE_MAP = Path("field/mapdata/bg/bghall_1/bghall_1.map")
RELATIVE_MIM = RELATIVE_MAP.with_suffix(".mim")
DIRECT_MAP = Path("direct") / RELATIVE_MAP


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def binary(url: str, path: str, payload: dict | None = None) -> bytes:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=120) as response:
        assert response.headers.get_content_type() == "image/png"
        return response.read()


def verify_runtime_merge(map_raw: bytes, mim_raw: bytes) -> dict:
    parsed = field_background.read(map_raw, mim_raw)
    first_x = parsed["tiles"][0]["x"]
    second_y = parsed["tiles"][1]["y"]
    low_raw, _ = field_background.apply_edits(
        map_raw, mim_raw, [{"tile": 0, "x": first_x + 1}])
    high_raw, _ = field_background.apply_edits(
        map_raw, mim_raw, [{"tile": 1, "y": second_y + 1}])
    with tempfile.TemporaryDirectory(prefix="lexeditor-field-background-merge-") as name:
        root = Path(name)
        baseline = root / "baseline"
        project = root / "project"
        runtime = root / "runtime/active"
        mods = []
        for order, (mod_id, raw) in enumerate((("low", low_raw), ("high", high_raw))):
            mod_root = root / mod_id
            target = mod_root / DIRECT_MAP
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            mods.append({"id": mod_id, "name": mod_id, "path": str(mod_root),
                         "enabled": True, "order": order, "readOnly": True,
                         "selected": False})
        baseline_map = baseline / RELATIVE_MAP
        baseline_map.parent.mkdir(parents=True, exist_ok=True)
        baseline_map.write_bytes(map_raw)
        (baseline / RELATIVE_MIM).write_bytes(mim_raw)
        result = runtime_layout.compose(
            project, runtime, mods, baseline_root=baseline,
            condition_state={"system": {}, "ffnx": {}},
        )
        merged = field_background.read((runtime / DIRECT_MAP).read_bytes(), mim_raw)
        assert merged["tiles"][0]["x"] == first_x + 1
        assert merged["tiles"][1]["y"] == second_y + 1
        conflict = next(row for row in result["conflicts"]
                        if row["path"] == DIRECT_MAP.as_posix())
        assert conflict["winner"] == "semantic merge"
        return {"mods": 2, "winner": conflict["winner"],
                "independentFieldsCombined": True}


def main() -> int:
    vanilla = field_data.map_rows(FIELD_KEY, "vanilla")
    assert vanilla["background"]["variant"] == "new"
    assert vanilla["background"]["tileCount"] > 0
    assert "Background" not in " ".join(vanilla["unsupported"])
    map_path = Path(vanilla["backgroundMapSource"])
    mim_path = Path(vanilla["backgroundMimSource"])
    map_raw, mim_raw = map_path.read_bytes(), mim_path.read_bytes()
    bounds = vanilla["background"]["bounds"]
    expected_size = (bounds["left"] + bounds["right"] + 16,
                     bounds["top"] + bounds["bottom"] + 16)
    runtime = verify_runtime_merge(map_raw, mim_raw)

    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-field-background-ui-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        # A reference can override MAP alone. The unmodified MIM comes from the
        # baseline, which proves the same provenance path used by the editor.
        reference_raw, _ = field_background.apply_edits(map_raw, mim_raw, [{
            "tile": 0, "x": vanilla["background"]["tiles"][0]["x"] + 2,
        }])
        reference = Path(project.name) / "references/reference-one/direct" / RELATIVE_MAP
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_bytes(reference_raw)

        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            detail = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            reference_detail = api(
                session.url, "/api/field?map=bg%2Fbghall_1&dataset=reference%3Areference-one")
            assert reference_detail["background"]["tiles"][0]["x"] == (
                detail["background"]["tiles"][0]["x"] + 2)
            assert reference_detail["backgroundMimSha256"] == detail["backgroundMimSha256"]

            saved_png = binary(
                session.url, "/assets/field-background.png?map=bg%2Fbghall_1&dataset=current")
            saved_image = Image.open(BytesIO(saved_png))
            assert saved_image.size == expected_size
            tile = detail["background"]["tiles"][0]
            preview_png = binary(session.url, "/api/field/background-preview", {
                "map": FIELD_KEY, "dataset": "current",
                "edits": [{"tile": 0, "x": tile["x"] + 1}],
                "enabledLayers": detail["background"]["layers"],
                "highlightTile": 0,
            })
            assert preview_png != saved_png
            assert Image.open(BytesIO(preview_png)).size == expected_size

            saved = api(session.url, "/api/field/save", {"edits": [{
                "type": "background", "map": FIELD_KEY, "tile": 0,
                "x": tile["x"] + 1,
            }]})
            assert saved == {"saved": 1, "maps": 1}
            output_map = Path(project.name) / DIRECT_MAP
            assert output_map.is_file()
            assert not output_map.with_suffix(".mim").exists()
            after = output_map.read_bytes()
            offset = field_background.read(map_raw, mim_raw)["tiles"][0]["offset"]
            changed = {index for index, pair in enumerate(zip(map_raw, after))
                       if pair[0] != pair[1]}
            assert changed and changed <= {offset, offset + 1}, changed
            reread = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert reread["background"]["tiles"][0]["x"] == tile["x"] + 1

            target = next(row for row in api(session.url, "/api/fields?dataset=current")["rows"]
                          if row["key"] == FIELD_KEY)
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 180)
            cdp.eval(
                f"state.selected.fields={target['id']};state.mapsTab='field';navigate('maps')")
            wait_eval(cdp, f"document.querySelector('.field-background-image')?.naturalWidth==={expected_size[0]}", 120)
            rendered = cdp.eval("""(()=>{const section=document.querySelector('.field-background-section'),image=section.querySelector('.field-background-image'),stage=section.querySelector('.field-background-stage');return{
              mapsTabs:[...document.querySelectorAll('.ff8-maps-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              title:section.querySelector('.lex-detail-section-title')?.textContent.trim(),
              image:[image.naturalWidth,image.naturalHeight],
              stage:[stage.clientWidth,stage.clientHeight],
              inputs:[...section.querySelectorAll('input[aria-label]')].map(node=>node.getAttribute('aria-label')),
              filters:section.querySelectorAll('.field-background-filter').length,
              sourceControls:section.querySelectorAll('.lex-source-control').length,
              exportText:section.querySelector('.field-background-actions')?.textContent.trim(),
              text:section.textContent,
              overflow:section.scrollWidth>section.clientWidth+1,
              errors:window.__testErrors,
            }})()""")
            assert rendered["mapsTabs"] == ["Field", "World"]
            assert rendered["title"].startswith("BACKGROUND")
            assert rendered["image"] == list(expected_size)
            assert rendered["stage"][0] >= 300 and rendered["stage"][1] >= 260
            assert any("tile 0 DESTINATION X" in label for label in rendered["inputs"])
            assert rendered["filters"] == 2
            assert rendered["sourceControls"] == len(detail["background"]["editableFields"])
            assert rendered["exportText"] == "EXPORT SAVED PNG"
            assert "MIM" in rendered["text"]
            assert not rendered["overflow"] and not rendered["errors"], rendered

            old_src = cdp.eval("document.querySelector('.field-background-image').src")
            before = cdp.eval("state.data.fields.rows.find(row=>row.key==='bg/bghall_1').background.tiles[0].x")
            cdp.eval("""(()=>{const input=[...document.querySelectorAll('.field-background-section input[aria-label]')].find(node=>node.getAttribute('aria-label').includes('tile 0 DESTINATION X'));input.value=String(Number(input.value.replaceAll(',',''))+1);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, f"state.data.fields.rows.find(row=>row.key==='bg/bghall_1').background.tiles[0].x==={before + 1}", 20)
            wait_eval(cdp, f"document.querySelector('.field-background-image').src!={old_src!r}&&document.querySelector('.field-background-image').complete", 120)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("saveAll()", True)
            try:
                wait_eval(cdp, "dirtyCount()===0", 20)
            except AssertionError:
                diagnostic = cdp.eval("""(()=>({
                  dirty:dirtyCount(),
                  status:document.querySelector('#status')?.textContent,
                  alert:document.querySelector('.lex-dialog')?.textContent,
                  datasets:editableDatasets.filter(name=>state.data[name]&&signature(state.data[name].rows)!==signature(state.base[name])),
                  settings:signature(state.data.settings)!==signature(state.base.settings),
                  init:signature(state.data.init)!==signature(state.base.init),
                  field:state.data.fields.rows.filter(row=>signature(row)!==signature(state.base.fields.find(base=>base.key===row.key))).map(row=>{
                    const base=state.base.fields.find(base=>base.key===row.key),paths=[],walk=(a,b,path)=>{if(paths.length>=20)return;if(signature(a)===signature(b))return;if(a&&b&&typeof a==='object'&&typeof b==='object'){for(const key of new Set([...Object.keys(a),...Object.keys(b)]))walk(a[key],b[key],path?`${path}.${key}`:key);return}paths.push({path,current:a,base:b})};walk(row,base,'');return{key:row.key,loaded:row._loaded,paths}
                  })
                }))()""")
                raise AssertionError(f"Save did not clear dirty state: {diagnostic}")
            browser_saved = api(
                session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert browser_saved["background"]["tiles"][0]["x"] == before + 1
            shot = screenshot(cdp, "goal-ff8-field-background-editor.png")
            print(json.dumps({
                "field": FIELD_KEY,
                "tiles": detail["background"]["tileCount"],
                "mapSize": saved_image.size,
                "previewChanged": True,
                "referenceMapWithBaselineMim": True,
                "saveChangedOffsets": sorted(changed),
                "uiSaveReadback": True,
                "runtime": runtime,
                "rendered": rendered,
                "screenshot": str(shot),
            }, ensure_ascii=True))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

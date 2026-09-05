"""Exact binary and API checks for the FF8 refine-table editor."""

from __future__ import annotations

import hashlib
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

from games.ff8 import paths, refine_tables  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


EXPECTED_COUNTS = {
    "m000": 102,
    "m001": 143,
    "m002": 10,
    "m003": 12,
    "m004": 110,
}
EDITABLE_FIELDS = ("text", "outputQuantity", "inputId", "inputQuantity", "outputId")


def api(url: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        url + path,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def assert_rejected(raw: bytes, edits: list[dict]) -> None:
    try:
        refine_tables.apply_edits(raw, edits)
    except (KeyError, TypeError, ValueError):
        return
    raise AssertionError(f"Accepted invalid refine edit: {edits!r}")


def outside_ranges(raw: bytes, ranges: list[tuple[int, int]]) -> bytes:
    """Return all bytes not covered by the sorted, non-overlapping ranges."""
    result = bytearray()
    cursor = 0
    for start, end in sorted(ranges):
        assert cursor <= start <= end <= len(raw)
        result.extend(raw[cursor:start])
        cursor = end
    result.extend(raw[cursor:])
    return bytes(result)


def table_map(payload: dict) -> dict[str, dict]:
    return {table["id"]: table for table in payload["tables"]}


def verify_binary(raw: bytes) -> dict:
    parsed = refine_tables.read(raw)
    tables = table_map(parsed)
    assert set(tables) == set(EXPECTED_COUNTS)
    assert {key: len(value["rows"]) for key, value in tables.items()} == EXPECTED_COUNTS
    assert sum(EXPECTED_COUNTS.values()) == 377

    # Supplying every editable value unchanged exercises a complete parse and
    # rebuild of each table. It must still be a byte-exact identity operation.
    identity_edits = []
    for table in parsed["tables"]:
        assert len(table["rows"]) == refine_tables.BY_KEY[table["id"]].count
        for row in table["rows"]:
            identity_edits.append({
                "table": table["id"],
                "id": row["id"],
                **{field: row[field] for field in EDITABLE_FIELDS},
            })
    identity, identity_changed = refine_tables.apply_edits(raw, identity_edits)
    assert identity_changed == 0
    assert identity == raw
    empty_identity, empty_changed = refine_tables.apply_edits(raw, [])
    assert empty_changed == 0 and empty_identity == raw

    numeric_offsets = {}
    for key, table_payload in tables.items():
        table = refine_tables.BY_KEY[key]
        row = table_payload["rows"][0]
        replacement = row["inputQuantity"] + 1 if row["inputQuantity"] < 255 else 254
        rebuilt, changed = refine_tables.apply_edits(raw, [{
            "table": key, "id": row["id"], "inputQuantity": replacement,
        }])
        expected_offset = table.binary_offset + row["id"] * refine_tables.ENTRY_SIZE + 6
        differences = [index for index, pair in enumerate(zip(raw, rebuilt))
                       if pair[0] != pair[1]]
        assert changed == 1 and len(rebuilt) == len(raw)
        assert differences == [expected_offset], (key, differences, expected_offset)
        assert rebuilt[expected_offset] == replacement
        assert table_map(refine_tables.read(rebuilt))[key]["rows"][0]["inputQuantity"] == replacement
        numeric_offsets[key] = expected_offset

    text_results = {}
    for key, table_payload in tables.items():
        table = refine_tables.BY_KEY[key]
        before_rows = table_payload["rows"]
        replacement = before_rows[0]["text"] + "!"
        rebuilt, changed = refine_tables.apply_edits(raw, [{
            "table": key, "id": 0, "text": replacement,
        }])
        assert changed == 1 and len(rebuilt) == len(raw)
        target_ranges = [
            (table.binary_offset, table.binary_offset + table.binary_size),
            (table.message_offset, table.message_offset + table.message_size),
        ]
        assert outside_ranges(raw, target_ranges) == outside_ranges(rebuilt, target_ranges)

        # Inside the recipe records, only the linked u16 text-offset fields may
        # move. Quantities, IDs, the unknown u16, and trailing padding stay exact.
        before_binary = raw[table.binary_offset:table.binary_offset + table.binary_size]
        after_binary = rebuilt[table.binary_offset:table.binary_offset + table.binary_size]
        allowed_offset_bytes = {
            slot * refine_tables.ENTRY_SIZE + byte
            for slot in range(table.count) for byte in (0, 1)
        }
        binary_differences = {
            index for index, pair in enumerate(zip(before_binary, after_binary))
            if pair[0] != pair[1]
        }
        assert binary_differences and binary_differences <= allowed_offset_bytes
        assert after_binary[table.count * refine_tables.ENTRY_SIZE:] == \
            before_binary[table.count * refine_tables.ENTRY_SIZE:]

        after_rows = table_map(refine_tables.read(rebuilt))[key]["rows"]
        assert after_rows[0]["text"] == replacement
        # The original FF8 byte stream can contain control encodings that do
        # not round-trip to the same length after an intentional text edit.
        # The next offset must follow the newly encoded row, not an assumed
        # one-byte delta from the source text.
        assert after_rows[1]["textOffset"] == len(bytes.fromhex(after_rows[0]["rawText"])) + 1
        assert [row["rawText"] for row in after_rows[1:]] == \
            [row["rawText"] for row in before_rows[1:]]
        for before, after in zip(before_rows, after_rows):
            for field in ("outputQuantity", "unknown", "inputId", "inputQuantity", "outputId"):
                assert after[field] == before[field]
        text_results[key] = {
            "offsetBytesChanged": len(binary_differences),
            "messageBytes": table.message_size,
        }

    invalid = [
        [{"table": "m999", "id": 0, "inputQuantity": 1}],
        [{"table": "m000", "id": -1, "inputQuantity": 1}],
        [{"table": "m000", "id": EXPECTED_COUNTS["m000"], "inputQuantity": 1}],
        [{"table": "m000", "id": 0, "inputQuantity": 1},
         {"table": "m000", "id": 0, "inputQuantity": 2}],
        [{"table": "m000", "id": 0, "unknown": 0}],
        [{"table": "m000", "id": 0, "outputQuantity": -1}],
        [{"table": "m000", "id": 0, "outputQuantity": 256}],
        [{"table": "m000", "id": 0, "inputId": "not-a-number"}],
        [{"table": "m000", "id": 0, "text": "A" * 0x1800}],
        [{"id": 0, "inputQuantity": 1}],
        [{"table": "m000", "inputQuantity": 1}],
    ]
    for edits in invalid:
        assert_rejected(raw, edits)

    malformed = bytearray(raw)
    first = refine_tables.BY_KEY["m000"]
    malformed[first.binary_offset + first.count * refine_tables.ENTRY_SIZE] = 1
    try:
        refine_tables.read(bytes(malformed))
    except ValueError as error:
        assert "trailing data" in str(error)
    else:
        raise AssertionError("Accepted a refine table with nonzero trailing recipe data")

    malformed = bytearray(raw)
    malformed[first.binary_offset + refine_tables.ENTRY_SIZE:
              first.binary_offset + refine_tables.ENTRY_SIZE + 2] = b"\0\0"
    try:
        refine_tables.read(bytes(malformed))
    except ValueError as error:
        assert "text offsets" in str(error)
    else:
        raise AssertionError("Accepted duplicate refine text offsets")

    return {
        "tables": EXPECTED_COUNTS,
        "recipes": sum(EXPECTED_COUNTS.values()),
        "numericOffsets": numeric_offsets,
        "textRebuilds": text_results,
        "invalidEditsRejected": len(invalid) + 2,
    }


def verify_api(raw: bytes) -> dict:
    baseline = paths.BASELINE_ROOT / "menu" / "mngrp.bin"
    baseline_hash = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-refine-project-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            vanilla = api(session.url, "/api/refine?dataset=vanilla")
            current = api(session.url, "/api/refine?dataset=current")
            assert {table["id"]: len(table["rows"]) for table in vanilla["tables"]} == EXPECTED_COUNTS
            assert current["tables"] == vanilla["tables"]
            assert {key: len(value) for key, value in current["choices"].items()} == {
                "item": 200, "magic": 97, "card": 111,
            }
            assert all(len({int(row["id"]) for row in values}) == len(values)
                       for values in current["choices"].values())
            assert len(current["rows"]) == 377

            numeric_edits = []
            expected_quantities = {}
            for table in current["tables"]:
                row = table["rows"][0]
                replacement = row["outputQuantity"] + 1 if row["outputQuantity"] < 255 else 254
                numeric_edits.append({
                    "table": table["id"], "id": 0, "outputQuantity": replacement,
                })
                expected_quantities[table["id"]] = replacement
            saved = api(session.url, "/api/refine/save", {"edits": numeric_edits})
            assert saved["saved"] == 5
            destination = Path(project) / "direct" / "menu" / "mngrp.bin"
            assert Path(saved["file"]).resolve() == destination.resolve()
            assert destination.is_file()
            reread = api(session.url, "/api/refine?dataset=current")
            for table in reread["tables"]:
                assert table["rows"][0]["outputQuantity"] == expected_quantities[table["id"]]

            text_edits = []
            expected_text = {}
            for table in reread["tables"]:
                replacement = table["rows"][0]["text"] + "!"
                text_edits.append({"table": table["id"], "id": 0, "text": replacement})
                expected_text[table["id"]] = replacement
            text_saved = api(session.url, "/api/refine/save", {"edits": text_edits})
            assert text_saved["saved"] == 5
            final = api(session.url, "/api/refine?dataset=current")
            for table in final["tables"]:
                assert table["rows"][0]["text"] == expected_text[table["id"]]
                assert table["rows"][0]["outputQuantity"] == expected_quantities[table["id"]]

            # The save endpoint must reject invalid input without replacing the
            # last valid output file.
            stable = destination.read_bytes()
            try:
                api(session.url, "/api/refine/save", {"edits": [
                    {"table": "m000", "id": 0, "inputQuantity": 256},
                ]})
            except Exception:
                pass
            else:
                raise AssertionError("API accepted an out-of-range refine quantity")
            assert destination.read_bytes() == stable
        assert session.wait_closed()
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == baseline_hash
    return {
        "numericRowsSaved": saved["saved"],
        "textRowsSaved": text_saved["saved"],
        "outputBytes": len(stable),
        "baselinePreserved": True,
    }


def verify_rendered() -> dict:
    output = ROOT / "worklog" / "issues" / "rendered" / "goal-ff8-refine-tables.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-refine-ui-project-", ignore_cleanup_errors=True)
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-refine-ui-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
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
                "width": 1800, "height": 1050, "deviceScaleFactor": 1, "mobile": False})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('refine')")
            wait_eval(cdp, "document.querySelectorAll('.refine-tabs [role=tab]').length===5", 45)
            rendered = cdp.eval("""(()=>({
              tabs:[...document.querySelectorAll('.refine-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              rows:document.querySelectorAll('.refine-view .lex-column-list-row').length,
              sources:document.querySelectorAll('.refine-view .lex-source-control').length,
              textareas:document.querySelectorAll('.refine-detail textarea').length,
              redundantLabel:[...document.querySelectorAll('.refine-detail .lex-detail-field-label')].some(node=>node.textContent.trim()==='DISPLAYED TEXT'),
              rightGap:Math.abs(document.querySelector('#main').getBoundingClientRect().right-document.querySelector('.refine-view').getBoundingClientRect().right),
              mainPaddingRight:parseFloat(getComputedStyle(document.querySelector('#main')).paddingRight),
              selects:[...document.querySelectorAll('.refine-view select')].map(node=>getComputedStyle(node).backgroundColor),
              errors:window.__testErrors||[],
            }))()""")
            assert rendered["tabs"] == [
                "Magic Refine", "Tool/Medicine Refine", "Magic Upgrade", "Med LV Up", "Card Mod",
            ], rendered
            assert rendered["rows"] == 15 and rendered["sources"] >= 60, rendered
            assert rendered["textareas"] == 1 and not rendered["errors"], rendered
            assert not rendered["redundantLabel"], rendered
            assert rendered["rightGap"] <= rendered["mainPaddingRight"] + 1, rendered
            assert all(color not in ("rgb(255, 255, 255)", "rgba(255, 255, 255, 1)")
                       for color in rendered["selects"]), rendered

            # Refine is the compact five-barrel case. Prove the actual FF8
            # table can reach that count at this viewport, and that every
            # barrel still contains its full final column without horizontal
            # overflow. A shared three-barrel test cannot cover this layout.
            for expected in range(2, 6):
                cdp.eval("document.querySelector('.refine-view .lex-barrel-increase').click()")
                wait_eval(cdp, (
                    "document.querySelectorAll('.refine-view .lex-barrel-grid>.lex-list').length==="
                    f"{expected}"), 5)
            five_barrels = cdp.eval("""(()=>{const lists=[...document.querySelectorAll('.refine-view .lex-barrel-grid>.lex-list')],grid=document.querySelector('.refine-view .lex-barrel-grid'),detail=document.querySelector('.refine-detail'),box=node=>{const r=node.getBoundingClientRect();return{left:r.left,right:r.right,width:r.width}};return{count:lists.length,grid:box(grid),detail:box(detail),lists:lists.map(list=>{const r=box(list),last=list.querySelector('.lex-column-list-row:not(.lex-filler-row) .lex-column-list-cell:last-child'),lr=last?box(last):null,headers=[...list.querySelectorAll('.lex-column-list-head-cell')].map(cell=>{const cr=box(cell),label=cell.querySelector('.header-label'),lr=box(label);return{cell:cr,label:lr,scroll:label.scrollWidth,client:label.clientWidth}});return{...r,scroll:list.scrollWidth,client:list.clientWidth,lastRight:lr?.right,headers}}),increaseDisabled:document.querySelector('.refine-view .lex-barrel-increase').disabled,errors:window.__testErrors||[]}})()""")
            assert five_barrels["count"] == 5 and five_barrels["increaseDisabled"], five_barrels
            assert five_barrels["detail"]["width"] >= 330, five_barrels
            # scrollWidth includes the table's bordered content box while
            # clientWidth excludes those borders. Compare it with the rendered
            # list width, then separately prove the final cell stays inside.
            assert all(item["scroll"] <= item["width"] + 1 and
                       item["lastRight"] <= item["right"] + 1
                       for item in five_barrels["lists"]), five_barrels
            assert all(header["label"]["left"] >= header["cell"]["left"] - 1 and
                       header["label"]["right"] <= header["cell"]["right"] + 1
                       for item in five_barrels["lists"] for header in item["headers"]), five_barrels
            assert not five_barrels["errors"], five_barrels

            changed = cdp.eval("""(()=>{const input=document.querySelector('.refine-view input[data-min]'),before=Number(input.value.replaceAll(',',''));input.value=String(before+1);input.dispatchEvent(new Event('input',{bubbles:true}));const text=document.querySelector('.refine-detail textarea');text.value+='!';text.dispatchEvent(new Event('input',{bubbles:true}));return{before,after:Number(input.value),dirty:dirtyCount()}})()""")
            assert changed["after"] == changed["before"] + 1 and changed["dirty"] >= 1, changed
            cdp.eval("saveAll().then(()=>true)", await_promise=True)
            assert cdp.eval("dirtyCount()") == 0
            saved = api(session.url, "/api/refine?dataset=current")
            first = saved["tables"][0]["rows"][0]
            assert first["inputQuantity"] == changed["after"] and first["text"].endswith("!"), first
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True})
            output.write_bytes(base64.b64decode(shot["data"]))
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        project.cleanup()
        profile.cleanup()
    return {"tabs": 5, "pageRows": 15, "barrels": 5,
            "globalSave": True, "screenshot": str(output)}


def main() -> int:
    baseline = paths.BASELINE_ROOT / "menu" / "mngrp.bin"
    raw = baseline.read_bytes()
    result = {
        "binary": verify_binary(raw),
        "api": verify_api(raw),
        "rendered": verify_rendered(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

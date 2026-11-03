"""The World Scripts tab: vehicle warps and sibling scripts as stored.

Opcodes are not decoded, so each script reads as a byte range with its
first words (codex/ff8/world-scripts.md). Sections that do not parse read
as empty instead of breaking the World page.
"""
import os
import struct
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8 import world_map  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import page, framework, ROOT  # noqa: E402


def _return_section(*bodies):
    base = (len(bodies) + 1) * 4
    table = [(base + sum(len(body) * 2 for body in bodies[:i])) for i in range(len(bodies))]
    raw = struct.pack(f"<{len(table) + 1}I", *table, 0)
    for body in bodies:
        raw += struct.pack(f"<{len(body)}H", *body)
    return raw


def _wmset(sections):
    bodies = {section: _return_section(*bodies) if section != 9 else bodies
              for section, bodies in sections.items()}
    pointers, cursor = [], 192
    for section in range(world_map.SECTION_COUNT):
        pointers.append(cursor)
        cursor += len(bodies.get(section, b""))
    return struct.pack("<48I", *pointers) + b"".join(
        bodies.get(section, b"") for section in range(world_map.SECTION_COUNT)) + b"\0"


def _fixture_sections():
    spawn = struct.pack("<3I", 12, 20, 0) + struct.pack(
        "<8H", 0xFF01, 0xFF05, 0, 0, 0xFF02, 0xFF05, 0, 0)
    return {
        7: [[0xFF01, 0x0007, 0xFF16], [0xFF01, 0x0008, 0xFF16]],
        9: spawn,
        11: [[0xFF01, 0x0000, 0xFF06, 0x00CD, 0xFF16],
             [0xFF01, 0x0000, 0xFF06, 0x012C, 0xFF16]],
        36: [[0xFF10, 0xFF16]],
    }


def test_world_scripts_serve_four_sections_as_byte_ranges(tmp_path):
    source = tmp_path / "wmsetus.obj"
    source.write_bytes(_wmset(_fixture_sections()))
    with patch.object(world_map, "source_path", return_value=source):
        payload = world_map.world_scripts("current")
    assert [(section["section"], section["label"], section["count"]) for section in payload["sections"]] == [
        (7, "Player location", 2), (9, "Entity spawn", 2),
        (11, "Vehicle warp", 2), (36, "Event", 1)]
    assert [row["id"] for row in payload["rows"]] == [7000, 7001, 9000, 9001, 11000, 11001, 36000]
    warps = [row for row in payload["rows"] if row["section"] == 11]
    assert warps[0]["head"] == "01 ff 00 00 06 ff cd 00"
    assert warps[0]["bytes"] == 10 and warps[1]["bytes"] == 10
    assert all(row["kind"] == "worldScript" for row in payload["rows"])
    with patch.object(world_map, "source_path", return_value=source):
        assert [row["head"] for row in world_map.vehicle_warp_scripts("current")["rows"]] == [
            row["head"] for row in warps]


def test_a_broken_section_reads_empty_without_hiding_the_rest(tmp_path):
    sections = _fixture_sections()
    sections[11] = [[0xFF01, 0x0000, 0xFF06, 0x00CD, 0xFF01]]
    source = tmp_path / "wmsetus.obj"
    source.write_bytes(_wmset(sections))
    with patch.object(world_map, "source_path", return_value=source):
        payload = world_map.world_scripts("current")
    counts = {section["section"]: section["count"] for section in payload["sections"]}
    assert counts == {7: 2, 9: 2, 11: 0, 36: 1}
    assert all(row["section"] != 11 for row in payload["rows"])


def test_shipped_script_section_counts():
    root = Path(os.environ["LOCALAPPDATA"]) / "Lexeditor/game-data/ff8/baseline/en/world/wmsetus.obj"
    if not root.is_file():
        pytest.skip("Requires extracted FF8 baseline")
    with patch.object(world_map, "source_path", return_value=root):
        payload = world_map.world_scripts("vanilla")
    assert {section["section"]: section["count"] for section in payload["sections"]} == {
        7: 38, 9: 20, 11: 4, 36: 92}


def test_scripts_tab_lists_scripts_with_a_readonly_detail(page, tmp_path):
    source = tmp_path / "wmsetus.obj"
    source.write_bytes(_wmset(_fixture_sections()))
    with patch.object(world_map, "source_path", return_value=source):
        scripts = world_map.world_scripts("current")["rows"]
    framework(page)
    page.add_style_tag(path=str(ROOT / "plugins/ff8/editor.css"))
    page.add_script_tag(content="function render(){};const shell={refresh(){}};")
    for name in ("cards_ui.js", "core.js", "records.js", "party.js", "battle.js",
                 "places.js", "model_viewer.js", "assets.js", "encounters_ui.js"):
        page.add_script_tag(path=str(ROOT / "plugins/ff8" / name))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.evaluate("""scripts => {
      document.body.insertAdjacentHTML('afterbegin', '<div id="toolbar"></div>');
      state.worldTab = 'scripts';
      state.data.world = {rows: scripts};
      state.selected.world = 11000;
      state.pages.world = 0;
      state.pageSizes.world = 80;
      renderWorldMapContent(true);
    }""", scripts)
    page.wait_for_timeout(800)
    assert page.locator(".ff8-world-tabs").get_by_role("tab", name="Scripts").count() == 1
    names = page.locator(".ff8-world-tabs .lex-tab-label-text").all_inner_texts()
    assert "scripts" in [name.strip().casefold() for name in names], names
    cells = page.locator(".ff8-record-list .lex-list-row").first.inner_text()
    assert "Vehicle warp" in cells or "Player location" in cells, cells
    detail = page.locator(".world-script-detail")
    assert detail.get_by_text("Vehicle warp script 0", exact=True).count() == 1
    assert detail.locator(".lex-readonly-field").evaluate_all(
        "es=>es.map(e=>e.value)") == [
            "Vehicle warp", "0", "10 bytes", "01 ff 00 00 06 ff cd 00"]
    assert detail.locator("input:not([disabled]), select, textarea").count() == 0
    assert not errors, errors

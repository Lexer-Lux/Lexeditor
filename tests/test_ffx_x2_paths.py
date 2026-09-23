from __future__ import annotations

from pathlib import Path

from games.ffx_x2 import paths, server, treasures
from games.ffx_x2.plugin import _write_fixture_vbf
from games.ffx_x2.vbf import read_index


def test_virtual_ffx_path_maps_to_raw_vbf_candidate_and_back():
    canonical = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin"
    raw = "ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin"
    assert paths.efl_archive_path("x", raw) == canonical
    assert paths.efl_archive_path("x", canonical) == canonical
    assert raw in paths.source_archive_candidates("x", canonical)


def test_structured_editor_resolves_raw_vbf_name_to_canonical_efl_target(tmp_path: Path, monkeypatch):
    raw = "ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin"
    archive = tmp_path / "FFX_Data.vbf"
    _write_fixture_vbf(archive, [(raw, b"fixture")])
    index = read_index(archive)

    entry = server._find_entry(index, "x", treasures.ARCHIVE_PATH)
    assert entry.path == raw

    project = tmp_path / "project"
    monkeypatch.setattr(paths, "PROJECT_ROOT", project)
    monkeypatch.setattr(server, "_index", lambda _game: index)
    _index, target, data, source = server._structured_current(treasures.ARCHIVE_PATH)

    assert source == "archive"
    assert data == b"fixture"
    assert target == project / "efl" / "x" / Path(*treasures.ARCHIVE_PATH.split("/"))

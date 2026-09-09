from __future__ import annotations

from pathlib import Path

import pytest

from games.ffx_x2.plugin import _write_fixture_vbf
from games.ffx_x2.vbf import VBFError, extract_to, normalize_archive_path, read_entry, read_index


def test_vbf_round_trip_extracts_compressed_and_partial_blocks(tmp_path: Path):
    archive = tmp_path / "fixture.vbf"
    files = [
        ("FFX_Data/ffx_ps2/test/compressed.bin", b"ABCD" * 20000),
        ("FFX_Data/ffx_ps2/test/partial.bin", bytes(range(251)) * 7),
    ]
    _write_fixture_vbf(archive, files)
    index = read_index(archive)
    assert index.file_count == 2
    for archive_path, expected in files:
        entry = index.find(archive_path.replace("/", "\\"))
        assert read_entry(index, entry) == expected


def test_vbf_rejects_corrupt_header_hash(tmp_path: Path):
    archive = tmp_path / "fixture.vbf"
    _write_fixture_vbf(archive, [("FFX_Data/a.bin", b"abc")])
    data = bytearray(archive.read_bytes())
    data[-1] ^= 0xFF
    archive.write_bytes(data)
    with pytest.raises(VBFError, match="header MD5"):
        read_index(archive)


def test_extract_refuses_to_overwrite_project_edits(tmp_path: Path):
    archive = tmp_path / "fixture.vbf"
    _write_fixture_vbf(archive, [("FFX_Data/a.bin", b"baseline")])
    index = read_index(archive)
    entry = index.find("FFX_Data/a.bin")
    target = tmp_path / "project" / "a.bin"
    first = extract_to(index, entry, target)
    assert first["created"] is True
    assert extract_to(index, entry, target)["created"] is False
    target.write_bytes(b"edited")
    with pytest.raises(FileExistsError, match="contains edits"):
        extract_to(index, entry, target)


@pytest.mark.parametrize("value", ["../escape.bin", "/absolute.bin", "C:/drive.bin", "a/../../b"])
def test_archive_paths_must_remain_relative(value: str):
    with pytest.raises(VBFError):
        normalize_archive_path(value)

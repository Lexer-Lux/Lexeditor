from __future__ import annotations

from pathlib import Path
import struct

from games.ffx_x2 import treasures
from games.ffx_x2.plugin import _write_fixture_vbf
from games.ffx_x2.verify_install import inspect_install


def _treasure_table() -> bytes:
    records = bytes([
        0x00, 50, 0x00, 0x00,
        0x02, 3, 0x34, 0x12,
    ])
    header = bytearray(0x14)
    header[:8] = b"TREASURE"
    struct.pack_into("<HHHH", header, 0x08, 0x20, 0x21, 4, len(records))
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + records + b"opaque-tail"


def _write_collection(game_root: Path, ffx_files: list[tuple[str, bytes]]) -> None:
    _write_fixture_vbf(game_root / "data" / "FFX_Data.vbf", ffx_files)
    _write_fixture_vbf(
        game_root / "data" / "FFX2_Data.vbf",
        [("ffx_ps2/ffx2/master/test.bin", b"X2 fixture")],
    )


def _touch_launch_files(game_root: Path) -> None:
    for relative in (
        "FFX.exe", "FFX-2.exe", "fahrenheit/bin/fhstage0.exe", "fahrenheit/bin/fhstage1.dll",
    ):
        target = game_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")


def test_verify_install_validates_raw_vbf_path_and_structured_table(tmp_path: Path):
    game_root = tmp_path / "game"
    source = _treasure_table()
    raw_path = treasures.ARCHIVE_PATH.removeprefix("FFX_Data/")
    _write_collection(game_root, [(raw_path, source)])
    _touch_launch_files(game_root)

    report = inspect_install(game_root, specs=({
        "game": "x",
        "key": "treasures",
        "archivePath": treasures.ARCHIVE_PATH,
        "builder": treasures.payload,
    },))

    assert report["ok"] is True
    assert report["contract"] == "Lexeditor.ffx-x2-install-verification"
    assert report["archives"]["x"]["ready"] is True
    assert report["archives"]["x2"]["ready"] is True
    row = report["structured"][0]
    assert row["status"] == "validated"
    assert row["sourcePath"] == raw_path
    assert row["archivePath"] == treasures.ARCHIVE_PATH
    assert row["rowCount"] == 2
    assert row["recordSize"] == 4
    assert row["tableSha256"] == treasures.sha256_bytes(source)
    assert report["launch"]["ready"] is True
    assert all(game["ready"] for game in report["launch"]["games"].values())


def test_verify_install_fails_closed_when_claimed_table_is_missing(tmp_path: Path):
    game_root = tmp_path / "game"
    _write_collection(game_root, [("ffx_ps2/ffx/master/new_uspc/battle/kernel/other.bin", b"fixture")])

    report = inspect_install(game_root, specs=({
        "game": "x",
        "key": "treasures",
        "archivePath": treasures.ARCHIVE_PATH,
        "builder": treasures.payload,
    },))

    assert report["ok"] is False
    row = report["structured"][0]
    assert row["status"] == "unavailable"
    assert treasures.ARCHIVE_PATH in row["error"]


def test_verify_install_reports_invalid_archive_without_parsing_tables(tmp_path: Path):
    game_root = tmp_path / "game"
    bad = game_root / "data" / "FFX_Data.vbf"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"not-a-vbf")
    _write_fixture_vbf(
        game_root / "data" / "FFX2_Data.vbf",
        [("ffx_ps2/ffx2/master/test.bin", b"X2 fixture")],
    )

    report = inspect_install(game_root, specs=({
        "game": "x",
        "key": "treasures",
        "archivePath": treasures.ARCHIVE_PATH,
        "builder": treasures.payload,
    },))

    assert report["ok"] is False
    assert report["archives"]["x"]["ready"] is False
    assert report["structured"][0]["status"] == "unavailable"
    assert report["structured"][0]["error"] == "x archive did not validate"

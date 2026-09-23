from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from games.ffx_x2 import treasures
from games.ffx_x2.plugin import _write_fixture_vbf
from games.ffx_x2.verify_install import (
    EXPECTED_STRUCTURED_KEYS, acceptance_checks, finalize_report, inspect_install,
)


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


def _treasure_spec() -> tuple[dict, ...]:
    return ({
        "game": "x",
        "key": "treasures",
        "archivePath": treasures.ARCHIVE_PATH,
        "builder": treasures.payload,
    },)


def _complete_acceptance_report() -> dict:
    return {
        "contract": "Lexeditor.ffx-x2-install-verification",
        "gameRoot": "fixture",
        "ok": True,
        "archiveHashesIncluded": True,
        "archives": {
            "x": {"ready": True, "sha256": "a" * 64},
            "x2": {"ready": True, "sha256": "b" * 64},
        },
        "structured": [
            {
                "key": key,
                "status": "validated",
                "tableSha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
            }
            for key in EXPECTED_STRUCTURED_KEYS
        ],
        "launch": {
            "ready": True,
            "games": {"x": {"ready": True}, "x2": {"ready": True}},
        },
    }


def test_verify_install_validates_raw_vbf_path_and_structured_table(tmp_path: Path):
    game_root = tmp_path / "game"
    source = _treasure_table()
    raw_path = treasures.ARCHIVE_PATH.removeprefix("FFX_Data/")
    _write_collection(game_root, [(raw_path, source)])
    _touch_launch_files(game_root)

    report = inspect_install(game_root, specs=_treasure_spec())

    assert report["ok"] is True
    assert report["contract"] == "Lexeditor.ffx-x2-install-verification"
    assert report["archiveHashesIncluded"] is False
    assert report["archives"]["x"]["ready"] is True
    assert report["archives"]["x2"]["ready"] is True
    assert "sha256" not in report["archives"]["x"]
    row = report["structured"][0]
    assert row["status"] == "validated"
    assert row["sourcePath"] == raw_path
    assert row["archivePath"] == treasures.ARCHIVE_PATH
    assert row["rowCount"] == 2
    assert row["recordSize"] == 4
    assert row["tableSha256"] == treasures.sha256_bytes(source)
    assert report["launch"]["ready"] is True
    assert all(game["ready"] for game in report["launch"]["games"].values())


def test_verify_install_optionally_hashes_complete_vbfs(tmp_path: Path):
    game_root = tmp_path / "game"
    source = _treasure_table()
    raw_path = treasures.ARCHIVE_PATH.removeprefix("FFX_Data/")
    _write_collection(game_root, [(raw_path, source)])

    report = inspect_install(game_root, specs=_treasure_spec(), hash_archives=True)

    assert report["ok"] is True
    assert report["archiveHashesIncluded"] is True
    for game, filename in (("x", "FFX_Data.vbf"), ("x2", "FFX2_Data.vbf")):
        target = game_root / "data" / filename
        assert report["archives"][game]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_strict_baseline_requires_hashes_all_tables_and_fahrenheit(tmp_path: Path):
    game_root = tmp_path / "game"
    source = _treasure_table()
    raw_path = treasures.ARCHIVE_PATH.removeprefix("FFX_Data/")
    _write_collection(game_root, [(raw_path, source)])
    _touch_launch_files(game_root)

    unhashed = finalize_report(
        inspect_install(game_root, specs=_treasure_spec(), hash_archives=False),
        require_fahrenheit=True,
    )
    assert unhashed["verificationPassed"] is True
    assert unhashed["acceptanceReady"] is False
    assert unhashed["acceptanceChecks"] == {
        "archivesAndStructuredValidated": False,
        "archiveHashesReady": False,
        "fahrenheitReady": True,
    }

    partial_hashed = finalize_report(
        inspect_install(game_root, specs=_treasure_spec(), hash_archives=True),
        require_fahrenheit=True,
    )
    assert partial_hashed["verificationPassed"] is True
    assert partial_hashed["acceptanceReady"] is False
    assert partial_hashed["acceptanceChecks"]["archivesAndStructuredValidated"] is False
    assert partial_hashed["acceptanceChecks"]["archiveHashesReady"] is True

    complete = finalize_report(_complete_acceptance_report(), require_fahrenheit=True)
    assert complete["verificationPassed"] is True
    assert complete["acceptanceReady"] is True
    assert complete["generatedAt"].endswith("Z")
    assert "T" in complete["generatedAt"]
    assert all(complete["acceptanceChecks"].values())

    missing_loader = _complete_acceptance_report()
    missing_loader["launch"]["ready"] = False
    missing_loader["launch"]["games"]["x2"]["ready"] = False
    missing_loader = finalize_report(missing_loader, require_fahrenheit=False)
    assert missing_loader["verificationPassed"] is True
    assert missing_loader["acceptanceReady"] is False
    assert missing_loader["acceptanceChecks"]["archiveHashesReady"] is True
    assert missing_loader["acceptanceChecks"]["fahrenheitReady"] is False


def test_strict_baseline_rejects_incomplete_or_malformed_maps():
    checks = acceptance_checks({
        "ok": True,
        "archiveHashesIncluded": True,
        "archives": {},
        "structured": [],
        "launch": {"ready": True, "games": {}},
    })
    assert checks == {
        "archivesAndStructuredValidated": False,
        "archiveHashesReady": False,
        "fahrenheitReady": False,
    }

    malformed = _complete_acceptance_report()
    malformed["archives"]["x"]["sha256"] = "z" * 64
    malformed["structured"][0]["tableSha256"] = "not-a-hash"
    checks = acceptance_checks(malformed)
    assert checks["archiveHashesReady"] is False
    assert checks["archivesAndStructuredValidated"] is False


def test_verify_install_fails_closed_when_claimed_table_is_missing(tmp_path: Path):
    game_root = tmp_path / "game"
    _write_collection(game_root, [("ffx_ps2/ffx/master/new_uspc/battle/kernel/other.bin", b"fixture")])

    report = inspect_install(game_root, specs=_treasure_spec())

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

    report = inspect_install(game_root, specs=_treasure_spec())

    assert report["ok"] is False
    assert report["archives"]["x"]["ready"] is False
    assert report["structured"][0]["status"] == "unavailable"
    assert report["structured"][0]["error"] == "x archive did not validate"

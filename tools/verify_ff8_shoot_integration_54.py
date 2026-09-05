"""Save/readback contract for the FF8 fixed Shoot integration (GitHub #54)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from service_session import request_json  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def post(session: FF8Session, endpoint: str, payload: dict) -> dict:
    return request_json(session.url + endpoint, payload)


def rejected(session: FF8Session, endpoint: str, payload: dict, phrase: str) -> None:
    try:
        post(session, endpoint, payload)
    except urllib.error.HTTPError as error:
        body = json.loads(error.read().decode("utf-8"))
        assert phrase in body.get("error", ""), body
    else:
        raise AssertionError(f"invalid request was accepted: {payload}")


def weapon_edit(weapon: dict, shots: int) -> dict:
    return {
        "id": weapon["id"],
        "upgradePrice": weapon["upgradePrice"],
        "ingredients": weapon["ingredients"],
        "fields": [{"field": "shots_per_atb", "value": shots}],
    }


def main() -> int:
    baseline_files = (
        paths.BASELINE_ROOT / "main" / "kernel.bin",
        paths.BASELINE_ROOT / "menu" / "mwepon.bin",
    )
    baseline = {path: digest(path) for path in baseline_files}

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-shoot-54-", ignore_cleanup_errors=True) as project:
        project_root = Path(project)
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            settings = request_json(session.url + "api/settings")
            assert settings["fixedCommandMenu"] is False

            rejected(session, "api/settings/save", {
                "flyingEvaBonus": settings["flyingEvaBonus"],
                "autoSortInventory": settings["autoSortInventory"],
                "singleGf": False,
                "fixedCommandMenu": True,
                "universalItem": settings["universalItem"],
                "scannedTargetScan": settings["scannedTargetScan"],
                "drawOncePerEnemy": settings["drawOncePerEnemy"],
            }, "requires Monogamy")

            saved = post(session, "api/settings/save", {
                "flyingEvaBonus": settings["flyingEvaBonus"],
                "autoSortInventory": settings["autoSortInventory"],
                "singleGf": True,
                "fixedCommandMenu": True,
                "universalItem": settings["universalItem"],
                "scannedTargetScan": settings["scannedTargetScan"],
                "drawOncePerEnemy": settings["drawOncePerEnemy"],
            })
            assert saved["saved"] == 1 and saved["singleGf"] is True
            assert saved["fixedCommandMenu"] is True
            reread = request_json(session.url + "api/settings")
            assert reread["singleGf"] is True and reread["fixedCommandMenu"] is True

            patch = Path(reread["patch"]).read_text(encoding="utf-8")
            assert "# Irvine fixed Shoot:" in patch
            for address in ("495805", "4BC492", "4ADAA1", "4ADBAC", "4843D5"):
                assert f"{address} =" in patch

            weapon = request_json(session.url + "api/weapons")["rows"][0]
            shots = next(field for field in weapon["fields"] if field["field"] == "shots_per_atb")
            assert (shots["value"], shots["minimum"], shots["maximum"]) == (1, 1, 10)

            result = post(session, "api/weapons/save", {"edits": [weapon_edit(weapon, 5)]})
            assert result["saved"] == 1
            reread_weapon = request_json(session.url + "api/weapons")["rows"][0]
            reread_shots = next(
                field for field in reread_weapon["fields"] if field["field"] == "shots_per_atb"
            )
            assert reread_shots["value"] == 5

            rejected(session, "api/weapons/save", {"edits": [weapon_edit(reread_weapon, 0)]},
                     "shots_per_atb must be 1 to 10")
            rejected(session, "api/weapons/save", {"edits": [weapon_edit(reread_weapon, 11)]},
                     "shots_per_atb must be 1 to 10")

        saved_settings = json.loads(
            (project_root / "lexeditor-settings.json").read_text(encoding="utf-8")
        )
        assert saved_settings["singleGf"] is True
        assert saved_settings["fixedCommandMenu"] is True

    assert all(digest(path) == expected for path, expected in baseline.items())
    print("FF8 fixed Shoot Settings/Weapons save and readback contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

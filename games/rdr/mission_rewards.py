"""Generate and validate the RDR Story mission reward editor contract."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import paths


ANALYSIS_ROOT = (
    paths.PROJECT_ROOT / "_analysis" / "decompiled" / "content" / "release64"
)
MISSION_REGISTRY_SOURCE = (
    ANALYSIS_ROOT / "scripting" / "designerdefined" / "long_update_thread.c"
)
REWARD_TABLE_SOURCE = (
    ANALYSIS_ROOT / "frontier" / "missions" / "ranch01" / "ranch01.c"
)
GENERATED_FILE = paths.PLUGIN_ROOT / "missions.generated.json"
OVERRIDE_FILE = paths.PROJECT_ROOT / "LexerRDR.missions.json"

REGISTRATION = re.compile(
    r"Function_(?:434|436|437)\(.*?&Global_6667,\s*(?P<id>\d+),\s*\d+,\s*"
    r'"(?P<path>\$/content/(?:Frontier|Mexico|North)/Missions/[^"]+)"',
    re.IGNORECASE,
)
CASE = re.compile(r"case\s+0x(?P<id>[0-9A-Fa-f]{8}):")
REWARD_CALL = re.compile(
    r"Function_(?P<helper>99|116|120)\(\s*(?P<amount>-?\d+)\s*,"
)
REWARD_HELPERS = {"99": "fame", "116": "honor", "120": "cash"}
ALLOWED_REWARDS = frozenset(REWARD_HELPERS.values())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_line(path: Path, offset: int) -> int:
    return path.read_text(encoding="utf-8", errors="replace")[:offset].count("\n") + 1


def _display_name(script_name: str) -> str:
    spaced = script_name.replace("_", " ")
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", spaced)
    spaced = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", spaced)
    match = re.fullmatch(r"(.+?)\s+(\d+)", spaced)
    if match:
        spaced = f"{match.group(1)} {int(match.group(2)):02d}"
    return spaced.replace("Fbi", "FBI").replace("Mex ", "Mexico ")


def _archive_path(asset_path: str) -> str:
    relative = asset_path.removeprefix("$/content/").casefold()
    return f"content/release64/{relative}.wsc"


def _parse_registry(text: str) -> dict[int, dict]:
    missions: dict[int, dict] = {}
    for match in REGISTRATION.finditer(text):
        mission_id = int(match.group("id"))
        asset_path = match.group("path")
        script_name = asset_path.rsplit("/", 1)[-1]
        missions[mission_id] = {
            "id": mission_id,
            "name": _display_name(script_name),
            "scriptName": script_name,
            "localizationKey": f"miss{mission_id}_short",
            "assetPath": asset_path,
            "archive": "game/content.rpf",
            "archivePath": _archive_path(asset_path),
            "region": asset_path.split("/")[3],
            "registryLine": _source_line(MISSION_REGISTRY_SOURCE, match.start()),
        }
    expected = set(range(1, 58))
    if set(missions) != expected:
        missing = sorted(expected - set(missions))
        extra = sorted(set(missions) - expected)
        raise ValueError(f"Mission registry mismatch; missing={missing}, extra={extra}")
    return missions


def _parse_rewards(text: str) -> dict[int, dict[str, int]]:
    start = text.find("void Function_115(int iParam0)")
    end = text.find("void Function_116(int iParam0", start)
    if start < 0 or end < 0:
        raise ValueError("The resolved mission reward table was not found")
    table = text[start:end]
    rewards = {mission_id: {} for mission_id in range(1, 58)}
    current: int | None = None
    for line in table.splitlines():
        case_match = CASE.search(line)
        if case_match:
            current = int(case_match.group("id"), 16)
            continue
        if current is None or not 1 <= current <= 57:
            continue
        reward_match = REWARD_CALL.search(line)
        if reward_match:
            kind = REWARD_HELPERS[reward_match.group("helper")]
            rewards[current][kind] = int(reward_match.group("amount"))
        if "break;" in line:
            current = None
    return rewards


def generate_document() -> dict:
    registry_text = MISSION_REGISTRY_SOURCE.read_text(
        encoding="utf-8", errors="replace"
    )
    reward_text = REWARD_TABLE_SOURCE.read_text(
        encoding="utf-8", errors="replace"
    )
    missions = _parse_registry(registry_text)
    rewards = _parse_rewards(reward_text)
    rows = []
    for mission_id in sorted(missions):
        row = missions[mission_id]
        row["rewards"] = {
            kind: rewards[mission_id].get(kind, 0)
            for kind in ("cash", "fame", "honor")
        }
        row["rewardSource"] = {
            "file": str(REWARD_TABLE_SOURCE),
            "function": "Function_115",
            "case": f"0x{mission_id:08X}",
        }
        rows.append(row)
    return {
        "schemaVersion": 1,
        "contract": "LexerRDR.mission-rewards",
        "game": "rdr",
        "summary": {
            "missions": len(rows),
            "cashRewards": sum(row["rewards"]["cash"] != 0 for row in rows),
            "fameRewards": sum(row["rewards"]["fame"] != 0 for row in rows),
            "honorRewards": sum(row["rewards"]["honor"] != 0 for row in rows),
        },
        "sources": [
            {
                "role": "mission identity registry",
                "file": str(MISSION_REGISTRY_SOURCE),
                "sha256": _sha256(MISSION_REGISTRY_SOURCE),
                "lines": "15591-15693",
            },
            {
                "role": "completion reward table",
                "file": str(REWARD_TABLE_SOURCE),
                "sha256": _sha256(REWARD_TABLE_SOURCE),
                "lines": "1496-1506, 4272-4341, 4891-5509",
            },
        ],
        "limits": {
            "step": 1,
            "rewards": {
                "cash": {"minimum": 0, "maximum": 999999},
                "fame": {"minimum": 0, "maximum": 999999},
                "honor": {"minimum": -999999, "maximum": 999999},
            },
            "runtimeConsumer": "LexerRDR.asi",
            "installedArchivesReadOnly": True,
        },
        "missions": rows,
    }


def validate_override(document: dict, base: dict | None = None) -> dict:
    if document.get("schemaVersion") != 1:
        raise ValueError("Unsupported mission reward schema version")
    if document.get("contract") != "LexerRDR.mission-rewards":
        raise ValueError("Invalid mission reward contract")
    base = base or load_generated()
    valid_ids = {row["id"] for row in base["missions"]}
    normalized = []
    seen = set()
    for row in document.get("overrides", []):
        if not isinstance(row, dict):
            raise ValueError("Each mission override must be an object")
        mission_id = row.get("id")
        if not isinstance(mission_id, int) or mission_id not in valid_ids:
            raise ValueError(f"Unknown mission ID: {mission_id}")
        if mission_id in seen:
            raise ValueError(f"Duplicate mission ID: {mission_id}")
        seen.add(mission_id)
        rewards = row.get("rewards")
        if not isinstance(rewards, dict) or not rewards:
            raise ValueError(f"Mission {mission_id} has no reward edits")
        unknown = set(rewards) - ALLOWED_REWARDS
        if unknown:
            raise ValueError(f"Unknown mission reward fields: {sorted(unknown)}")
        clean_rewards = {}
        for kind, value in rewards.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"Mission {mission_id} {kind} must be an integer")
            minimum = -999999 if kind == "honor" else 0
            if not minimum <= value <= 999999:
                raise ValueError(f"Mission {mission_id} {kind} is out of range")
            clean_rewards[kind] = value
        normalized.append({"id": mission_id, "rewards": clean_rewards})
    normalized.sort(key=lambda row: row["id"])
    return {
        "schemaVersion": 1,
        "contract": "LexerRDR.mission-rewards",
        "overrides": normalized,
    }


def load_generated() -> dict:
    document = json.loads(GENERATED_FILE.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != 1 or len(document.get("missions", [])) != 57:
        raise ValueError("Generated mission reward data is invalid")
    return document


def write_generated() -> dict:
    document = generate_document()
    GENERATED_FILE.write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return document


if __name__ == "__main__":
    generated = write_generated()
    print(json.dumps(generated["summary"], sort_keys=True))

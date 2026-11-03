"""Exact, editor-facing model of Story Mode's shared honor controls (#62).

Rockstar's Story scripts use a global event-block bitmask and a fixed 19-entry
magnitude function.  They do not provide one editable value per named action:
call sites choose one of these shared tiers, often with the same event hash.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from core.numeric_values import integer_value
from core.plugin_files import atomic_write


EVENTS = (
    ("HONOR_EVENT_LOOT_INNOCENT", 1, "Loot an innocent"),
    ("HONOR_EVENT_AMBIENT_KILL", 2, "Kill a person"),
    ("HONOR_EVENT_AMBIENT_KO", 4, "Knock out a person"),
    ("HONOR_EVENT_SCARE", 32, "Scare a person"),
    ("HONOR_EVENT_KILL_VERMIN", 64, "Kill vermin"),
    ("HONOR_EVENT_KILL_FARM_ANIMAL", 128, "Kill a farm animal or dog"),
    ("HONOR_EVENT_KILL_HORSE", 256, "Kill a horse"),
    ("HONOR_EVENT_STEAL_HORSE", 512, "Steal a horse"),
    ("HONOR_EVENT_STEAL_DONKEY", 1024, "Steal a donkey"),
    ("HONOR_EVENT_STEAL_MULE", 2048, "Steal a mule"),
    ("HONOR_EVENT_TRAMPLED_INNOCENT", 4096, "Trample an innocent"),
    ("HONOR_EVENT_STEAL_WAGON", 8192, "Steal a wagon"),
    ("HONOR_EVENT_ABANDON_ANIMALS", 16384, "Abandon hunted animals"),
    ("HONOR_EVENT_ANIMAL_BLEEDOUT", 32768, "Let an animal bleed out"),
    ("HONOR_EVENT_ANTAGONIZE", 65536, "Antagonize"),
    ("HONOR_EVENT_THEFT", 131072, "Theft"),
    ("HONOR_EVENT_INTERVENED", 262144, "Intervene or help"),
    ("HONOR_EVENT_WANTED_IN_CAMP", 524288, "Bring law or combat into camp"),
    ("HONOR_EVENT_DONATED_GAME", 1048576, "Donate game"),
    ("HONOR_EVENT_ITEM_REQUEST", 2097152, "Fulfil an item request"),
    ("HONOR_EVENT_LONG_ABSENCE", 4194304, "Return after a long absence"),
)

TIERS = (-640, -480, -320, -160, -40, -20, -10, -5, -2, -1,
         0, 1, 2, 5, 10, 20, 40, 160, 640)


def _defaults() -> dict:
    return {
        "events": [{"id": key, "bit": bit, "label": label, "enabled": True}
                   for key, bit, label in EVENTS],
        "tiers": [{"id": f"tier_{value:+d}", "vanilla": value,
                   "amount": value, "enabled": True} for value in TIERS],
    }


def read_honor_actions(path: Path) -> dict:
    data = _defaults()
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ['kind', 'id', 'enabled', 'amount']:
                raise ValueError("Unsupported honor control columns")
            rows = list(reader)
        event_by_id = {row["id"]: row for row in data["events"]}
        tier_by_id = {row["id"]: row for row in data["tiers"]}
        seen = set()
        for row in rows:
            if set(row) != {'kind', 'id', 'enabled', 'amount'} or any(value is None for value in row.values()):
                raise ValueError("Malformed honor control row")
            target = event_by_id.get(row.get("id")) or tier_by_id.get(row.get("id"))
            if not target:
                raise ValueError(f"unknown honor control: {row.get('id')!r}")
            if row['id'] in seen or row['kind'] != ('tier' if 'amount' in target else 'event'):
                raise ValueError("Duplicate or unsupported honor control owner")
            seen.add(row['id'])
            enabled = row['enabled'].strip().lower()
            if enabled not in {'0', '1', 'false', 'true', 'no', 'yes'}:
                raise ValueError("Unsupported honor enable value")
            target["enabled"] = enabled in {'1', 'true', 'yes'}
            if "amount" in target:
                target["amount"] = integer_value(row["amount"], 'Honor amount')
            elif row['amount'].strip():
                raise ValueError("Honor event has no independent amount")
    data.update({
        "available": True,
        "file": str(path),
        "scopeNote": "Edit replacement amounts in the honor-amount table. Event toggles map to Rockstar's exact Global_36616 bits; amounts are shared tiers selected by script call sites, not independent values for each event/action.",
        "bountyAudit": "Hostile human bounty hunters are recognized by REL_BOUNTY_HUNTER. PoliceDog uses A_C_DogHound_01, but short_update classifies all dog animal types as farm animals and applies HONOR_EVENT_KILL_FARM_ANIMAL unless that ped is explicitly blocked.",
    })
    return data


def prepare_honor_actions(path: Path, edits: list[dict]) -> tuple[int, bytes | None]:
    if not isinstance(edits, list):
        raise ValueError("Honor edits must be a list")
    if not edits:
        return 0, None
    data = read_honor_actions(path)
    controls = {row["id"]: row for row in data["events"] + data["tiers"]}
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or not {'id'} < set(edit) or set(edit) - {'id', 'enabled', 'amount'}:
            raise ValueError("Honor edits require id and enabled or amount")
        key = edit['id']
        if not isinstance(key, str):
            raise ValueError("Honor control id must be text")
        if key in seen or key not in controls:
            raise ValueError(f"duplicate or unknown honor control: {key!r}")
        seen.add(key); row = controls[key]
        if "enabled" in edit:
            value = edit["enabled"]
            if not isinstance(value, bool):
                raise ValueError(f"enabled must be boolean for {key}")
            row["enabled"] = value
        if "amount" in edit:
            if "amount" not in row:
                raise ValueError(f"honor event {key} has no independent amount")
            row["amount"] = integer_value(edit["amount"], 'Honor amount')
    handle = io.StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=("kind", "id", "enabled", "amount"))
    writer.writeheader()
    for row in data["events"]:
        writer.writerow({"kind": "event", "id": row["id"], "enabled": int(row["enabled"]), "amount": ""})
    for row in data["tiers"]:
        writer.writerow({"kind": "tier", "id": row["id"], "enabled": int(row["enabled"]), "amount": row["amount"]})
    return len(edits), handle.getvalue().encode('utf-8')


def save_honor_actions(path: Path, edits: list[dict]) -> int:
    count, payload = prepare_honor_actions(path, edits)
    if payload is not None:atomic_write(path, payload)
    return count

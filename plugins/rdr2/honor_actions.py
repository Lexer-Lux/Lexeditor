"""Exact, editor-facing model of Story Mode's shared honor controls (#62).

Rockstar's Story scripts use a global event-block bitmask and a fixed 19-entry
magnitude function.  They do not provide one editable value per named action:
call sites choose one of these shared tiers, often with the same event hash.
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path


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
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
        event_by_id = {row["id"]: row for row in data["events"]}
        tier_by_id = {row["id"]: row for row in data["tiers"]}
        for row in rows:
            target = event_by_id.get(row.get("id")) or tier_by_id.get(row.get("id"))
            if not target:
                raise ValueError(f"unknown honor control: {row.get('id')!r}")
            target["enabled"] = row.get("enabled", "1").strip().lower() not in ("0", "false", "no")
            if "amount" in target:
                target["amount"] = int(row["amount"])
    data.update({
        "available": True,
        "file": str(path),
        "scopeNote": "Edit replacement amounts in the honor-amount table. Event toggles map to Rockstar's exact Global_36616 bits; amounts are shared tiers selected by script call sites, not independent values for each event/action.",
        "bountyAudit": "Hostile human bounty hunters are recognized by REL_BOUNTY_HUNTER. PoliceDog uses A_C_DogHound_01, but short_update classifies all dog animal types as farm animals and applies HONOR_EVENT_KILL_FARM_ANIMAL unless that ped is explicitly blocked.",
    })
    return data


def save_honor_actions(path: Path, edits: list[dict]) -> int:
    data = read_honor_actions(path)
    controls = {row["id"]: row for row in data["events"] + data["tiers"]}
    seen = set()
    for edit in edits:
        key = str(edit.get("id", ""))
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
            row["amount"] = int(edit["amount"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("kind", "id", "enabled", "amount"))
        writer.writeheader()
        for row in data["events"]:
            writer.writerow({"kind": "event", "id": row["id"], "enabled": int(row["enabled"]), "amount": ""})
        for row in data["tiers"]:
            writer.writerow({"kind": "tier", "id": row["id"], "enabled": int(row["enabled"]), "amount": row["amount"]})
    os.replace(temporary, path)
    # Strict round trip catches malformed or silently dropped settings.
    check = read_honor_actions(path)
    if len(check["events"]) != len(EVENTS) or len(check["tiers"]) != len(TIERS):
        raise ValueError("honor controls failed round-trip validation")
    return len(edits)

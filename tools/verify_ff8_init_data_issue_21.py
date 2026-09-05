"""Verify the lossless FF8 init.out Starting Data editor."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff8 import formats, init_data, paths


def fail(message: str) -> None:
    raise AssertionError(message)


source = paths.BASELINE_ROOT / "main" / "init.out"
original = source.read_bytes()
original_hash = sha256(original).hexdigest()
payload = formats.init_rows("vanilla")

if len(payload["gfs"]["rows"]) != 16:
    fail("init.out did not expose all 16 GF records")
if len(payload["characters"]["rows"]) != 8:
    fail("init.out did not expose all 8 character records")
if len(payload["characters"]["rows"][0]["magics"]) != 32:
    fail("init.out did not expose all 32 character Magic slots")
if len(payload["inventory"]["rows"]) != 198:
    fail("init.out did not expose all 198 inventory slots")

edits = [
    {"kind": "general", "id": 0, "field": "gil", "value": 123456},
    {"kind": "config", "id": 0, "field": "volume", "value": 77},
    {"kind": "gf", "id": 2, "field": "current_hp", "value": 4321},
    {"kind": "character", "id": 1, "field": "current_hp", "value": 8765},
    {"kind": "magic", "id": 1, "slot": 31, "magicId": 1, "quantity": 80},
    {"kind": "inventory", "id": 0, "slot": 197, "itemId": 1, "quantity": 12},
]
updated, changed = init_data.apply(
    original, edits,
    item_ids=set(formats.ITEM_NAMES),
    weapon_ids={int(row["id"]) for row in formats.WEAPONS},
    magic_ids={int(row["id"]) for row in formats.MAGIC},
    weapons=formats.WEAPONS, magic=formats.MAGIC, gfs=formats.GFORCES,
    abilities=formats.INIT_ABILITIES,
)
if changed != len(edits):
    fail("init.out did not report every edited record")
if len(updated) != init_data.FULL_SIZE:
    fail("init.out was not safely grown to the complete 198-slot layout")

expected = set()
for offset, size in (
    (init_data.MISC_OFFSET + 24, 4),
    (init_data.CONFIG_OFFSET + 3, 1),
    (2 * init_data.GF_SIZE + 18, 2),
    (init_data.CHARACTER_OFFSET + init_data.CHARACTER_SIZE + 0, 2),
    (init_data.CHARACTER_OFFSET + init_data.CHARACTER_SIZE + 16 + 31 * 2, 2),
    (init_data.ITEMS_OFFSET + 197 * 2, 2),
):
    expected.update(range(offset, offset + size))

padded = original.ljust(init_data.FULL_SIZE, b"\0")
changed_offsets = {index for index, (before, after) in enumerate(zip(padded, updated)) if before != after}
if not changed_offsets or not changed_offsets <= expected:
    fail(f"init.out changed bytes outside the named fields: {sorted(changed_offsets - expected)[:8]}")

readback = init_data.read(
    updated, items=formats.item_choices(), weapons=formats.WEAPONS,
    magic=formats.MAGIC, gfs=formats.GFORCES, abilities=formats.INIT_ABILITIES,
)
field = lambda owner, name: next(row["value"] for row in owner["fields"] if row["field"] == name)
if field(readback["general"], "gil") != 123456:
    fail("Starting Gil did not read back")
if field(readback["config"], "volume") != 77:
    fail("Starting config did not read back")
if field(readback["gfs"]["rows"][2], "current_hp") != 4321:
    fail("Starting GF state did not read back")
if field(readback["characters"]["rows"][1], "current_hp") != 8765:
    fail("Starting character state did not read back")
if readback["characters"]["rows"][1]["magics"][31] != {"slot": 31, "magicId": 1, "quantity": 80}:
    fail("Starting Magic did not read back")
if readback["inventory"]["rows"][197] != {"slot": 197, "itemId": 1, "quantity": 12}:
    fail("Starting inventory did not read back")

invalid_edits = [
    [{"kind": "inventory", "id": 0, "slot": 198, "itemId": 1, "quantity": 1}],
    [{"kind": "inventory", "id": 0, "slot": 0, "itemId": 999, "quantity": 1}],
    [{"kind": "magic", "id": 0, "slot": 32, "magicId": 1, "quantity": 1}],
    [{"kind": "magic", "id": 0, "slot": 0, "magicId": 999, "quantity": 1}],
    [{"kind": "gf", "id": 0, "field": "current_hp", "value": 70000}],
    [edits[0], edits[0]],
]
for case in invalid_edits:
    try:
        init_data.apply(
            original, case, item_ids=set(formats.ITEM_NAMES),
            weapon_ids={int(row["id"]) for row in formats.WEAPONS},
            magic_ids={int(row["id"]) for row in formats.MAGIC},
            weapons=formats.WEAPONS, magic=formats.MAGIC, gfs=formats.GFORCES,
            abilities=formats.INIT_ABILITIES,
        )
    except (ValueError, KeyError):
        continue
    fail(f"init.out accepted an invalid edit: {case}")

if sha256(source.read_bytes()).hexdigest() != original_hash:
    fail("The init.out verifier changed the extracted baseline")

print({
    "records": {"gfs": 16, "characters": 8, "magicSlotsPerCharacter": 32, "inventorySlots": 198},
    "roundTripEdits": len(edits),
    "unknownBytesPreserved": True,
    "baselineUnchanged": True,
})

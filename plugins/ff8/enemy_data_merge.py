"""Per-section, per-record merge for FF8 battle enemy files (``c0m*.dat``).

Two mods that touch the same enemy used to collide wholesale: the composer
kept one mod's whole file and dropped the other's. This merger combines them
at the finest level the plugin's writers prove:

- the information section (monster section 7, no-model section 1) merges
  per record: one unit per stat field and per ability, Draw, Mug, drop,
  card, Devour, Renzokuken and defence slot;
- the battle-script/AI section (monster section 8, no-model section 2)
  merges per script (Init, Turn, Counter, Death, Pre-hit) and per battle-text
  line, rebuilt through the same writers the enemy pages use;
- every other section (skeleton, model, animation, textures, sounds and the
  rest) stays one opaque claim per section: the last mod to change it wins,
  and the unit says so.

A section whose bytes differ outside its proved records degrades to one
opaque section claim rather than failing the whole file; only an unparsable
container, a changed section count or an unsupported layout falls back to a
whole-file opaque winner, the way the other FF8 mergers fail closed.
"""

from __future__ import annotations

import struct

from . import assets, enemy_ai, enemy_battle_text, enemy_tables
from .formats import ENEMY_FIELDS


def _layout(filename: str, section_count: int) -> tuple[str, int, int] | None:
    """(kind, info section, AI section), 1-based, or None when unsupported."""
    if assets.MONSTER_FILENAME.fullmatch(filename) is None:
        return None
    if section_count == len(assets.MONSTER_SECTIONS):
        return ("monster", assets.MONSTER_SECTIONS.index("Information & stats") + 1,
                assets.MONSTER_SECTIONS.index("Battle scripts / AI") + 1)
    if section_count == len(assets.NOMODEL_SECTIONS):
        return ("nomodel", assets.NOMODEL_SECTIONS.index("Information & stats") + 1,
                assets.NOMODEL_SECTIONS.index("Battle scripts / AI") + 1)
    return None


def _section_names(kind: str) -> tuple[str, ...]:
    return assets.MONSTER_SECTIONS if kind == "monster" else assets.NOMODEL_SECTIONS


def _info_units() -> tuple[list[tuple[str, int, int]], dict[int, list[tuple[str, int]]]]:
    """(byte units, masked bit fields by offset) of the information section."""
    units: list[tuple[str, int, int]] = []
    for tier in enemy_tables.TIERS:
        base = enemy_tables.ABILITY_OFFSETS[tier]
        units.extend((f"ability:{tier}:{slot}", base + slot * 4, 4) for slot in range(16))
    for kind in ("draw", "mug", "drop"):
        for tier in enemy_tables.TIERS:
            base = enemy_tables.PAIR_OFFSETS[kind][tier]
            units.extend((f"{kind}:{tier}:{slot}", base + slot * 2, 2) for slot in range(4))
    units.extend((f"card:{slot}", enemy_tables.CARD_OFFSET + slot, 1) for slot in range(3))
    units.extend((f"devour:{slot}", enemy_tables.DEVOUR_OFFSET + slot, 1) for slot in range(3))
    units.extend((f"renzokuken:{slot}", enemy_tables.RENZOKUKEN_OFFSET + slot * 2, 2)
                 for slot in range(8))
    units.extend((f"elementDefence:{slot}", enemy_tables.ELEMENT_DEFENCE_OFFSET + slot, 1)
                 for slot in range(8))
    units.extend((f"statusDefence:{slot}", enemy_tables.STATUS_DEFENCE_OFFSET + slot, 1)
                 for slot in range(20))
    masked: dict[int, list[tuple[str, int]]] = {}
    for field in ENEMY_FIELDS:
        offset, size = int(field["offset"]), int(field["size"])
        if field.get("mask") is not None:
            masked.setdefault(offset, []).append((str(field["name"]), int(field["mask"])))
        else:
            units.append((f"stat:{field['name']}", offset, size))
    return units, masked


def _covered(units: list[tuple[str, int, int]], masked: dict[int, list[tuple[str, int]]],
             size: int) -> tuple[set[int], dict[int, int]]:
    """Every provably writable byte, plus each masked byte's known bits."""
    covered: set[int] = set()
    for _, offset, length in units:
        covered.update(range(offset, min(offset + length, size)))
    union: dict[int, int] = {}
    for offset, fields in masked.items():
        if offset < size:
            covered.add(offset)
            union[offset] = 0
            for _, mask in fields:
                union[offset] |= mask
    return covered, union


def _merge_info(vanilla: bytes, claims: list[tuple[str, bytes]], path: str,
                ) -> tuple[bytes | None, list[dict]]:
    """Merge information-section records, or None to keep the section whole."""
    units, masked = _info_units()
    for _, source in claims:
        if len(source) != len(vanilla):
            return None, []
    covered, union = _covered(units, masked, len(vanilla))
    for _, source in claims:
        for offset in range(len(vanilla)):
            if source[offset] == vanilla[offset]:
                continue
            if offset not in covered:
                return None, []
            known = union.get(offset)
            if known is not None and (source[offset] ^ vanilla[offset]) & ~known:
                return None, []
    output = bytearray(vanilla)
    conflicts: list[dict] = []
    for label, offset, length in units:
        if offset + length > len(vanilla):
            continue
        baseline = vanilla[offset:offset + length]
        values = [(mod_id, source[offset:offset + length]) for mod_id, source in claims
                  if source[offset:offset + length] != baseline]
        if not values:
            continue
        output[offset:offset + length] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({"unit": f"{path}:info:{label}", "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    for offset, fields in masked.items():
        if offset >= len(vanilla):
            continue
        for name, mask in fields:
            baseline = vanilla[offset] & mask
            values = [(mod_id, source[offset] & mask) for mod_id, source in claims
                      if (source[offset] & mask) != baseline]
            if not values:
                continue
            output[offset] = (output[offset] & ~mask) | (values[-1][1] & mask)
            if len(values) > 1 and len({value for _, value in values}) > 1:
                conflicts.append({"unit": f"{path}:info:stat:{name}",
                                  "winner": values[-1][0],
                                  "claimants": [mod_id for mod_id, _ in values]})
    return bytes(output), conflicts


def _script_key(script: dict) -> bytes | None:
    """The script's compiled bytes, or None when it cannot be rebuilt."""
    try:
        return enemy_ai._compile_script(script)
    except (KeyError, TypeError, ValueError):
        return None


def _readable_scripts(source: bytes) -> list[dict] | None:
    """Five rebuildable AI scripts, or None when the section is unproved."""
    try:
        document = enemy_ai.read(source)
    except ValueError:
        return None
    if not document["available"] or len(document["scripts"]) != 5:
        return None
    if any(not instruction.get("editable", False)
           for script in document["scripts"] for instruction in script["instructions"]):
        return None
    if any(_script_key(script) is None for script in document["scripts"]):
        return None
    return document["scripts"]


def _readable_lines(source: bytes) -> list[str] | None:
    """The decoded battle-text lines, or None when the section is unproved."""
    try:
        return [line["text"] for line in enemy_battle_text.read(source)["lines"]]
    except ValueError:
        return None


def _merge_ai(vanilla: bytes, claims: list[tuple[str, bytes]], ai_number: int,
              path: str) -> tuple[bytes | None, list[dict]]:
    """Merge AI scripts and battle-text lines, or None to keep the section whole."""
    base_scripts = _readable_scripts(vanilla)
    base_texts = _readable_lines(vanilla)
    if base_scripts is None or base_texts is None:
        return None, []
    base_compiled = [_script_key(script) for script in base_scripts]
    decoded: list[tuple[str, list[dict], list[str]]] = []
    for mod_id, source in claims:
        scripts = _readable_scripts(source)
        texts = _readable_lines(source)
        if scripts is None or texts is None or len(texts) != len(base_texts):
            return None, []
        decoded.append((mod_id, scripts, texts))
    merged_scripts = list(base_scripts)
    merged_texts = list(base_texts)
    conflicts: list[dict] = []
    script_changed = text_changed = False
    for index, name in enumerate(enemy_ai.SCRIPT_NAMES):
        values = [(mod_id, scripts[index]) for mod_id, scripts, _ in decoded
                  if _script_key(scripts[index]) != base_compiled[index]]
        if not values:
            continue
        script_changed = True
        merged_scripts[index] = values[-1][1]
        if len(values) > 1 and len({_script_key(script) for _, script in values}) > 1:
            conflicts.append({"unit": f"{path}:ai:{name}", "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    for line_id, baseline in enumerate(base_texts):
        values = [(mod_id, texts[line_id]) for mod_id, _, texts in decoded
                  if texts[line_id] != baseline]
        if not values:
            continue
        text_changed = True
        merged_texts[line_id] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({"unit": f"{path}:text:{line_id}", "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    if not script_changed and not text_changed:
        return None, []
    try:
        rebuilt = vanilla
        if text_changed:
            rebuilt, _ = enemy_battle_text.rebuild(rebuilt, merged_texts)
        if script_changed:
            rebuilt, _ = enemy_ai.rebuild_scripts(rebuilt, merged_scripts)
        sections = assets.parse_dat_sections(rebuilt)
    except ValueError:
        return None, []
    if sections is None:
        return None, []
    row = sections[ai_number - 1]
    return rebuilt[row["offset"]:row["offset"] + row["size"]], conflicts


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge enemy edits per section and per record, or name a whole-file fallback."""
    filename = path.rsplit("/", 1)[-1]
    vanilla_sections = assets.parse_dat_sections(vanilla)
    if vanilla_sections is None:
        return None, [], f"vanilla {path} is not a supported battle model file"
    layout = _layout(filename, len(vanilla_sections))
    if layout is None:
        return None, [], f"vanilla {path} is not a supported enemy layout"
    kind, info_number, ai_number = layout
    names = _section_names(kind)
    full = dict(mods)
    bodies: list[tuple[str, list[bytes]]] = []
    for mod_id, source in mods:
        sections = assets.parse_dat_sections(source)
        if sections is None:
            return None, [], f"{mod_id} is not a supported {path}"
        if len(sections) != len(vanilla_sections):
            return None, [], f"{mod_id} changes the section count of {path}"
        bodies.append((mod_id, [source[row["offset"]:row["offset"] + row["size"]]
                                for row in sections]))
    vanilla_bodies = [vanilla[row["offset"]:row["offset"] + row["size"]]
                      for row in vanilla_sections]
    output_bodies = list(vanilla_bodies)
    conflicts: list[dict] = []
    for number, name in enumerate(names, 1):
        index = number - 1
        claims = [(mod_id, owned[index]) for mod_id, owned in bodies
                  if owned[index] != vanilla_bodies[index]]
        if not claims:
            continue
        if number == info_number:
            merged, unit_conflicts = _merge_info(vanilla_bodies[index], claims, path)
            if merged is not None:
                output_bodies[index] = merged
                conflicts.extend(unit_conflicts)
                continue
        elif number == ai_number:
            merged, unit_conflicts = _merge_ai(
                vanilla, [(mod_id, full[mod_id]) for mod_id, _ in claims],
                ai_number, path)
            if merged is not None:
                output_bodies[index] = merged
                conflicts.extend(unit_conflicts)
                continue
        output_bodies[index] = claims[-1][1]
        if len(claims) > 1 and len({body for _, body in claims}) > 1:
            conflicts.append({"unit": f"{path}:section:{number}:{name}",
                              "winner": claims[-1][0],
                              "claimants": [mod_id for mod_id, _ in claims]})
    positions = []
    cursor = 4 + (len(output_bodies) + 1) * 4
    for body in output_bodies:
        positions.append(cursor)
        cursor += len(body)
    positions.append(cursor)
    output = (struct.pack("<I", len(output_bodies))
              + struct.pack(f"<{len(positions)}I", *positions)
              + b"".join(output_bodies))
    rows = assets.parse_dat_sections(output)
    if rows is None or any(
            output[row["offset"]:row["offset"] + row["size"]] != body
            for row, body in zip(rows, output_bodies)):
        return None, [], f"merged {path} did not reassemble its sections"
    return output, conflicts, ""

"""Structured FF8 enemy battle-AI editing.

The DAT section layout and opcode sizes come from FF8 Ultimate Editor's
MonsterAnalyser/AIData and ai_cronos.json.  Lexeditor can change operands in
place or rebuild all five proved scripts.  A rebuild preserves the battle-text
offset and data payload byte-for-byte and shifts later DAT sections by the
exact aligned size delta.  Unknown tails remain fail-closed.
"""

from __future__ import annotations

import re


SCRIPT_NAMES = ("Init", "Turn", "Counter", "Death", "Pre-hit")

# opcode: (display name, operand types).  These are all entries in the upstream
# ai_cronos.json table, including commands absent from the English baseline.
OPCODES = {
    0: ("Stop", ()), 1: ("Show text", ("battle_text",)),
    2: ("If", ("subject", "subject_param", "comparator", "value16", "skip16")),
    3: ("Prepare magic", ("magic",)), 4: ("Target", ("target",)),
    5: ("Prepare animation", ("u8",)), 6: ("Use prepared action", ()),
    7: ("Prepare monster ability", ("monster_ability",)), 8: ("Die", ()),
    9: ("Set hit/death animation", ("u8",)),
    11: ("Use random ability", ("ability_line", "ability_line", "ability_line")),
    12: ("Use ability", ("ability_line",)), 13: ("No-op", ("u8",)),
    14: ("Set local variable", ("local_var", "u8")),
    15: ("Set battle variable", ("battle_var", "u8")),
    17: ("Set global variable", ("global_var", "u8")),
    18: ("Add to local variable", ("local_var", "u8")),
    19: ("Add to battle variable", ("battle_var", "u8")),
    21: ("Add to global variable", ("global_var", "u8")),
    22: ("Recover HP", ()), 23: ("Prevent escape", ("bool",)),
    24: ("Show text at configured speed", ("battle_text",)),
    25: ("Do nothing", ("u8",)), 26: ("Show and lock text", ("battle_text",)),
    27: ("Enemy enters with animation", ("encounter_slot", "u8")),
    28: ("Wait for text", ("u8",)), 29: ("Enemy leaves", ("target_slot",)),
    30: ("Play attack animation", ("animation",)),
    31: ("Enemy enters", ("u8",)), 32: ("Wait for text (fast)", ("u8",)),
    34: ("Set address", ("u32", "u8", "u32")),
    35: ("Jump", ("jump16",)), 36: ("Fill ATB", ()),
    37: ("Set extra Scan text", ("scan_text",)),
    # ai_cronos param_index proves that these two commands store operands in a
    # different order from their player-facing sentence.
    38: ("Target by status", ("bool", "target_group", "comparator", "status")),
    39: ("Set auto-status", ("status", "activate")),
    40: ("Change stat", ("stat", "percent",)), 41: ("Draw", ()),
    42: ("Cast drawn magic", ()), 43: ("Target battle slot", ("battle_slot",)),
    44: ("Vanish", ()), 45: ("Change elemental damage", ("element", "value16")),
    46: ("Blow away", ()), 47: ("Become targetable", ()),
    48: ("Become untargetable", ()), 49: ("Give GF", ("gf",)),
    50: ("Prepare summon", ()), 51: ("Activate", ()),
    52: ("Enable enemy slot", ("encounter_slot",)),
    53: ("Load and target enemy slot", ("enemy_slot",)), 54: ("Call Gilgamesh", ()),
    55: ("Give card", ("card",)), 56: ("Give item", ("item",)),
    57: ("Game over", ()), 58: ("Make slot targetable", ("battle_slot",)),
    59: ("Assign slot", ("encounter_slot", "battle_slot")),
    60: ("Add current HP", ("u8",)), 61: ("Set Omega proof", ()),
    255: ("Unused", ()),
}

COMPARATORS = ("=", "<", ">", "!=", "<=", ">=")
SUBJECTS = {
    0: "HP", 1: "HP in team", 2: "Random value", 3: "Encounter ID",
    4: "Status", 5: "Status in team", 6: "Alive members", 7: "Level",
    8: "Dead", 9: "Alive", 10: "Attacker", 14: "Difficulty",
    15: "Alive in slot", 16: "Gender in team", 17: "GF drawable",
    18: "Special byte", 19: "Countdown", 20: "Status of all",
    **{value: f"Global variable {value}" for value in range(80, 88)},
    **{value: f"Battle variable {value}" for value in range(96, 104)},
    **{value: f"Local {chr(65 + value - 220)}" for value in range(220, 228)},
}

_SOURCE_LINE = re.compile(
    r"^(?P<label>[A-Za-z_][A-Za-z0-9_]*):\s+"
    r"(?P<mnemonic>[A-Z][A-Z0-9_]*)\[(?P<opcode>[0-9]{1,3})\]"
    r"(?P<operands>(?:\s+[^\s]+)*)$")
_SOURCE_LABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _mnemonic(name: str) -> str:
    """Return the stable source spelling for an opcode name."""
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def format_script(script: dict) -> str:
    """Render one decoded script as strict, typed, editable source text."""
    lines = []
    for instruction in script.get("instructions", []):
        if not instruction.get("editable", False):
            raise ValueError("Unsupported enemy AI raw tails have no editable source form")
        opcode = int(instruction["opcode"])
        definition = OPCODES.get(opcode)
        if definition is None:
            raise ValueError(f"Unsupported enemy AI opcode: {opcode}")
        name, types = definition
        supplied = list(instruction.get("operands", []))
        if len(supplied) != len(types):
            raise ValueError(f"Enemy AI {name} requires {len(types)} operands")
        label = str(instruction.get("label") or instruction.get("key") or "")
        if not _SOURCE_LABEL.fullmatch(label):
            raise ValueError(f"Enemy AI source label is invalid: {label}")
        values = []
        for kind, operand in zip(types, supplied):
            if kind in {"jump16", "skip16"}:
                target = instruction.get("targetLabel")
                if target == "END":
                    value = "@END"
                elif target and _SOURCE_LABEL.fullmatch(str(target)):
                    value = f"@{target}"
                else:
                    raise ValueError(f"Enemy AI branch at {label} has no valid label target")
            elif kind == "bool":
                value = "true" if int(operand["value"]) else "false"
            else:
                value = str(int(operand["value"]))
            values.append(f"{kind}={value}")
        suffix = " " + " ".join(values) if values else ""
        lines.append(f"{label}: {_mnemonic(name)}[{opcode}]{suffix}")
    return "\n".join(lines)


def parse_script(source: str, script_id: int = 0, name: str | None = None) -> dict:
    """Parse one strict source script into the structural compiler document."""
    if not isinstance(source, str):
        raise ValueError("Enemy AI source must be text")
    rows = []
    labels = set()
    pending_targets: list[tuple[dict, str]] = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        match = _SOURCE_LINE.fullmatch(line)
        if not match:
            raise ValueError(f"Enemy AI source line {line_number} has invalid syntax")
        label = match.group("label")
        if label == "END" or label in labels:
            raise ValueError(f"Enemy AI source line {line_number} has a duplicate or reserved label: {label}")
        labels.add(label)
        opcode = int(match.group("opcode"))
        definition = OPCODES.get(opcode)
        if definition is None:
            raise ValueError(f"Enemy AI source line {line_number} uses unsupported opcode {opcode}")
        opcode_name, types = definition
        if match.group("mnemonic") != _mnemonic(opcode_name):
            raise ValueError(
                f"Enemy AI source line {line_number} mnemonic does not match opcode {opcode}")
        tokens = match.group("operands").split()
        if len(tokens) != len(types):
            raise ValueError(
                f"Enemy AI source line {line_number} requires {len(types)} typed operands")
        operands = []
        target_key = None
        for operand_index, (kind, token) in enumerate(zip(types, tokens)):
            if "=" not in token:
                raise ValueError(f"Enemy AI source line {line_number} has an untyped operand")
            supplied_kind, text = token.split("=", 1)
            if supplied_kind != kind:
                raise ValueError(
                    f"Enemy AI source line {line_number} expected {kind}, not {supplied_kind}")
            if kind in {"jump16", "skip16"}:
                if not text.startswith("@") or not _SOURCE_LABEL.fullmatch(text[1:]):
                    raise ValueError(
                        f"Enemy AI source line {line_number} branch must name a label")
                target_key = text[1:]
                value = 0
            elif kind == "bool":
                if text not in {"true", "false"}:
                    raise ValueError(
                        f"Enemy AI source line {line_number} bool must be true or false")
                value = int(text == "true")
            else:
                if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", text):
                    raise ValueError(
                        f"Enemy AI source line {line_number} {kind} must be a decimal integer")
                value = int(text)
            value = _validated_operand(kind, value)
            operand = _control(kind, value)
            operand.update(index=operand_index, size=_operand_width(kind))
            operands.append(operand)
        row = {"key": label, "label": label, "opcode": opcode, "name": opcode_name,
               "operands": operands, "size": 1 + sum(_operand_width(kind) for kind in types),
               "raw": "Rebuilt from source", "editable": True}
        if target_key is not None:
            row["targetKey"] = target_key
            pending_targets.append((row, target_key))
        rows.append(row)
    if not rows:
        raise ValueError("Enemy AI source cannot be empty")
    for _, target in pending_targets:
        if target != "END" and target not in labels:
            raise ValueError(f"Enemy AI source branch target does not exist: {target}")
    return {"id": int(script_id), "name": name or SCRIPT_NAMES[int(script_id)],
            "instructions": rows, "source": source}


def parse_sources(sources: list[object]) -> list[dict]:
    """Parse the complete five-script source document."""
    if not isinstance(sources, list) or len(sources) != len(SCRIPT_NAMES):
        raise ValueError("Enemy AI source requires Init, Turn, Counter, Death, and Pre-hit")
    result = []
    for index, entry in enumerate(sources):
        if isinstance(entry, dict):
            if int(entry.get("id", -1)) != index:
                raise ValueError("Enemy AI source scripts must remain in their fixed order")
            source = entry.get("source")
        else:
            source = entry
        result.append(parse_script(source, index, SCRIPT_NAMES[index]))
    return result


def compile_sources(sources: list[object]) -> list[dict]:
    """Parse and compile all source blocks without writing a DAT file."""
    scripts = parse_sources(sources)
    for script in scripts:
        _compile_script(script)
    return scripts


def _section(raw: bytes) -> tuple[int, int]:
    if len(raw) < 16:
        raise ValueError("Enemy DAT header is too short for battle AI")
    section_count = int.from_bytes(raw[0:4], "little") + 1
    section_number = 2 if section_count == 3 else 8
    if section_count <= section_number:
        raise ValueError("Enemy DAT has no battle-script section")
    table_index = section_number - 1
    start = int.from_bytes(raw[4 + table_index * 4:8 + table_index * 4], "little")
    end = int.from_bytes(raw[8 + table_index * 4:12 + table_index * 4], "little")
    if start < 4 + section_count * 4 or end < start or end > len(raw):
        raise ValueError("Enemy DAT battle-script section is invalid")
    return start, end


def _operand_width(kind: str) -> int:
    return 4 if kind == "u32" else 2 if kind in {"value16", "jump16", "skip16"} else 1


def _control(kind: str, value: int) -> dict:
    result = {"type": kind, "value": value, "minimum": 0, "maximum": 255,
              "control": "number"}
    if kind == "u32":
        result["maximum"] = 0xFFFFFFFF
    elif kind == "value16":
        result["maximum"] = 0xFFFF
    elif kind == "jump16":
        result.update(minimum=-32768, maximum=32767)
    elif kind == "skip16":
        result.update(minimum=0, maximum=65535)
    elif kind == "bool":
        result.update(minimum=0, maximum=1, control="boolean")
    elif kind == "comparator":
        result.update(minimum=0, maximum=5, control="enum",
                      choices=[{"id": i, "name": name} for i, name in enumerate(COMPARATORS)])
    elif kind == "subject":
        result.update(minimum=0, maximum=255, control="enum",
                      choices=[{"id": key, "name": name} for key, name in SUBJECTS.items()])
    elif kind == "ability_line":
        # Vanilla also uses sentinel lines such as 253; keep the full stored
        # byte range instead of pretending only the 16 definition rows exist.
        result.update(minimum=0, maximum=255)
    elif kind == "local_var":
        result.update(minimum=0, maximum=255, control="enum", choices=[
            {"id": 96, "name": "Soldier local 96"},
            *[{"id": value, "name": f"Local {chr(65 + value - 220)}"}
              for value in range(220, 228)],
        ])
    return result


def instruction_template(opcode: int) -> dict:
    """Return a validated new instruction with neutral operand values."""
    definition = OPCODES.get(int(opcode))
    if definition is None:
        raise ValueError(f"Unsupported enemy AI opcode: {opcode}")
    name, types = definition
    operands = []
    for index, kind in enumerate(types):
        operand = _control(kind, 0)
        operand.update(index=index, size=_operand_width(kind))
        operands.append(operand)
    return {"opcode": int(opcode), "name": name, "operands": operands,
            "size": 1 + sum(_operand_width(kind) for kind in types),
            "editable": True}


def opcode_catalog() -> list[dict]:
    return [instruction_template(opcode) for opcode in sorted(OPCODES)]


def _decode_instruction(code: bytes, position: int, base: int) -> tuple[dict, int] | None:
    opcode = code[position]
    definition = OPCODES.get(opcode)
    if definition is None:
        return None
    name, types = definition
    width = sum(_operand_width(kind) for kind in types)
    end = position + 1 + width
    if end > len(code):
        return None
    operands = []
    cursor = position + 1
    for operand_index, kind in enumerate(types):
        size = _operand_width(kind)
        signed = kind == "jump16"
        value = int.from_bytes(code[cursor:cursor + size], "little", signed=signed)
        operand = _control(kind, value)
        operand.update(index=operand_index, offset=base + cursor, size=size)
        operands.append(operand)
        cursor += size
    row = {"offset": position, "label": f"L{position:04X}", "opcode": opcode,
           "name": name, "size": end - position, "raw": code[position:end].hex(" ").upper(),
           "operands": operands, "editable": True}
    branch = next((operand for operand in operands if operand["type"] in {"jump16", "skip16"}), None)
    if branch is not None:
        target = end + int(branch["value"])
        row["targetOffset"] = target
        row["targetLabel"] = f"L{target:04X}" if 0 <= target <= len(code) else "Outside section"
    return row, end


def read(raw: bytes) -> dict:
    section_start, section_end = _section(raw)
    if section_start == section_end:
        return {"scripts": [], "sectionOffset": section_start, "sectionSize": 0,
                "available": False}
    section = raw[section_start:section_end]
    if len(section) < 36:
        raise ValueError("Enemy DAT battle-script section is too short")
    subsection_count = int.from_bytes(section[0:4], "little")
    ai_offset = int.from_bytes(section[4:8], "little")
    text_offset = int.from_bytes(section[8:12], "little")
    text_data_offset = int.from_bytes(section[12:16], "little")
    if subsection_count != 3 or ai_offset < 16 or ai_offset + 20 > text_offset \
            or text_offset > text_data_offset or text_data_offset > len(section):
        raise ValueError("Enemy DAT battle-script header is unsupported")
    starts = [int.from_bytes(section[ai_offset + i * 4:ai_offset + i * 4 + 4], "little")
              for i in range(5)]
    limit = text_offset - ai_offset
    if starts != sorted(starts) or starts[0] < 20 or starts[-1] > limit:
        raise ValueError("Enemy DAT AI section offsets are invalid")
    scripts = []
    for index, relative_start in enumerate(starts):
        relative_end = starts[index + 1] if index < 4 else limit
        absolute = section_start + ai_offset + relative_start
        code = section[ai_offset + relative_start:ai_offset + relative_end]
        instructions = []
        position = 0
        while position < len(code):
            decoded = _decode_instruction(code, position, absolute)
            if decoded is None:
                instructions.append({"offset": position, "label": f"L{position:04X}",
                                     "name": "Unsupported raw tail", "opcode": code[position],
                                     "raw": code[position:].hex(" ").upper(), "operands": [],
                                     "editable": False})
                break
            instruction, position = decoded
            instructions.append(instruction)
        labels = {row["offset"] for row in instructions}
        for row in instructions:
            if "targetOffset" in row:
                row["targetValid"] = row["targetOffset"] in labels or row["targetOffset"] == len(code)
                if not row["targetValid"]:
                    row["targetLabel"] += " (unaligned)"
        for instruction_index, row in enumerate(instructions):
            row["key"] = f"s{index}-o{row['offset']:04X}"
            row["index"] = instruction_index
        by_offset = {row["offset"]: row for row in instructions}
        for row in instructions:
            if "targetOffset" in row and row.get("targetValid"):
                target = by_offset.get(row["targetOffset"])
                row["targetKey"] = target["key"] if target else "end"
        script = {"id": index, "name": SCRIPT_NAMES[index], "offset": absolute,
                  "size": len(code), "instructions": instructions}
        if all(row.get("editable", False) for row in instructions):
            script["source"] = format_script(script)
        else:
            script["source"] = None
        scripts.append(script)
    return {"scripts": scripts, "sectionOffset": section_start,
            "sectionSize": section_end - section_start, "available": True}


def apply_edits(raw: bytes, edits: list[dict]) -> tuple[bytes, int]:
    parsed = read(raw)
    lookup = {}
    for script in parsed["scripts"]:
        for instruction in script["instructions"]:
            if not instruction["editable"]:
                continue
            for operand in instruction["operands"]:
                lookup[(script["id"], instruction["offset"], operand["index"])] = operand
    result = bytearray(raw)
    seen = set()
    changed = 0
    for edit in edits:
        key = (int(edit["script"]), int(edit["offset"]), int(edit["operand"]))
        if key in seen or key not in lookup:
            raise ValueError(f"Invalid, unsupported, or duplicate enemy AI operand: {key}")
        seen.add(key)
        operand = lookup[key]
        value = int(edit["value"])
        if not int(operand["minimum"]) <= value <= int(operand["maximum"]):
            raise ValueError(f"Enemy AI {operand['type']} must be {operand['minimum']} to {operand['maximum']}")
        choices = operand.get("choices")
        if choices is not None and value not in {int(choice["id"]) for choice in choices}:
            raise ValueError(f"Enemy AI {operand['type']} value is not supported: {value}")
        size = int(operand["size"])
        encoded = value.to_bytes(size, "little", signed=operand["type"] == "jump16")
        start = int(operand["offset"])
        if result[start:start + size] != encoded:
            result[start:start + size] = encoded
            changed += 1
    if len(result) != len(raw):
        raise ValueError("Enemy AI edits cannot change the DAT size")
    return bytes(result), changed


def _validated_operand(kind: str, value: object) -> int:
    control = _control(kind, int(value))
    number = int(value)
    if not int(control["minimum"]) <= number <= int(control["maximum"]):
        raise ValueError(
            f"Enemy AI {kind} must be {control['minimum']} to {control['maximum']}")
    choices = control.get("choices")
    if choices is not None and number not in {int(choice["id"]) for choice in choices}:
        raise ValueError(f"Enemy AI {kind} value is not supported: {number}")
    return number


def _compile_script(script: dict) -> bytes:
    rows = list(script.get("instructions", []))
    if not rows:
        rows = [instruction_template(0)]
    prepared = []
    keys = set()
    cursor = 0
    for index, source in enumerate(rows):
        opcode = int(source["opcode"])
        definition = OPCODES.get(opcode)
        if definition is None:
            raise ValueError(f"Unsupported enemy AI opcode: {opcode}")
        name, types = definition
        values = list(source.get("operands", []))
        if len(values) != len(types):
            raise ValueError(f"Enemy AI {name} requires {len(types)} operands")
        key = str(source.get("key") or f"new-{index}")
        if key == "end" or key in keys:
            raise ValueError(f"Duplicate or reserved enemy AI instruction key: {key}")
        keys.add(key)
        size = 1 + sum(_operand_width(kind) for kind in types)
        prepared.append({"key": key, "opcode": opcode, "types": types,
                         "operands": values, "offset": cursor, "size": size,
                         "targetKey": source.get("targetKey")})
        cursor += size

    # Existing trailing Stops are preserved so an unchanged script is byte
    # identical and branch targets remain stable.  New/edited scripts still
    # receive the final Stop and four-byte padding required by Ifrit's writer.
    cursor = sum(row["size"] for row in prepared)
    if not prepared or prepared[-1]["opcode"] != 0:
        prepared.append({"key": "__final_stop", "opcode": 0, "types": (),
                         "operands": [], "offset": cursor, "size": 1,
                         "targetKey": None})
        cursor += 1
    while cursor % 4:
        prepared.append({"key": f"__padding_{cursor}", "opcode": 0, "types": (),
                         "operands": [], "offset": cursor, "size": 1,
                         "targetKey": None})
        cursor += 1

    offsets = {row["key"]: row["offset"] for row in prepared}
    result = bytearray()
    for row in prepared:
        result.append(row["opcode"])
        branch_used = False
        for kind, supplied in zip(row["types"], row["operands"]):
            value = supplied.get("value") if isinstance(supplied, dict) else supplied
            if kind in {"jump16", "skip16"} and row["targetKey"] is not None:
                if branch_used:
                    raise ValueError("An enemy AI instruction has multiple branch targets")
                target_key = str(row["targetKey"])
                target = cursor if target_key == "end" else offsets.get(target_key)
                if target is None:
                    raise ValueError(f"Unknown enemy AI branch target: {target_key}")
                value = target - (row["offset"] + row["size"])
                branch_used = True
            number = _validated_operand(kind, value)
            result.extend(number.to_bytes(_operand_width(kind), "little",
                                          signed=kind == "jump16"))
    return bytes(result)


def rebuild_scripts(raw: bytes, scripts: list[dict]) -> tuple[bytes, int]:
    """Recompile all five AI scripts and preserve every non-AI payload byte."""
    parsed = read(raw)
    if not parsed["available"] or len(parsed["scripts"]) != 5:
        raise ValueError("Enemy DAT has no supported battle-script section")
    if len(scripts) != 5 or [int(row.get("id", -1)) for row in scripts] != list(range(5)):
        raise ValueError("Enemy AI rebuild requires Init, Turn, Counter, Death, and Pre-hit")
    if any(not instruction.get("editable", True)
           for script in parsed["scripts"] for instruction in script["instructions"]):
        raise ValueError("Enemy AI containing an unsupported raw tail cannot be rebuilt")

    section_start, section_end = _section(raw)
    old_section = raw[section_start:section_end]
    ai_offset = int.from_bytes(old_section[4:8], "little")
    text_offset = int.from_bytes(old_section[8:12], "little")
    text_data_offset = int.from_bytes(old_section[12:16], "little")
    if ai_offset != 16:
        raise ValueError("Enemy AI subsection offset is unsupported")

    compiled = [_compile_script(script) for script in scripts]
    offset_cursor = 20
    offset_table = bytearray()
    code = bytearray()
    for block in compiled:
        offset_table.extend(offset_cursor.to_bytes(4, "little"))
        code.extend(block)
        offset_cursor += len(block)
    old_text_offsets = old_section[text_offset:text_data_offset]
    old_text_data = old_section[text_data_offset:]
    new_text_offset = 16 + len(offset_table) + len(code)
    new_text_data_offset = new_text_offset + len(old_text_offsets)
    new_section = bytearray()
    new_section.extend((3).to_bytes(4, "little"))
    new_section.extend((16).to_bytes(4, "little"))
    new_section.extend(new_text_offset.to_bytes(4, "little"))
    new_section.extend(new_text_data_offset.to_bytes(4, "little"))
    new_section.extend(offset_table)
    new_section.extend(code)
    new_section.extend(old_text_offsets)
    new_section.extend(old_text_data)
    if len(new_section) % 4:
        raise ValueError("Rebuilt enemy AI section is not four-byte aligned")

    delta = len(new_section) - len(old_section)
    result = bytearray(raw[:section_start])
    result.extend(new_section)
    result.extend(raw[section_end:])
    section_count = int.from_bytes(raw[0:4], "little") + 1
    for index in range(section_count):
        position = 4 + index * 4
        old_offset = int.from_bytes(raw[position:position + 4], "little")
        if old_offset >= section_end:
            result[position:position + 4] = (old_offset + delta).to_bytes(4, "little")

    reread = read(bytes(result))
    if len(reread["scripts"]) != 5 or any(
            not instruction.get("editable", False)
            for script in reread["scripts"] for instruction in script["instructions"]):
        raise ValueError("Rebuilt enemy AI did not decode completely")
    return bytes(result), int(bytes(result) != raw)

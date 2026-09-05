"""Strict structural reader and source compiler for FF8 PC field JSM files.

The file table follows Deling ``JsmFile::open`` and ``JsmFile::save``.  Each
stored instruction is one little-endian u32.  Deling proves direct parameters
for opcode IDs 1 through 0x38 and relative branches for JMP/JPF/GJMP.  Other
known opcodes consume their operands from the script stack and have no direct
parameter.  This module keeps group and method counts fixed, rebuilds method
positions and relative branches, and rejects all unknown structures.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct


_SCHEMA = json.loads((Path(__file__).parent / "schema/jsm_opcodes.json").read_text(
    encoding="utf-8"))
OPCODE_NAMES: tuple[str, ...] = tuple(_SCHEMA["names"])
if len(OPCODE_NAMES) != 376 or len(set(OPCODE_NAMES)) != 376:
    raise RuntimeError("The Deling JSM opcode table is incomplete or ambiguous")
OPCODE_IDS = {name: opcode for opcode, name in enumerate(OPCODE_NAMES)}
BRANCH_IDS = {OPCODE_IDS[name] for name in ("JMP", "JPF", "GJMP")}
DIRECT_PARAM_MIN = 1
DIRECT_PARAM_MAX = 0x38
SIGNED24_MIN = -(1 << 23)
SIGNED24_MAX = (1 << 23) - 1
_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _signed24(value: int) -> int:
    value &= 0xFFFFFF
    return value - 0x1000000 if value & 0x800000 else value


def _decode_word(word: int) -> tuple[int, int | None]:
    if word & 0xFF000000:
        return word >> 24, _signed24(word)
    return word, None


def _group_intervals(words: list[int], old: bool) -> list[tuple[int, int]] | None:
    intervals = []
    for word in words:
        label, count = ((word & 0xFF), (word >> 8)) if old else (
            (word >> 7), (word & 0x7F))
        intervals.append((label, count + 1))
    ordered = sorted(intervals)
    cursor = 0
    for label, count in ordered:
        if label != cursor or count < 1:
            return None
        cursor += count
    return intervals


def _sym_names(sym: bytes, header: dict, groups: list[dict], method_count: int) -> list[str]:
    lines = [line.strip() for line in sym.decode("ascii", errors="replace").splitlines()
             if line.strip()]
    entity_count = header["lines"] + header["backgrounds"] + header["others"]
    method_lines = lines[entity_count:]
    if len(method_lines) != method_count:
        return [f"Script {index}" for index in range(method_count)]
    names = [f"Script {index}" for index in range(method_count)]
    for group in sorted(groups, key=lambda value: value["firstMethod"]):
        for local_id in range(group["methodCount"]):
            method_id = group["firstMethod"] + local_id
            names[method_id] = method_lines[method_id]
    return names


def _source(words: list[int]) -> tuple[str, bool]:
    targets: set[int] = set()
    editable = True
    decoded = [_decode_word(word) for word in words]
    for index, (opcode, parameter) in enumerate(decoded):
        if opcode >= len(OPCODE_NAMES):
            editable = False
        if opcode in BRANCH_IDS:
            if parameter is None or not 0 <= index + parameter < len(words):
                editable = False
            else:
                targets.add(index + parameter)
    labels = {target: f"TARGET_{number}" for number, target in enumerate(sorted(targets))}
    lines = []
    for index, (opcode, parameter) in enumerate(decoded):
        if index in labels:
            lines.append(labels[index] + ":")
        if opcode >= len(OPCODE_NAMES):
            lines.append(f"RAW_LOCKED 0x{words[index]:08X}")
            continue
        name = OPCODE_NAMES[opcode]
        if parameter is None:
            lines.append(name)
        elif opcode in BRANCH_IDS and index + parameter in labels:
            lines.append(f"{name} {labels[index + parameter]}")
        else:
            lines.append(f"{name} {parameter}")
    return "\n".join(lines), editable


def read(raw: bytes, sym: bytes = b"") -> dict:
    if len(raw) < 8:
        raise ValueError("Field JSM is shorter than its header")
    doors, lines, backgrounds, others, positions_offset, data_offset = struct.unpack_from(
        "<BBBBHH", raw, 0)
    if positions_offset < 8 or (positions_offset - 8) % 2:
        raise ValueError("Field JSM group table has an unexpected extent")
    group_count = (positions_offset - 8) // 2
    counts = [doors, lines, backgrounds, others]
    if sum(counts) != group_count:
        # Deling's proved recovery for shipped maps with a corrupt high count:
        # only values above 48 are discarded, then the total must match.
        counts = [0 if value > 48 else value for value in counts]
        if sum(counts) != group_count:
            raise ValueError("Field JSM header counts do not match its group table")
        doors, lines, backgrounds, others = counts
    if not positions_offset <= data_offset <= len(raw) or data_offset % 4:
        raise ValueError("Field JSM method-position section is invalid")
    group_words = list(struct.unpack_from(f"<{group_count}H", raw, 8)) if group_count else []
    new_intervals = _group_intervals(group_words, False)
    old_intervals = _group_intervals(group_words, True)
    if new_intervals is not None:
        intervals, old_format = new_intervals, False
    elif old_intervals is not None:
        intervals, old_format = old_intervals, True
    else:
        raise ValueError("Field JSM groups do not form one contiguous method table")
    method_count = sum(count for _, count in intervals)
    needed_position_bytes = (method_count + 1) * 2
    if data_offset - positions_offset < needed_position_bytes:
        raise ValueError("Field JSM method-position table is truncated")
    position_words = list(struct.unpack_from(
        f"<{method_count + 1}H", raw, positions_offset))
    padding = raw[positions_offset + needed_position_bytes:data_offset]
    if len(padding) > 3 or any(padding):
        raise ValueError("Field JSM has unsupported method-position padding")
    positions = [word & 0x7FFF for word in position_words]
    if positions != sorted(positions) or positions[0] != 0:
        raise ValueError("Field JSM method positions are not monotonic from zero")
    if len(raw) - data_offset != positions[-1] * 4:
        raise ValueError("Field JSM final method position does not match its data size")
    header = {"doors": doors, "lines": lines, "backgrounds": backgrounds,
              "others": others, "positionsOffset": positions_offset,
              "dataOffset": data_offset, "oldFormat": old_format}
    type_bounds = (("location", lines), ("door", doors),
                   ("background", backgrounds), ("other", others))
    groups = []
    group_id = 0
    for group_type, count in type_bounds:
        for _ in range(count):
            first, method_total = intervals[group_id]
            groups.append({"id": group_id, "type": group_type,
                           "firstMethod": first, "methodCount": method_total})
            group_id += 1
    names = _sym_names(sym, header, groups, method_count)
    methods = []
    for method_id in range(method_count):
        start, end = positions[method_id], positions[method_id + 1]
        words = list(struct.unpack_from(
            f"<{end - start}I", raw, data_offset + start * 4)) if end > start else []
        if not words:
            raise ValueError("Field JSM contains an empty method")
        source, editable = _source(words)
        opcode, parameter = _decode_word(words[0])
        if opcode != OPCODE_IDS["LBL"] or parameter is None:
            raise ValueError("Field JSM method does not start with LBL")
        group = next((value for value in groups
                      if value["firstMethod"] <= method_id <
                      value["firstMethod"] + value["methodCount"]), None)
        if group is None:
            raise ValueError("Field JSM method has no owning group")
        methods.append({"id": method_id, "name": names[method_id],
                        "groupId": group["id"], "groupType": group["type"],
                        "localId": method_id - group["firstMethod"],
                        "labelId": parameter,
                        "flagged": bool(position_words[method_id] & 0x8000),
                        "source": source, "editable": editable,
                        "instructionCount": len(words),
                        "raw": raw[data_offset + start * 4:data_offset + end * 4].hex()})
    return {"header": header, "groups": groups, "methods": methods,
            "opcodeCount": len(OPCODE_NAMES)}


def compile_source(source: str, method_id: int, label_id: int | None = None) -> list[int]:
    labels: dict[str, int] = {}
    instructions: list[tuple[int, str | int | None, int]] = []
    for line_number, original in enumerate(source.splitlines(), 1):
        line = original.strip()
        if not line:
            continue
        if line.endswith(":"):
            label = line[:-1].strip()
            if not _LABEL.fullmatch(label) or label in labels:
                raise ValueError(f"Invalid or duplicate JSM label on line {line_number}")
            labels[label] = len(instructions)
            continue
        parts = line.split()
        name = parts[0].upper()
        if name == "RAW_LOCKED":
            raise ValueError("Unknown JSM opcodes are read-only")
        opcode = OPCODE_IDS.get(name)
        if opcode is None or len(parts) not in (1, 2):
            raise ValueError(f"Invalid JSM instruction on line {line_number}")
        argument: str | int | None = None
        if len(parts) == 2:
            if not DIRECT_PARAM_MIN <= opcode <= DIRECT_PARAM_MAX:
                raise ValueError(f"{name} cannot have a direct parameter")
            if opcode in BRANCH_IDS and _LABEL.fullmatch(parts[1]):
                argument = parts[1]
            else:
                try:
                    argument = int(parts[1], 0)
                except ValueError as error:
                    raise ValueError(f"Invalid JSM parameter on line {line_number}") from error
                if not SIGNED24_MIN <= argument <= SIGNED24_MAX:
                    raise ValueError(f"JSM parameter on line {line_number} exceeds signed 24-bit range")
        instructions.append((opcode, argument, line_number))
    if not instructions:
        raise ValueError("A field JSM method cannot be empty")
    first_opcode, first_argument, _ = instructions[0]
    expected_label = method_id if label_id is None else label_id
    if first_opcode != OPCODE_IDS["LBL"] or first_argument != expected_label:
        raise ValueError(f"Field JSM method {method_id} must retain its leading LBL {expected_label}")
    words = []
    for index, (opcode, argument, line_number) in enumerate(instructions):
        if isinstance(argument, str):
            if argument not in labels:
                raise ValueError(f"Undefined JSM label {argument!r} on line {line_number}")
            argument = labels[argument] - index
            if not SIGNED24_MIN <= argument <= SIGNED24_MAX:
                raise ValueError("JSM branch exceeds signed 24-bit range")
        if argument is None:
            words.append(opcode)
        else:
            words.append((opcode << 24) | (argument & 0xFFFFFF))
    for index, word in enumerate(words):
        opcode, parameter = _decode_word(word)
        if opcode in BRANCH_IDS and (parameter is None or
                                     not 0 <= index + parameter < len(words)):
            raise ValueError("Field JSM branch target is outside its method")
    return words


def rebuild(raw: bytes, sym: bytes, documents: list[dict]) -> tuple[bytes, int]:
    parsed = read(raw, sym)
    by_id = {method["id"]: method for method in parsed["methods"]}
    replacements: dict[int, str] = {}
    for document in documents:
        method_id = int(document.get("id", -1))
        if method_id in replacements or method_id not in by_id:
            raise ValueError("Invalid or duplicate field JSM method document")
        if not by_id[method_id]["editable"]:
            raise ValueError("This field JSM method contains an unsupported instruction")
        replacements[method_id] = str(document.get("source", ""))
    compiled = []
    changed = 0
    for method in parsed["methods"]:
        source = replacements.get(method["id"], method["source"])
        if method["editable"]:
            words = compile_source(source, method["id"], method["labelId"])
            compiled.append(struct.pack(f"<{len(words)}I", *words))
        else:
            compiled.append(bytes.fromhex(method["raw"]))
        if source != method["source"]:
            changed += 1
    if not changed:
        # Compiling every method above is an identity contract, not a shortcut.
        identity = _assemble(raw, parsed, compiled)
        if identity != raw:
            raise ValueError("Field JSM identity rebuild changed bytes")
        return raw, 0
    rebuilt = _assemble(raw, parsed, compiled)
    read(rebuilt, sym)
    return rebuilt, changed


def _assemble(raw: bytes, parsed: dict, methods: list[bytes]) -> bytes:
    header = parsed["header"]
    positions = []
    cursor = 0
    for method, encoded in zip(parsed["methods"], methods):
        if cursor > 0x7FFF:
            raise ValueError("Field JSM method data exceeds its 15-bit position range")
        positions.append(cursor | (0x8000 if method["flagged"] else 0))
        cursor += len(encoded) // 4
    if cursor > 0x7FFF:
        raise ValueError("Field JSM method data exceeds its 15-bit position range")
    position_words = positions + [cursor]
    position_raw = struct.pack(f"<{len(position_words)}H", *position_words)
    padding_size = header["dataOffset"] - header["positionsOffset"] - len(position_raw)
    if not 0 <= padding_size <= 3:
        raise ValueError("Field JSM method-position padding cannot be preserved")
    prefix = raw[:header["positionsOffset"]]
    return prefix + position_raw + bytes(padding_size) + b"".join(methods)

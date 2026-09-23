"""Derived RDR1 input remaps built from the installed PC content archive.

This module never stores Rockstar scripts in the repository.  It works on decoded
WSC bytecode produced by the existing MagicRDR bridge, rewrites only structurally
proven input-action string operands, relocates the bytecode references affected by
the longer string, then hands the result back to the encrypted type-2 resource
packer and the existing update-folder archive transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import paths, script_features


CONTENT_ARCHIVE_RELATIVE = Path("game") / "content.rpf"
CONTENT_OVERRIDE_ROOT = paths.MOD_ROOT / "content"
STATE_FILE = script_features.STATE_FILE

PASS_CAMP_TRAVEL = b"PASS_CAMP_Travel"
CAMP_OLD_ACTIONS = (b"@UI.ACCEPT", b"@UI.CANCELMINIGAME")
CAMP_NEW_ACTION = b"@GENERIC.ZOOM_RADAR"  # INPUT_GENERIC_ZOOM_RADAR: T on stock PC binds.
CUTSCENE_OLD_ACTION = b"@UI.ACCEPT"
CUTSCENE_NEW_ACTION = b"@GENERIC.USE"     # INPUT_GENERIC_USE: E on stock PC binds.

ADD_SCRIPT_USE_CONTEXT_HASH = 0xD7591B0E
IS_DIGITAL_ACTION_PRESSED_HASH = 0xDA674AE0
CUTSCENE_STOP_HASH = 0x9E6CAD1D
CUTSCENE_MARKERS = (b"Cutscenes_Paused", b"LoadingScreen", b"PauseScene")

OP_ENTER = 45
OP_CALL_MIN = 82
OP_CALL_MAX = 97
OP_JUMP_MIN = 98
OP_JUMP_MAX = 105
OP_SWITCH = 110
OP_PUSH_STRING = 111
OP_PCALL = 121


@dataclass(frozen=True)
class Instruction:
    offset: int
    opcode: int
    length: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _instructions(code: bytes | bytearray) -> list[Instruction]:
    result: list[Instruction] = []
    offset = 0
    while offset < len(code):
        length = script_features._instruction_length(code, offset)
        if length <= 0 or offset + length > len(code):
            raise ValueError(f"Invalid WSC instruction length at 0x{offset:X}")
        result.append(Instruction(offset, code[offset], length))
        offset += length
    if offset != len(code):
        raise ValueError("WSC instruction stream did not end at CodeLength")
    return result


def _push_string(code: bytes | bytearray, instruction: Instruction) -> bytes | None:
    if instruction.opcode != OP_PUSH_STRING:
        return None
    length = code[instruction.offset + 1]
    if instruction.length != length + 2:
        raise ValueError("Malformed WSC PushString instruction")
    return bytes(code[instruction.offset + 2:instruction.offset + 2 + length])


def _native_hash(layout: dict, code: bytes | bytearray, instruction: Instruction) -> int | None:
    if instruction.opcode != script_features.OP_NATIVE:
        return None
    index = script_features._native_index(code, instruction.offset)
    if index >= len(layout["natives"]):
        raise ValueError(f"Native index {index} is outside the WSC native table")
    return layout["natives"][index]


def _function_ranges(code: bytes | bytearray, instructions: list[Instruction]) -> list[tuple[int, int]]:
    starts = [item.offset for item in instructions if item.opcode == OP_ENTER]
    if not starts or starts[0] != 0:
        raise ValueError("WSC code does not begin with the main Enter instruction")
    return [(start, starts[index + 1] if index + 1 < len(starts) else len(code))
            for index, start in enumerate(starts)]


def _integer_push_values(code: bytes | bytearray, item: Instruction) -> list[int] | None:
    off, op = item.offset, item.opcode
    if op == 37:
        return [code[off + 1]]
    if op == 38:
        return [code[off + 1], code[off + 2]]
    if op == 39:
        return [code[off + 1], code[off + 2], code[off + 3]]
    if op == 40:
        return [struct.unpack_from(">i", bytes(code), off + 1)[0]]
    if op == 65:
        return [struct.unpack_from(">h", bytes(code), off + 1)[0]]
    if op == 109:
        value = (code[off + 1] << 16) | (code[off + 2] << 8) | code[off + 3]
        if value & 0x800000:
            value -= 0x1000000
        return [value]
    if 138 <= op <= 146:
        return [op - 139]
    return None


def _action_feeds_native(layout: dict, code: bytes | bytearray,
                         instructions: list[Instruction], index: int,
                         native_hash: int, wanted_args: list[int]) -> bool:
    values: list[int] = []
    cursor = index + 1
    while cursor < len(instructions) and len(values) <= len(wanted_args):
        item = instructions[cursor]
        pushed = _integer_push_values(code, item)
        if pushed is not None:
            values.extend(pushed)
            cursor += 1
            continue
        if item.opcode == script_features.OP_NATIVE:
            return values == wanted_args and _native_hash(layout, code, item) == native_hash
        return False
    return False


def _map_target(position: int, *, old_end: int, delta: int,
                boundaries: set[int], functions: set[int], code_length: int) -> int:
    """Relocate a code address, accepting Rockstar's occasional function-2 call form."""
    if position == code_length or position in boundaries:
        return position + delta if position >= old_end else position
    if position + 2 in functions:
        moved = position + 2 + (delta if position + 2 >= old_end else 0)
        return moved - 2
    raise ValueError(f"WSC control-flow target 0x{position:X} is not an instruction boundary")


def _pointer_push(code: bytes | bytearray, item: Instruction) -> tuple[int, str] | None:
    off, op = item.offset, item.opcode
    if op == 37:
        return code[off + 1], "u8"
    if op == 40:
        return struct.unpack_from(">I", bytes(code), off + 1)[0], "u32"
    if op == 65:
        return struct.unpack_from(">H", bytes(code), off + 1)[0], "u16"
    if op == 109:
        return ((code[off + 1] << 16) | (code[off + 2] << 8) | code[off + 3]), "u24"
    return None


def _write_pointer_push(code: bytearray, offset: int, kind: str, value: int) -> None:
    if kind == "u8":
        if not 0 <= value <= 0xFF:
            raise ValueError("Relocated WSC function pointer no longer fits PushB1")
        code[offset + 1] = value
    elif kind == "u16":
        if not 0 <= value <= 0xFFFF:
            raise ValueError("Relocated WSC function pointer no longer fits PushShort")
        struct.pack_into(">H", code, offset + 1, value)
    elif kind == "u24":
        if not 0 <= value <= 0xFFFFFF:
            raise ValueError("Relocated WSC function pointer no longer fits PushI24")
        code[offset + 1:offset + 4] = value.to_bytes(3, "big")
    elif kind == "u32":
        struct.pack_into(">I", code, offset + 1, value)
    else:
        raise ValueError(f"Unsupported WSC pointer push kind: {kind}")


def _relocate_push_string(raw: bytes, object_start: int, string_offset: int,
                          expected: bytes, replacement: bytes) -> tuple[bytes, dict]:
    """Replace one PushString and relocate every encoded control-flow/code pointer.

    Growth is allowed only inside the existing final code page and only over zero
    padding.  No resource allocation/pointer table is moved.  Direct calls,
    relative jumps, switch targets and compiler-emitted function-pointer integer
    literals are adjusted.  Any unfamiliar target/width fails closed.
    """
    if len(replacement) > 255:
        raise ValueError("Replacement WSC action string is too long")
    layout = script_features._script_layout(raw, object_start)
    old_code = bytes(layout["code"])
    old_instructions = _instructions(old_code)
    by_offset = {item.offset: item for item in old_instructions}
    target = by_offset.get(string_offset)
    if target is None or target.opcode != OP_PUSH_STRING or _push_string(old_code, target) != expected:
        raise ValueError(f"Expected {expected!r} PushString at 0x{string_offset:X}")
    old_end = target.offset + target.length
    delta = len(replacement) - len(expected)
    if delta <= 0:
        raise ValueError("This relocator is reserved for the audited growing input remaps")
    new_length = len(old_code) + delta
    if (new_length + 0x3FFF) >> 14 != len(layout["pages"]):
        raise ValueError("Input remap would require allocating another WSC code page")

    # The extra logical bytes must consume real zero padding in the already-owned
    # code page, never bytes belonging to another object.
    growth_positions = [script_features._raw_code_offset(layout["pages"], len(old_code) + i)
                        for i in range(delta)]
    for position in growth_positions:
        if position >= len(raw) or raw[position] != 0:
            raise ValueError("WSC code page has no verified zero padding for the longer action string")

    new_code = bytearray(old_code[:target.offset])
    new_code.extend((OP_PUSH_STRING, len(replacement)))
    new_code.extend(replacement)
    new_code.extend(old_code[old_end:])
    if len(new_code) != new_length:
        raise RuntimeError("WSC string relocation produced the wrong CodeLength")

    boundaries = {item.offset for item in old_instructions}
    boundaries.add(len(old_code))
    functions = {item.offset for item in old_instructions if item.opcode == OP_ENTER}

    def moved(position: int) -> int:
        return position + delta if position >= old_end else position

    # Relocate control flow from the original instruction stream into the rebuilt one.
    for item in old_instructions:
        if item.offset == target.offset:
            continue
        new_off = moved(item.offset)
        op = item.opcode
        if OP_CALL_MIN <= op <= OP_CALL_MAX:
            low = struct.unpack_from(">H", old_code, item.offset + 1)[0]
            old_target = ((op - OP_CALL_MIN) << 16) | low
            new_target = _map_target(old_target, old_end=old_end, delta=delta,
                                     boundaries=boundaries, functions=functions,
                                     code_length=len(old_code))
            if not 0 <= new_target <= 0xFFFFF:
                raise ValueError("Relocated WSC call target exceeds Call2 encoding")
            new_code[new_off] = OP_CALL_MIN + (new_target >> 16)
            struct.pack_into(">H", new_code, new_off + 1, new_target & 0xFFFF)
        elif OP_JUMP_MIN <= op <= OP_JUMP_MAX:
            relative = struct.unpack_from(">h", old_code, item.offset + 1)[0]
            old_target = item.offset + 3 + relative
            new_target = _map_target(old_target, old_end=old_end, delta=delta,
                                     boundaries=boundaries, functions=functions,
                                     code_length=len(old_code))
            new_relative = new_target - (new_off + 3)
            if not -0x8000 <= new_relative <= 0x7FFF:
                raise ValueError("Relocated WSC jump exceeds signed 16-bit range")
            struct.pack_into(">h", new_code, new_off + 1, new_relative)
        elif op == OP_SWITCH:
            count = old_code[item.offset + 1]
            for case in range(count):
                relative_at = item.offset + 6 + case * 6
                relative = struct.unpack_from(">h", old_code, relative_at)[0]
                old_base = item.offset + 8 + case * 6
                old_target = old_base + relative
                new_target = _map_target(old_target, old_end=old_end, delta=delta,
                                         boundaries=boundaries, functions=functions,
                                         code_length=len(old_code))
                new_base = new_off + 8 + case * 6
                new_relative = new_target - new_base
                if not -0x8000 <= new_relative <= 0x7FFF:
                    raise ValueError("Relocated WSC switch target exceeds signed 16-bit range")
                struct.pack_into(">h", new_code, new_off + 6 + case * 6, new_relative)

        pointer = _pointer_push(old_code, item)
        if pointer is not None:
            value, kind = pointer
            if value in functions or value + 2 in functions:
                new_value = _map_target(value, old_end=old_end, delta=delta,
                                        boundaries=boundaries, functions=functions,
                                        code_length=len(old_code))
                _write_pointer_push(new_code, new_off, kind, new_value)

    # A complete parse is a cheap guard against a length/operand mistake before raw writeback.
    new_instructions = _instructions(new_code)
    old_functions = sorted(functions)
    new_functions = sorted(item.offset for item in new_instructions if item.opcode == OP_ENTER)
    expected_functions = sorted(moved(offset) for offset in old_functions)
    if new_functions != expected_functions:
        raise RuntimeError("WSC function entry points did not relocate as expected")

    patched = bytearray(raw)
    struct.pack_into("<I", patched, object_start + 12, new_length)
    for page_index, page in enumerate(layout["pages"]):
        start = page_index * 0x4000
        block = bytes(new_code[start:min(start + 0x4000, new_length)])
        if page + len(block) > len(patched):
            raise ValueError("Relocated WSC code exceeds its backing resource page")
        patched[page:page + len(block)] = block

    check = script_features._script_layout(bytes(patched), object_start)
    if bytes(check["code"]) != bytes(new_code):
        raise RuntimeError("Relocated WSC code did not read back byte-for-byte")
    if check["natives"] != layout["natives"]:
        raise RuntimeError("Input remap unexpectedly changed the WSC native table")
    return bytes(patched), {
        "offset": string_offset,
        "old": expected.decode("ascii"),
        "new": replacement.decode("ascii"),
        "delta": delta,
        "oldCodeLength": len(old_code),
        "newCodeLength": new_length,
        "functionsRelocated": sum(1 for value in old_functions if value >= old_end),
    }


def _find_camp_candidates(raw: bytes, object_start: int) -> list[tuple[int, bytes]]:
    layout = script_features._script_layout(raw, object_start)
    code = layout["code"]
    instructions = _instructions(code)
    ranges = _function_ranges(code, instructions)
    candidates: list[tuple[int, bytes]] = []
    for start, end in ranges:
        items = [item for item in instructions if start <= item.offset < end]
        labels = [index for index, item in enumerate(items)
                  if _push_string(code, item) == PASS_CAMP_TRAVEL]
        if not labels:
            continue
        for label_index in labels:
            for action_index in range(label_index + 1, min(label_index + 20, len(items))):
                action = _push_string(code, items[action_index])
                if action not in CAMP_OLD_ACTIONS:
                    continue
                # ADD_SCRIPT_USE_CONTEXT follows this argument list directly. There
                # must be no other native call between the context label and it.
                native = None
                for probe in range(action_index + 1, min(action_index + 20, len(items))):
                    if items[probe].opcode == script_features.OP_NATIVE:
                        native = items[probe]
                        break
                if native is None or _native_hash(layout, code, native) != ADD_SCRIPT_USE_CONTEXT_HASH:
                    continue
                if any(item.opcode == script_features.OP_NATIVE
                       for item in items[label_index + 1:action_index]):
                    continue
                candidates.append((items[action_index].offset, action))
    return candidates


def patch_camp_travel(raw: bytes, object_start: int) -> tuple[bytes, list[dict]]:
    reports: list[dict] = []
    working = raw
    while True:
        candidates = _find_camp_candidates(working, object_start)
        if not candidates:
            break
        # Work from the highest offset so another candidate below it keeps its address.
        offset, old = max(candidates, key=lambda value: value[0])
        working, report = _relocate_push_string(
            working, object_start, offset, old, CAMP_NEW_ACTION)
        reports.append({"kind": "campTravel", **report})
        if len(reports) > 8:
            raise ValueError("Unexpected number of PASS_CAMP_Travel contexts")
    return working, reports


def _cutscene_candidates(raw: bytes, object_start: int) -> list[int]:
    layout = script_features._script_layout(raw, object_start)
    code = layout["code"]
    instructions = _instructions(code)
    ranges = _function_ranges(code, instructions)
    result: list[int] = []
    for start, end in ranges:
        items = [item for item in instructions if start <= item.offset < end]
        strings = {_push_string(code, item) for item in items if item.opcode == OP_PUSH_STRING}
        if not all(marker in strings for marker in CUTSCENE_MARKERS):
            continue
        native_hashes = {_native_hash(layout, code, item) for item in items
                         if item.opcode == script_features.OP_NATIVE}
        if CUTSCENE_STOP_HASH not in native_hashes or IS_DIGITAL_ACTION_PRESSED_HASH not in native_hashes:
            continue
        for index, item in enumerate(items):
            if _push_string(code, item) != CUTSCENE_OLD_ACTION:
                continue
            # The stock helper is IS_DIGITAL_ACTION_PRESSED(action, true, 0).
            if _action_feeds_native(layout, code, items, index,
                                    IS_DIGITAL_ACTION_PRESSED_HASH, [1, 0]):
                result.append(item.offset)
    return result


def patch_cutscene_skip(raw: bytes, object_start: int) -> tuple[bytes, list[dict]]:
    reports: list[dict] = []
    working = raw
    while True:
        candidates = _cutscene_candidates(working, object_start)
        if not candidates:
            break
        offset = max(candidates)
        working, report = _relocate_push_string(
            working, object_start, offset, CUTSCENE_OLD_ACTION, CUTSCENE_NEW_ACTION)
        reports.append({"kind": "cutsceneSkip", **report})
        if len(reports) > 16:
            raise ValueError("Unexpected number of cutscene Skip helpers in one WSC")
    return working, reports


def _source_record(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path.resolve()), "size": stat.st_size, "mtimeNs": stat.st_mtime_ns}


def _owned_entries(feature: dict | None) -> dict[str, dict]:
    if not isinstance(feature, dict) or not isinstance(feature.get("entries"), dict):
        return {}
    return feature["entries"]


def _write_generated(target: Path, payload: bytes, old_entry: dict | None) -> bool:
    if target.is_file():
        current = _sha256_file(target)
        if not old_entry or old_entry.get("generatedSha256") != current:
            raise RuntimeError(f"Refusing to overwrite an unowned project script override: {target}")
    digest = hashlib.sha256(payload).hexdigest()
    changed = not target.is_file() or _sha256_file(target) != digest
    if changed:
        script_features._atomic_bytes(target, payload)
    if not target.is_file() or _sha256_file(target) != digest:
        raise RuntimeError(f"Generated input-remap script did not read back exactly: {target}")
    return changed


def prepare_input_remaps(
        game_root: Path = paths.GAME_ROOT,
        tool: Path = paths.RPF6_TOOL,
        override_root: Path = CONTENT_OVERRIDE_ROOT,
        state_file: Path = STATE_FILE) -> dict:
    """Generate the camp-Travel and cutscene-Skip WSC overrides from installed data."""
    archive = (Path(game_root) / CONTENT_ARCHIVE_RELATIVE).resolve()
    tool = Path(tool).resolve()
    override_root = Path(override_root).resolve()
    state_file = Path(state_file).resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Installed RDR content archive was not found: {archive}")
    if not tool.is_file():
        raise FileNotFoundError(f"RPF6 bridge was not found: {tool}")

    state = script_features._load_state(state_file)
    previous_feature = state["features"].get("inputRemaps")
    previous = _owned_entries(previous_feature)
    source_record = _source_record(archive)
    if isinstance(previous_feature, dict) and previous_feature.get("source") == source_record and previous:
        exact = True
        for entry in previous.values():
            target = Path(entry.get("target", ""))
            if not target.is_file() or _sha256_file(target) != entry.get("generatedSha256"):
                exact = False
                break
        if exact:
            return {"prepared": True, "changed": 0, "cached": True,
                    "campContexts": previous_feature.get("campContexts", 0),
                    "cutsceneScripts": previous_feature.get("cutsceneScripts", 0),
                    "entries": previous}

    requested: dict[str, dict] = {}
    camp_contexts = 0
    cutscene_scripts = 0
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-input-remaps-") as temporary:
        root = Path(temporary)
        packed_root = root / "packed"
        decoded_root = root / "decoded"
        # Two archive passes keep all candidate discovery inside one MagicRDR process
        # each; we do not spawn one process per WSC while scanning the game.
        script_features._run_tool(tool, "extract", archive, packed_root, "**/*.wsc", timeout=900)
        script_features._run_tool(tool, "unpack", archive, decoded_root, "**/*.wsc", timeout=900)
        decoded_files = sorted(path for path in decoded_root.rglob("*.wsc") if path.is_file())
        if not decoded_files:
            raise RuntimeError("RPF6 unpack returned no PC WSC scripts")

        for decoded in decoded_files:
            relative = decoded.relative_to(decoded_root)
            template = packed_root / relative
            if not template.is_file():
                raise RuntimeError(f"Packed WSC template is missing for {relative.as_posix()}")
            packed = template.read_bytes()
            object_start = script_features._object_start_from_rsc85(packed)
            source_raw = decoded.read_bytes()
            working, camp = patch_camp_travel(source_raw, object_start)
            working, cutscene = patch_cutscene_skip(working, object_start)
            if not camp and not cutscene:
                continue
            camp_contexts += len(camp)
            if cutscene:
                cutscene_scripts += 1
            decoded.write_bytes(working)
            candidate = root / "repacked" / relative
            candidate.parent.mkdir(parents=True, exist_ok=True)
            script_features._run_tool(tool, "resource-pack", template, decoded, candidate)
            verified = root / "verified" / relative
            verified.parent.mkdir(parents=True, exist_ok=True)
            script_features._run_tool(tool, "resource-unpack", candidate, verified)
            if verified.read_bytes() != working:
                raise RuntimeError(f"Repacked input-remap WSC did not verify: {relative.as_posix()}")
            payload = candidate.read_bytes()
            archive_path = "root/" + relative.as_posix()
            target = override_root / relative
            old_entry = previous.get(archive_path)
            changed = _write_generated(target, payload, old_entry)
            requested[archive_path] = {
                "archivePath": archive_path,
                "sourceSha256": hashlib.sha256(packed).hexdigest(),
                "generatedSha256": hashlib.sha256(payload).hexdigest(),
                "target": str(target),
                "changed": bool(changed),
                "patches": [*camp, *cutscene],
            }

    # PC evidence contains PASS_CAMP_Travel in player.wsc and the Undead sleep
    # script, plus many cutscene helpers. Treat absence as source drift, not success.
    if camp_contexts < 1:
        raise RuntimeError("No structurally verified PASS_CAMP_Travel action was found")
    if cutscene_scripts < 1:
        raise RuntimeError("No structurally verified cutscene Skip helper was found")

    # Remove only stale files which this feature still proves it owns.
    for archive_path, old in previous.items():
        if archive_path in requested:
            continue
        target = Path(old.get("target", ""))
        if target.is_file():
            if _sha256_file(target) != old.get("generatedSha256"):
                raise RuntimeError(f"Stale input-remap override changed outside Lexeditor: {target}")
            target.unlink()

    feature_state = {
        "source": source_record,
        "campContexts": camp_contexts,
        "cutsceneScripts": cutscene_scripts,
        "entries": requested,
    }
    state["features"]["inputRemaps"] = feature_state
    script_features._atomic_bytes(
        state_file, (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return {"prepared": True, "changed": sum(int(row["changed"]) for row in requested.values()),
            "cached": False, **feature_state}

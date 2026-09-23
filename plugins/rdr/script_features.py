"""Derived RDR1 script overrides built from the user's installed content.rpf.

The installed archive is read-only.  Lexeditor extracts the exact PC WSC, patches
one audited bytecode branch without relocating code, repacks it, verifies it, and
places the generated resource in the normal project content override tree.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

from . import paths


CONTENT_ARCHIVE_RELATIVE = Path("game") / "content.rpf"
CONTENT_OVERRIDE_ROOT = paths.MOD_ROOT / "content"
STATE_FILE = paths.PROJECT_ROOT / ".lexeditor-generated" / "rdr-script-features.json"
COACH_SCRIPT_NAME = "passenger_coach.wsc"
COACH_FUNCTION_OFFSET = 0x1DC8
WAS_CONTEXT_EVER_PRESSED_HASH = 0x971559CA
OP_NATIVE = 44
OP_POP = 43
OP_JUMP_FALSE = 99
RSC85_MAGIC = 0x85435352


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, target)


def _run_tool(tool: Path, *args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [str(tool), *map(str, args)],
        cwd=str(tool.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"RPF6 tool failed ({args[0]}): {detail}")
    return result


def _archive_entry(tool: Path, archive: Path, filename: str) -> str:
    result = _run_tool(tool, "list", archive, "**")
    matches = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("path\t") or line.startswith("LISTED\t"):
            continue
        path = line.split("\t", 1)[0].strip().replace("\\", "/")
        if path.rsplit("/", 1)[-1].casefold() == filename.casefold():
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {filename} in {archive.name}; found {len(matches)}")
    if not matches[0].casefold().startswith("root/"):
        raise RuntimeError(f"Unexpected RPF6 script path: {matches[0]}")
    return matches[0]


def _object_start_from_rsc85(packed: bytes) -> int:
    if len(packed) < 16 or struct.unpack_from("<I", packed, 0)[0] != RSC85_MAGIC:
        raise ValueError("Passenger coach template is not an RSC85 resource")
    if struct.unpack_from("<I", packed, 4)[0] != 2:
        raise ValueError("Passenger coach template is not the expected type-2 WSC resource")
    flag1, flag2 = struct.unpack_from("<II", packed, 8)
    if not (flag2 & 0x80000000):
        raise ValueError("Passenger coach WSC does not use RSC85 extended flags")
    total = (flag2 & 0x3FFF) << 12
    wanted_page = 4096 << ((flag2 >> 28) & 7)
    counts = ((flag1 >> 14) & 3, (flag1 >> 8) & 63, flag1 & 0xFF)
    remaining = total
    page_size = 524288
    offset = 0
    for count in counts:
        for _ in range(count):
            while page_size > remaining and page_size > 0:
                page_size >>= 1
            if page_size == wanted_page:
                return offset
            offset += page_size
            remaining -= page_size
        page_size >>= 1
    while remaining > 0:
        while page_size > remaining and page_size > 0:
            page_size >>= 1
        if page_size == wanted_page:
            return offset
        offset += page_size
        remaining -= page_size
    raise ValueError("Could not resolve the WSC object-start page")


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("WSC pointer is outside the unpacked resource")
    return struct.unpack_from("<I", data, offset)[0]


def _pointer(data: bytes, offset: int) -> int:
    value = _u32(data, offset)
    return value & 0x0FFFFFFF if value >> 28 == 5 else value


def _script_layout(raw: bytes, object_start: int) -> dict:
    if object_start < 0 or object_start + 40 > len(raw):
        raise ValueError("WSC object start is outside the unpacked resource")
    code_table = _pointer(raw, object_start + 8)
    code_length = _u32(raw, object_start + 12)
    native_count = _pointer(raw, object_start + 32)
    native_table = _pointer(raw, object_start + 36)
    if code_length <= 0 or code_length > len(raw):
        raise ValueError(f"Unexpected WSC code length: {code_length}")
    if native_count <= 0 or native_count > 4096:
        raise ValueError(f"Unexpected WSC native count: {native_count}")
    if native_table < 0 or native_table + native_count * 4 > len(raw):
        raise ValueError("WSC native table is outside the unpacked resource")
    page_count = (code_length + 0x3FFF) >> 14
    if code_table < 0 or code_table + page_count * 4 > len(raw):
        raise ValueError("WSC code table is outside the unpacked resource")
    pages = [_pointer(raw, code_table + index * 4) for index in range(page_count)]
    code = bytearray()
    for index, page in enumerate(pages):
        length = min(0x4000, code_length - index * 0x4000)
        if page < 0 or page + length > len(raw):
            raise ValueError("WSC code page is outside the unpacked resource")
        code.extend(raw[page:page + length])
    if len(code) != code_length:
        raise ValueError("WSC code pages did not reconstruct to CodeLength")
    natives = [_u32(raw, native_table + index * 4) for index in range(native_count)]
    return {"code": code, "pages": pages, "codeLength": code_length, "natives": natives}


def _instruction_length(code: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset >= len(code):
        raise ValueError("Instruction offset is outside WSC code")
    opcode = code[offset]
    if opcode == 37:
        return 2
    if opcode == 38:
        return 3
    if opcode == 39:
        return 4
    if opcode in (40, 41):
        return 5
    if opcode == OP_NATIVE or 65 <= opcode <= 105:
        return 3
    if 52 <= opcode <= 64 or 114 <= opcode <= 117:
        return 2
    if 106 <= opcode <= 109:
        return 4
    if opcode == 110:
        if offset + 2 > len(code):
            raise ValueError("Truncated WSC switch")
        return 2 + code[offset + 1] * 6
    if opcode == 111:
        if offset + 2 > len(code):
            raise ValueError("Truncated WSC PushString")
        return 2 + code[offset + 1]
    if opcode == 112:
        if offset + 2 > len(code):
            raise ValueError("Truncated WSC PushArrayP")
        return 6 + code[offset + 1]
    if opcode == 45:
        if offset + 5 > len(code):
            raise ValueError("Truncated WSC Enter")
        return 5 + code[offset + 4]
    if 0 <= opcode <= 178:
        return 1
    raise ValueError(f"Unsupported WSC opcode {opcode} at 0x{offset:X}")


def _native_index(code: bytes | bytearray, offset: int) -> int:
    if code[offset] != OP_NATIVE or offset + 3 > len(code):
        raise ValueError("Expected WSC native instruction")
    return ((code[offset + 1] << 2) & 0x300) | code[offset + 2]


def _raw_code_offset(pages: list[int], code_offset: int) -> int:
    page = code_offset >> 14
    if page < 0 or page >= len(pages):
        raise ValueError("WSC code offset has no backing page")
    return pages[page] + (code_offset & 0x3FFF)


def patch_auto_carriage_rest(raw: bytes, object_start: int) -> tuple[bytes, dict]:
    """Auto-fire only the already-valid PASS_COACH Rest branch.

    Function_41 is the audited PC function at 0x1DC8.  The native still runs and
    consumes its use-context argument.  Its following JumpFalse normally consumes
    the returned boolean; replacing that 3-byte jump with POP,NOP,NOP preserves
    stack balance while making the true branch fall through every time the context
    is valid.  No code moves and no eligibility/state code is replaced.
    """
    layout = _script_layout(raw, object_start)
    code = layout["code"]
    start = COACH_FUNCTION_OFFSET
    if start >= len(code):
        raise ValueError(f"Passenger coach WSC is shorter than audited Function_41 offset 0x{start:X}")
    if code[start] != 45:
        raise ValueError(f"Expected Function_41 Enter at 0x{start:X}")
    cursor = start + _instruction_length(code, start)
    candidates = []
    while cursor < len(code):
        opcode = code[cursor]
        if opcode == 46 or 122 <= opcode <= 137:
            break
        length = _instruction_length(code, cursor)
        if cursor + length > len(code):
            raise ValueError("Instruction crosses WSC CodeLength")
        if opcode == OP_NATIVE:
            index = _native_index(code, cursor)
            if index >= len(layout["natives"]):
                raise ValueError(f"Native index {index} is outside the WSC native table")
            if layout["natives"][index] == WAS_CONTEXT_EVER_PRESSED_HASH:
                following = cursor + length
                if following + 3 > len(code) or code[following] != OP_JUMP_FALSE:
                    raise ValueError("Rest input native is not followed by the audited JumpFalse")
                relative = struct.unpack_from(">h", bytes(code), following + 1)[0]
                destination = following + 3 + relative
                if destination <= following + 3 or destination > len(code):
                    raise ValueError("Rest-input JumpFalse has an unexpected target")
                candidates.append((cursor, following, destination, index))
        cursor += length
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one Rest-input branch in passenger_coach Function_41; found {len(candidates)}")
    native_offset, jump_offset, jump_target, native_index = candidates[0]
    patched = bytearray(raw)
    replacement = bytes((OP_POP, 0, 0))
    raw_locations = [_raw_code_offset(layout["pages"], jump_offset + index) for index in range(3)]
    before = bytes(patched[position] for position in raw_locations)
    if before[0] != OP_JUMP_FALSE:
        raise ValueError("Mapped WSC branch is not JumpFalse in the unpacked resource")
    for position, value in zip(raw_locations, replacement):
        patched[position] = value
    # Reparse the exact output shape.  The native call must remain intact and the
    # three-byte branch slot must now be POP/NOP/NOP with every other byte unchanged.
    check = _script_layout(bytes(patched), object_start)
    if check["code"][native_offset] != OP_NATIVE or \
            check["natives"][_native_index(check["code"], native_offset)] != WAS_CONTEXT_EVER_PRESSED_HASH:
        raise RuntimeError("Passenger coach native call changed unexpectedly")
    if bytes(check["code"][jump_offset:jump_offset + 3]) != replacement:
        raise RuntimeError("Passenger coach Rest branch did not read back as POP/NOP/NOP")
    return bytes(patched), {
        "functionOffset": COACH_FUNCTION_OFFSET,
        "nativeOffset": native_offset,
        "nativeIndex": native_index,
        "nativeHash": f"0x{WAS_CONTEXT_EVER_PRESSED_HASH:08X}",
        "branchOffset": jump_offset,
        "oldBranchHex": before.hex(),
        "newBranchHex": replacement.hex(),
        "oldJumpTarget": jump_target,
    }


def _load_state(state_file: Path) -> dict:
    if not state_file.is_file():
        return {"schemaVersion": 1, "features": {}}
    try:
        document = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Script-feature ownership manifest is invalid: {error}") from error
    if not isinstance(document, dict) or document.get("schemaVersion") != 1 or not isinstance(document.get("features"), dict):
        raise ValueError("Script-feature ownership manifest has an unsupported schema")
    return document


def prepare_auto_carriage_rest(
        game_root: Path = paths.GAME_ROOT,
        tool: Path = paths.RPF6_TOOL,
        override_root: Path = CONTENT_OVERRIDE_ROOT,
        state_file: Path = STATE_FILE) -> dict:
    archive = Path(game_root) / CONTENT_ARCHIVE_RELATIVE
    tool = Path(tool)
    override_root = Path(override_root)
    state_file = Path(state_file)
    if not archive.is_file():
        raise FileNotFoundError(f"Installed RDR content archive was not found: {archive}")
    if not tool.is_file():
        raise FileNotFoundError(f"RPF6 bridge was not found: {tool}")
    archive_path = _archive_entry(tool, archive, COACH_SCRIPT_NAME)
    relative = archive_path[5:]  # validated root/ prefix
    target = override_root / Path(relative.replace("/", os.sep))
    state = _load_state(state_file)
    owned = state["features"].get("autoCarriageRest")
    if target.is_file():
        current_hash = _sha256_bytes(target.read_bytes())
        if not isinstance(owned, dict) or owned.get("archivePath") != archive_path or owned.get("generatedSha256") != current_hash:
            raise RuntimeError(
                f"Refusing to overwrite an unowned project script override: {target}")

    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-coach-rest-") as temporary:
        root = Path(temporary)
        extracted = root / "extract"
        _run_tool(tool, "extract", archive, extracted, archive_path)
        template = extracted / Path(relative.replace("/", os.sep))
        if not template.is_file():
            raise RuntimeError("RPF6 extraction did not produce passenger_coach.wsc")
        packed = template.read_bytes()
        object_start = _object_start_from_rsc85(packed)
        raw = root / "passenger_coach.raw"
        _run_tool(tool, "resource-unpack", template, raw)
        source_raw = raw.read_bytes()
        patched_raw, patch = patch_auto_carriage_rest(source_raw, object_start)
        raw.write_bytes(patched_raw)
        candidate = root / "passenger_coach.wsc"
        _run_tool(tool, "resource-pack", template, raw, candidate)
        verified_raw = root / "verified.raw"
        _run_tool(tool, "resource-unpack", candidate, verified_raw)
        if verified_raw.read_bytes() != patched_raw:
            raise RuntimeError("Repacked passenger coach WSC did not verify byte-for-byte")
        generated = candidate.read_bytes()

    source_sha = _sha256_bytes(packed)
    generated_sha = _sha256_bytes(generated)
    changed = not target.is_file() or _sha256_bytes(target.read_bytes()) != generated_sha
    if changed:
        _atomic_bytes(target, generated)
    feature_state = {
        "archive": CONTENT_ARCHIVE_RELATIVE.as_posix(),
        "archivePath": archive_path,
        "sourceSha256": source_sha,
        "generatedSha256": generated_sha,
        "target": str(target),
        "patch": patch,
    }
    state["features"]["autoCarriageRest"] = feature_state
    _atomic_bytes(state_file, (json.dumps(state, indent=2) + "\n").encode("utf-8"))
    if not target.is_file() or _sha256_bytes(target.read_bytes()) != generated_sha:
        raise RuntimeError("Generated passenger coach override did not read back exactly")
    return {"prepared": True, "changed": int(changed), **feature_state}

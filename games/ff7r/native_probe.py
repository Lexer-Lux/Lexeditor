"""Read-only current-build probe for FF7R native runtime hook research.

No fixed executable offsets live here. The probe parses the installed PE image,
finds useful literal names when Square left them in the binary, and reports
common x86-64 RIP-relative LEA references to those strings. Results are
research evidence/candidates only; they are never treated as a safe hook until a
specific runtime signature is validated.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from pathlib import Path
from typing import Iterable


EXE_RELATIVE_PATH = Path("End") / "Binaries" / "Win64" / "ff7remake_.exe"
DEFAULT_NEEDLES = (
    "FastForward",
    "EventScene",
    "CutScene",
    "SkipCinema",
    "IsSkipCinemaAtThisFrame",
    "IsSkipCinema",
    "RequestPlayCutScene",
    "PlayCutScene",
    "SetGameSpeed",
    "GetGameSpeed",
    "EGameSpeed_CUT",
    "NaviMap",
    "HideNavimap",
    "BPShowNavimap",
    "BPHideNavimap",
    "SendStateTrigger",
    "SendStateTriggerDirect",
    "trgCmn_NaviMap_Update_On",
    "trgCmn_NaviMap_Update_Off",
    # Exact generated playable/final-status HP APIs. These are deliberately kept
    # separate from generic GetHP/GetHPMax strings so installed xref research can
    # distinguish player-status reads/writes from unrelated enemy/UI health code.
    "BPSetPlayerHPMax",
    "BPSetPlayerHP",
    "BPGetPlayerStatus",
    "BPGetPlayerStatusWithEquipment",
    "BPGetPlayerStatusWithMateria",
    "BPGetPlayerHPMax",
    "BPGetPlayerHP",
    "GetCharaHPMax",
    "GetCharaHP",
    # Broader legacy anchors remain useful for correlation but are never promoted
    # into an HP Rebalance hook solely by name.
    "GetHPMax",
    "GetHP",
    "DashRootMotionTranslationScale",
    "RunToDashBlendInputThreshold",
)
MAX_HITS_PER_ENCODING = 64
MAX_XREFS_PER_STRING = 64
FUNCTION_WINDOW_BYTES = 64
FUNCTION_CODE_SCAN_MAX_BYTES = 2048
MAX_CODE_REFS_PER_FUNCTION = 64
XREF_CONTEXT_BEFORE = 16
XREF_CONTEXT_AFTER = 32
IMAGE_FILE_MACHINE_AMD64 = 0x8664
EXCEPTION_DIRECTORY_INDEX = 3
RUNTIME_FUNCTION_SIZE = 12


class PEFormatError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int

    @property
    def mapped_size(self) -> int:
        return max(self.virtual_size, self.raw_size)


@dataclass(frozen=True)
class RuntimeFunction:
    begin_rva: int
    end_rva: int
    unwind_info_rva: int


@dataclass(frozen=True)
class PEImage:
    data: bytes
    machine: int
    timestamp: int
    image_base: int
    exception_directory_rva: int
    exception_directory_size: int
    sections: tuple[Section, ...]
    runtime_functions: tuple[RuntimeFunction, ...]

    @classmethod
    def from_bytes(cls, data: bytes) -> "PEImage":
        if len(data) < 0x100 or data[:2] != b"MZ":
            raise PEFormatError("not a PE image")
        pe_offset = _u32(data, 0x3C)
        if pe_offset < 0 or pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
            raise PEFormatError("invalid PE header")
        coff = pe_offset + 4
        machine = _u16(data, coff)
        section_count = _u16(data, coff + 2)
        timestamp = _u32(data, coff + 4)
        optional_size = _u16(data, coff + 16)
        optional = coff + 20
        optional_end = optional + optional_size
        if optional_end > len(data):
            raise PEFormatError("truncated optional header")
        magic = _u16(data, optional)
        if magic == 0x20B:  # PE32+
            image_base = _u64(data, optional + 24)
            directory_count_offset = optional + 108
            directory_table_offset = optional + 112
        elif magic == 0x10B:  # PE32, supported for parser completeness
            image_base = _u32(data, optional + 28)
            directory_count_offset = optional + 92
            directory_table_offset = optional + 96
        else:
            raise PEFormatError(f"unsupported optional-header magic 0x{magic:X}")

        exception_directory_rva = 0
        exception_directory_size = 0
        if directory_count_offset + 4 <= optional_end:
            directory_count = _u32(data, directory_count_offset)
            exception_entry = directory_table_offset + EXCEPTION_DIRECTORY_INDEX * 8
            if directory_count > EXCEPTION_DIRECTORY_INDEX and exception_entry + 8 <= optional_end:
                exception_directory_rva = _u32(data, exception_entry)
                exception_directory_size = _u32(data, exception_entry + 4)

        section_table = optional_end
        sections = []
        for index in range(section_count):
            offset = section_table + index * 40
            if offset + 40 > len(data):
                raise PEFormatError("truncated section table")
            name = data[offset:offset + 8].split(b"\0", 1)[0].decode("ascii", errors="replace")
            sections.append(Section(
                name=name,
                virtual_size=_u32(data, offset + 8),
                virtual_address=_u32(data, offset + 12),
                raw_size=_u32(data, offset + 16),
                raw_offset=_u32(data, offset + 20),
            ))
        provisional = cls(
            data=data,
            machine=machine,
            timestamp=timestamp,
            image_base=image_base,
            exception_directory_rva=exception_directory_rva,
            exception_directory_size=exception_directory_size,
            sections=tuple(sections),
            runtime_functions=(),
        )
        runtime_functions = tuple(_parse_runtime_functions(provisional))
        return cls(
            data=data,
            machine=machine,
            timestamp=timestamp,
            image_base=image_base,
            exception_directory_rva=exception_directory_rva,
            exception_directory_size=exception_directory_size,
            sections=tuple(sections),
            runtime_functions=runtime_functions,
        )

    def section(self, name: str) -> Section | None:
        return next((section for section in self.sections if section.name == name), None)

    def rva_to_offset(self, rva: int) -> int | None:
        for section in self.sections:
            if section.virtual_address <= rva < section.virtual_address + section.mapped_size:
                offset = section.raw_offset + (rva - section.virtual_address)
                return offset if 0 <= offset < len(self.data) else None
        # PE headers are mapped at RVA == file offset.
        if 0 <= rva < min((section.raw_offset for section in self.sections), default=len(self.data)):
            return rva if rva < len(self.data) else None
        return None

    def offset_to_rva(self, offset: int) -> int | None:
        for section in self.sections:
            if section.raw_offset <= offset < section.raw_offset + section.raw_size:
                return section.virtual_address + (offset - section.raw_offset)
        if 0 <= offset < min((section.raw_offset for section in self.sections), default=len(self.data)):
            return offset
        return None


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise PEFormatError("truncated 16-bit field")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise PEFormatError("truncated 32-bit field")
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 8 > len(data):
        raise PEFormatError("truncated 64-bit field")
    return struct.unpack_from("<Q", data, offset)[0]


def _parse_runtime_functions(image: PEImage) -> list[RuntimeFunction]:
    if image.machine != IMAGE_FILE_MACHINE_AMD64:
        return []
    rva = image.exception_directory_rva
    size = image.exception_directory_size
    if rva <= 0 or size < RUNTIME_FUNCTION_SIZE or size % RUNTIME_FUNCTION_SIZE:
        return []
    offset = image.rva_to_offset(rva)
    if offset is None or offset + size > len(image.data):
        return []
    rows: list[RuntimeFunction] = []
    for cursor in range(offset, offset + size, RUNTIME_FUNCTION_SIZE):
        begin_rva, end_rva, unwind_info_rva = struct.unpack_from("<III", image.data, cursor)
        if begin_rva == 0 and end_rva == 0:
            continue
        if begin_rva >= end_rva:
            return []
        rows.append(RuntimeFunction(begin_rva, end_rva, unwind_info_rva))
    return sorted(rows, key=lambda row: (row.begin_rva, row.end_rva))


def _read_window(image: PEImage, rva: int, *, before: int, after: int) -> dict | None:
    section = next(
        (
            section for section in image.sections
            if section.virtual_address <= rva < section.virtual_address + section.mapped_size
        ),
        None,
    )
    if section is None:
        return None
    section_start = section.virtual_address
    section_end = section.virtual_address + min(section.virtual_size or section.raw_size, section.raw_size)
    start_rva = max(section_start, rva - before)
    end_rva = min(section_end, rva + after)
    start_offset = image.rva_to_offset(start_rva)
    end_offset = image.rva_to_offset(end_rva - 1) if end_rva > start_rva else None
    if start_offset is None or end_offset is None:
        return None
    end_offset += 1
    return {
        "rva": start_rva,
        "bytesHex": image.data[start_offset:end_offset].hex(),
    }


def _function_for_rva(image: PEImage, rva: int) -> RuntimeFunction | None:
    # Exception metadata is sorted by function start. This deliberately avoids
    # inventing a function when the candidate falls only in compiler padding.
    for row in image.runtime_functions:
        if row.begin_rva <= rva < row.end_rva:
            return row
        if row.begin_rva > rva:
            break
    return None


def _heuristic_function_bounds(section: Section, rva: int) -> tuple[int, int]:
    section_start = section.virtual_address
    section_end = section.virtual_address + min(section.virtual_size or section.raw_size, section.raw_size)
    start = max(section_start, rva - FUNCTION_WINDOW_BYTES)
    end = min(section_end, rva + FUNCTION_WINDOW_BYTES)
    return start, end


def _function_window(image: PEImage, rva: int) -> dict | None:
    section = image.section(".text")
    if section is None:
        return None
    runtime = _function_for_rva(image, rva)
    if runtime is not None:
        start_rva, end_rva = runtime.begin_rva, runtime.end_rva
        source = "pdata"
        unwind_info_rva: int | None = runtime.unwind_info_rva
    else:
        start_rva, end_rva = _heuristic_function_bounds(section, rva)
        source = "heuristic"
        unwind_info_rva = None
    start_offset = image.rva_to_offset(start_rva)
    last_offset = image.rva_to_offset(end_rva - 1) if end_rva > start_rva else None
    if start_offset is None or last_offset is None:
        return None
    return {
        "startRva": start_rva,
        "endRva": end_rva,
        "size": end_rva - start_rva,
        "source": source,
        "unwindInfoRva": unwind_info_rva,
        "bytesHex": image.data[start_offset:last_offset + 1].hex(),
    }


def _find_code_refs(image: PEImage, function: dict) -> list[dict]:
    # Only exact .pdata-bounded functions are safe to trace between. Heuristic
    # windows are retained as evidence but never used to infer a call graph.
    if function.get("source") != "pdata":
        return []
    start_rva = int(function["startRva"])
    end_rva = int(function["endRva"])
    if end_rva <= start_rva or end_rva - start_rva > FUNCTION_CODE_SCAN_MAX_BYTES:
        return []
    start_offset = image.rva_to_offset(start_rva)
    last_offset = image.rva_to_offset(end_rva - 1)
    if start_offset is None or last_offset is None:
        return []
    code = image.data[start_offset:last_offset + 1]
    refs: list[dict] = []
    # This remains intentionally narrow rather than pretending to be a general
    # x86-64 decoder: CALL/JMP rel32 and canonical RIP-relative LEA are useful
    # compiler-stable next-hop shapes for reflected-name registration glue.
    for index in range(len(code)):
        instruction_rva = start_rva + index
        opcode = code[index]
        kind: str | None = None
        target_rva: int | None = None
        instruction_size = 0
        if opcode in (0xE8, 0xE9) and index + 5 <= len(code):
            displacement = struct.unpack_from("<i", code, index + 1)[0]
            target_rva = instruction_rva + 5 + displacement
            kind = "callRel32" if opcode == 0xE8 else "jmpRel32"
            instruction_size = 5
        elif index + 7 <= len(code) and code[index] == 0x48 and code[index + 1] == 0x8D:
            modrm = code[index + 2]
            if (modrm & 0xC7) == 0x05:  # mod=00, r/m=101 => RIP+disp32
                displacement = struct.unpack_from("<i", code, index + 3)[0]
                target_rva = instruction_rva + 7 + displacement
                kind = "leaRip"
                instruction_size = 7
        if target_rva is None or kind is None:
            continue
        target_function = _function_for_rva(image, target_rva)
        if target_function is None:
            continue
        target_window = _function_window(image, target_rva)
        if target_window is None or target_window.get("source") != "pdata":
            continue
        refs.append({
            "kind": kind,
            "instructionRva": instruction_rva,
            "instructionSize": instruction_size,
            "targetRva": target_rva,
            "targetFunctionRva": int(target_window["startRva"]),
            "targetFunction": target_window,
        })
        if len(refs) >= MAX_CODE_REFS_PER_FUNCTION:
            break
    return refs


def _find_lea_xrefs(image: PEImage, target_rva: int) -> list[dict]:
    text = image.section(".text")
    if text is None or text.raw_size < 7:
        return []
    start = text.raw_offset
    end = min(len(image.data), text.raw_offset + text.raw_size)
    code = image.data[start:end]
    hits: list[dict] = []
    # Canonical x86-64 LEA reg,[RIP+disp32]: REX.W 8D /r with mod=00 r/m=101.
    # Seven bytes is the full instruction. Include the last legal start offset.
    for index in range(0, len(code) - 7 + 1):
        if code[index] != 0x48 or code[index + 1] != 0x8D:
            continue
        modrm = code[index + 2]
        if (modrm & 0xC7) != 0x05:
            continue
        instruction_rva = text.virtual_address + index
        displacement = struct.unpack_from("<i", code, index + 3)[0]
        resolved = instruction_rva + 7 + displacement
        if resolved != target_rva:
            continue
        function = _function_window(image, instruction_rva)
        hits.append({
            "instructionRva": instruction_rva,
            "candidateFunctionRva": function["startRva"] if function else None,
            "context": _read_window(
                image,
                instruction_rva,
                before=XREF_CONTEXT_BEFORE,
                after=XREF_CONTEXT_AFTER,
            ),
            "candidateFunction": function,
            "candidateFunctionCodeRefs": _find_code_refs(image, function) if function else [],
        })
        if len(hits) >= MAX_XREFS_PER_STRING:
            break
    return hits


def _find_strings(image: PEImage, needle: str) -> list[dict]:
    hits: list[dict] = []
    encodings = (("ascii", needle.encode("utf-8")), ("utf16le", needle.encode("utf-16le")))
    # Reflected names/resources normally live outside .text. Search all mapped
    # raw section bytes while preserving each concrete string RVA.
    for encoding, encoded in encodings:
        for section in image.sections:
            if not encoded or section.raw_size < len(encoded):
                continue
            start = section.raw_offset
            end = min(len(image.data), section.raw_offset + section.raw_size)
            cursor = start
            count = 0
            while count < MAX_HITS_PER_ENCODING:
                offset = image.data.find(encoded, cursor, end)
                if offset < 0:
                    break
                rva = image.offset_to_rva(offset)
                if rva is not None:
                    hits.append({
                        "encoding": encoding,
                        "section": section.name,
                        "offset": offset,
                        "rva": rva,
                        "context": _read_window(
                            image,
                            rva,
                            before=XREF_CONTEXT_BEFORE,
                            after=XREF_CONTEXT_AFTER,
                        ),
                    })
                    count += 1
                cursor = offset + 1
    return hits


def scan_executable_bytes(data: bytes, needles: Iterable[str] = DEFAULT_NEEDLES) -> dict:
    image = PEImage.from_bytes(data)
    needle_list = tuple(dict.fromkeys(str(needle) for needle in needles if str(needle)))
    results = []
    for needle in needle_list:
        hits = _find_strings(image, needle)
        for hit in hits:
            hit["leaRipXrefs"] = _find_lea_xrefs(image, int(hit["rva"]))
        results.append({"needle": needle, "hits": hits})
    return {
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "imageBase": image.image_base,
        "machine": image.machine,
        "runtimeFunctionCount": len(image.runtime_functions),
        "needles": results,
        "notes": (
            "String/xref/function-range evidence is read-only research. Candidate functions use exact "
            ".pdata unwind ranges when available; heuristic windows are retained only as evidence. "
            "Cross-function next-hop tracing is limited to .pdata-described CALL/JMP rel32 and RIP-relative LEA targets "
            "and is not a validated hook or a full disassembler."
        ),
    }


def probe_installed_exe(game_root: Path, needles: Iterable[str] = DEFAULT_NEEDLES) -> dict:
    path = Path(game_root) / EXE_RELATIVE_PATH
    if not path.is_file():
        raise FileNotFoundError(f"FF7R executable not found: {path}")
    result = scan_executable_bytes(path.read_bytes(), needles)
    result["path"] = str(path)
    return result

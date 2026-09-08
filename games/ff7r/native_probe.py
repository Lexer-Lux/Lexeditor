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
    "BPSetPlayerHPMax",
    "BPGetPlayerStatus",
    "BPGetPlayerStatusWithEquipment",
    "BPGetPlayerStatusWithMateria",
    "BPGetPlayerHPMax",
    "BPGetPlayerHP",
    "GetHPMax",
    "GetHP",
    "DashRootMotionTranslationScale",
    "RunToDashBlendInputThreshold",
)
MAX_HITS_PER_ENCODING = 64
MAX_XREFS_PER_STRING = 64
FUNCTION_WINDOW_BYTES = 64
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
            virtual_size = _u32(data, offset + 8)
            virtual_address = _u32(data, offset + 12)
            raw_size = _u32(data, offset + 16)
            raw_offset = _u32(data, offset + 20)
            if raw_offset + raw_size > len(data):
                raise PEFormatError(f"section {name!r} is outside the file")
            sections.append(Section(name, virtual_address, virtual_size, raw_offset, raw_size))

        image = cls(
            data=data,
            machine=machine,
            timestamp=timestamp,
            image_base=image_base,
            exception_directory_rva=exception_directory_rva,
            exception_directory_size=exception_directory_size,
            sections=tuple(sections),
            runtime_functions=(),
        )
        runtime_functions = _runtime_functions(image)
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
        folded = name.casefold()
        return next((section for section in self.sections if section.name.casefold() == folded), None)

    def section_for_rva(self, rva: int) -> Section | None:
        return next((
            section
            for section in self.sections
            if section.virtual_address <= rva < section.virtual_address + section.mapped_size
        ), None)

    def offset_to_rva(self, offset: int) -> int | None:
        for section in self.sections:
            if section.raw_offset <= offset < section.raw_offset + section.raw_size:
                return section.virtual_address + (offset - section.raw_offset)
        return None

    def rva_to_offset(self, rva: int) -> int | None:
        for section in self.sections:
            if section.virtual_address <= rva < section.virtual_address + section.mapped_size:
                delta = rva - section.virtual_address
                if delta >= section.raw_size:
                    return None
                return section.raw_offset + delta
        return None

    def runtime_function_for_rva(self, rva: int) -> RuntimeFunction | None:
        """Return the AMD64 unwind-table function containing one RVA, if any."""
        low = 0
        high = len(self.runtime_functions)
        while low < high:
            middle = (low + high) // 2
            candidate = self.runtime_functions[middle]
            if rva < candidate.begin_rva:
                high = middle
            elif rva >= candidate.end_rva:
                low = middle + 1
            else:
                return candidate
        return None


def _u16(data: bytes, offset: int) -> int:
    try:
        return struct.unpack_from("<H", data, offset)[0]
    except struct.error as error:
        raise PEFormatError("truncated PE integer") from error


def _u32(data: bytes, offset: int) -> int:
    try:
        return struct.unpack_from("<I", data, offset)[0]
    except struct.error as error:
        raise PEFormatError("truncated PE integer") from error


def _u64(data: bytes, offset: int) -> int:
    try:
        return struct.unpack_from("<Q", data, offset)[0]
    except struct.error as error:
        raise PEFormatError("truncated PE integer") from error


def _runtime_functions(image: PEImage) -> tuple[RuntimeFunction, ...]:
    """Parse AMD64 IMAGE_RUNTIME_FUNCTION_ENTRY rows from the exception directory."""
    if (
        image.machine != IMAGE_FILE_MACHINE_AMD64
        or image.exception_directory_rva <= 0
        or image.exception_directory_size < RUNTIME_FUNCTION_SIZE
    ):
        return ()
    section = image.section_for_rva(image.exception_directory_rva)
    if section is None:
        return ()
    relative = image.exception_directory_rva - section.virtual_address
    if relative < 0 or relative >= section.raw_size:
        return ()
    start = section.raw_offset + relative
    available = min(
        image.exception_directory_size,
        section.raw_size - relative,
        len(image.data) - start,
    )
    functions = []
    for offset in range(start, start + available - RUNTIME_FUNCTION_SIZE + 1, RUNTIME_FUNCTION_SIZE):
        begin_rva, end_rva, unwind_info_rva = struct.unpack_from("<III", image.data, offset)
        if begin_rva <= 0 or end_rva <= begin_rva:
            continue
        functions.append(RuntimeFunction(begin_rva, end_rva, unwind_info_rva))
    functions.sort(key=lambda entry: (entry.begin_rva, entry.end_rva))
    return tuple(functions)


def _find_all(haystack: bytes, needle: bytes, *, start: int = 0, end: int | None = None,
              limit: int = MAX_HITS_PER_ENCODING) -> list[int]:
    if not needle:
        return []
    stop = len(haystack) if end is None else min(end, len(haystack))
    hits = []
    cursor = max(0, start)
    while cursor < stop and len(hits) < limit:
        hit = haystack.find(needle, cursor, stop)
        if hit < 0:
            break
        hits.append(hit)
        cursor = hit + max(1, len(needle))
    return hits


def _hex_bytes(value: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in value)


def _byte_window(image: PEImage, rva: int, *, before: int = 0, after: int) -> dict | None:
    section = image.section_for_rva(rva)
    if section is None:
        return None
    relative = rva - section.virtual_address
    if relative >= section.raw_size:
        return None
    start_relative = max(0, relative - max(0, before))
    end_relative = min(section.raw_size, relative + max(0, after))
    if end_relative <= start_relative:
        return None
    start_offset = section.raw_offset + start_relative
    end_offset = section.raw_offset + end_relative
    raw = image.data[start_offset:end_offset]
    start_rva = section.virtual_address + start_relative
    return {
        "section": section.name,
        "startRva": start_rva,
        "startVa": image.image_base + start_rva,
        "focusRva": rva,
        "focusOffset": relative - start_relative,
        "byteCount": len(raw),
        "hex": _hex_bytes(raw),
    }


def _string_hits(image: PEImage, needle: str) -> list[dict]:
    hits = []
    variants = (
        ("ascii", needle.encode("ascii", errors="ignore")),
        ("utf16le", needle.encode("utf-16-le")),
    )
    for encoding, raw in variants:
        if not raw:
            continue
        for offset in _find_all(image.data, raw):
            rva = image.offset_to_rva(offset)
            if rva is None:
                continue
            hits.append({
                "encoding": encoding,
                "fileOffset": offset,
                "rva": rva,
                "va": image.image_base + rva,
            })
    return hits


def _xref_candidate(image: PEImage, text: Section, raw: bytes, index: int) -> dict:
    instruction_rva = text.virtual_address + index
    runtime_function = image.runtime_function_for_rva(instruction_rva)
    if runtime_function is not None:
        function_rva = runtime_function.begin_rva
        function_end_rva = runtime_function.end_rva
        function_source = "pdata"
        unwind_info_rva = runtime_function.unwind_info_rva
    else:
        function_rva = _nearest_padded_function_start(raw, index, text.virtual_address)
        function_end_rva = None
        function_source = "padding-heuristic" if function_rva is not None else None
        unwind_info_rva = None

    function_window = FUNCTION_WINDOW_BYTES
    if function_rva is not None and function_end_rva is not None:
        function_window = min(function_window, function_end_rva - function_rva)

    return {
        "instructionRva": instruction_rva,
        "instructionVa": image.image_base + instruction_rva,
        "candidateFunctionRva": function_rva,
        "candidateFunctionVa": image.image_base + function_rva if function_rva is not None else None,
        "candidateFunctionEndRva": function_end_rva,
        "candidateFunctionEndVa": (
            image.image_base + function_end_rva if function_end_rva is not None else None
        ),
        "candidateFunctionSource": function_source,
        "candidateFunctionUnwindInfoRva": unwind_info_rva,
        "candidateFunctionUnwindInfoVa": (
            image.image_base + unwind_info_rva if unwind_info_rva is not None else None
        ),
        "xrefContext": _byte_window(
            image,
            instruction_rva,
            before=XREF_CONTEXT_BEFORE,
            after=XREF_CONTEXT_AFTER,
        ),
        "candidateFunctionBytes": (
            _byte_window(image, function_rva, after=function_window)
            if function_rva is not None
            else None
        ),
    }


def _lea_rip_xrefs_many(image: PEImage, target_rvas: Iterable[int]) -> dict[int, list[dict]]:
    """Scan .text once for common RIP-relative LEAs resolving to requested RVAs."""
    targets = {int(rva) for rva in target_rvas}
    results = {rva: [] for rva in targets}
    text = image.section(".text")
    if text is None or not targets:
        return results
    raw = image.data[text.raw_offset:text.raw_offset + text.raw_size]
    remaining = set(targets)
    # 4? 8D /r, mod=00 r/m=101. This deliberately recognizes only the very
    # common RIP-relative LEA form instead of pretending to be an x86 decoder.
    for index in range(max(0, len(raw) - 6)):
        rex = raw[index]
        if not (0x48 <= rex <= 0x4F) or raw[index + 1] != 0x8D:
            continue
        modrm = raw[index + 2]
        if modrm & 0xC7 != 0x05:
            continue
        displacement = struct.unpack_from("<i", raw, index + 3)[0]
        instruction_rva = text.virtual_address + index
        resolved = instruction_rva + 7 + displacement
        if resolved not in remaining:
            continue
        bucket = results[resolved]
        bucket.append(_xref_candidate(image, text, raw, index))
        if len(bucket) >= MAX_XREFS_PER_STRING:
            remaining.remove(resolved)
            if not remaining:
                break
    return results


def _lea_rip_xrefs(image: PEImage, target_rva: int) -> list[dict]:
    """Compatibility helper for one target RVA."""
    return _lea_rip_xrefs_many(image, (target_rva,)).get(target_rva, [])


def _nearest_padded_function_start(text: bytes, index: int, text_rva: int) -> int | None:
    """Heuristic only: find first non-INT3 byte after nearby compiler padding."""
    floor = max(0, index - 768)
    cursor = index - 1
    while cursor >= floor:
        if text[cursor] == 0xCC:
            run_end = cursor
            while cursor >= floor and text[cursor] == 0xCC:
                cursor -= 1
            candidate = run_end + 1
            if candidate <= index:
                return text_rva + candidate
        cursor -= 1
    return None


def probe_bytes(data: bytes, *, needles: Iterable[str] = DEFAULT_NEEDLES) -> dict:
    image = PEImage.from_bytes(data)
    entries = []
    target_rvas = set()
    for needle in needles:
        strings = _string_hits(image, str(needle))
        target_rvas.update(hit["rva"] for hit in strings)
        entries.append({"needle": str(needle), "hits": strings})

    xrefs = _lea_rip_xrefs_many(image, target_rvas)
    for entry in entries:
        for hit in entry["hits"]:
            hit["leaRipXrefs"] = xrefs.get(hit["rva"], [])

    return {
        "machine": image.machine,
        "machineHex": f"0x{image.machine:04X}",
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "imageBase": image.image_base,
        "exceptionDirectory": {
            "rva": image.exception_directory_rva,
            "size": image.exception_directory_size,
            "runtimeFunctionCount": len(image.runtime_functions),
        },
        "sections": [
            {
                "name": section.name,
                "rva": section.virtual_address,
                "virtualSize": section.virtual_size,
                "rawOffset": section.raw_offset,
                "rawSize": section.raw_size,
            }
            for section in image.sections
        ],
        "needles": entries,
        "notes": [
            "String and LEA matches are research candidates, not validated hook addresses.",
            "AMD64 candidate function ranges prefer PE exception-directory (.pdata) unwind metadata when available.",
            "When unwind metadata is unavailable, candidate starts fall back to compiler-padding heuristics.",
            "Candidate byte windows are raw executable evidence for signature research; they are not instruction-decoded or stability-validated.",
            "The probe is read-only and does not modify the installed executable.",
        ],
    }


def probe_installed_exe(game_root: Path, *, needles: Iterable[str] = DEFAULT_NEEDLES) -> dict:
    exe = Path(game_root) / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    result = probe_bytes(data, needles=needles)
    return {"path": str(exe), "size": len(data), **result}

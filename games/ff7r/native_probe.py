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
    "NaviMap",
    "HideNavimap",
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
class PEImage:
    data: bytes
    timestamp: int
    image_base: int
    sections: tuple[Section, ...]

    @classmethod
    def from_bytes(cls, data: bytes) -> "PEImage":
        if len(data) < 0x100 or data[:2] != b"MZ":
            raise PEFormatError("not a PE image")
        pe_offset = _u32(data, 0x3C)
        if pe_offset < 0 or pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
            raise PEFormatError("invalid PE header")
        coff = pe_offset + 4
        section_count = _u16(data, coff + 2)
        timestamp = _u32(data, coff + 4)
        optional_size = _u16(data, coff + 16)
        optional = coff + 20
        if optional + optional_size > len(data):
            raise PEFormatError("truncated optional header")
        magic = _u16(data, optional)
        if magic == 0x20B:  # PE32+
            image_base = _u64(data, optional + 24)
        elif magic == 0x10B:  # PE32, supported for parser completeness
            image_base = _u32(data, optional + 28)
        else:
            raise PEFormatError(f"unsupported optional-header magic 0x{magic:X}")
        section_table = optional + optional_size
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
        return cls(data=data, timestamp=timestamp, image_base=image_base, sections=tuple(sections))

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


def _lea_rip_xrefs(image: PEImage, target_rva: int) -> list[dict]:
    """Find common `REX.W + LEA reg,[RIP+disp32]` references to one RVA."""
    text = image.section(".text")
    if text is None:
        return []
    raw = image.data[text.raw_offset:text.raw_offset + text.raw_size]
    results = []
    # 4? 8D /r, mod=00 r/m=101. This deliberately recognizes only the very
    # common RIP-relative LEA form instead of pretending to be an x86 decoder.
    for index in range(max(0, len(raw) - 7)):
        rex = raw[index]
        if not (0x48 <= rex <= 0x4F) or raw[index + 1] != 0x8D:
            continue
        modrm = raw[index + 2]
        if modrm & 0xC7 != 0x05:
            continue
        displacement = struct.unpack_from("<i", raw, index + 3)[0]
        instruction_rva = text.virtual_address + index
        resolved = instruction_rva + 7 + displacement
        if resolved != target_rva:
            continue
        function_rva = _nearest_padded_function_start(raw, index, text.virtual_address)
        result = {
            "instructionRva": instruction_rva,
            "instructionVa": image.image_base + instruction_rva,
            "candidateFunctionRva": function_rva,
            "candidateFunctionVa": image.image_base + function_rva if function_rva is not None else None,
            "xrefContext": _byte_window(
                image,
                instruction_rva,
                before=XREF_CONTEXT_BEFORE,
                after=XREF_CONTEXT_AFTER,
            ),
            "candidateFunctionBytes": (
                _byte_window(image, function_rva, after=FUNCTION_WINDOW_BYTES)
                if function_rva is not None
                else None
            ),
        }
        results.append(result)
        if len(results) >= MAX_XREFS_PER_STRING:
            break
    return results


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
    for needle in needles:
        strings = _string_hits(image, str(needle))
        for hit in strings:
            hit["leaRipXrefs"] = _lea_rip_xrefs(image, hit["rva"])
        entries.append({"needle": str(needle), "hits": strings})
    return {
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "imageBase": image.image_base,
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
            "Candidate function starts are compiler-padding heuristics and must be signature-validated before patching.",
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

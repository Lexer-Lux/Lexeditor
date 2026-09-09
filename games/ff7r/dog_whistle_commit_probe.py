"""Read-only native discovery for FF7R Dog Whistle's player item commit path.

The existing Dog Whistle probe can locate reflected item/ability helpers such as
``IsItem`` and ``RequestAIPCExecuteAbility``, but the remaining blocker is the
*human player's* Items-menu commit callsite. Guessing more exported/reflected
names is weak evidence, so this stage works in the opposite direction:

1. locate the existing item/ability anchor names in the installed executable;
2. keep only exact AMD64 ``.pdata`` function owners/targets and their inbound
   caller functions already exposed by :mod:`native_probe`;
3. scan those exact caller bounds for common RIP-relative LEA references to
   printable strings in non-code sections;
4. rank co-referenced names that look command/menu/item related.

The result is discovery evidence only. A co-referenced name, even from a caller
shared by multiple anchor families, is never treated as a validated hook.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import struct
from typing import Any, Iterable, Mapping

from .native_probe import EXE_RELATIVE_PATH, PEImage, RuntimeFunction, probe_installed_exe


ITEM_COMMIT_ANCHORS = (
    "IsItem",
    "RequestAIPCAbility",
    "RequestAIPCExecuteAbility",
    "ReserveAbility",
    "RequestUseAbility",
    "EndFieldOnOffTable_IgnoreBattleCommandItem",
)
MAX_STRING_BYTES = 192
MAX_STRING_REFS_PER_FUNCTION = 192
MAX_RANKED_LEADS = 128
MIN_PRINTABLE_LENGTH = 3

# These weights rank leads for manual inspection only. They are deliberately not
# a semantic classifier or hook-authorization mechanism.
LEAD_TOKENS = {
    "item": 5,
    "command": 5,
    "menu": 4,
    "commit": 4,
    "consume": 4,
    "ability": 3,
    "execute": 3,
    "select": 3,
    "decision": 3,
    "decide": 3,
    "confirm": 3,
    "use": 2,
    "request": 2,
    "battle": 2,
    "target": 1,
}


def _iter_inbound_callers(value: Mapping[str, Any] | None) -> Iterable[int]:
    for ref in (value or {}).get("refs", ()):
        raw = ref.get("sourceFunctionRva")
        if raw is not None:
            yield int(raw)


def _caller_anchor_map(native: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    """Map exact inbound callers to the known item/ability anchors they reach."""
    callers: dict[int, dict[str, Any]] = {}
    allowed = set(ITEM_COMMIT_ANCHORS)
    for row in native.get("needles", ()):
        needle = str(row.get("needle", ""))
        if needle not in allowed:
            continue
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                if xref.get("candidateFunctionSource") != "pdata":
                    continue
                for caller in _iter_inbound_callers(
                    xref.get("candidateFunctionInboundCodeRefs")
                ):
                    bucket = callers.setdefault(caller, {
                        "anchorNeedles": set(),
                        "provenance": set(),
                    })
                    bucket["anchorNeedles"].add(needle)
                    bucket["provenance"].add("direct-owner-inbound")
                for code_ref in (xref.get("candidateFunctionCodeRefs") or {}).get("refs", ()):
                    target_rva = code_ref.get("targetFunctionRva")
                    if target_rva is None:
                        continue
                    for caller in _iter_inbound_callers(
                        code_ref.get("targetFunctionInboundCodeRefs")
                    ):
                        bucket = callers.setdefault(caller, {
                            "anchorNeedles": set(),
                            "provenance": set(),
                        })
                        bucket["anchorNeedles"].add(needle)
                        bucket["provenance"].add("next-hop-target-inbound")

    return {
        rva: {
            "anchorNeedles": sorted(row["anchorNeedles"]),
            "provenance": sorted(row["provenance"]),
        }
        for rva, row in sorted(callers.items())
    }


def _ascii_string(data: bytes, offset: int) -> str | None:
    end = min(len(data), offset + MAX_STRING_BYTES)
    chars = bytearray()
    for cursor in range(offset, end):
        byte = data[cursor]
        if byte == 0:
            break
        if byte < 0x20 or byte > 0x7E:
            return None
        chars.append(byte)
    else:
        return None
    if len(chars) < MIN_PRINTABLE_LENGTH:
        return None
    return chars.decode("ascii")


def _utf16_ascii_string(data: bytes, offset: int) -> str | None:
    end = min(len(data), offset + MAX_STRING_BYTES)
    chars: list[str] = []
    cursor = offset
    while cursor + 1 < end:
        low = data[cursor]
        high = data[cursor + 1]
        if low == 0 and high == 0:
            break
        if high != 0 or low < 0x20 or low > 0x7E:
            return None
        chars.append(chr(low))
        cursor += 2
    else:
        return None
    if len(chars) < MIN_PRINTABLE_LENGTH:
        return None
    return "".join(chars)


def _decode_string_target(image: PEImage, target_rva: int) -> dict[str, Any] | None:
    section = image.section_for_rva(target_rva)
    if section is None or section.name.casefold() == ".text":
        return None
    offset = image.rva_to_offset(target_rva)
    if offset is None:
        return None
    ascii_text = _ascii_string(image.data, offset)
    utf16_text = _utf16_ascii_string(image.data, offset)
    if ascii_text is None and utf16_text is None:
        return None
    # ASCII is preferred when both decoders happen to succeed at the same byte.
    text = ascii_text if ascii_text is not None else utf16_text
    encoding = "ascii" if ascii_text is not None else "utf16le"
    return {
        "targetRva": target_rva,
        "targetVa": image.image_base + target_rva,
        "section": section.name,
        "encoding": encoding,
        "text": text,
    }


def _function_string_refs(image: PEImage, function_rva: int) -> dict[str, Any]:
    """Scan one exact .pdata function for common RIP-relative LEA string refs."""
    function = image.runtime_function_for_rva(int(function_rva))
    if function is None or function.begin_rva != int(function_rva):
        return {
            "functionRva": int(function_rva),
            "exactPdataFunction": False,
            "refs": [],
            "refsTruncated": False,
            "rangeTruncated": False,
        }
    text = image.section(".text")
    if text is None or not (
        text.virtual_address <= function.begin_rva < function.end_rva
        <= text.virtual_address + text.mapped_size
    ):
        return {
            "functionRva": function.begin_rva,
            "exactPdataFunction": True,
            "refs": [],
            "refsTruncated": False,
            "rangeTruncated": False,
        }

    start_relative = function.begin_rva - text.virtual_address
    end_relative = function.end_rva - text.virtual_address
    if start_relative < 0 or start_relative >= text.raw_size:
        raw = b""
    else:
        end_relative = min(end_relative, text.raw_size)
        raw = image.data[
            text.raw_offset + start_relative:
            text.raw_offset + end_relative
        ]

    refs: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    truncated = False
    for index in range(max(0, len(raw) - 6)):
        rex = raw[index]
        if not (0x48 <= rex <= 0x4F) or raw[index + 1] != 0x8D:
            continue
        modrm = raw[index + 2]
        if modrm & 0xC7 != 0x05:
            continue
        displacement = struct.unpack_from("<i", raw, index + 3)[0]
        instruction_rva = function.begin_rva + index
        target_rva = instruction_rva + 7 + displacement
        decoded = _decode_string_target(image, target_rva)
        if decoded is None:
            continue
        key = (target_rva, decoded["encoding"], decoded["text"])
        if key in seen:
            continue
        seen.add(key)
        refs.append({
            "instructionRva": instruction_rva,
            "instructionVa": image.image_base + instruction_rva,
            **decoded,
        })
        if len(refs) >= MAX_STRING_REFS_PER_FUNCTION:
            truncated = True
            break

    return {
        "functionRva": function.begin_rva,
        "functionVa": image.image_base + function.begin_rva,
        "functionEndRva": function.end_rva,
        "functionEndVa": image.image_base + function.end_rva,
        "exactPdataFunction": True,
        "byteCount": len(raw),
        "rangeTruncated": function.begin_rva + len(raw) < function.end_rva,
        "refsTruncated": truncated,
        "refs": refs,
    }


def _lead_score(text: str) -> tuple[int, list[str]]:
    folded = text.casefold()
    matched = sorted(token for token in LEAD_TOKENS if token in folded)
    return sum(LEAD_TOKENS[token] for token in matched), matched


def analyze_item_commit_caller_strings(
    image: PEImage,
    native: Mapping[str, Any],
) -> dict[str, Any]:
    """Enumerate/rank co-referenced strings from exact item/ability callers."""
    caller_map = _caller_anchor_map(native)
    caller_rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = {}
    any_truncated = False

    for caller_rva, anchor_info in caller_map.items():
        scanned = _function_string_refs(image, caller_rva)
        any_truncated = any_truncated or bool(
            scanned.get("refsTruncated") or scanned.get("rangeTruncated")
        )
        ranked_refs = []
        for ref in scanned.get("refs", ()):
            score, tokens = _lead_score(str(ref.get("text", "")))
            ranked_ref = {**ref, "leadScore": score, "matchedLeadTokens": tokens}
            ranked_refs.append(ranked_ref)
            if score <= 0:
                continue
            key = str(ref["text"])
            bucket = aggregate.setdefault(key, {
                "text": key,
                "leadScore": score,
                "matchedLeadTokens": set(tokens),
                "callerFunctions": set(),
                "anchorNeedles": set(),
                "provenance": set(),
                "locations": [],
            })
            bucket["leadScore"] = max(int(bucket["leadScore"]), score)
            bucket["matchedLeadTokens"].update(tokens)
            bucket["callerFunctions"].add(caller_rva)
            bucket["anchorNeedles"].update(anchor_info["anchorNeedles"])
            bucket["provenance"].update(anchor_info["provenance"])
            bucket["locations"].append({
                "callerFunctionRva": caller_rva,
                "instructionRva": ref["instructionRva"],
                "targetRva": ref["targetRva"],
                "section": ref["section"],
                "encoding": ref["encoding"],
            })

        ranked_refs.sort(key=lambda row: (-row["leadScore"], row["text"], row["targetRva"]))
        caller_rows.append({
            **scanned,
            "anchorNeedles": anchor_info["anchorNeedles"],
            "anchorCount": len(anchor_info["anchorNeedles"]),
            "provenance": anchor_info["provenance"],
            "multiAnchorCaller": len(anchor_info["anchorNeedles"]) >= 2,
            "rankedStringRefs": ranked_refs,
        })

    leads = []
    anchor_names = {name.casefold() for name in ITEM_COMMIT_ANCHORS}
    for row in aggregate.values():
        # Keep known anchor names out of the discovery ranking; they are useful
        # in per-caller evidence but cannot be the missing commit-path discovery.
        if str(row["text"]).casefold() in anchor_names:
            continue
        caller_count = len(row["callerFunctions"])
        anchor_count = len(row["anchorNeedles"])
        leads.append({
            "text": row["text"],
            "leadScore": row["leadScore"],
            "supportCallerCount": caller_count,
            "supportAnchorCount": anchor_count,
            "matchedLeadTokens": sorted(row["matchedLeadTokens"]),
            "callerFunctions": sorted(row["callerFunctions"]),
            "anchorNeedles": sorted(row["anchorNeedles"]),
            "provenance": sorted(row["provenance"]),
            "locations": sorted(
                row["locations"],
                key=lambda location: (
                    location["callerFunctionRva"],
                    location["instructionRva"],
                    location["targetRva"],
                ),
            ),
        })
    leads.sort(key=lambda row: (
        -row["supportAnchorCount"],
        -row["supportCallerCount"],
        -row["leadScore"],
        row["text"].casefold(),
    ))

    exact_callers = sum(row.get("exactPdataFunction", False) for row in caller_rows)
    multi_anchor_callers = sum(row["multiAnchorCaller"] for row in caller_rows)
    return {
        "implementationReady": False,
        "playerItemCommandCommitValidated": False,
        "anchorNeedles": list(ITEM_COMMIT_ANCHORS),
        "callerCandidateCount": len(caller_rows),
        "exactPdataCallerCount": exact_callers,
        "multiAnchorCallerCount": multi_anchor_callers,
        "callerStringEvidenceTruncated": any_truncated,
        "callers": caller_rows,
        "rankedReflectedNameLeadCount": len(leads),
        "rankedReflectedNameLeads": leads[:MAX_RANKED_LEADS],
        "rankedReflectedNameLeadsTruncated": len(leads) > MAX_RANKED_LEADS,
        "blockers": [
            "player-item-command-commit-hook-unresolved",
            "ranked-name-leads-require-installed-disassembly-validation",
        ],
        "notes": [
            "Only inbound caller function RVAs already resolved through exact AMD64 .pdata metadata are scanned.",
            "Only common RIP-relative LEA forms resolving to printable strings in non-.text sections are reported; this is deliberately not a full x86-64 disassembler.",
            "Ranked names are manual reverse-engineering leads. Co-reference does not prove execution order, call semantics, ABI, player-vs-AI ownership, or hook safety.",
            "A caller shared by multiple item/ability anchor families is stronger locality evidence but still cannot validate the human Items-menu commit path by itself.",
            "The probe is read-only and never modifies the installed executable.",
        ],
    }


def probe_item_commit_callers(game_root: Path) -> dict[str, Any]:
    """Run the caller-string discovery against one installed FF7R executable."""
    root = Path(game_root)
    exe = root / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    image = PEImage.from_bytes(data)
    native = probe_installed_exe(root, needles=ITEM_COMMIT_ANCHORS)
    analysis = analyze_item_commit_caller_strings(image, native)
    return {
        "path": str(exe),
        "size": len(data),
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "native": native,
        "analysis": analysis,
    }

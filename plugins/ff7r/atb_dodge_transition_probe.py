"""Read-only dodge-transition call sequencing for FF7R ATB Tweaks (#425).

The existing ATB probe can show that exact callers/functions are shared between
``IsDodge`` candidates and ``SetATB`` candidates, but overlap alone cannot prove
a once-per-roll transition. This stage inspects only exact `.pdata` common caller
bounds for direct ``call rel32`` instructions that resolve to the known dodge and
ATB-set function candidates, then reports their order and whether a recognizable
conditional jump lies between them.

The scan is intentionally narrow and does not perform general x86-64 decoding.
A dodge-call -> branch -> SetATB-call sequence is a high-value disassembly lead,
not proof of branch condition, edge timing, subtraction semantics or hook safety.
"""

from __future__ import annotations

from pathlib import Path
import struct
from typing import Any, Mapping

from .atb_runtime_probe import ATB_NATIVE_NEEDLES, assess_atb_runtime_evidence
from .native_probe import EXE_RELATIVE_PATH, PEImage, probe_installed_exe


DODGE_NEEDLES = ("IsDodge", "IsDodgeInvincible")
ATB_SET_NEEDLES = ("SetATB", "SetATBAll", "ForceUpdateATBGauge")
MAX_REPORTED_CALLS = 256
MAX_REPORTED_PAIRS = 128
MAX_SEQUENCE_GAP = 512


def _expanded(
    evidence: Mapping[str, Any], needles: tuple[str, ...], field: str
) -> set[int]:
    result: set[int] = set()
    for needle in needles:
        row = evidence.get(needle, {})
        if isinstance(row, Mapping):
            result.update(int(value) for value in row.get(field, ()))
    return result


def _function_bytes(image: PEImage, function_rva: int) -> tuple[bytes, int | None]:
    function = image.runtime_function_for_rva(int(function_rva))
    if function is None or function.begin_rva != int(function_rva):
        return b"", None
    text = image.section(".text")
    if text is None:
        return b"", function.end_rva
    if not (
        text.virtual_address <= function.begin_rva < function.end_rva
        <= text.virtual_address + text.mapped_size
    ):
        return b"", function.end_rva
    start = function.begin_rva - text.virtual_address
    end = min(function.end_rva - text.virtual_address, text.raw_size)
    if start < 0 or start >= text.raw_size or end <= start:
        return b"", function.end_rva
    return image.data[text.raw_offset + start:text.raw_offset + end], function.end_rva


def _scan_direct_calls(
    image: PEImage,
    function_rva: int,
    dodge_targets: set[int],
    atb_targets: set[int],
) -> dict[str, Any]:
    raw, function_end = _function_bytes(image, function_rva)
    if function_end is None:
        return {
            "functionRva": int(function_rva),
            "exactPdataFunction": False,
            "calls": [],
            "callsTruncated": False,
        }
    calls: list[dict[str, Any]] = []
    truncated = False
    for index in range(max(0, len(raw) - 4)):
        if raw[index] != 0xE8:
            continue
        displacement = struct.unpack_from("<i", raw, index + 1)[0]
        instruction_rva = int(function_rva) + index
        target_rva = instruction_rva + 5 + displacement
        roles = []
        if target_rva in dodge_targets:
            roles.append("dodge-predicate")
        if target_rva in atb_targets:
            roles.append("atb-set")
        if not roles:
            continue
        calls.append({
            "instructionRva": instruction_rva,
            "instructionVa": image.image_base + instruction_rva,
            "targetRva": target_rva,
            "targetVa": image.image_base + target_rva,
            "roles": roles,
        })
        if len(calls) >= MAX_REPORTED_CALLS:
            truncated = True
            break
    return {
        "functionRva": int(function_rva),
        "functionVa": image.image_base + int(function_rva),
        "functionEndRva": function_end,
        "exactPdataFunction": True,
        "byteCount": len(raw),
        "calls": calls,
        "callsTruncated": truncated,
    }


def _conditional_branches_between(
    raw: bytes,
    function_rva: int,
    start_rva: int,
    end_rva: int,
) -> list[dict[str, Any]]:
    start = max(0, int(start_rva) - int(function_rva))
    end = min(len(raw), int(end_rva) - int(function_rva))
    if end <= start:
        return []
    branches: list[dict[str, Any]] = []
    index = start
    while index < end:
        opcode = raw[index]
        instruction_rva = int(function_rva) + index
        if 0x70 <= opcode <= 0x7F and index + 1 < end:
            displacement = struct.unpack_from("<b", raw, index + 1)[0]
            branches.append({
                "instructionRva": instruction_rva,
                "encoding": "jcc-rel8",
                "opcode": opcode,
                "targetRva": instruction_rva + 2 + displacement,
            })
            index += 2
            continue
        if (
            opcode == 0x0F
            and index + 5 < end
            and 0x80 <= raw[index + 1] <= 0x8F
        ):
            displacement = struct.unpack_from("<i", raw, index + 2)[0]
            branches.append({
                "instructionRva": instruction_rva,
                "encoding": "jcc-rel32",
                "opcode": raw[index + 1],
                "targetRva": instruction_rva + 6 + displacement,
            })
            index += 6
            continue
        index += 1
    return branches


def analyze_dodge_atb_call_sequences(
    image: PEImage,
    atb_assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Report exact common callers and dodge→SetATB ordering evidence."""
    runtime = atb_assessment.get("runtimeResearch", {})
    evidence = (
        runtime.get("nativeFunctionEvidence", {})
        if isinstance(runtime, Mapping) else {}
    )
    if not isinstance(evidence, Mapping):
        evidence = {}

    dodge_targets = _expanded(evidence, DODGE_NEEDLES, "expandedPdataFunctions")
    atb_targets = _expanded(evidence, ATB_SET_NEEDLES, "expandedPdataFunctions")
    dodge_callers = _expanded(
        evidence, DODGE_NEEDLES, "expandedInboundCallerFunctions"
    )
    atb_callers = _expanded(
        evidence, ATB_SET_NEEDLES, "expandedInboundCallerFunctions"
    )
    common_callers = sorted(dodge_callers & atb_callers)

    caller_rows: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    any_truncated = False
    for caller_rva in common_callers:
        scan = _scan_direct_calls(
            image, caller_rva, dodge_targets, atb_targets
        )
        any_truncated = any_truncated or bool(scan.get("callsTruncated"))
        raw, _ = _function_bytes(image, caller_rva)
        calls = list(scan.get("calls", ()))
        dodge_calls = [
            call for call in calls if "dodge-predicate" in call.get("roles", ())
        ]
        atb_calls = [
            call for call in calls if "atb-set" in call.get("roles", ())
        ]
        local_pairs = []
        for dodge in dodge_calls:
            for atb in atb_calls:
                gap = int(atb["instructionRva"]) - int(dodge["instructionRva"])
                if abs(gap) > MAX_SEQUENCE_GAP:
                    continue
                if gap > 0:
                    branches = _conditional_branches_between(
                        raw,
                        caller_rva,
                        int(dodge["instructionRva"]) + 5,
                        int(atb["instructionRva"]),
                    )
                else:
                    branches = []
                row = {
                    "callerFunctionRva": caller_rva,
                    "dodgeCallRva": dodge["instructionRva"],
                    "dodgeTargetRva": dodge["targetRva"],
                    "atbCallRva": atb["instructionRva"],
                    "atbTargetRva": atb["targetRva"],
                    "atbCallAfterDodgeCall": gap > 0,
                    "byteGap": gap,
                    "conditionalBranchBetween": bool(branches),
                    "conditionalBranches": branches,
                    "preferredTransitionLead": bool(gap > 0 and branches),
                }
                local_pairs.append(row)
                pairs.append(row)
                if len(pairs) >= MAX_REPORTED_PAIRS:
                    any_truncated = True
                    break
            if len(pairs) >= MAX_REPORTED_PAIRS:
                break
        caller_rows.append({
            **scan,
            "dodgeCallCount": len(dodge_calls),
            "atbSetCallCount": len(atb_calls),
            "sequencePairCount": len(local_pairs),
            "sequencePairs": local_pairs,
        })
        if len(pairs) >= MAX_REPORTED_PAIRS:
            break

    preferred = [row for row in pairs if row["preferredTransitionLead"]]
    return {
        "implementationReady": False,
        "dodgeTransitionValidated": False,
        "oncePerDodgeEdgeValidated": False,
        "atbSubtractionSemanticsValidated": False,
        "dodgeTargetFunctions": sorted(dodge_targets),
        "atbSetTargetFunctions": sorted(atb_targets),
        "commonCallerCount": len(common_callers),
        "commonCallers": common_callers,
        "callerEvidence": caller_rows,
        "sequencePairCount": len(pairs),
        "sequencePairs": pairs,
        "preferredTransitionLeadCount": len(preferred),
        "preferredTransitionLeads": preferred,
        "sequenceEvidenceTruncated": any_truncated,
        "blockers": [
            "dodge-transition-edge-unvalidated",
            "once-per-dodge-edge-semantics-unvalidated",
            "dodge-atb-subtraction-semantics-unvalidated",
            "candidate-dodge-atb-call-sequence-requires-installed-disassembly-validation",
        ],
        "notes": [
            "Only exact .pdata callers shared by known dodge-predicate candidates and SetATB-family candidates are scanned.",
            "Only direct E8 rel32 calls resolving exactly to those known target RVAs are reported. Other call encodings are omitted rather than guessed.",
            "A recognizable conditional jump between a dodge-target call and a later SetATB-target call is a high-value control-flow lead, but this narrow byte scanner does not prove the jump condition or that both calls are on the same executed path.",
            "Even an apparent dodge→branch→SetATB sequence cannot establish once-per-roll behavior, subtraction direction/units, player ownership or disabled-tweak isolation without installed disassembly and runtime tracing.",
            "A valid roll reduction must trigger on the dodge transition edge once, preserve the normal ATB floor/cap rules, and never continuously drain while IsDodge remains true.",
            "This stage is read-only and never modifies the executable.",
        ],
    }


def probe_dodge_atb_call_sequences(game_root: Path) -> dict[str, Any]:
    """Run dodge/SetATB call-order discovery against one installed FF7R EXE."""
    root = Path(game_root).resolve()
    exe = root / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    image = PEImage.from_bytes(data)
    native = probe_installed_exe(root, needles=ATB_NATIVE_NEEDLES)
    assessment = assess_atb_runtime_evidence(native)
    transition = analyze_dodge_atb_call_sequences(image, assessment)
    return {
        "path": str(exe),
        "size": len(data),
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "assessment": assessment,
        "dodgeTransitionResearch": transition,
    }

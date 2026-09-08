"""Read-only final-HP recalculation call sequencing for FF7R #427.

The HP source probe separates composed status, max/current reads and max/current
writes, but a reflected setter or a shared registration owner is not the
requested authority. This stage looks one level outward: exact `.pdata` callers
shared by two or more HP roles are scanned for direct `call rel32` instructions
that resolve exactly to those known role targets.

A caller that actually invokes composed-status construction, max-HP write and
current-HP read/write APIs is a strong manual-disassembly lead for the final
recalculation/clamp transaction. It still does not prove formula, call arguments,
playable-only scope, rounding or current-HP preservation semantics.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import struct
from typing import Any, Mapping

from .atb_dodge_transition_probe import _function_bytes
from .hp_rebalance_probe import (
    NATIVE_NEEDLES,
    PLAYER_CURRENT_READ_NEEDLES,
    PLAYER_CURRENT_WRITE_NEEDLES,
    PLAYER_MAX_READ_NEEDLES,
    PLAYER_MAX_WRITE_NEEDLES,
    STATUS_NEEDLES,
    assess_hp_native_evidence,
)
from .native_probe import EXE_RELATIVE_PATH, PEImage, probe_installed_exe


ROLE_NEEDLES = {
    "composed-status": STATUS_NEEDLES,
    "max-read": PLAYER_MAX_READ_NEEDLES,
    "current-read": PLAYER_CURRENT_READ_NEEDLES,
    "max-write": PLAYER_MAX_WRITE_NEEDLES,
    "current-write": PLAYER_CURRENT_WRITE_NEEDLES,
}
MAX_REPORTED_CALLS = 256
MAX_REPORTED_CALLERS = 128


def _expanded(
    evidence: Mapping[str, Any], needles: tuple[str, ...], field: str
) -> set[int]:
    result: set[int] = set()
    for needle in needles:
        row = evidence.get(needle, {})
        if isinstance(row, Mapping):
            result.update(int(value) for value in row.get(field, ()))
    return result


def _role_sets(evidence: Mapping[str, Any], field: str) -> dict[str, set[int]]:
    return {
        role: _expanded(evidence, needles, field)
        for role, needles in ROLE_NEEDLES.items()
    }


def _candidate_callers(caller_roles: Mapping[str, set[int]]) -> dict[int, list[str]]:
    by_caller: dict[int, set[str]] = defaultdict(set)
    for role, callers in caller_roles.items():
        for caller in callers:
            by_caller[int(caller)].add(role)
    return {
        caller: sorted(roles)
        for caller, roles in sorted(by_caller.items())
        if len(roles) >= 2
    }


def _scan_role_calls(
    image: PEImage,
    caller_rva: int,
    target_roles: Mapping[str, set[int]],
) -> dict[str, Any]:
    raw, function_end = _function_bytes(image, caller_rva)
    if function_end is None:
        return {
            "functionRva": int(caller_rva),
            "exactPdataFunction": False,
            "calls": [],
            "callsTruncated": False,
        }
    roles_by_target: dict[int, set[str]] = defaultdict(set)
    for role, targets in target_roles.items():
        for target in targets:
            roles_by_target[int(target)].add(role)

    calls: list[dict[str, Any]] = []
    truncated = False
    for index in range(max(0, len(raw) - 4)):
        if raw[index] != 0xE8:
            continue
        displacement = struct.unpack_from("<i", raw, index + 1)[0]
        instruction_rva = int(caller_rva) + index
        target_rva = instruction_rva + 5 + displacement
        roles = sorted(roles_by_target.get(target_rva, ()))
        if not roles:
            continue
        calls.append({
            "instructionRva": instruction_rva,
            "instructionVa": image.image_base + instruction_rva,
            "targetRva": target_rva,
            "targetVa": image.image_base + target_rva,
            "roles": roles,
            "multiRoleTarget": len(roles) >= 2,
        })
        if len(calls) >= MAX_REPORTED_CALLS:
            truncated = True
            break
    return {
        "functionRva": int(caller_rva),
        "functionVa": image.image_base + int(caller_rva),
        "functionEndRva": function_end,
        "exactPdataFunction": True,
        "byteCount": len(raw),
        "calls": calls,
        "callsTruncated": truncated,
    }


def _ordered_pair(calls: list[Mapping[str, Any]], before_role: str, after_role: str) -> bool:
    before = [
        int(call["instructionRva"])
        for call in calls if before_role in call.get("roles", ())
    ]
    after = [
        int(call["instructionRva"])
        for call in calls if after_role in call.get("roles", ())
    ]
    return any(left < right for left in before for right in after)


def analyze_hp_recalc_call_sequences(
    image: PEImage,
    native_assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Identify exact multi-role callers and their observed direct HP API calls."""
    evidence = native_assessment.get("functionEvidence", {})
    if not isinstance(evidence, Mapping):
        evidence = {}
    target_roles = _role_sets(evidence, "expandedPdataFunctions")
    caller_roles = _role_sets(evidence, "expandedInboundCallerFunctions")
    candidates = _candidate_callers(caller_roles)

    target_role_counts: dict[int, set[str]] = defaultdict(set)
    for role, targets in target_roles.items():
        for target in targets:
            target_role_counts[int(target)].add(role)
    multi_role_targets = {
        rva: sorted(roles)
        for rva, roles in sorted(target_role_counts.items())
        if len(roles) >= 2
    }

    rows: list[dict[str, Any]] = []
    any_truncated = False
    for caller_rva, correlated_roles in list(candidates.items())[:MAX_REPORTED_CALLERS]:
        scan = _scan_role_calls(image, caller_rva, target_roles)
        any_truncated = any_truncated or bool(scan.get("callsTruncated"))
        calls = list(scan.get("calls", ()))
        observed_roles = sorted({
            role for call in calls for role in call.get("roles", ())
        })
        status_then_max_write = _ordered_pair(
            calls, "composed-status", "max-write"
        )
        current_read_then_write = _ordered_pair(
            calls, "current-read", "current-write"
        )
        max_read_then_write = _ordered_pair(calls, "max-read", "max-write")
        role_set = set(observed_roles)
        clamp_neighborhood = {"current-read", "current-write"}.issubset(role_set)
        full_transaction = {
            "composed-status", "max-write", "current-read", "current-write"
        }.issubset(role_set)
        collision_in_calls = any(bool(call["multiRoleTarget"]) for call in calls)
        preferred = bool(
            scan.get("exactPdataFunction")
            and status_then_max_write
            and clamp_neighborhood
            and not collision_in_calls
        )
        rows.append({
            **scan,
            "correlatedCallerRoles": correlated_roles,
            "observedCallRoles": observed_roles,
            "statusThenMaxWrite": status_then_max_write,
            "maxReadThenMaxWrite": max_read_then_write,
            "currentReadThenCurrentWrite": current_read_then_write,
            "currentClampNeighborhood": clamp_neighborhood,
            "fullRecalcClampNeighborhood": full_transaction,
            "multiRoleTargetCollisionInCalls": collision_in_calls,
            "preferredRecalculationLead": preferred,
        })

    rows.sort(key=lambda row: (
        not bool(row["preferredRecalculationLead"]),
        not bool(row["fullRecalcClampNeighborhood"]),
        -len(row["observedCallRoles"]),
        int(row["functionRva"]),
    ))
    preferred = [row for row in rows if row["preferredRecalculationLead"]]
    full = [row for row in rows if row["fullRecalcClampNeighborhood"]]
    return {
        "implementationReady": False,
        "authoritativeMaxHPRecalculationValidated": False,
        "playableOnlyScopeValidated": False,
        "finalComposedValueValidated": False,
        "currentHPClampSemanticsValidated": False,
        "roleTargetFunctions": {
            role: sorted(targets) for role, targets in target_roles.items()
        },
        "roleInboundCallerFunctions": {
            role: sorted(callers) for role, callers in caller_roles.items()
        },
        "multiRoleTargetFunctions": multi_role_targets,
        "candidateCallerCount": len(candidates),
        "candidateCallersTruncated": len(candidates) > MAX_REPORTED_CALLERS,
        "candidateCallerEvidence": rows,
        "preferredRecalculationLeadCount": len(preferred),
        "preferredRecalculationLeads": preferred,
        "fullRecalcClampNeighborhoodCount": len(full),
        "callEvidenceTruncated": any_truncated,
        "blockers": [
            "authoritative-max-hp-recalculation-interception-unvalidated",
            "final-composed-player-max-hp-value-unvalidated",
            "playable-only-scope-unvalidated",
            "current-hp-clamp-semantics-unvalidated",
            "candidate-hp-recalculation-call-sequence-requires-installed-disassembly-validation",
        ],
        "notes": [
            "Candidate callers must already be exact .pdata inbound callers shared by at least two independently classified HP roles.",
            "Only direct E8 rel32 calls resolving exactly to known HP role target RVAs are reported; indirect/virtual calls are intentionally omitted rather than guessed.",
            "A status-call before max-write plus current-read/current-write calls in the same exact caller is a strong transaction lead, not proof of arguments, formula, player identity, rounding or clamp policy.",
            "Targets that satisfy multiple HP roles are reported as multi-role collisions; calls through those targets prevent preferred-lead promotion because registration/shared glue remains plausible.",
            "The requested implementation must scale the final composed playable-party max HP after equipment/materia/weapon effects, exclude enemies/non-playable entities, and clamp/preserve current HP according to explicitly validated semantics.",
            "This stage is read-only and never modifies the executable.",
        ],
    }


def probe_hp_recalc_call_sequences(game_root: Path) -> dict[str, Any]:
    """Run HP recalculation transaction discovery against one installed FF7R EXE."""
    root = Path(game_root).resolve()
    exe = root / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    image = PEImage.from_bytes(data)
    native = probe_installed_exe(root, needles=NATIVE_NEEDLES)
    assessment = assess_hp_native_evidence(native)
    sequence = analyze_hp_recalc_call_sequences(image, assessment)
    return {
        "path": str(exe),
        "size": len(data),
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "nativeAssessment": assessment,
        "recalculationSequenceResearch": sequence,
    }

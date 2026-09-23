"""Read-only movement-predicate research for FF7R ATB Tweaks (#425).

The requested movement multiplier must apply only while the player is actually
moving and must modify passive/normal ATB restoration at the authoritative
accumulator. Rather than guessing reflected names such as ``IsMoving``, this
stage reuses two independently bounded evidence sets already present in Lexeditor:

* exact ATB accumulator/accessor owners, one-hop targets and callers; and
* exact Better-Sprint dash-state/root-motion owners, targets and callers.

It reports direct function overlap and shared exact callers, then optionally
ranks movement-looking printable strings in only those bridge functions. This is
locality evidence, not proof of a movement predicate or ATB write path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .atb_runtime_probe import (
    ACCUMULATOR_NEEDLES,
    ATB_NATIVE_NEEDLES,
    assess_atb_runtime_evidence,
)
from .dog_whistle_commit_probe import _function_string_refs
from .native_probe import EXE_RELATIVE_PATH, PEImage, probe_installed_exe
from .sprint_probe import SPRINT_NATIVE_NEEDLES, assess_sprint_evidence


ATB_MOVEMENT_NEEDLES = (
    "SetATB",
    "GetATB",
    "GetATBMax",
    *ACCUMULATOR_NEEDLES,
)
MOVEMENT_NAME_WEIGHTS = {
    "movement": 10,
    "moving": 10,
    "velocity": 9,
    "locomotion": 9,
    "stationary": 9,
    "idle": 8,
    "dash": 6,
    "run": 5,
    "rootmotion": 5,
    "translation": 4,
    "input": 3,
    "speed": 3,
    "atb": 2,
}
MAX_RANKED_LEADS = 128


def _expanded(
    evidence: Mapping[str, Any],
    needles: tuple[str, ...],
    field: str,
) -> set[int]:
    result: set[int] = set()
    for needle in needles:
        row = evidence.get(needle, {})
        if isinstance(row, Mapping):
            result.update(int(value) for value in row.get(field, ()))
    return result


def _name_score(text: str) -> tuple[int, list[str]]:
    compact = str(text).casefold().replace("_", "").replace(" ", "")
    matched = sorted(
        token for token in MOVEMENT_NAME_WEIGHTS
        if token in compact
    )
    return sum(MOVEMENT_NAME_WEIGHTS[token] for token in matched), matched


def correlate_atb_movement_evidence(
    atb_assessment: Mapping[str, Any],
    sprint_assessment: Mapping[str, Any],
    *,
    image: PEImage | None = None,
) -> dict[str, Any]:
    """Correlate exact ATB and locomotion function/caller neighborhoods."""
    atb_runtime = atb_assessment.get("runtimeResearch", {})
    atb_evidence = (
        atb_runtime.get("nativeFunctionEvidence", {})
        if isinstance(atb_runtime, Mapping) else {}
    )
    sprint_evidence = sprint_assessment.get("nativeFunctionEvidence", {})
    if not isinstance(atb_evidence, Mapping):
        atb_evidence = {}
    if not isinstance(sprint_evidence, Mapping):
        sprint_evidence = {}

    atb_functions = _expanded(
        atb_evidence, ATB_MOVEMENT_NEEDLES, "expandedPdataFunctions"
    )
    atb_callers = _expanded(
        atb_evidence, ATB_MOVEMENT_NEEDLES, "expandedInboundCallerFunctions"
    )
    sprint_functions = _expanded(
        sprint_evidence, SPRINT_NATIVE_NEEDLES, "expandedPdataFunctions"
    )
    sprint_callers = _expanded(
        sprint_evidence, SPRINT_NATIVE_NEEDLES, "expandedInboundCallerFunctions"
    )

    shared_functions = sorted(atb_functions & sprint_functions)
    shared_callers = sorted(atb_callers & sprint_callers)
    bridge_rvas = sorted(set(shared_functions) | set(shared_callers))

    function_rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = {}
    any_truncated = False
    if image is not None:
        known_names = {
            *(needle.casefold() for needle in ATB_NATIVE_NEEDLES),
            *(needle.casefold() for needle in SPRINT_NATIVE_NEEDLES),
        }
        for rva in bridge_rvas:
            scan = _function_string_refs(image, rva)
            any_truncated = any_truncated or bool(
                scan.get("refsTruncated") or scan.get("rangeTruncated")
            )
            origins = []
            if rva in shared_functions:
                origins.append("shared-function")
            if rva in shared_callers:
                origins.append("shared-inbound-caller")
            ranked = []
            for ref in scan.get("refs", ()):
                text = str(ref.get("text", ""))
                score, tokens = _name_score(text)
                row = {
                    **ref,
                    "movementLeadScore": score,
                    "matchedMovementTokens": tokens,
                }
                ranked.append(row)
                if score <= 0 or text.casefold() in known_names:
                    continue
                bucket = aggregate.setdefault(text, {
                    "text": text,
                    "movementLeadScore": score,
                    "matchedMovementTokens": set(tokens),
                    "functionRvas": set(),
                    "origins": set(),
                    "locations": [],
                })
                bucket["movementLeadScore"] = max(
                    int(bucket["movementLeadScore"]), score
                )
                bucket["matchedMovementTokens"].update(tokens)
                bucket["functionRvas"].add(rva)
                bucket["origins"].update(origins)
                bucket["locations"].append({
                    "functionRva": rva,
                    "instructionRva": ref.get("instructionRva"),
                    "targetRva": ref.get("targetRva"),
                    "encoding": ref.get("encoding"),
                    "section": ref.get("section"),
                })
            ranked.sort(key=lambda row: (
                -int(row["movementLeadScore"]),
                str(row["text"]).casefold(),
                int(row["targetRva"]),
            ))
            function_rows.append({
                "functionRva": rva,
                "origins": origins,
                "exactPdataFunction": bool(scan.get("exactPdataFunction")),
                "functionEndRva": scan.get("functionEndRva"),
                "refsTruncated": bool(scan.get("refsTruncated")),
                "rangeTruncated": bool(scan.get("rangeTruncated")),
                "rankedStringRefs": ranked,
            })

    name_leads = []
    for row in aggregate.values():
        name_leads.append({
            "text": row["text"],
            "movementLeadScore": row["movementLeadScore"],
            "matchedMovementTokens": sorted(row["matchedMovementTokens"]),
            "supportFunctionCount": len(row["functionRvas"]),
            "functionRvas": sorted(row["functionRvas"]),
            "supportOrigins": sorted(row["origins"]),
            "locations": sorted(
                row["locations"],
                key=lambda location: (
                    int(location["functionRva"]),
                    int(location["instructionRva"]),
                    int(location["targetRva"]),
                ),
            ),
        })
    name_leads.sort(key=lambda row: (
        -int(row["supportFunctionCount"]),
        -int(row["movementLeadScore"]),
        str(row["text"]).casefold(),
    ))

    return {
        "implementationReady": False,
        "movementPredicateValidated": False,
        "movementToATBAccumulatorLinkValidated": False,
        "sharedFunctionCount": len(shared_functions),
        "sharedFunctions": shared_functions,
        "sharedInboundCallerCount": len(shared_callers),
        "sharedInboundCallers": shared_callers,
        "bridgeFunctionCount": len(bridge_rvas),
        "bridgeFunctions": bridge_rvas,
        "bridgeStringEvidenceTruncated": any_truncated,
        "bridgeFunctionEvidence": function_rows,
        "rankedMovementNameLeadCount": len(name_leads),
        "rankedMovementNameLeads": name_leads[:MAX_RANKED_LEADS],
        "rankedMovementNameLeadsTruncated": len(name_leads) > MAX_RANKED_LEADS,
        "blockers": [
            "authoritative-player-movement-predicate-unvalidated",
            "movement-to-atb-accumulator-link-unvalidated",
            "idle-vs-moving-atb-runtime-comparison-unvalidated",
            "candidate-movement-bridge-requires-installed-disassembly-validation",
        ],
        "notes": [
            "ATB-side candidates are exact Set/Get/Max/accumulator .pdata functions and exact inbound callers; movement-side candidates are the exact dash-state/root-motion function and caller neighborhoods already used by Better Sprint.",
            "A shared exact function is stronger locality evidence than a shared caller, but neither proves that the function evaluates player movement or updates ATB.",
            "The optional string scan is limited to bridge RVAs and common RIP-relative printable references; names such as Movement/Velocity/Idle/Dash are ranking hints only.",
            "Sprint/root-motion evidence is intentionally not equated with generic moving-vs-stationary state. Walking, jogging and non-root-motion locomotion must still be covered by runtime validation.",
            "A valid implementation must measure the authoritative player movement state at the passive/normal ATB accumulator and leave attack/guard/scripted gains unchanged unless explicitly configured.",
            "This stage is read-only and never modifies the executable.",
        ],
    }


def probe_atb_movement_bridge(game_root: Path) -> dict[str, Any]:
    """Run ATB↔locomotion correlation against one installed FF7R executable."""
    root = Path(game_root).resolve()
    exe = root / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    image = PEImage.from_bytes(data)
    needles = tuple(dict.fromkeys((*ATB_NATIVE_NEEDLES, *SPRINT_NATIVE_NEEDLES)))
    native = probe_installed_exe(root, needles=needles)
    atb = assess_atb_runtime_evidence(native)
    sprint = assess_sprint_evidence(native, [])
    bridge = correlate_atb_movement_evidence(atb, sprint, image=image)
    return {
        "path": str(exe),
        "size": len(data),
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "atbAssessment": atb,
        "movementAssessment": sprint,
        "movementBridge": bridge,
    }

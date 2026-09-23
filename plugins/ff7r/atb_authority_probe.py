"""Read-only installed-build narrowing for FF7R ATB Tweaks (#425).

The main ATB runtime probe already provides exact `.pdata` owners, bounded
one-hop targets, cross-family clusters and common inbound callers around ATB
accessors, accumulator, Dexterity, hit and dodge anchors. This stage inspects only
those exact function leads for two additional kinds of evidence:

* RIP-relative printable string references, ranked for ATB/gauge/rate/hit/dodge
  terminology; and
* a deliberately narrow set of RIP-relative scalar SSE float operands whose
  values match documented vanilla ATB fingerprints (1000/2000 internal units,
  0.35 AI passive, 0.1 guard, 1.4 Haste, 0.6 Slow, etc.).

Neither co-referenced names nor matching constants validate units, formulas,
event granularity, transition edges or a safe write hook. The scanner is a
bounded reverse-engineering aid, not a general x86-64 disassembler.
"""

from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
import struct
from typing import Any, Mapping

from .atb_runtime_probe import (
    ACCUMULATOR_NEEDLES,
    ATB_NATIVE_NEEDLES,
    DOCUMENTED_VANILLA_ATB_REFERENCES,
    HIT_EVENT_NEEDLES,
    assess_atb_runtime_evidence,
)
from .dog_whistle_commit_probe import _function_string_refs
from .native_probe import EXE_RELATIVE_PATH, PEImage, probe_installed_exe


MAX_RANKED_LEADS = 128
MAX_FLOAT_REFS_PER_FUNCTION = 128
HIGH_VALUE_ANCHORS = (
    "SetATB",
    "GetATB",
    "GetATBMax",
    *ACCUMULATOR_NEEDLES,
    "BPGetPlayerDexterity",
    "GetResidentParameterFloatBP",
    "HitBonusATBRecoverAdd",
    "IsDodge",
    "IsDodgeInvincible",
    *HIT_EVENT_NEEDLES,
)
NAME_TOKEN_WEIGHTS = {
    "atb": 12,
    "gauge": 9,
    "dexterity": 8,
    "recover": 8,
    "charge": 7,
    "passive": 7,
    "haste": 7,
    "slow": 7,
    "speed": 6,
    "guard": 5,
    "dodge": 5,
    "hit": 4,
    "rate": 4,
    "time": 3,
    "add": 1,
}
SSE_SCALAR_OPCODES = {
    0x10: "movss",
    0x58: "addss",
    0x59: "mulss",
    0x5C: "subss",
    0x5E: "divss",
}

# Keep each label distinct even when two documented concepts currently share a
# value. The report can therefore say which fingerprints a constant is
# compatible with without pretending to know which semantic role it serves.
FINGERPRINTS = tuple(
    (name, float(value))
    for name, value in DOCUMENTED_VANILLA_ATB_REFERENCES.items()
)


def _name_score(text: str) -> tuple[int, list[str]]:
    compact = str(text).casefold().replace("_", "").replace(" ", "")
    matched = sorted(token for token in NAME_TOKEN_WEIGHTS if token in compact)
    return sum(NAME_TOKEN_WEIGHTS[token] for token in matched), matched


def _fingerprint_labels(value: float) -> list[str]:
    if not math.isfinite(value):
        return []
    labels = []
    for name, expected in FINGERPRINTS:
        tolerance = max(1e-6, abs(expected) * 1e-6)
        if math.isclose(value, expected, rel_tol=0.0, abs_tol=tolerance):
            labels.append(name)
    return sorted(labels)


def _candidate_functions(assessment: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    runtime = assessment.get("runtimeResearch", {})
    if not isinstance(runtime, Mapping):
        return {}
    candidates: dict[int, dict[str, Any]] = {}

    def ensure(rva: int) -> dict[str, Any]:
        return candidates.setdefault(rva, {
            "functionRva": rva,
            "origins": set(),
            "families": set(),
            "anchorNeedles": set(),
            "registrationCollisionRisk": False,
            "crossFamily": False,
        })

    for cluster in runtime.get("nativeFunctionClusters", ()):
        if not isinstance(cluster, Mapping):
            continue
        raw_rva = cluster.get("functionRva")
        if raw_rva is None:
            continue
        rva = int(raw_rva)
        row = ensure(rva)
        row["origins"].add("function-cluster")
        row["families"].update(str(value) for value in cluster.get("families", ()))
        row["anchorNeedles"].update(str(value) for value in cluster.get("directNeedles", ()))
        row["anchorNeedles"].update(str(value) for value in cluster.get("nextHopNeedles", ()))
        row["registrationCollisionRisk"] = bool(
            row["registrationCollisionRisk"] or cluster.get("registrationCollisionRisk")
        )
        row["crossFamily"] = bool(row["crossFamily"] or cluster.get("crossFamily"))

    correlations = runtime.get("nativeFunctionCorrelations", {})
    if isinstance(correlations, Mapping):
        for name, raw_rvas in correlations.items():
            for raw_rva in raw_rvas or ():
                rva = int(raw_rva)
                row = ensure(rva)
                row["origins"].add(f"correlation:{name}")

    evidence = runtime.get("nativeFunctionEvidence", {})
    if isinstance(evidence, Mapping):
        for needle in HIGH_VALUE_ANCHORS:
            needle_evidence = evidence.get(needle, {})
            if not isinstance(needle_evidence, Mapping):
                continue
            for raw_rva in needle_evidence.get("expandedPdataFunctions", ()):
                rva = int(raw_rva)
                row = ensure(rva)
                row["origins"].add(f"anchor:{needle}")
                row["anchorNeedles"].add(needle)

    result: dict[int, dict[str, Any]] = {}
    for rva, row in sorted(candidates.items()):
        correlated = any(
            str(origin).startswith("correlation:") for origin in row["origins"]
        )
        preferred = bool(
            not row["registrationCollisionRisk"]
            and (row["crossFamily"] or correlated)
        )
        result[rva] = {
            "functionRva": rva,
            "origins": sorted(row["origins"]),
            "families": sorted(row["families"]),
            "anchorNeedles": sorted(row["anchorNeedles"]),
            "registrationCollisionRisk": bool(row["registrationCollisionRisk"]),
            "crossFamily": bool(row["crossFamily"]),
            "correlated": correlated,
            "preferredManualLead": preferred,
        }
    return result


def _function_float_refs(image: PEImage, function_rva: int) -> dict[str, Any]:
    """Scan one exact .pdata function for narrow scalar-SSE RIP-relative operands."""
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
    seen: set[tuple[int, int]] = set()
    truncated = False
    # Exact narrow form: F3 0F <scalar-op> <ModRM RIP+disp32>.
    # This intentionally omits REX/prefix variants rather than guessing their
    # boundaries. False negatives are preferable to fabricated precision here.
    for index in range(max(0, len(raw) - 7)):
        if raw[index] != 0xF3 or raw[index + 1] != 0x0F:
            continue
        opcode = raw[index + 2]
        operation = SSE_SCALAR_OPCODES.get(opcode)
        if operation is None:
            continue
        modrm = raw[index + 3]
        if modrm & 0xC7 != 0x05:
            continue
        displacement = struct.unpack_from("<i", raw, index + 4)[0]
        instruction_rva = function.begin_rva + index
        target_rva = instruction_rva + 8 + displacement
        target_section = image.section_for_rva(target_rva)
        if target_section is None or target_section.name.casefold() == ".text":
            continue
        target_offset = image.rva_to_offset(target_rva)
        if target_offset is None or target_offset + 4 > len(image.data):
            continue
        key = (target_rva, opcode)
        if key in seen:
            continue
        seen.add(key)
        value = struct.unpack_from("<f", image.data, target_offset)[0]
        if not math.isfinite(value):
            continue
        labels = _fingerprint_labels(value)
        refs.append({
            "instructionRva": instruction_rva,
            "instructionVa": image.image_base + instruction_rva,
            "operation": operation,
            "targetRva": target_rva,
            "targetVa": image.image_base + target_rva,
            "section": target_section.name,
            "floatValue": value,
            "rawHex": image.data[target_offset:target_offset + 4].hex(),
            "fingerprintLabels": labels,
            "matchesDocumentedFingerprint": bool(labels),
        })
        if len(refs) >= MAX_FLOAT_REFS_PER_FUNCTION:
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


def analyze_atb_authority_refs(
    image: PEImage,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Rank exact-function ATB names and documented scalar fingerprints."""
    candidates = _candidate_functions(assessment)
    function_rows: list[dict[str, Any]] = []
    name_aggregate: dict[str, dict[str, Any]] = {}
    fingerprint_rows: list[dict[str, Any]] = []
    known_names = {needle.casefold() for needle in ATB_NATIVE_NEEDLES}
    any_truncated = False

    for rva, provenance in candidates.items():
        string_scan = _function_string_refs(image, rva)
        float_scan = _function_float_refs(image, rva)
        any_truncated = any_truncated or bool(
            string_scan.get("refsTruncated")
            or string_scan.get("rangeTruncated")
            or float_scan.get("refsTruncated")
            or float_scan.get("rangeTruncated")
        )

        ranked_strings = []
        for ref in string_scan.get("refs", ()):
            text = str(ref.get("text", ""))
            score, tokens = _name_score(text)
            ranked = {**ref, "authorityLeadScore": score, "matchedAuthorityTokens": tokens}
            ranked_strings.append(ranked)
            if score <= 0 or text.casefold() in known_names:
                continue
            bucket = name_aggregate.setdefault(text, {
                "text": text,
                "authorityLeadScore": score,
                "matchedAuthorityTokens": set(tokens),
                "functionRvas": set(),
                "origins": set(),
                "families": set(),
                "preferredSupportCount": 0,
                "locations": [],
            })
            bucket["authorityLeadScore"] = max(int(bucket["authorityLeadScore"]), score)
            bucket["matchedAuthorityTokens"].update(tokens)
            bucket["functionRvas"].add(rva)
            bucket["origins"].update(provenance["origins"])
            bucket["families"].update(provenance["families"])
            if provenance["preferredManualLead"]:
                bucket["preferredSupportCount"] += 1
            bucket["locations"].append({
                "functionRva": rva,
                "instructionRva": ref.get("instructionRva"),
                "targetRva": ref.get("targetRva"),
                "encoding": ref.get("encoding"),
                "section": ref.get("section"),
            })

        ranked_strings.sort(key=lambda row: (
            -int(row["authorityLeadScore"]),
            str(row["text"]).casefold(),
            int(row["targetRva"]),
        ))
        floats = list(float_scan.get("refs", ()))
        for ref in floats:
            if not ref["matchesDocumentedFingerprint"]:
                continue
            fingerprint_rows.append({
                **ref,
                "functionRva": rva,
                "origins": provenance["origins"],
                "families": provenance["families"],
                "anchorNeedles": provenance["anchorNeedles"],
                "preferredManualLead": provenance["preferredManualLead"],
            })

        function_rows.append({
            **provenance,
            "exactPdataFunction": bool(string_scan.get("exactPdataFunction")),
            "functionEndRva": string_scan.get("functionEndRva"),
            "byteCount": string_scan.get("byteCount", 0),
            "stringRefsTruncated": bool(string_scan.get("refsTruncated")),
            "floatRefsTruncated": bool(float_scan.get("refsTruncated")),
            "rangeTruncated": bool(
                string_scan.get("rangeTruncated") or float_scan.get("rangeTruncated")
            ),
            "rankedStringRefs": ranked_strings,
            "floatRefs": floats,
            "documentedFingerprintRefCount": sum(
                bool(ref["matchesDocumentedFingerprint"]) for ref in floats
            ),
        })

    name_leads = []
    for row in name_aggregate.values():
        name_leads.append({
            "text": row["text"],
            "authorityLeadScore": row["authorityLeadScore"],
            "matchedAuthorityTokens": sorted(row["matchedAuthorityTokens"]),
            "supportFunctionCount": len(row["functionRvas"]),
            "functionRvas": sorted(row["functionRvas"]),
            "supportOrigins": sorted(row["origins"]),
            "supportFamilies": sorted(row["families"]),
            "preferredSupportCount": row["preferredSupportCount"],
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
        -int(row["preferredSupportCount"]),
        -int(row["supportFunctionCount"]),
        -int(row["authorityLeadScore"]),
        str(row["text"]).casefold(),
    ))
    fingerprint_rows.sort(key=lambda row: (
        not bool(row["preferredManualLead"]),
        int(row["functionRva"]),
        int(row["instructionRva"]),
        float(row["floatValue"]),
    ))

    preferred_count = sum(row["preferredManualLead"] for row in function_rows)
    return {
        "implementationReady": False,
        "unitsValidated": False,
        "passiveFormulaValidated": False,
        "speedFormulaValidated": False,
        "hitFormulaValidated": False,
        "hitEventGranularityValidated": False,
        "dodgeTransitionValidated": False,
        "candidateFunctionCount": len(function_rows),
        "preferredManualCandidateCount": preferred_count,
        "functionEvidenceTruncated": any_truncated,
        "functions": function_rows,
        "rankedAuthorityNameLeadCount": len(name_leads),
        "rankedAuthorityNameLeads": name_leads[:MAX_RANKED_LEADS],
        "rankedAuthorityNameLeadsTruncated": len(name_leads) > MAX_RANKED_LEADS,
        "documentedFingerprintReferenceCount": len(fingerprint_rows),
        "documentedFingerprintReferences": fingerprint_rows[:MAX_RANKED_LEADS],
        "documentedFingerprintReferencesTruncated": len(fingerprint_rows) > MAX_RANKED_LEADS,
        "documentedVanillaReference": dict(DOCUMENTED_VANILLA_ATB_REFERENCES),
        "blockers": [
            "atb-accumulator-semantics-unvalidated",
            "atb-unit-contract-unvalidated",
            "speed-atb-formula-unvalidated",
            "hit-atb-formula-unvalidated",
            "hit-atb-event-granularity-unvalidated",
            "dodge-transition-edge-unvalidated",
            "candidate-atb-names-and-constants-require-installed-disassembly-validation",
        ],
        "notes": [
            "Candidate functions are limited to the main probe's exact .pdata high-value anchors, cross-family clusters and exact function/caller correlations.",
            "Preferred manual leads require a cross-family or correlation provenance and reject direct multi-name registration-collision owners.",
            "The float scanner recognizes only the narrow no-REX `F3 0F {movss,addss,mulss,subss,divss} /r` RIP-relative form inside exact .pdata bounds. Unsupported forms are omitted rather than guessed.",
            "A scalar constant equal to 1000, 2000, 1.0, 0.35, 0.1, 0.0, 1.4 or 0.6 is only compatible with one or more documented fingerprints. Common constants can occur for unrelated reasons and never validate ATB units or formula terms by themselves.",
            "Ranked string names are likewise locality evidence only; ABI, player/AI ownership, displayed/internal unit conversion, per-hit vs per-action semantics and dodge transition timing still require installed disassembly/runtime validation.",
            "This stage is read-only and never modifies the executable.",
        ],
    }


def probe_atb_authority_refs(game_root: Path) -> dict[str, Any]:
    """Run exact-function ATB name/constant discovery against one installed EXE."""
    root = Path(game_root).resolve()
    exe = root / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    image = PEImage.from_bytes(data)
    native = probe_installed_exe(root, needles=ATB_NATIVE_NEEDLES)
    assessment = assess_atb_runtime_evidence(native)
    authority = analyze_atb_authority_refs(image, assessment)
    return {
        "path": str(exe),
        "size": len(data),
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "assessment": assessment,
        "authorityDiscovery": authority,
    }

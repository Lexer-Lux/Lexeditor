"""Read-only native discovery for FF7R Better Sprint's authority path (#430).

The main sprint probe already correlates exact `.pdata` functions across dash
scale/state and root-motion families, and separately reports exact common inbound
callers. Those RVAs are much better places to look for an authoritative movement
path than guessed global byte signatures.

This stage scans only those exact function/caller leads for RIP-relative printable
strings and ranks velocity/displacement/speed/movement-style names. It reuses the
bounded exact-function scanner from the Dog Whistle reverse-engineering stage.
A promising co-reference is still not a validated hook: ABI, write semantics,
player ownership and sprint-only isolation all remain runtime acceptance gates.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from .dog_whistle_commit_probe import _function_string_refs
from .native_probe import EXE_RELATIVE_PATH, PEImage, probe_installed_exe
from .sprint_probe import SPRINT_NATIVE_NEEDLES, assess_sprint_evidence


MAX_RANKED_LEADS = 128
AUTHORITY_TOKEN_WEIGHTS = {
    "sprint": 12,
    "velocity": 11,
    "displacement": 11,
    "maxwalkspeed": 10,
    "movementspeed": 10,
    "acceleration": 8,
    "speed": 7,
    "movement": 6,
    "translation": 5,
    "distance": 5,
    "dash": 4,
    "rootmotion": 3,
    "move": 2,
}


def _token_score(text: str) -> tuple[int, list[str]]:
    compact = str(text).casefold().replace("_", "").replace(" ", "")
    matched = sorted(
        token for token in AUTHORITY_TOKEN_WEIGHTS
        if token in compact
    )
    return sum(AUTHORITY_TOKEN_WEIGHTS[token] for token in matched), matched


def _candidate_functions(assessment: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    candidates: dict[int, dict[str, Any]] = {}

    for cluster in assessment.get("nativeFunctionClusters", ()):
        if not isinstance(cluster, Mapping) or not cluster.get("crossFamily"):
            continue
        rva = int(cluster.get("functionRva", -1))
        if rva < 0:
            continue
        row = candidates.setdefault(rva, {
            "functionRva": rva,
            "origins": set(),
            "families": set(),
            "directNeedles": set(),
            "nextHopNeedles": set(),
            "registrationCollisionRisk": False,
            "threeFamily": False,
        })
        row["origins"].add("cross-family-function-cluster")
        row["families"].update(str(value) for value in cluster.get("families", ()))
        row["directNeedles"].update(str(value) for value in cluster.get("directNeedles", ()))
        row["nextHopNeedles"].update(str(value) for value in cluster.get("nextHopNeedles", ()))
        row["registrationCollisionRisk"] = bool(
            row["registrationCollisionRisk"] or cluster.get("registrationCollisionRisk")
        )
        row["threeFamily"] = bool(
            row["threeFamily"] or cluster.get("allThreeFamilies")
        )

    correlations = assessment.get("nativeFunctionCorrelations", {})
    if isinstance(correlations, Mapping):
        for name, raw_rvas in correlations.items():
            if not str(name).endswith("Callers"):
                continue
            for raw_rva in raw_rvas or ():
                rva = int(raw_rva)
                row = candidates.setdefault(rva, {
                    "functionRva": rva,
                    "origins": set(),
                    "families": set(),
                    "directNeedles": set(),
                    "nextHopNeedles": set(),
                    "registrationCollisionRisk": False,
                    "threeFamily": False,
                })
                row["origins"].add(f"common-inbound:{name}")

    return {
        rva: {
            "functionRva": rva,
            "origins": sorted(row["origins"]),
            "families": sorted(row["families"]),
            "directNeedles": sorted(row["directNeedles"]),
            "nextHopNeedles": sorted(row["nextHopNeedles"]),
            "registrationCollisionRisk": bool(row["registrationCollisionRisk"]),
            "threeFamily": bool(row["threeFamily"]),
            "preferredManualLead": bool(
                (row["nextHopNeedles"] or len(row["origins"]) >= 2)
                and not row["registrationCollisionRisk"]
            ),
        }
        for rva, row in sorted(candidates.items())
    }


def analyze_sprint_authority_strings(
    image: PEImage,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Rank movement-authority-looking strings from exact sprint function leads."""
    candidates = _candidate_functions(assessment)
    function_rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = {}
    known = {needle.casefold() for needle in SPRINT_NATIVE_NEEDLES}
    any_truncated = False

    for rva, provenance in candidates.items():
        scanned = _function_string_refs(image, rva)
        any_truncated = any_truncated or bool(
            scanned.get("refsTruncated") or scanned.get("rangeTruncated")
        )
        refs = []
        for ref in scanned.get("refs", ()):
            text = str(ref.get("text", ""))
            score, tokens = _token_score(text)
            ranked = {**ref, "authorityLeadScore": score, "matchedAuthorityTokens": tokens}
            refs.append(ranked)
            if score <= 0 or text.casefold() in known:
                continue
            bucket = aggregate.setdefault(text, {
                "text": text,
                "authorityLeadScore": score,
                "matchedAuthorityTokens": set(tokens),
                "functionRvas": set(),
                "origins": set(),
                "families": set(),
                "preferredSupportCount": 0,
                "locations": [],
            })
            bucket["authorityLeadScore"] = max(
                int(bucket["authorityLeadScore"]), score
            )
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
        refs.sort(key=lambda row: (
            -int(row["authorityLeadScore"]),
            str(row["text"]).casefold(),
            int(row["targetRva"]),
        ))
        function_rows.append({
            **provenance,
            "exactPdataFunction": bool(scanned.get("exactPdataFunction")),
            "functionEndRva": scanned.get("functionEndRva"),
            "byteCount": scanned.get("byteCount", 0),
            "refsTruncated": bool(scanned.get("refsTruncated")),
            "rangeTruncated": bool(scanned.get("rangeTruncated")),
            "rankedStringRefs": refs,
        })

    leads = []
    for row in aggregate.values():
        leads.append({
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
                key=lambda item: (
                    int(item["functionRva"]),
                    int(item["instructionRva"]),
                    int(item["targetRva"]),
                ),
            ),
        })
    leads.sort(key=lambda row: (
        -int(row["preferredSupportCount"]),
        -int(row["supportFunctionCount"]),
        -int(row["authorityLeadScore"]),
        str(row["text"]).casefold(),
    ))

    exact_count = sum(row["exactPdataFunction"] for row in function_rows)
    preferred_count = sum(row["preferredManualLead"] for row in function_rows)
    return {
        "implementationReady": False,
        "sprintSpeedAuthorityValidated": False,
        "candidateFunctionCount": len(function_rows),
        "exactPdataCandidateFunctionCount": exact_count,
        "preferredManualCandidateCount": preferred_count,
        "functionStringEvidenceTruncated": any_truncated,
        "functions": function_rows,
        "rankedAuthorityLeadCount": len(leads),
        "rankedAuthorityLeads": leads[:MAX_RANKED_LEADS],
        "rankedAuthorityLeadsTruncated": len(leads) > MAX_RANKED_LEADS,
        "blockers": [
            "authoritative-player-sprint-speed-path-unvalidated",
            "candidate-authority-names-require-installed-disassembly-validation",
            "walk-jog-scripted-movement-isolation-unvalidated",
            "playable-character-relative-speed-preservation-unvalidated",
        ],
        "notes": [
            "Candidate RVAs come only from the existing exact cross-family .pdata sprint clusters or exact common inbound-caller correlations.",
            "The string scanner is bounded to exact .pdata function ranges and common RIP-relative LEA references into printable non-code data.",
            "Velocity/displacement/speed/movement-looking names are ranking hints for manual installed-build disassembly; co-reference alone does not prove a write path or execution semantics.",
            "Registration-collision-risk functions remain visible but are not marked preferred manual leads.",
            "Even a high-scoring name must be proved player-owned and sprint-only, and the final hook must preserve walk/jog/scripted movement and relative playable-character speeds.",
            "This stage is read-only and never modifies the executable.",
        ],
    }


def probe_sprint_authority_strings(game_root: Path) -> dict[str, Any]:
    """Run the authority-name discovery against one installed executable."""
    root = Path(game_root).resolve()
    exe = root / EXE_RELATIVE_PATH
    if not exe.is_file():
        raise FileNotFoundError(f"FF7R executable was not found: {exe}")
    data = exe.read_bytes()
    image = PEImage.from_bytes(data)
    native = probe_installed_exe(root, needles=SPRINT_NATIVE_NEEDLES)
    assessment = assess_sprint_evidence(native, [])
    authority = analyze_sprint_authority_strings(image, assessment)
    return {
        "path": str(exe),
        "size": len(data),
        "timestamp": image.timestamp,
        "timestampHex": f"0x{image.timestamp:08X}",
        "assessment": assessment,
        "authorityDiscovery": authority,
    }

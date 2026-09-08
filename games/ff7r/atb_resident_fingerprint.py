"""Fail-closed semantic fingerprints for FF7R ResidentParameter ATB rows (#425).

Public Remake mod documentation independently reports the vanilla state
coefficients used by ResidentParameter: Player 1.0, PlayerAI 0.35, ActionAI
0.25, Guard 0.1, and Caution/Action/Damage/Dodge/SuspendAction 0.0. Values alone
are not identities, so this classifier also requires semantic tokens in the
installed row tag and a float-valued ResidentParameter field.

A unique tag+value match is still a high-confidence research candidate, not a
claim that Lexeditor has validated the runtime meaning or units on this build.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable


VALUE_TOLERANCE = 1e-6

SEMANTIC_FINGERPRINTS: dict[str, dict[str, Any]] = {
    "player-passive": {
        "expected": 1.0,
        "required": ("atb", "player"),
        "forbidden": ("ai", "action", "guard", "damage", "dodge", "suspend", "caution"),
        "label": "Player passive ATB state coefficient",
    },
    "ai-passive": {
        "expected": 0.35,
        "required": ("atb", "player", "ai"),
        "forbidden": ("action", "guard", "damage", "dodge", "suspend", "caution"),
        "label": "AI-controlled player passive ATB state coefficient",
    },
    "action-ai": {
        "expected": 0.25,
        "required": ("atb", "action", "ai"),
        "forbidden": (),
        "label": "AI action-state ATB coefficient",
    },
    "guard": {
        "expected": 0.1,
        "required": ("atb", "guard"),
        "forbidden": (),
        "label": "Guarding ATB state coefficient",
    },
    "caution": {
        "expected": 0.0,
        "required": ("atb", "caution"),
        "forbidden": (),
        "label": "Caution-state ATB coefficient",
    },
    "action": {
        "expected": 0.0,
        "required": ("atb", "action"),
        "forbidden": ("ai", "suspend"),
        "label": "Player action-state ATB coefficient",
    },
    "damage": {
        "expected": 0.0,
        "required": ("atb", "damage"),
        "forbidden": (),
        "label": "Damage-state ATB coefficient",
    },
    "dodge": {
        "expected": 0.0,
        "required": ("atb", "dodge"),
        "forbidden": (),
        "label": "Dodge-state ATB coefficient",
    },
    "suspend-action": {
        "expected": 0.0,
        "required": ("atb", "suspend", "action"),
        "forbidden": (),
        "label": "Suspend-action ATB coefficient",
    },
}


def _tag_words(tag: str) -> tuple[str, ...]:
    """Split separators, CamelCase, and acronym-to-word boundaries."""
    expanded = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", str(tag))
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", expanded)
    return tuple(
        token.casefold()
        for token in re.findall(r"[A-Za-z]+|\d+", expanded)
    )


def _tag_matches(words: tuple[str, ...], spec: dict[str, Any]) -> bool:
    tokens = set(words)
    return all(token in tokens for token in spec["required"]) and not any(
        token in tokens for token in spec["forbidden"]
    )


def _numeric_value(row: dict[str, Any]) -> float | None:
    if str(row.get("property", "")) != "ParamFloat":
        return None
    value = row.get("vanilla")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def classify_resident_atb_fingerprints(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Require semantic row-tag tokens plus the documented vanilla value."""
    source_rows = [dict(row) for row in rows]
    results: dict[str, dict[str, Any]] = {}
    for semantic, spec in SEMANTIC_FINGERPRINTS.items():
        tag_candidates = []
        fingerprint_matches = []
        for row in source_rows:
            words = _tag_words(str(row.get("tag", "")))
            if not _tag_matches(words, spec):
                continue
            value = _numeric_value(row)
            candidate = {
                "key": row.get("key"),
                "tag": row.get("tag"),
                "property": row.get("property"),
                "vanilla": row.get("vanilla"),
                "tagWords": list(words),
            }
            tag_candidates.append(candidate)
            if value is not None and abs(value - float(spec["expected"])) <= VALUE_TOLERANCE:
                fingerprint_matches.append(candidate)
        unique = len(fingerprint_matches) == 1
        results[semantic] = {
            "label": spec["label"],
            "documentedVanilla": float(spec["expected"]),
            "tagCandidates": tag_candidates,
            "fingerprintMatches": fingerprint_matches,
            "uniqueFingerprintMatch": unique,
            "candidate": fingerprint_matches[0] if unique else None,
            "runtimeSemanticsValidated": False,
            "editableAsNamedSemantic": False,
            "status": (
                "unique-tag-and-value-research-candidate"
                if unique
                else "ambiguous-tag-and-value-candidates"
                if len(fingerprint_matches) > 1
                else "tag-candidate-value-mismatch"
                if tag_candidates
                else "semantic-tag-not-found"
            ),
        }

    unique = [name for name, row in results.items() if row["uniqueFingerprintMatch"]]
    ambiguous = [
        name for name, row in results.items()
        if len(row["fingerprintMatches"]) > 1
    ]
    return {
        "semantics": results,
        "uniqueFingerprintCount": len(unique),
        "uniqueFingerprintSemantics": unique,
        "ambiguousFingerprintSemantics": ambiguous,
        "runtimeSemanticsValidated": False,
        "notes": [
            "The documented vanilla values are independent validation fingerprints, never row identities by themselves.",
            "A row must use ParamFloat, contain all required semantic tag tokens, contain none of the forbidden tokens, and match the documented vanilla value before it becomes a unique research candidate.",
            "Even a unique tag+value candidate remains read-only research until an installed runtime path proves that row controls the named ATB term and establishes units/composition.",
            "Zero-valued state rows are especially collision-prone; no zero value is promoted without the semantic tag-token gate.",
        ],
    }

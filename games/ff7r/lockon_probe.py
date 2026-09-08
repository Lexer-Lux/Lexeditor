"""Read-only installed-build research for the FF7R Better Lock-on tweak.

The tweak is presentation-only: remove the small ``LOCK ON`` label and tint the
active lock-on reticle red without touching target selection or camera behavior.
Remake exposes a dedicated battle lock-on marker widget/API in its reflected
runtime surface, so this probe ranks cooked UI assets against those narrow
anchors instead of treating generic target/lock strings as sufficient evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .native_probe import probe_installed_exe
from .raw_asset_probe import probe_installed_assets


ASSET_TERMS = ("lockon", "lock_on", "battlelock")
WIDGET_ANCHORS = (
    "EndBattleLockonMarkerIcon",
    "BattleLockonMarker",
)
API_ANCHORS = (
    "BPShowBattleLockonMarkerIcon",
    "EEndMenuLockonMarkerType",
)
PRESENTATION_TERMS = (
    "ColorAndOpacity",
    "SlateColor",
    "Color",
    "Tint",
    "Brush",
    "Image",
    "Opacity",
    "Visibility",
    "Visible",
    "Hidden",
    "Text",
)
INTERESTING_TOKENS = WIDGET_ANCHORS + API_ANCHORS + PRESENTATION_TERMS + (
    "LOCK ON",
    "LockOn",
    "Marker",
    "Reticle",
    "Crosshair",
)
NATIVE_NEEDLES = (
    "BPShowBattleLockonMarkerIcon",
    "BattleLockonMarker",
    "EndBattleLockonMarkerIcon",
    "EEndMenuLockonMarkerType",
)


def _flatten_strings(asset: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_row in asset.get("files", ()):
        suffix = str(file_row.get("suffix", ""))
        path = str(file_row.get("path", ""))
        for string_row in file_row.get("interestingStrings", ()):
            rows.append({"suffix": suffix, "path": path, **string_row})
    return rows


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    folded = value.casefold()
    return any(str(term).casefold() in folded for term in terms)


def _literal_lock_on_label(value: str) -> bool:
    # Class/API names such as EndBattleLockonMarkerIcon must not count as label
    # evidence. Only a standalone printable label candidate qualifies here.
    normalized = " ".join(value.strip().casefold().replace("-", " ").split())
    return normalized in {"lock on", "lockon"}


def rank_lockon_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank cooked assets; exact widget + presentation evidence dominates noise."""
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        strings = _flatten_strings(asset)
        widget_hits = [row for row in strings if _contains_any(str(row.get("text", "")), WIDGET_ANCHORS)]
        api_hits = [row for row in strings if _contains_any(str(row.get("text", "")), API_ANCHORS)]
        presentation_hits = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), PRESENTATION_TERMS)
        ]
        label_hits = [
            row for row in strings
            if _literal_lock_on_label(str(row.get("text", "")))
        ]
        if not widget_hits and not api_hits and not label_hits:
            continue

        score = (
            len(widget_hits) * 1200
            + len(api_hits) * 500
            + len(label_hits) * 1600
            + min(len(presentation_hits), 32) * 30
        )
        if widget_hits and presentation_hits:
            score += 1800
        if widget_hits and label_hits:
            score += 3500

        ranked.append({
            **asset,
            "widgetAnchorHits": widget_hits,
            "apiAnchorHits": api_hits,
            "literalLockOnLabelHits": label_hits,
            "presentationPropertyHits": presentation_hits,
            "containsDedicatedWidgetAnchor": bool(widget_hits),
            "containsLiteralLockOnLabel": bool(label_hits),
            "strongPresentationCandidate": bool(widget_hits and presentation_hits),
            "score": score,
        })

    return sorted(
        ranked,
        key=lambda row: (-int(row["score"]), str(row.get("asset", "")).casefold()),
    )


def probe_better_lockon_sources(game_root: Path) -> dict[str, Any]:
    """Inspect installed cooked UI assets and reflected native anchors read-only."""
    raw = probe_installed_assets(
        Path(game_root),
        terms=ASSET_TERMS,
        interesting_tokens=INTERESTING_TOKENS,
    )
    ranked = rank_lockon_assets(raw.get("assets", ()))
    native = probe_installed_exe(Path(game_root), needles=NATIVE_NEEDLES)
    return {
        "candidates": ranked,
        "native": native,
        "scanErrors": list(raw.get("scanErrors", ())),
        "implementationReady": False,
        "knownContracts": {
            "widgetClass": "UEndBattleLockonMarkerIcon",
            "widgetSetting": "UEndMenuSettings::BattleLockonMarker",
            "showFunction": "UEndMenuAPI::BPShowBattleLockonMarkerIcon",
            "markerType": "EEndMenuLockonMarkerType",
        },
        "notes": [
            "The dedicated battle lock-on marker widget is the preferred presentation owner; generic battle target widgets are not assumed equivalent.",
            "A standalone LOCK ON string is label evidence only when tied to the same cooked presentation asset; class names containing Lockon do not count as label evidence.",
            "Color/tint/brush/visibility strings rank candidates but do not prove which widget child owns the reticle or label.",
            "No UI asset is rewritten by this probe; an exact cooked widget/property owner must be validated before implementing suppression/tinting.",
        ],
    }

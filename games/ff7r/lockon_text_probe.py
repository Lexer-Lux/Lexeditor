"""Read-only localized-text research for Better Lock-on (#429).

A long-standing Remake UI mod reports that removing the Lock On battle prompt
modifies ``Resident_TxtRes.uexp`` while the small blue target square lives
elsewhere.  Lexeditor can therefore research prompt suppression through its
normal text-resource parser without conflating that operation with reticle tint.

The US resource is used only to discover an exact ``LOCK ON`` text ID. Once one
unique ID is found, that *same ID* is correlated across every installed
Resident_TxtRes language, so translated strings do not need to equal the English
label. This module is read-only and never blanks text itself.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from .text_storage import load_text_package


RESIDENT_TEXT_BASENAME = "resident_txtres"
ANCHOR_LANGUAGE = "US"
ANCHOR_TEXT = "LOCK ON"
STATUS_TEXT = "LOCKED ON"


def _basename(asset: str) -> str:
    return PurePosixPath(str(asset)).name.casefold()


def _normalized(value: str) -> str:
    return " ".join(str(value).replace("\u00a0", " ").split()).casefold()


def _entry_rows(package, *, asset: str, language: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry_index, entry in enumerate(package.entries):
        rows.append({
            "asset": asset,
            "language": language,
            "entryIndex": entry_index,
            "subentryIndex": None,
            "textId": str(entry.id),
            "text": str(entry.text),
        })
        for sub_index, subentry in enumerate(entry.subentries):
            rows.append({
                "asset": asset,
                "language": language,
                "entryIndex": entry_index,
                "subentryIndex": sub_index,
                "textId": str(subentry.id),
                "text": str(subentry.text),
            })
    return rows


def discover_lockon_prompt_texts(
    game_root,
    data_root,
    project_root,
    index: dict,
    *,
    anchor_language: str = ANCHOR_LANGUAGE,
) -> dict[str, Any]:
    """Find one English prompt ID, then correlate that ID across languages."""
    anchor_language = str(anchor_language).upper()
    resources = [
        row for row in index.get("textAssets", ())
        if _basename(row.get("asset", "")) == RESIDENT_TEXT_BASENAME
    ]
    resources.sort(key=lambda row: (
        str(row.get("language", "")).upper(),
        str(row.get("asset", "")).casefold(),
    ))

    scanned: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in resources:
        asset = str(row.get("asset", ""))
        language = str(row.get("language", "")).upper()
        try:
            package, _active_uasset, _active_uexp, _using_project = load_text_package(
                game_root, data_root, project_root, index, asset, vanilla=True,
            )
        except Exception as error:
            errors.append(f"{language or 'unknown'} | {asset}: {error}")
            continue
        entries = _entry_rows(package, asset=asset, language=language)
        scanned.append({
            "asset": asset,
            "language": language,
            "entries": entries,
        })

    anchor_rows = [
        entry
        for resource in scanned
        if resource["language"] == anchor_language
        for entry in resource["entries"]
        if _normalized(entry["text"]) == _normalized(ANCHOR_TEXT)
    ]
    status_rows = [
        entry
        for resource in scanned
        if resource["language"] == anchor_language
        for entry in resource["entries"]
        if _normalized(entry["text"]) == _normalized(STATUS_TEXT)
    ]

    anchor_id = anchor_rows[0]["textId"] if len(anchor_rows) == 1 else ""
    localized_rows: list[dict[str, Any]] = []
    missing_languages: list[str] = []
    duplicate_languages: list[str] = []
    if anchor_id:
        for resource in scanned:
            matches = [
                entry for entry in resource["entries"]
                if entry["textId"] == anchor_id
            ]
            if len(matches) == 1:
                localized_rows.append(matches[0])
            elif not matches:
                missing_languages.append(resource["language"] or resource["asset"])
            else:
                duplicate_languages.append(resource["language"] or resource["asset"])

    blockers: list[str] = []
    if errors:
        blockers.append("resident-text-scan-errors")
    if not resources:
        blockers.append("resident-text-resources-not-found")
    if len(anchor_rows) == 0:
        blockers.append("exact-us-lock-on-label-not-found")
    elif len(anchor_rows) > 1:
        blockers.append("exact-us-lock-on-label-ambiguous")
    if anchor_id and missing_languages:
        blockers.append("lock-on-text-id-missing-in-localized-resource")
    if anchor_id and duplicate_languages:
        blockers.append("lock-on-text-id-duplicated-in-localized-resource")

    label_id_resolved = bool(
        anchor_id
        and not errors
        and not missing_languages
        and not duplicate_languages
        and len(localized_rows) == len(scanned)
    )
    return {
        "implementationReady": False,
        "labelTextIdResolved": label_id_resolved,
        "anchorLanguage": anchor_language,
        "anchorText": ANCHOR_TEXT,
        "anchorTextId": anchor_id,
        "anchorCandidates": anchor_rows,
        "lockedOnStatusCandidates": status_rows,
        "localizedPromptEntries": localized_rows,
        "residentTextResourceCount": len(resources),
        "scannedResourceCount": len(scanned),
        "missingLanguages": sorted(set(missing_languages)),
        "duplicateLanguages": sorted(set(duplicate_languages)),
        "scanErrors": errors,
        "blockers": blockers,
        "knownContracts": {
            "historicalResourceLead": "Resident_TxtRes.uexp",
            "writerSurface": "TextResourcePackage supports variable-length localized text edits with rebuild/readback",
            "reticleSeparation": "Prompt text ownership does not identify the small target-square/reticle asset",
        },
        "notes": [
            "Only an exact US 'LOCK ON' value is used to discover the prompt ID; partial/class-name matches are rejected.",
            "Once resolved, the same text ID is correlated across installed Resident_TxtRes languages, preserving localization-aware ownership even when the displayed phrase is translated.",
            "A separate exact 'LOCKED ON' status phrase is reported for diagnosis but is not treated as the small prompt requested for removal.",
            "This can prove the label half of #429 without proving or modifying the active-reticle tint path.",
        ],
    }

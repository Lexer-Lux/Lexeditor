"""Semantic low-to-high merge for supported ``menu/mngrp.bin`` units.

The file contains many unrelated menu assets.  A source is eligible for this
merge only when rebuilding its changed, proved text and refine units from the
vanilla file reproduces the complete source byte-for-byte.  Any other change
falls back to the normal opaque-path rule instead of being silently discarded.
"""

from __future__ import annotations

from . import mngrp_text, refine_tables


REFINE_FIELDS = ("text", "outputQuantity", "inputId", "inputQuantity", "outputId")


def _text_values(data: bytes) -> dict[tuple[int, int], str]:
    return {(int(row["sectionId"]), int(row["recordId"])): str(row["value"])
            for row in mngrp_text.rows(data)["rows"]}


def _refine_values(data: bytes) -> dict[tuple[str, int, str], object]:
    values = {}
    for table in refine_tables.read(data)["tables"]:
        for row in table["rows"]:
            for field in REFINE_FIELDS:
                values[(str(table["id"]), int(row["id"]), field)] = row[field]
    return values


def _extract(vanilla: bytes, source: bytes) -> tuple[dict[tuple, object] | None, str]:
    if len(source) != len(vanilla):
        return None, "file size differs from vanilla"
    vanilla_text, source_text = _text_values(vanilla), _text_values(source)
    vanilla_refine, source_refine = _refine_values(vanilla), _refine_values(source)
    changes: dict[tuple, object] = {}
    for key, value in source_text.items():
        if value != vanilla_text[key]:
            changes[("text", *key)] = value
    for key, value in source_refine.items():
        if value != vanilla_refine[key]:
            changes[("refine", *key)] = value

    text_edits = [{"source": "mngrp", "sectionId": key[1], "recordId": key[2],
                   "value": value}
                  for key, value in changes.items() if key[0] == "text"]
    rebuilt, _ = mngrp_text.apply_edits(vanilla, text_edits)
    refine_rows: dict[tuple[str, int], dict] = {}
    for key, value in changes.items():
        if key[0] != "refine":
            continue
        edit = refine_rows.setdefault((key[1], key[2]), {"table": key[1], "id": key[2]})
        edit[key[3]] = value
    rebuilt, _ = refine_tables.apply_edits(rebuilt, list(refine_rows.values()))
    if rebuilt != source:
        return None, "contains changes outside proved text and refine units"
    return changes, ""


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge supported units, or return a reason for opaque fallback."""
    extracted = []
    for mod_id, source in mods:
        try:
            changes, reason = _extract(vanilla, source)
        except (KeyError, TypeError, ValueError) as error:
            return None, [], f"{mod_id} is not a supported mngrp.bin: {error}"
        if changes is None:
            return None, [], f"{mod_id} {reason}"
        extracted.append((mod_id, changes))

    claims: dict[tuple, list[tuple[str, object]]] = {}
    for mod_id, changes in extracted:
        for unit, value in changes.items():
            claims.setdefault(unit, []).append((mod_id, value))

    winners = {unit: values[-1][1] for unit, values in claims.items()}
    text_edits = [{"source": "mngrp", "sectionId": unit[1], "recordId": unit[2],
                   "value": value}
                  for unit, value in winners.items() if unit[0] == "text"]
    output, _ = mngrp_text.apply_edits(vanilla, text_edits)
    refine_rows: dict[tuple[str, int], dict] = {}
    for unit, value in winners.items():
        if unit[0] != "refine":
            continue
        edit = refine_rows.setdefault((unit[1], unit[2]), {"table": unit[1], "id": unit[2]})
        edit[unit[3]] = value
    output, _ = refine_tables.apply_edits(output, list(refine_rows.values()))

    conflicts = []
    for unit, values in claims.items():
        if len(values) < 2 or len({repr(value) for _, value in values}) < 2:
            continue
        if unit[0] == "text":
            label = f"{path}:text:section:{unit[1]}:record:{unit[2]}"
        else:
            label = f"{path}:refine:{unit[1]}:record:{unit[2]}:{unit[3]}"
        conflicts.append({"unit": label, "winner": values[-1][0],
                          "claimants": [mod_id for mod_id, _ in values]})
    return output, conflicts, ""

"""Bounded read-only payload probes for Chrono Trigger Steam research.

This module is intentionally diagnostic. It only reads explicitly selected
candidate resources, enforces count/size caps before decompression, and reports
byte-level differences without assigning gameplay semantics to any offset.
"""

from __future__ import annotations

from collections import Counter
import hashlib

from .inventory import CANDIDATE_KEYWORDS, _candidate_score
from .resources import ResourceArchive


MAX_LIMIT = 64
MAX_WINDOW = 512


def _family_name(value: str) -> str:
    family = str(value).strip().casefold()
    if family not in CANDIDATE_KEYWORDS:
        raise ValueError(
            f"unknown candidate family {value!r}; expected one of {', '.join(CANDIDATE_KEYWORDS)}"
        )
    return family


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _constant_ranges(samples: list[bytes], window: int) -> list[dict]:
    if len(samples) < 2 or window <= 0:
        return []
    distinct = [len({sample[offset] for sample in samples}) for offset in range(window)]
    ranges: list[dict] = []
    start = None
    for offset, count in enumerate(distinct + [2]):
        if count == 1 and start is None:
            start = offset
        elif count != 1 and start is not None:
            end = offset
            ranges.append({
                "start": start,
                "endExclusive": end,
                "length": end - start,
                "hex": samples[0][start:end].hex(" ").upper(),
            })
            start = None
    return ranges


def _same_size_analysis(rows: list[dict], payloads: list[bytes], byte_window: int) -> dict:
    size = len(payloads[0])
    window = min(byte_window, size)
    variable = []
    if len(payloads) >= 2:
        for offset in range(window):
            values = sorted({payload[offset] for payload in payloads})
            if len(values) > 1:
                variable.append({
                    "offset": offset,
                    "distinctCount": len(values),
                    "valuesHex": [f"{value:02X}" for value in values[:16]],
                    "valuesTruncated": len(values) > 16,
                })
    return {
        "payloadSize": size,
        "sampleCount": len(rows),
        "analysisWindow": window,
        "constantByteCount": window - len(variable) if len(payloads) >= 2 else None,
        "variableByteCount": len(variable) if len(payloads) >= 2 else None,
        "constantRanges": _constant_ranges(payloads, window),
        "variablePositions": variable,
        "paths": [row["path"] for row in rows],
    }


def probe_family(
    archive: ResourceArchive,
    family: str,
    *,
    limit: int = 12,
    byte_window: int = 128,
    max_payload_bytes: int = 1024 * 1024,
    max_stored_bytes: int = 1024 * 1024,
    path_prefix: str | None = None,
) -> dict:
    """Probe a bounded set of one candidate family without writing anything.

    Candidate ranking is filename/path evidence only. ``path_prefix`` may narrow
    a family to a directory cluster discovered by the index-only inventory. Each
    selected entry's four-byte declared uncompressed size is read first. Entries
    exceeding either configured cap are skipped before gzip decompression.
    """
    family = _family_name(family)
    limit = _bounded(limit, 1, MAX_LIMIT, "Probe limit")
    byte_window = _bounded(byte_window, 1, MAX_WINDOW, "Byte window")
    max_payload_bytes = _bounded(max_payload_bytes, 1, 64 * 1024 * 1024, "Maximum payload bytes")
    max_stored_bytes = _bounded(max_stored_bytes, 4, 64 * 1024 * 1024, "Maximum stored bytes")
    prefix = str(path_prefix or "").strip().replace("\\", "/").strip("/")
    prefix_folded = prefix.casefold()

    words = CANDIDATE_KEYWORDS[family]
    ranked = []
    for entry in archive.entries:
        score = _candidate_score(entry.path, words)
        if score:
            ranked.append((score, entry))
    ranked.sort(key=lambda value: (-value[0], value[1].path.casefold()))
    filtered = [
        value for value in ranked
        if not prefix_folded or value[1].path.casefold().lstrip("/").startswith(prefix_folded + "/")
        or value[1].path.casefold().lstrip("/") == prefix_folded
    ]

    rows = []
    loaded_payloads: list[tuple[dict, bytes]] = []
    for score, entry in filtered[:limit]:
        row = {
            "path": entry.path,
            "score": score,
            "storedSize": int(entry.stored_size),
        }
        rows.append(row)
        if entry.stored_size > max_stored_bytes:
            row["skipped"] = f"stored size {entry.stored_size} exceeds cap {max_stored_bytes}"
            continue
        try:
            declared_size = int(archive.declared_payload_size(entry))
        except Exception as error:
            row["error"] = f"declared-size peek failed: {error}"
            continue
        row["declaredSize"] = declared_size
        if declared_size > max_payload_bytes:
            row["skipped"] = f"declared payload size {declared_size} exceeds cap {max_payload_bytes}"
            continue
        try:
            payload = archive.read(entry)
        except Exception as error:
            row["error"] = f"payload read failed: {error}"
            continue
        if len(payload) > max_payload_bytes:
            row["error"] = f"decoded payload size {len(payload)} exceeds cap {max_payload_bytes}"
            continue
        row.update({
            "payloadSize": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "prefixHex": payload[:byte_window].hex(" ").upper(),
            "zeroByteCount": payload.count(0),
        })
        loaded_payloads.append((row, payload))

    size_groups: dict[int, list[tuple[dict, bytes]]] = {}
    for row, payload in loaded_payloads:
        size_groups.setdefault(len(payload), []).append((row, payload))
    comparisons = []
    for size in sorted(size_groups):
        group = size_groups[size]
        comparisons.append(_same_size_analysis(
            [row for row, _payload in group],
            [payload for _row, payload in group],
            byte_window,
        ))

    loaded_sizes = Counter(len(payload) for _row, payload in loaded_payloads)
    return {
        "kind": "chrono-trigger-family-probe",
        "archive": str(archive.path),
        "family": family,
        "pathPrefix": prefix or None,
        "candidateCount": len(ranked),
        "filteredCandidateCount": len(filtered),
        "attemptedCount": len(rows),
        "loadedCount": len(loaded_payloads),
        "limits": {
            "resources": limit,
            "byteWindow": byte_window,
            "maxPayloadBytes": max_payload_bytes,
            "maxStoredBytes": max_stored_bytes,
        },
        "payloadSizeClusters": [
            {"payloadSize": size, "count": count}
            for size, count in sorted(loaded_sizes.items(), key=lambda value: (-value[1], value[0]))
        ],
        "resources": rows,
        "sameSizeComparisons": comparisons,
        "method": (
            "read-only selected-family probe; optional path-prefix filtering is applied before payload reads; "
            "declared-size and stored-size caps are checked before candidate gzip decompression; byte differences are "
            "structural diagnostics only and do not assign gameplay semantics"
        ),
    }

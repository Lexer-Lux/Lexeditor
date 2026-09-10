"""Read-only coverage audit for Chrono Trigger Steam field-event scripts.

This module is shared by the CLI and desktop server so both surfaces use the
same fail-closed parser/editor coverage policy. Audits never write project or
game files.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from .data import OverlayStore
from .editor_registry import decorate_event_editors
from .event_edit import VARIABLE_OR_UNRESOLVED
from .events import event_entries, parse_event


HOTSPOT_EVENT_SAMPLE_LIMIT = 8


def _opcode_key(value: int) -> str:
    return f"0x{int(value):02X}"


def _iter_functions(payload: dict):
    """Yield unique decoded function bounds, not aliased 16-slot references."""
    seen_bounds: set[tuple[int, int]] = set()
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            if "start" in function and "end" in function:
                key = (int(function["start"]), int(function["end"]))
                if key in seen_bounds:
                    continue
                seen_bounds.add(key)
            yield function


def audit_event(payload: dict) -> dict:
    """Return deterministic editor-coverage counters for one parsed field event."""
    opcode_counts: Counter[int] = Counter()
    argument_counts: Counter[int] = Counter()
    writable_counts: Counter[int] = Counter()
    read_only_counts: Counter[int] = Counter()
    stop_counts: Counter[int] = Counter()
    stop_reasons: Counter[str] = Counter()
    functions = 0
    complete_functions = 0

    for function in _iter_functions(payload):
        functions += 1
        if function.get("complete"):
            complete_functions += 1
        for command in function.get("commands", []):
            opcode = int(command["opcode"])
            opcode_counts[opcode] += 1
            argument_bytes = int(command.get("argumentBytes", 0))
            if argument_bytes > 0:
                argument_counts[opcode] += 1
                editor = command.get("editor")
                if editor and bool(editor.get("fixedWidth")):
                    writable_counts[opcode] += 1
                else:
                    read_only_counts[opcode] += 1
        problem = function.get("problem")
        if problem:
            opcode = int(problem.get("opcode", -1))
            if 0 <= opcode <= 0xFF:
                stop_counts[opcode] += 1
            stop_reasons[str(problem.get("reason") or "unknown")] += 1

    decoded = sum(opcode_counts.values())
    argument_commands = sum(argument_counts.values())
    writable = sum(writable_counts.values())
    read_only = sum(read_only_counts.values())
    return {
        "kind": "chrono-trigger-event-audit",
        "eventId": payload.get("id"),
        "path": payload.get("path"),
        "functions": functions,
        "completeFunctions": complete_functions,
        "problemFunctions": functions - complete_functions,
        "decodedCommands": decoded,
        "argumentCommands": argument_commands,
        "zeroArgumentCommands": decoded - argument_commands,
        "writableCommands": writable,
        "readOnlyCommands": read_only,
        "writablePercent": round((writable * 100.0 / argument_commands), 2) if argument_commands else 0.0,
        "opcodes": [
            {
                "opcode": opcode,
                "opcodeHex": _opcode_key(opcode),
                "count": opcode_counts[opcode],
                "argumentBearing": argument_counts[opcode],
                "writable": writable_counts[opcode],
                "readOnly": read_only_counts[opcode],
                "dynamicOrUnresolvedBoundary": opcode in VARIABLE_OR_UNRESOLVED,
            }
            for opcode in sorted(opcode_counts)
        ],
        "stops": [
            {"opcode": opcode, "opcodeHex": _opcode_key(opcode), "count": count}
            for opcode, count in sorted(stop_counts.items())
        ],
        "stopReasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(stop_reasons.items(), key=lambda row: (-row[1], row[0]))
        ],
    }


def merge_audits(audits: Iterable[dict]) -> dict:
    """Aggregate event audits and rank read-only/parser research hotspots.

    Each hotspot includes a bounded deterministic list of event IDs containing
    that opcode. This makes an exported aggregate report actionable without
    embedding event payloads or requiring the whole archive to be shared.
    """
    audits = list(audits)
    counts: Counter[int] = Counter()
    argument_counts: Counter[int] = Counter()
    writable: Counter[int] = Counter()
    read_only: Counter[int] = Counter()
    stops: Counter[int] = Counter()
    reasons: Counter[str] = Counter()
    read_only_events: dict[int, set[int]] = defaultdict(set)
    stop_events: dict[int, set[int]] = defaultdict(set)

    for audit in audits:
        event_id = audit.get("eventId")
        normalized_event_id = int(event_id) if event_id is not None else None
        for row in audit.get("opcodes", []):
            opcode = int(row["opcode"])
            counts[opcode] += int(row.get("count", 0))
            argument_counts[opcode] += int(row.get("argumentBearing", 0))
            writable[opcode] += int(row.get("writable", 0))
            read_only_count = int(row.get("readOnly", 0))
            read_only[opcode] += read_only_count
            if read_only_count and normalized_event_id is not None:
                read_only_events[opcode].add(normalized_event_id)
        for row in audit.get("stops", []):
            opcode = int(row["opcode"])
            stop_count = int(row.get("count", 0))
            stops[opcode] += stop_count
            if stop_count and normalized_event_id is not None:
                stop_events[opcode].add(normalized_event_id)
        for row in audit.get("stopReasons", []):
            reasons[str(row["reason"])] += int(row.get("count", 0))

    decoded = sum(counts.values())
    argument_commands = sum(argument_counts.values())
    writable_total = sum(writable.values())
    read_only_total = sum(read_only.values())
    hotspot_rows = []
    for opcode in set(counts) | set(stops):
        if not read_only[opcode] and not stops[opcode]:
            continue
        read_only_ids = sorted(read_only_events[opcode])
        stop_ids = sorted(stop_events[opcode])
        combined_ids = sorted(read_only_events[opcode] | stop_events[opcode])
        hotspot_rows.append({
            "opcode": opcode,
            "opcodeHex": _opcode_key(opcode),
            "readOnlyCount": read_only[opcode],
            "decodedCount": counts[opcode],
            "argumentCount": argument_counts[opcode],
            "stopCount": stops[opcode],
            "dynamicOrUnresolvedBoundary": opcode in VARIABLE_OR_UNRESOLVED,
            "sampleEventIds": combined_ids[:HOTSPOT_EVENT_SAMPLE_LIMIT],
            "sampleEventIdsTruncated": len(combined_ids) > HOTSPOT_EVENT_SAMPLE_LIMIT,
            "readOnlyEventIds": read_only_ids[:HOTSPOT_EVENT_SAMPLE_LIMIT],
            "readOnlyEventIdsTruncated": len(read_only_ids) > HOTSPOT_EVENT_SAMPLE_LIMIT,
            "stopEventIds": stop_ids[:HOTSPOT_EVENT_SAMPLE_LIMIT],
            "stopEventIdsTruncated": len(stop_ids) > HOTSPOT_EVENT_SAMPLE_LIMIT,
        })
    hotspots = sorted(
        hotspot_rows,
        key=lambda row: (-row["stopCount"], -row["readOnlyCount"], row["opcode"]),
    )
    return {
        "kind": "chrono-trigger-event-audit-summary",
        "events": len(audits),
        "functions": sum(int(audit.get("functions", 0)) for audit in audits),
        "completeFunctions": sum(int(audit.get("completeFunctions", 0)) for audit in audits),
        "problemFunctions": sum(int(audit.get("problemFunctions", 0)) for audit in audits),
        "decodedCommands": decoded,
        "argumentCommands": argument_commands,
        "zeroArgumentCommands": decoded - argument_commands,
        "writableCommands": writable_total,
        "readOnlyCommands": read_only_total,
        "writablePercent": round((writable_total * 100.0 / argument_commands), 2) if argument_commands else 0.0,
        "hotspots": hotspots,
        "stopReasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reasons.items(), key=lambda row: (-row[1], row[0]))
        ],
    }


def audit_store(store: OverlayStore, source: str = "mine", event_ids: Iterable[int] = (),
                limit: int = 0) -> dict:
    """Audit selected/all Atel entries from an existing overlay store.

    Malformed individual resources are reported in ``scanErrors`` and do not
    abort an install-wide audit. Unknown explicitly requested event IDs remain a
    hard input error so a typo cannot silently produce a partial report.
    """
    source = str(source or "mine")
    if source not in {"mine", "vanilla"}:
        raise ValueError("Audit source must be 'mine' or 'vanilla'")
    limit = int(limit)
    if limit < 0:
        raise ValueError("Audit limit must be 0 or greater")

    entries = event_entries(store)
    by_id = {event_id: path for event_id, path in entries}
    requested = sorted(set(int(value) for value in event_ids))
    if requested:
        missing = [event_id for event_id in requested if event_id not in by_id]
        if missing:
            rendered = ", ".join(str(value) for value in missing)
            raise ValueError(f"Unknown Chrono Trigger field event(s): {rendered}")
        selected = [(event_id, by_id[event_id]) for event_id in requested]
    else:
        selected = entries
    if limit:
        selected = selected[:limit]

    selected_ids = [event_id for event_id, _path in selected]
    audits: list[dict] = []
    errors: list[dict] = []
    for event_id, path in selected:
        try:
            raw, origin = store.read(path, source)
            payload = {"id": event_id, "path": path, "source": origin, **parse_event(raw)}
            decorate_event_editors(payload)
            audits.append(audit_event(payload))
        except Exception as error:
            errors.append({"eventId": event_id, "path": path, "error": str(error)})

    if len(selected_ids) == 1 and len(audits) == 1 and not errors:
        output = audits[0]
    else:
        output = merge_audits(audits)
    output["scanSource"] = source
    output["selectedEventIds"] = selected_ids
    output["auditedEventIds"] = [audit.get("eventId") for audit in audits]
    output["scanErrorCount"] = len(errors)
    output["scanErrors"] = errors
    return output

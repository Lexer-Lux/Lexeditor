#!/usr/bin/env python3
"""Audit Chrono Trigger Steam field-event editor coverage.

Two read-only input modes are supported:

- one or more JSON payloads produced by ``tools/chrono_trigger_event.py show``;
- a real Steam install/project pair, which scans selected or all ``Atel_*.dat``
  resources directly through Lexeditor's fail-closed PC parser.

The report ranks parser-stop opcodes ahead of ordinary read-only frequency so
research effort is driven by real Steam scripts instead of opcode-name guesses.
Zero-argument commands are reported but do not count as missing editor coverage.
Direct scans report malformed events individually and continue. This tool never
writes game or project files.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.editor_registry import decorate_event_editors
from games.chrono_trigger.event_edit import VARIABLE_OR_UNRESOLVED
from games.chrono_trigger.events import event_entries, parse_event


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
    """Return deterministic coverage counters for one parsed field event."""
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
    """Aggregate event audits and rank read-only/editor-research hotspots."""
    audits = list(audits)
    counts: Counter[int] = Counter()
    argument_counts: Counter[int] = Counter()
    writable: Counter[int] = Counter()
    read_only: Counter[int] = Counter()
    stops: Counter[int] = Counter()
    reasons: Counter[str] = Counter()

    for audit in audits:
        for row in audit.get("opcodes", []):
            opcode = int(row["opcode"])
            counts[opcode] += int(row.get("count", 0))
            argument_counts[opcode] += int(row.get("argumentBearing", 0))
            writable[opcode] += int(row.get("writable", 0))
            read_only[opcode] += int(row.get("readOnly", 0))
        for row in audit.get("stops", []):
            stops[int(row["opcode"])] += int(row.get("count", 0))
        for row in audit.get("stopReasons", []):
            reasons[str(row["reason"])] += int(row.get("count", 0))

    decoded = sum(counts.values())
    argument_commands = sum(argument_counts.values())
    writable_total = sum(writable.values())
    read_only_total = sum(read_only.values())
    hotspots = sorted(
        (
            {
                "opcode": opcode,
                "opcodeHex": _opcode_key(opcode),
                "readOnlyCount": read_only[opcode],
                "decodedCount": counts[opcode],
                "argumentCount": argument_counts[opcode],
                "stopCount": stops[opcode],
                "dynamicOrUnresolvedBoundary": opcode in VARIABLE_OR_UNRESOLVED,
            }
            for opcode in set(counts) | set(stops)
            if read_only[opcode] or stops[opcode]
        ),
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


def _load(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _direct_audits(game: Path, project: Path, source: str,
                   requested_ids: list[int], limit: int) -> tuple[list[dict], list[int], list[dict]]:
    game = game.expanduser().resolve()
    project = project.expanduser().resolve()
    archive = game / "resources.bin"
    if not archive.is_file():
        raise FileNotFoundError(f"resources.bin not found: {archive}")

    store = OverlayStore(archive, project)
    entries = event_entries(store)
    by_id = {event_id: path for event_id, path in entries}
    if requested_ids:
        selected_ids = sorted(set(int(value) for value in requested_ids))
        missing = [event_id for event_id in selected_ids if event_id not in by_id]
        if missing:
            rendered = ", ".join(str(value) for value in missing)
            raise ValueError(f"Unknown Chrono Trigger field event(s): {rendered}")
        selected = [(event_id, by_id[event_id]) for event_id in selected_ids]
    else:
        selected = entries

    if limit < 0:
        raise ValueError("Audit limit must be 0 or greater")
    if limit:
        selected = selected[:limit]

    selected_ids = [event_id for event_id, _path in selected]
    audits: list[dict] = []
    errors: list[dict] = []
    for event_id, path in selected:
        try:
            raw, origin = store.read(path, source)
            payload = {
                "id": event_id,
                "path": path,
                "source": origin,
                **parse_event(raw),
            }
            decorate_event_editors(payload)
            audits.append(audit_event(payload))
        except Exception as error:
            errors.append({"eventId": event_id, "path": path, "error": str(error)})
    return audits, selected_ids, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Chrono Trigger Steam field-event editor coverage."
    )
    parser.add_argument("inputs", nargs="*", help="Event JSON file(s), or '-' for stdin")
    parser.add_argument("--game", type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--project", type=Path, help="Lexeditor/CTExt project overlay")
    parser.add_argument("--source", choices=("mine", "vanilla"), default="mine",
                        help="Direct-scan source: project overlay when present, or immutable vanilla")
    parser.add_argument("--event", dest="event_ids", action="append", type=int, default=[],
                        help="Direct scan: restrict to this event ID; repeat for multiple events")
    parser.add_argument("--limit", type=int, default=0,
                        help="Direct scan: maximum events after filtering; 0 scans all")
    args = parser.parse_args(argv)

    direct_mode = args.game is not None or args.project is not None
    selected_ids: list[int] = []
    scan_errors: list[dict] = []
    if direct_mode:
        if args.game is None or args.project is None:
            parser.error("--game and --project must be supplied together")
        if args.inputs:
            parser.error("JSON inputs cannot be combined with --game/--project")
        try:
            audits, selected_ids, scan_errors = _direct_audits(
                args.game, args.project, args.source, args.event_ids, args.limit,
            )
        except Exception as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
            return 1
    else:
        if args.event_ids or args.limit or args.source != "mine":
            parser.error("--event, --limit and --source require --game/--project")
        if not args.inputs:
            parser.error("provide event JSON input(s) or --game/--project")
        if args.inputs.count("-") > 1:
            parser.error("stdin may be specified only once")
        audits = [audit_event(_load(path)) for path in args.inputs]

    if direct_mode:
        if len(selected_ids) == 1 and len(audits) == 1 and not scan_errors:
            output = audits[0]
        else:
            output = merge_audits(audits)
        output["scanSource"] = args.source
        output["selectedEventIds"] = selected_ids
        output["auditedEventIds"] = [audit.get("eventId") for audit in audits]
        output["scanErrorCount"] = len(scan_errors)
        output["scanErrors"] = scan_errors
    else:
        output = audits[0] if len(audits) == 1 else merge_audits(audits)

    print(json.dumps(output, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

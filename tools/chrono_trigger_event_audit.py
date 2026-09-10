#!/usr/bin/env python3
"""Summarize writable/read-only coverage from Chrono Trigger event JSON.

Input is one or more JSON payloads produced by `tools/chrono_trigger_event.py
show` (or `-` for stdin).  This tool never opens or writes game files.  It is
intended to rank the next PC event commands using real Steam script frequency
rather than opcode-name guesses.
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

from games.chrono_trigger.event_edit import VARIABLE_OR_UNRESOLVED


def _opcode_key(value: int) -> str:
    return f"0x{int(value):02X}"


def _iter_functions(payload: dict):
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            yield function


def audit_event(payload: dict) -> dict:
    """Return deterministic coverage counters for one parsed field event."""
    opcode_counts: Counter[int] = Counter()
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
        "writableCommands": writable,
        "readOnlyCommands": read_only,
        "writablePercent": round((writable * 100.0 / decoded), 2) if decoded else 0.0,
        "opcodes": [
            {
                "opcode": opcode,
                "opcodeHex": _opcode_key(opcode),
                "count": opcode_counts[opcode],
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
    writable: Counter[int] = Counter()
    read_only: Counter[int] = Counter()
    stops: Counter[int] = Counter()
    reasons: Counter[str] = Counter()

    for audit in audits:
        for row in audit.get("opcodes", []):
            opcode = int(row["opcode"])
            counts[opcode] += int(row.get("count", 0))
            writable[opcode] += int(row.get("writable", 0))
            read_only[opcode] += int(row.get("readOnly", 0))
        for row in audit.get("stops", []):
            stops[int(row["opcode"])] += int(row.get("count", 0))
        for row in audit.get("stopReasons", []):
            reasons[str(row["reason"])] += int(row.get("count", 0))

    decoded = sum(counts.values())
    writable_total = sum(writable.values())
    read_only_total = sum(read_only.values())
    hotspots = sorted(
        (
            {
                "opcode": opcode,
                "opcodeHex": _opcode_key(opcode),
                "readOnlyCount": read_only[opcode],
                "decodedCount": counts[opcode],
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
        "writableCommands": writable_total,
        "readOnlyCommands": read_only_total,
        "writablePercent": round((writable_total * 100.0 / decoded), 2) if decoded else 0.0,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit named event-editor coverage from Chrono Trigger event-show JSON."
    )
    parser.add_argument("inputs", nargs="+", help="Event JSON file(s), or '-' for stdin")
    args = parser.parse_args(argv)
    if args.inputs.count("-") > 1:
        parser.error("stdin may be specified only once")

    audits = [audit_event(_load(path)) for path in args.inputs]
    output = audits[0] if len(audits) == 1 else merge_audits(audits)
    print(json.dumps(output, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

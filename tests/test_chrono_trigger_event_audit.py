from __future__ import annotations

import unittest

from tools.chrono_trigger_event_audit import audit_event, merge_audits


def event_payload(event_id: int, commands: list[dict], *, problem: dict | None = None) -> dict:
    return {
        "id": event_id,
        "path": f"Game/field/atel/Atel_{event_id:04d}.dat",
        "objects": [{
            "functions": [{
                "complete": problem is None,
                "commands": commands,
                "problem": problem,
            }],
        }],
    }


def command(opcode: int, *, writable: bool, argument_bytes: int = 1) -> dict:
    row = {"opcode": opcode, "argumentBytes": argument_bytes}
    if writable:
        row["editor"] = {"fixedWidth": True}
    return row


class EventAuditTests(unittest.TestCase):
    def test_single_event_counts_writable_read_only_and_fail_closed_stop(self):
        payload = event_payload(
            7,
            [
                command(0x83, writable=True),
                command(0x83, writable=True),
                command(0x8E, writable=False),
                command(0xEC, writable=False),
            ],
            problem={"opcode": 0xF1, "reason": "PC command boundary is unresolved"},
        )
        audit = audit_event(payload)
        self.assertEqual(audit["eventId"], 7)
        self.assertEqual(audit["functions"], 1)
        self.assertEqual(audit["completeFunctions"], 0)
        self.assertEqual(audit["problemFunctions"], 1)
        self.assertEqual(audit["decodedCommands"], 4)
        self.assertEqual(audit["argumentCommands"], 4)
        self.assertEqual(audit["zeroArgumentCommands"], 0)
        self.assertEqual(audit["writableCommands"], 2)
        self.assertEqual(audit["readOnlyCommands"], 2)
        self.assertEqual(audit["writablePercent"], 50.0)

        rows = {row["opcode"]: row for row in audit["opcodes"]}
        self.assertEqual(rows[0x83]["writable"], 2)
        self.assertEqual(rows[0x8E]["readOnly"], 1)
        self.assertTrue(rows[0xEC]["dynamicOrUnresolvedBoundary"])
        self.assertEqual(audit["stops"], [{"opcode": 0xF1, "opcodeHex": "0xF1", "count": 1}])

    def test_zero_argument_commands_do_not_pollute_editor_gap_metrics(self):
        payload = event_payload(8, [
            command(0x00, writable=False, argument_bytes=0),
            command(0x90, writable=False, argument_bytes=0),
            command(0x8E, writable=False),
        ])
        audit = audit_event(payload)
        self.assertEqual(audit["decodedCommands"], 3)
        self.assertEqual(audit["argumentCommands"], 1)
        self.assertEqual(audit["zeroArgumentCommands"], 2)
        self.assertEqual(audit["readOnlyCommands"], 1)
        summary = merge_audits([audit])
        self.assertEqual([row["opcode"] for row in summary["hotspots"]], [0x8E])

    def test_aliased_function_slots_are_counted_once_by_bounds(self):
        shared = {
            "start": 32,
            "end": 36,
            "complete": True,
            "commands": [command(0x83, writable=True)],
            "problem": None,
        }
        payload = {
            "id": 11,
            "path": "Game/field/atel/Atel_0011.dat",
            "objects": [{"functions": [dict(shared), dict(shared), dict(shared)]}],
        }
        audit = audit_event(payload)
        self.assertEqual(audit["functions"], 1)
        self.assertEqual(audit["completeFunctions"], 1)
        self.assertEqual(audit["decodedCommands"], 1)
        self.assertEqual(audit["writableCommands"], 1)
        self.assertEqual(audit["opcodes"][0]["count"], 1)

    def test_merge_ranks_stops_before_plain_read_only_frequency(self):
        first = audit_event(event_payload(
            1,
            [
                command(0x8E, writable=False),
                command(0x8E, writable=False),
                command(0x82, writable=True),
            ],
            problem={"opcode": 0xF1, "reason": "unresolved F1"},
        ))
        second = audit_event(event_payload(
            2,
            [
                command(0x8E, writable=False),
                command(0xEC, writable=False),
                command(0x82, writable=True),
            ],
            problem={"opcode": 0x9E, "reason": "unresolved movement width"},
        ))
        summary = merge_audits([first, second])
        self.assertEqual(summary["events"], 2)
        self.assertEqual(summary["decodedCommands"], 6)
        self.assertEqual(summary["argumentCommands"], 6)
        self.assertEqual(summary["writableCommands"], 2)
        self.assertEqual(summary["readOnlyCommands"], 4)
        self.assertEqual(summary["writablePercent"], 33.33)

        # Stop-producing opcodes rank ahead of a more frequent plain read-only
        # opcode, because parser blockers prevent the remainder of a function
        # from being analyzed at all.
        self.assertEqual([row["opcode"] for row in summary["hotspots"][:2]], [0x9E, 0xF1])
        self.assertEqual(summary["hotspots"][2]["opcode"], 0x8E)
        self.assertTrue(summary["hotspots"][0]["dynamicOrUnresolvedBoundary"])
        self.assertTrue(summary["hotspots"][1]["dynamicOrUnresolvedBoundary"])

    def test_empty_event_has_zero_percent_without_division_error(self):
        audit = audit_event(event_payload(0, []))
        self.assertEqual(audit["decodedCommands"], 0)
        self.assertEqual(audit["argumentCommands"], 0)
        self.assertEqual(audit["writablePercent"], 0.0)
        summary = merge_audits([audit])
        self.assertEqual(summary["decodedCommands"], 0)
        self.assertEqual(summary["argumentCommands"], 0)
        self.assertEqual(summary["writablePercent"], 0.0)
        self.assertEqual(summary["hotspots"], [])


if __name__ == "__main__":
    unittest.main()

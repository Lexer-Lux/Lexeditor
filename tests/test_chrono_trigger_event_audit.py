from __future__ import annotations

import unittest

from tools.chrono_trigger_event_audit import audit_event, merge_audits


def event_payload(event_id: int, commands: list[dict], *, problem: dict | None = None) -> dict:
    return {
        "id": event_id,
        "path": f"Game/field/atel/Atel_{event_id:04d}.dat",
        "objects": [{
            "functions": [{
                "start": 32,
                "end": 48,
                "complete": problem is None,
                "commands": commands,
                "problem": problem,
            }],
        }],
    }


def command(opcode: int, *, writable: bool, argument_bytes: int = 1,
            offset: int = 32, raw_hex: str = "", arguments_hex: str = "") -> dict:
    row = {
        "opcode": opcode,
        "argumentBytes": argument_bytes,
        "offset": offset,
        "name": f"Opcode 0x{opcode:02X}",
        "rawHex": raw_hex,
        "argumentsHex": arguments_hex,
    }
    if writable:
        row["editor"] = {"fixedWidth": True}
    return row


class EventAuditTests(unittest.TestCase):
    def test_single_event_counts_writable_read_only_and_fail_closed_stop(self):
        payload = event_payload(
            7,
            [
                command(0x83, writable=True),
                command(0x83, writable=True, offset=34),
                command(0x8E, writable=False, offset=36, raw_hex="8E 80", arguments_hex="80"),
                command(0xEC, writable=False, offset=38, raw_hex="EC 88", arguments_hex="88"),
            ],
            problem={
                "opcode": 0xF1,
                "offset": 40,
                "reason": "PC command boundary is unresolved",
                "remainingBytes": 8,
                "rawPreview": "F1 22 80 00 00 00 00 00",
                "truncatedPreview": False,
            },
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
        self.assertEqual(audit["readOnlySamples"][0]["rawHex"], "8E 80")
        self.assertEqual(audit["readOnlySamples"][0]["offset"], 36)
        self.assertEqual(audit["stopSamples"][0]["rawPreview"], "F1 22 80 00 00 00 00 00")
        self.assertEqual(audit["stopSamples"][0]["remainingBytes"], 8)

    def test_zero_argument_commands_do_not_pollute_editor_gap_metrics(self):
        payload = event_payload(8, [
            command(0x00, writable=False, argument_bytes=0),
            command(0x90, writable=False, argument_bytes=0, offset=33),
            command(0x8E, writable=False, offset=34, raw_hex="8E 80", arguments_hex="80"),
        ])
        audit = audit_event(payload)
        self.assertEqual(audit["decodedCommands"], 3)
        self.assertEqual(audit["argumentCommands"], 1)
        self.assertEqual(audit["zeroArgumentCommands"], 2)
        self.assertEqual(audit["readOnlyCommands"], 1)
        summary = merge_audits([audit])
        self.assertEqual([row["opcode"] for row in summary["hotspots"]], [0x8E])
        self.assertEqual(summary["hotspots"][0]["sampleEventIds"], [8])
        self.assertEqual(summary["hotspots"][0]["readOnlySamples"][0]["rawHex"], "8E 80")

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

    def test_merge_ranks_stops_before_plain_read_only_frequency_and_reports_events(self):
        first = audit_event(event_payload(
            1,
            [
                command(0x8E, writable=False, raw_hex="8E 80", arguments_hex="80"),
                command(0x8E, writable=False, offset=34, raw_hex="8E 40", arguments_hex="40"),
                command(0x82, writable=True, offset=36, raw_hex="82 01", arguments_hex="01"),
            ],
            problem={
                "opcode": 0xF1,
                "offset": 38,
                "reason": "unresolved F1",
                "remainingBytes": 10,
                "rawPreview": "F1 22 80 00 00 00 00 00 00 00",
                "truncatedPreview": False,
            },
        ))
        second = audit_event(event_payload(
            2,
            [
                command(0x8E, writable=False, raw_hex="8E C0", arguments_hex="C0"),
                command(0xEC, writable=False, offset=34, raw_hex="EC 88", arguments_hex="88"),
                command(0x82, writable=True, offset=36, raw_hex="82 02", arguments_hex="02"),
            ],
            problem={
                "opcode": 0x9E,
                "offset": 38,
                "reason": "unresolved movement width",
                "remainingBytes": 10,
                "rawPreview": "9E 04 08 00 00 00 00 00 00 00",
                "truncatedPreview": False,
            },
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

        by_opcode = {row["opcode"]: row for row in summary["hotspots"]}
        self.assertEqual(by_opcode[0x9E]["sampleEventIds"], [2])
        self.assertEqual(by_opcode[0x9E]["stopEventIds"], [2])
        self.assertEqual(by_opcode[0x9E]["readOnlyEventIds"], [])
        self.assertEqual(by_opcode[0x9E]["stopSamples"][0]["eventId"], 2)
        self.assertEqual(by_opcode[0x9E]["stopSamples"][0]["rawPreview"], "9E 04 08 00 00 00 00 00 00 00")
        self.assertEqual(by_opcode[0xF1]["sampleEventIds"], [1])
        self.assertEqual(by_opcode[0xF1]["stopSamples"][0]["eventId"], 1)
        self.assertEqual(by_opcode[0xF1]["stopSamples"][0]["rawPreview"], "F1 22 80 00 00 00 00 00 00 00")
        self.assertEqual(by_opcode[0x8E]["sampleEventIds"], [1, 2])
        self.assertEqual(by_opcode[0x8E]["readOnlyEventIds"], [1, 2])
        self.assertEqual(by_opcode[0x8E]["stopEventIds"], [])
        self.assertEqual(
            [(row["eventId"], row["rawHex"]) for row in by_opcode[0x8E]["readOnlySamples"]],
            [(1, "8E 80"), (1, "8E 40"), (2, "8E C0")],
        )
        self.assertFalse(by_opcode[0x8E]["sampleEventIdsTruncated"])

    def test_hotspot_event_and_context_samples_are_sorted_unique_and_bounded(self):
        audits = [
            audit_event(event_payload(event_id, [
                command(
                    0x8E, writable=False, raw_hex=f"8E {event_id:02X}",
                    arguments_hex=f"{event_id:02X}",
                )
            ]))
            for event_id in range(12, 1, -1)
        ]
        # Duplicate one event audit deliberately; samples must still be unique.
        audits.append(audits[-1])
        summary = merge_audits(audits)
        hotspot = summary["hotspots"][0]
        self.assertEqual(hotspot["opcode"], 0x8E)
        self.assertEqual(hotspot["sampleEventIds"], list(range(2, 10)))
        self.assertEqual(hotspot["readOnlyEventIds"], list(range(2, 10)))
        self.assertEqual(hotspot["stopEventIds"], [])
        self.assertTrue(hotspot["sampleEventIdsTruncated"])
        self.assertTrue(hotspot["readOnlyEventIdsTruncated"])
        self.assertFalse(hotspot["stopEventIdsTruncated"])
        self.assertEqual(
            [row["eventId"] for row in hotspot["readOnlySamples"]],
            [2, 3, 4, 5],
        )
        self.assertTrue(hotspot["readOnlySamplesTruncated"])
        self.assertEqual(hotspot["stopSamples"], [])
        self.assertFalse(hotspot["stopSamplesTruncated"])

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

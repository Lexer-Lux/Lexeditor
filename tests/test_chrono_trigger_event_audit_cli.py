from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from games.chrono_trigger.plugin import _build_smoke_archive, _field_event
from tools.chrono_trigger_event_audit import main


def payload(event_id: int, opcode: int, writable: bool, problem: dict | None = None) -> dict:
    command = {"opcode": opcode, "argumentBytes": 1}
    if writable:
        command["editor"] = {"fixedWidth": True}
    return {
        "id": event_id,
        "path": f"Game/field/atel/Atel_{event_id:04d}.dat",
        "objects": [{
            "functions": [{
                "complete": problem is None,
                "commands": [command],
                "problem": problem,
            }],
        }],
    }


class EventAuditCliTests(unittest.TestCase):
    def test_multiple_json_inputs_emit_aggregate_summary(self):
        with tempfile.TemporaryDirectory(prefix="chrono-event-audit-") as temp_name:
            root = Path(temp_name)
            first = root / "one.json"
            second = root / "two.json"
            first.write_text(json.dumps(payload(1, 0x83, True)), encoding="utf-8")
            second.write_text(json.dumps(payload(
                2, 0x8E, False,
                {"opcode": 0xF1, "reason": "PC command boundary is unresolved"},
            )), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main([str(first), str(second)])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["kind"], "chrono-trigger-event-audit-summary")
            self.assertEqual(result["events"], 2)
            self.assertEqual(result["decodedCommands"], 2)
            self.assertEqual(result["argumentCommands"], 2)
            self.assertEqual(result["writableCommands"], 1)
            self.assertEqual(result["readOnlyCommands"], 1)
            self.assertEqual(result["hotspots"][0]["opcode"], 0xF1)
            self.assertEqual(result["hotspots"][0]["stopCount"], 1)
            self.assertEqual(result["hotspots"][0]["sampleEventIds"], [2])
            self.assertEqual(result["hotspots"][0]["stopEventIds"], [2])
            self.assertTrue(result["hotspots"][0]["dynamicOrUnresolvedBoundary"])

    def test_single_input_keeps_event_level_output(self):
        with tempfile.TemporaryDirectory(prefix="chrono-event-audit-") as temp_name:
            path = Path(temp_name) / "event.json"
            path.write_text(json.dumps(payload(9, 0x82, True)), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([str(path)])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["kind"], "chrono-trigger-event-audit")
            self.assertEqual(result["eventId"], 9)
            self.assertEqual(result["writablePercent"], 100.0)

    def test_direct_install_scan_reads_arc1_and_filters_events(self):
        with tempfile.TemporaryDirectory(prefix="chrono-event-audit-live-") as temp_name:
            root = Path(temp_name)
            game = root / "game"
            project = root / "project"
            game.mkdir()
            _build_smoke_archive(game / "resources.bin", [
                ("Game/field/atel/Atel_0001.dat", _field_event(bytes((0x82, 0x04, 0x00)))),
                ("Game/field/atel/Atel_0002.dat", _field_event(bytes((0x8E, 0x80, 0x00)))),
            ])

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--game", str(game), "--project", str(project)])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["kind"], "chrono-trigger-event-audit-summary")
            self.assertEqual(result["scanSource"], "mine")
            self.assertEqual(result["selectedEventIds"], [1, 2])
            self.assertEqual(result["auditedEventIds"], [1, 2])
            self.assertEqual(result["scanErrorCount"], 0)
            self.assertEqual(result["scanErrors"], [])
            self.assertEqual(result["events"], 2)
            self.assertEqual(result["functions"], 2)
            self.assertEqual(result["decodedCommands"], 4)
            self.assertEqual(result["argumentCommands"], 2)
            self.assertEqual(result["zeroArgumentCommands"], 2)
            self.assertEqual(result["writableCommands"], 1)
            self.assertEqual(result["readOnlyCommands"], 1)
            self.assertEqual(result["writablePercent"], 50.0)
            self.assertEqual([row["opcode"] for row in result["hotspots"]], [0x8E])
            self.assertEqual(result["hotspots"][0]["sampleEventIds"], [2])
            self.assertEqual(result["hotspots"][0]["readOnlyEventIds"], [2])
            self.assertEqual(result["hotspots"][0]["stopEventIds"], [])

            selected_output = io.StringIO()
            with redirect_stdout(selected_output):
                code = main([
                    "--game", str(game), "--project", str(project),
                    "--source", "vanilla", "--event", "2",
                ])
            self.assertEqual(code, 0)
            selected = json.loads(selected_output.getvalue())
            self.assertEqual(selected["kind"], "chrono-trigger-event-audit")
            self.assertEqual(selected["eventId"], 2)
            self.assertEqual(selected["scanSource"], "vanilla")
            self.assertEqual(selected["selectedEventIds"], [2])
            self.assertEqual(selected["auditedEventIds"], [2])
            self.assertEqual(selected["scanErrorCount"], 0)
            self.assertEqual(selected["argumentCommands"], 1)
            self.assertEqual(selected["readOnlyCommands"], 1)
            self.assertEqual(selected["writablePercent"], 0.0)

    def test_direct_scan_reports_bad_overlay_and_vanilla_still_audits(self):
        with tempfile.TemporaryDirectory(prefix="chrono-event-audit-overlay-") as temp_name:
            root = Path(temp_name)
            game = root / "game"
            project = root / "project"
            game.mkdir()
            _build_smoke_archive(game / "resources.bin", [
                ("Game/field/atel/Atel_0001.dat", _field_event(bytes((0x82, 0x04, 0x00)))),
            ])
            overlay = project / "Game" / "field" / "atel" / "Atel_0001.dat"
            overlay.parent.mkdir(parents=True)
            overlay.write_bytes(b"\x01")

            mine_output = io.StringIO()
            with redirect_stdout(mine_output):
                code = main([
                    "--game", str(game), "--project", str(project), "--event", "1",
                ])
            self.assertEqual(code, 0)
            mine = json.loads(mine_output.getvalue())
            self.assertEqual(mine["kind"], "chrono-trigger-event-audit-summary")
            self.assertEqual(mine["selectedEventIds"], [1])
            self.assertEqual(mine["auditedEventIds"], [])
            self.assertEqual(mine["scanErrorCount"], 1)
            self.assertEqual(mine["scanErrors"][0]["eventId"], 1)
            self.assertIn("pointer table is truncated", mine["scanErrors"][0]["error"])

            vanilla_output = io.StringIO()
            with redirect_stdout(vanilla_output):
                code = main([
                    "--game", str(game), "--project", str(project),
                    "--source", "vanilla", "--event", "1",
                ])
            self.assertEqual(code, 0)
            vanilla = json.loads(vanilla_output.getvalue())
            self.assertEqual(vanilla["kind"], "chrono-trigger-event-audit")
            self.assertEqual(vanilla["auditedEventIds"], [1])
            self.assertEqual(vanilla["scanErrorCount"], 0)
            self.assertEqual(vanilla["argumentCommands"], 1)
            self.assertEqual(vanilla["writableCommands"], 1)


if __name__ == "__main__":
    unittest.main()

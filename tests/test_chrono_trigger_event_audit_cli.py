from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.chrono_trigger_event_audit import main


def payload(event_id: int, opcode: int, writable: bool, problem: dict | None = None) -> dict:
    command = {"opcode": opcode}
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
            self.assertEqual(result["writableCommands"], 1)
            self.assertEqual(result["readOnlyCommands"], 1)
            self.assertEqual(result["hotspots"][0]["opcode"], 0xF1)
            self.assertEqual(result["hotspots"][0]["stopCount"], 1)
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


if __name__ == "__main__":
    unittest.main()

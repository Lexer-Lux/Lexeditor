"""Hermetic checks for the issue-177 recording tool spec (no game)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.rdr2 import core_recording_tool as crt


def valid_plan():
    return {
        "approach": "frame_synced_integer_sampler",
        "cadence_hz": 60,
        "timebase": "monotonic",
        "sample_fields": ["timestamp", "core_value"],
        "output_format": "jsonl",
        "video_pairing": "paired_reference_video",
        "sequence_binding": "restoration_then_drain",
    }


def samples(count=5, cadence_hz=60, start_value=50):
    return [
        {"timestamp": i / cadence_hz, "core_value": start_value - i}
        for i in range(count)
    ]


class CoreRecordingToolTests(unittest.TestCase):
    def test_valid_plan_passes(self):
        self.assertEqual(crt.validate_recorder_plan(valid_plan()), [])

    def test_tween_approach_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "gameplay_tween smoother"
        errors = crt.validate_recorder_plan(plan)
        self.assertTrue(any("gameplay_tween" in e for e in errors))

    def test_non_monotonic_timebase_is_rejected(self):
        plan = valid_plan()
        plan["timebase"] = "wall_clock"
        errors = crt.validate_recorder_plan(plan)
        self.assertTrue(any("monotonic" in e for e in errors))

    def test_valid_samples_pass(self):
        self.assertEqual(crt.validate_trace_records(samples(), 60), [])

    def test_non_monotonic_samples_rejected(self):
        rows = samples()
        rows[2]["timestamp"] = rows[1]["timestamp"]
        errors = crt.validate_trace_records(rows, 60)
        self.assertTrue(any("monotonic" in e for e in errors))

    def test_fractional_core_value_rejected(self):
        rows = samples()
        rows[1]["core_value"] = 49.5
        errors = crt.validate_trace_records(rows, 60)
        self.assertTrue(any("integer" in e for e in errors))

    def test_out_of_range_core_value_rejected(self):
        rows = samples()
        rows[0]["core_value"] = 101
        errors = crt.validate_trace_records(rows, 60)
        self.assertTrue(any("0-100" in e for e in errors))

    def test_broken_cadence_rejected(self):
        rows = samples()
        rows[3]["timestamp"] = 1.0
        errors = crt.validate_trace_records(rows, 60)
        self.assertTrue(any("cadence" in e for e in errors))

    def test_empty_trace_rejected(self):
        self.assertTrue(crt.validate_trace_records([], 60))


def trace(values, cadence_hz=60.0):
    gap = 1.0 / cadence_hz
    return [
        {"timestamp": index * gap, "core_value": value}
        for index, value in enumerate(values)
    ]


class TraceSummaryTests(unittest.TestCase):
    def test_single_step_trace_reads_single_step_only(self):
        samples = trace([50, 50, 51, 52, 52, 53])
        self.assertEqual(crt.validate_trace_records(samples, 60.0), [])
        summary = crt.summarize_trace(samples)
        self.assertEqual(summary["cadence_read"], "single_step_only")
        self.assertEqual(summary["max_step"], 1)
        self.assertEqual(summary["changes"], 3)

    def test_multi_point_jump_reads_batching(self):
        samples = trace([50, 50, 55, 55, 56])
        self.assertEqual(crt.validate_trace_records(samples, 60.0), [])
        summary = crt.summarize_trace(samples)
        self.assertEqual(summary["cadence_read"], "multi_point_batching")
        self.assertEqual(summary["max_step"], 5)

    def test_flat_trace_reads_no_change(self):
        samples = trace([70, 70, 70])
        summary = crt.summarize_trace(samples)
        self.assertEqual(summary["cadence_read"], "no_change_observed")
        self.assertEqual(summary["samples"], 3)

    def test_summary_counts_samples_and_changes(self):
        samples = trace([10, 11, 11, 12])
        summary = crt.summarize_trace(samples)
        self.assertEqual(summary["samples"], 4)
        self.assertEqual(summary["changes"], 2)


if __name__ == "__main__":
    unittest.main()

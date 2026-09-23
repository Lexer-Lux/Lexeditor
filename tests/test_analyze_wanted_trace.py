"""Hermetic tests for tools/analyze_wanted_trace.py: synthetic log in, rows out."""
import unittest

from tools.analyze_wanted_trace import summarize, report


SAMPLE_LINES = [
    "0 pos=1.00,2.00,3.00 law_incident=1 wanted_score=50 wanted_level=1 "
    "hud_crime=0x1 dispatch=0x0 witnesses=1 pending_witnesses=0 "
    "investigators=1 any_law_investigating=1 seconds_since_seen=0.000 "
    "radius=60.0 origin_distance=0.0 visual_dark_red=0 nearby_law=candidates=0",
    "250 pos=1.50,2.00,3.00 law_incident=1 wanted_score=50 wanted_level=1 "
    "hud_crime=0x1 dispatch=0x0 witnesses=1 pending_witnesses=0 "
    "investigators=1 any_law_investigating=1 seconds_since_seen=0.250 "
    "radius=60.0 origin_distance=0.5 visual_dark_red=0 nearby_law=candidates=0",
    "500 VISUAL_MARK dark_red=1",
    "750 pos=5.00,2.00,3.00 law_incident=0 wanted_score=0 wanted_level=0 "
    "hud_crime=0x0 dispatch=0x0 witnesses=0 pending_witnesses=0 "
    "investigators=0 any_law_investigating=0 seconds_since_seen=12.500 "
    "radius=0.0 origin_distance=4.0 visual_dark_red=1 nearby_law=candidates=0",
]


class AnalyzeWantedTraceTests(unittest.TestCase):
    def test_folds_same_state_into_one_row(self):
        rows, marks = summarize(SAMPLE_LINES)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["first_ms"], 0)
        self.assertEqual(rows[0]["last_ms"], 250)
        self.assertEqual(rows[0]["level"], "1")

    def test_transition_opens_new_row(self):
        rows, _ = summarize(SAMPLE_LINES)
        self.assertEqual(rows[1]["first_ms"], 750)
        self.assertEqual(rows[1]["level"], "0")
        self.assertEqual(rows[1]["last_seen"], "12.500")

    def test_marks_collected(self):
        _, marks = summarize(SAMPLE_LINES)
        self.assertEqual(marks, [(500, 1)])

    def test_report_renders_durations(self):
        rows, marks = summarize(SAMPLE_LINES)
        text = report(rows, marks)
        self.assertIn("duration=250ms", text)
        self.assertIn("mark@500ms dark_red=1", text)

    def test_noise_lines_ignored(self):
        rows, marks = summarize(["BEGIN", "# header", "garbage"])
        self.assertEqual((rows, marks), ([], []))


if __name__ == "__main__":
    unittest.main()

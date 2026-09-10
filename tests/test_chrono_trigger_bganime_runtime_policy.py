from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "games" / "chrono_trigger"


class BgAnimeRuntimePolicyTests(unittest.TestCase):
    def test_runtime_evidence_gate_records_required_hypotheses_and_separate_composition_gate(self):
        text = (GAME / "BGANIME_RUNTIME_EVIDENCE.md").read_text(encoding="utf-8")
        for phrase in (
            "H0 — base graphics first",
            "H1 — frame 0 copied on load",
            "H2 — frame 0 copied on first tick",
            "H3 — pre-advanced phase",
            "first observable rendered state",
            "wraps at least once",
            "leaving and re-entering the location resets or preserves the phase",
            "Composition remains a separate gate",
            "PrioMap",
            "Runtime animation playback: unsupported",
            "Main/sub/priority composition: unsupported",
        ):
            self.assertIn(phrase, text)

    def test_readme_still_refuses_runtime_playback_and_composition_claims(self):
        text = (GAME / "README.md").read_text(encoding="utf-8")
        self.assertIn("animation playback remains disabled", text)
        self.assertIn("Main/sub blend and priority composition remain unsupported", text)
        self.assertIn("PrioMap", text)
        self.assertIn("unknown PC-only layer-priority data", text)
        self.assertIn("BGANIME_RUNTIME_EVIDENCE.md", text)

    def test_data_map_keeps_bganime_structural_not_integrated_playback(self):
        text = (GAME / "coverage.py").read_text(encoding="utf-8")
        self.assertIn('"kind": "scene-chip-animation"', text)
        self.assertIn('"coverage": "structural"', text)
        self.assertIn("playback remains unsupported", text)
        self.assertIn("blend/priority composition remain explicitly unsupported", text)


if __name__ == "__main__":
    unittest.main()

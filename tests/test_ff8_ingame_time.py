"""Contracts for FF8's local-clock main-menu tweak."""
from pathlib import Path
import unittest

from games.ff8 import menu_qol_issue_61

ROOT = Path(__file__).resolve().parents[1]


class InGameTimeTests(unittest.TestCase):
    def test_clock_is_available_and_old_blocker_is_gone(self):
        self.assertTrue(menu_qol_issue_61.INGAME_TIME_AVAILABLE)
        self.assertEqual(menu_qol_issue_61.INGAME_TIME_BLOCKER, "")

    def test_runtime_uses_wall_clock_not_saved_play_time(self):
        source = (ROOT / "games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("enable_ff8_ingame_time", source)
        self.assertIn("draw_main_menu_clock", source)
        self.assertIn("std::time(nullptr)", source)
        self.assertIn("localtime_s", source)
        self.assertNotIn("played_time_secs", source)
        self.assertIn("MODE_MENU", source)

    def test_clock_has_independent_runtime_config(self):
        prepare = (ROOT / "tools/prepare_ff8_native_build.py").read_text(encoding="utf-8")
        self.assertIn("enable_ff8_ingame_time", prepare)
        settings = (ROOT / "games/ff8/gameplay_settings.py").read_text(encoding="utf-8")
        self.assertIn('"inGameTime"', settings)
        self.assertIn('("enable_ff8_ingame_time", in_game_time)', settings)
        self.assertIn("in_game_time=in_game_time", settings)

    def test_editor_exposes_clock_and_explains_semantics(self):
        editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
        self.assertIn('aria-label="In-game Time"', editor)
        self.assertIn('row("IN-GAME TIME"', editor)
        self.assertIn("local clock", editor)
        self.assertIn("does not replace FF8's saved play-time counter", editor)

    def test_main_menu_hook_can_be_installed_without_xp_bars(self):
        source = (ROOT / "games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("if (!enable_ff8_xp_bars && !enable_ff8_ingame_time) return;", source)
        self.assertIn("if (!enable_ff8_xp_bars) return;", source)
        self.assertIn("enable_ff8_ingame_time && g_capture.surface == XpSurface::main_menu", source)


if __name__ == "__main__":
    unittest.main()

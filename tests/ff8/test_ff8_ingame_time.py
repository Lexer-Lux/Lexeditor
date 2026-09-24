"""Contracts for FF8's local-clock main-menu tweak."""
from pathlib import Path
import unittest

from plugins.ff8 import menu_qol_issue_61

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui


class InGameTimeTests(unittest.TestCase):
    def test_clock_is_available_and_old_blocker_is_gone(self):
        self.assertTrue(menu_qol_issue_61.INGAME_TIME_AVAILABLE)
        self.assertEqual(menu_qol_issue_61.INGAME_TIME_BLOCKER, "")

    def test_runtime_uses_wall_clock_not_saved_play_time(self):
        source = (ROOT / "plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("enable_ff8_ingame_time", source)
        # The clock is drawn by hooking the native PLAY-time renderer rather
        # than by a function of our own, which is why the hook is named for
        # the menu it intercepts.
        self.assertIn("main_menu_clock_hook", source)
        self.assertIn("g_clock_renderer", source)
        self.assertIn("std::time(nullptr)", source)
        self.assertIn("localtime_s", source)
        self.assertNotIn("played_time_secs", source)
        self.assertIn("MODE_MENU", source)

    def test_clock_has_independent_runtime_config(self):
        prepare = (ROOT / "tools/prepare_ff8_native_build.py").read_text(encoding="utf-8")
        self.assertIn("enable_ff8_ingame_time", prepare)
        settings = (ROOT / "plugins/ff8/gameplay_settings.py").read_text(encoding="utf-8")
        self.assertIn('"inGameTime"', settings)
        self.assertIn('("enable_ff8_ingame_time", in_game_time)', settings)
        self.assertIn("in_game_time=in_game_time", settings)

    def test_editor_exposes_clock_and_explains_semantics(self):
        editor = plugin_ui('ff8')
        self.assertIn('"aria-label":"In-game Time"', editor)
        self.assertIn('row("IN-GAME TIME"', editor)
        self.assertIn("local clock", editor)
        self.assertIn("does not replace FF8's saved play-time counter", editor)

    def test_main_menu_hook_can_be_installed_without_xp_bars(self):
        source = (ROOT / "plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp").read_text(
            encoding="utf-8"
        )
        # The clock installs without XP bars. The gate has since grown to
        # cover the HP and GF bars too, so it is checked by what it means
        # rather than by one exact spelling that keeps moving.
        gate = "if (!ff8 || (!enable_ff8_xp_bars && !enable_ff8_hp_bars"
        self.assertIn(gate, source)
        self.assertIn("!enable_ff8_gf_hp_bars", source)
        self.assertIn("!enable_ff8_ingame_time && !enable_ff8_better_hp_colors", source)
        self.assertIn("if (!enable_ff8_xp_bars) return;", source)
        # The clock is not an overlay surface any more; it hooks the native
        # PLAY-time renderer. What still has to hold is the ordering: the
        # clock is installed before the XP-bars early return, so turning XP
        # bars off cannot take the clock with it.
        clock = source.index("replace_call(0x004C1C6E")
        xp_only = source.index("if (!enable_ff8_xp_bars) return;")
        self.assertLess(clock, xp_only)


if __name__ == "__main__":
    unittest.main()

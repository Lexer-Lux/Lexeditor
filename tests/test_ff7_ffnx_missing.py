"""FF7 missing FFNx.toml degrades (save/export work) instead of erroring."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plugins.ff7 import deployment  # noqa: E402
from test_shared_ui_feedback import framework, page  # noqa: E402,F401  (pytest fixture)


class FFNxMissingTests(unittest.TestCase):
    def test_missing_config_degrades_with_clear_copy(self):
        with tempfile.TemporaryDirectory() as name:
            config = deployment.ffnx_config(Path(name))
        self.assertFalse(config["available"])
        self.assertNotIn("was not found", config["message"])
        for phrase in ("has not created", "game root", "ff7/workingdir",
                       "Saving and exporting", "deploy"):
            self.assertIn(phrase, config["message"])
        self.assertTrue(config["path"].endswith("FFNx.toml"))

    def test_missing_ffnx_is_flagged_not_a_plan_blocker(self):
        from tests.verify_ff7_datasets import write_kernel
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_kernel(root / "game/data/lang-en/kernel/KERNEL.BIN")
            plan = deployment.build_plan(root / "game", root / "project")
            self.assertFalse(plan["ffnx"]["available"])
            self.assertFalse(any("FFNx" in blocker for blocker in plan["blocked"]),
                             plan["blocked"])


def test_unavailable_settings_render_degrade_copy(page):
    with tempfile.TemporaryDirectory() as name:
        config = deployment.ffnx_config(Path(name))
    framework(page)
    page.evaluate("""config => {
      document.querySelector('main').append(
        LexeditorUI.platformConfigView({config}));
    }""", config)
    block = page.locator('.lex-platform-config-unavailable')
    assert block.count() == 1
    assert 'has not created' in block.inner_text()
    assert block.locator('code').inner_text().endswith('FFNx.toml')


if __name__ == "__main__":
    unittest.main()

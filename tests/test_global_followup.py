from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from plugin_api import GamePlugin, ModProjectSpec, validate_plugin
from tools import generate_credits

def _noop():return []

def _launch():return 0

class FollowupTests(unittest.TestCase):
    def test_credits_check_is_read_only_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'ui').mkdir()
            result={'schema':1,'shared':{},'plugins':{}}
            with patch.object(generate_credits,'ROOT',root),patch.object(generate_credits,'generate',return_value=result):
                generate_credits.main([])
                dest=root/'ui/credits.json';before=dest.read_bytes()
                self.assertEqual(generate_credits.main(['--check']),0)
                self.assertEqual(dest.read_bytes(),before)
                dest.write_text('changed by a fixture',encoding='utf-8')
                with self.assertRaises(SystemExit) as raised:generate_credits.main(['--check'])
                self.assertEqual(raised.exception.code,1)
                self.assertEqual(dest.read_text(encoding='utf-8'),'changed by a fixture')
    def test_windows_project_root_is_absolute_even_on_non_windows_ci(self):
        plugin=GamePlugin(
            plugin_id='windows-project-fixture',name='Fixture',subtitle='Fixture',description='Fixture',accent='#fff',
            check=_noop,launch=_launch,
            projects=ModProjectSpec(root_env='LEXEDITOR_FIXTURE_PROJECT',default_root=Path('C:/FixtureMod')),
        )
        validate_plugin(plugin)
    def test_obsolete_camera_clamps_not_reintroduced_in_help(self):
        text=(ROOT/'games/rdr2/editor.html').read_text(encoding='utf-8')
        self.assertNotIn('Clamped to -2.00..2.00',text)
        self.assertNotIn('Clamped to 0.30..8.00',text)
        # 1.2 puts bounds on the control and keeps only behavior in its help.
        self.assertIn('{min:range.min}',text)
        self.assertIn('{max:range.max}',text)
        self.assertIn('Changing this setting requires: ${boundary}',text)
    def test_blank_keeps_graphs_without_removed_design_review_assets(self):
        blank=(ROOT/'games/blank/editor.html').read_text(encoding='utf-8')
        self.assertNotIn('design-review.js',blank)
        self.assertNotIn('design-review.css',blank)
        self.assertIn('id:"graphs",label:"Graphs"',blank)
        self.assertIn('curveEditor(',blank)
    def test_guide_edits_sources_not_generated_bundle(self):
        text=(ROOT/'docs/ADDING_A_GAME.md').read_text(encoding='utf-8')
        self.assertIn('ui/credits-sources.json',text)
        self.assertIn('generate_credits.py --check',text)

if __name__=='__main__':unittest.main()

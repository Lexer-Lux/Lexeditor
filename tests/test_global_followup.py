from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import generate_credits

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
    def test_obsolete_camera_clamps_not_reintroduced_in_help(self):
        text=(ROOT/'games/rdr2/editor.html').read_text(encoding='utf-8')
        self.assertNotIn('Clamped to -2.00..2.00',text)
        self.assertNotIn('Clamped to 0.30..8.00',text)
        self.assertIn('Editor range: ${range.min} to ${range.max}',text)
        self.assertIn('Apply requirement: ${boundary}',text)
    def test_design_review_is_opt_in_and_has_no_write_or_launch(self):
        text=(ROOT/'ui/design-review.js').read_text(encoding='utf-8')
        for forbidden in ('fetch(', 'pywebview', 'localStorage', 'sessionStorage', '/api/'):
            self.assertNotIn(forbidden,text)
        blank=(ROOT/'games/blank/editor.html').read_text(encoding='utf-8')
        self.assertIn('id:"design",label:"Design Review"',blank)
        self.assertIn('id:"graphs",label:"Graphs"',blank)
        self.assertIn('curveEditor(',blank)
    def test_guide_edits_sources_not_generated_bundle(self):
        text=(ROOT/'docs/ADDING_A_GAME.md').read_text(encoding='utf-8')
        self.assertIn('ui/credits-sources.json',text)
        self.assertIn('generate_credits.py --check',text)

if __name__=='__main__':unittest.main()

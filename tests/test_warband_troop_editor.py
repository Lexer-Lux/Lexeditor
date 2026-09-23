from pathlib import Path
import tempfile
import unittest
from games.warband.troop_editor import troop_data, save_troops

SOURCE = '''# encoding: utf-8
from header_troops import *
troops = [
 ["soldier", "Soldier", "Soldiers", tf_hero, 0, 0, fac_commoners,
  [itm_sword, itm_sword], str_4|agi_4|int_4|cha_4|level(10), wp(20), 0, 0],
 ## ["cut", "Cut", "Cut troops", 0, 0, 0, fac_commoners, [], 0, 0, 0, 0],
]
upgrade(troops, "soldier", "cut")
'''

class TroopEditorTests(unittest.TestCase):
    def test_save_preserves_cut_markers_equipment_and_upgrade_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(SOURCE)
            (root/'header_troops.py').write_text('tf_hero=16\nstr_4=4\nagi_4=1024\nint_4=262144\ncha_4=67108864\n')
            before=source.read_bytes();data=troop_data(root)
            self.assertEqual(data['rows'][0]['stats']['level'],10)
            save_troops(root,data['sha256'],[
                {'id':'soldier','fields':{'name':'New "café"','attributes':'str_4|agi_4|int_4|cha_4|level(255)'}},
                {'id':'cut','fields':{'plural':'Hidden troops'}}])
            result=troop_data(root)
            self.assertEqual(result['rows'][0]['name'],'New "café"')
            self.assertEqual(result['rows'][0]['stats']['level'],255)
            self.assertEqual(result['rows'][0]['items'],['itm_sword','itm_sword'])
            self.assertEqual(result['rows'][1]['status'],'CUT')
            self.assertEqual(result['rows'][1]['plural'],'Hidden troops')
            self.assertIn('upgrade(troops, "soldier", "cut")',source.read_text())
            self.assertEqual(source.with_suffix('.py.lexeditor.bak').read_bytes(),before)
            with self.assertRaises(ValueError):save_troops(root,data['sha256'],[])

    def test_nested_literals_are_ignored_and_duplicate_ids_need_record_identity(self):
        source_text = '''troops = [
 ["dup", "First", "Firsts", 0, 0, 0, 0, [], 0, 0, 0, 0],
 helper([
   ["nested", "Nested", "Nesteds", 0, 0, 0, 0, [], 0, 0, 0, 0],
 ]),
 ["dup", "Second", "Seconds", 0, 0, 0, 0, [], 0, 0, 0, 0],
]
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(source_text)
            data=troop_data(root)
            self.assertEqual([row['name'] for row in data['rows']], ['First', 'Second'])
            self.assertEqual([row['recordIndex'] for row in data['rows']], [0, 1])
            with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
                save_troops(root,data['sha256'],[{'id':'dup','fields':{'name':'Wrong'}}])
            self.assertEqual(source.read_text(),source_text)
            save_troops(root,data['sha256'],[
                {'recordIndex':1,'originalId':'dup','fields':{'name':'Updated Second'}}])
            result=troop_data(root)
            self.assertEqual([row['name'] for row in result['rows']], ['First', 'Updated Second'])
            self.assertIn('"nested", "Nested"',source.read_text())

    def test_invalid_edits_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(SOURCE)
            data=troop_data(root);before=source.read_bytes()
            for fields in ({'id':'renamed'}, {'flags':'1, 2'}, {'attributes':'invalid('}):
                with self.assertRaises((ValueError,SyntaxError)):
                    save_troops(root,data['sha256'],[{'id':'soldier','fields':fields}])
                self.assertEqual(source.read_bytes(),before)

if __name__=='__main__':unittest.main()

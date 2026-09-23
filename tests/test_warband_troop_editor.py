from pathlib import Path
import tempfile
import unittest

from plugins.warband.troop_editor import troop_data, save_troops


SOURCE = '''# encoding: utf-8
from header_troops import *
troops = [
 ["soldier", "Soldier", "Soldiers", tf_hero, 0, 0, fac_commoners,
  [itm_sword, itm_sword], str_4|agi_4|int_4|cha_4|level(10), wp(20), 0, 0],
 ## ["cut", "Cut", "Cut troops", 0, 0, 0, fac_commoners, [], 0, 0, 0, 0],
]
upgrade(troops, "soldier", "cut")
'''

NESTED_STRING_LIST = '''troops = [
 ["soldier", "Soldier", "Soldiers", 0, 0, 0, fac_commoners,
  ["itm_a","itm_b","itm_c","itm_d","itm_e","itm_f","itm_g","itm_h","itm_i","itm_j","itm_k","itm_l","itm_m"],
  0, 0, 0, 0],
]
'''

DUPLICATE_ACTIVE_CUT = '''troops = [
 ["same", "Active", "Actives", 0, 0, 0, fac_commoners, [], 0, 0, 0, 0],
 ## ["same", "Old cut", "Old cuts", 0, 0, 0, fac_commoners, [], 0, 0, 0, 0],
]
'''


class TroopEditorTests(unittest.TestCase):
    def test_save_preserves_cut_markers_equipment_and_upgrade_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(SOURCE)
            (root/'header_troops.py').write_text('tf_hero=16\nstr_4=4\nagi_4=1024\nint_4=262144\ncha_4=67108864\n')
            before=source.read_bytes();data=troop_data(root)
            soldier,cut=data['rows']
            self.assertEqual(soldier['stats']['level'],10)
            save_troops(root,data['sha256'],[
                {'recordIndex':soldier['recordIndex'],'originalId':'soldier','fields':{'name':'New "café"','attributes':'str_4|agi_4|int_4|cha_4|level(255)'}},
                {'recordIndex':cut['recordIndex'],'originalId':'cut','fields':{'plural':'Hidden troops'}}])
            result=troop_data(root)
            self.assertEqual(result['rows'][0]['name'],'New "café"')
            self.assertEqual(result['rows'][0]['stats']['level'],255)
            self.assertEqual(result['rows'][0]['items'],['itm_sword','itm_sword'])
            self.assertEqual(result['rows'][1]['status'],'CUT')
            self.assertEqual(result['rows'][1]['plural'],'Hidden troops')
            self.assertIn('upgrade(troops, "soldier", "cut")',source.read_text())
            self.assertEqual(source.with_suffix('.py.lexeditor.bak').read_bytes(),before)
            with self.assertRaises(ValueError):save_troops(root,data['sha256'],[])

    def test_invalid_edits_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(SOURCE)
            data=troop_data(root);before=source.read_bytes();soldier=data['rows'][0]
            for fields in ({'id':'renamed'}, {'flags':'1, 2'}, {'attributes':'invalid('}):
                with self.assertRaises((ValueError,SyntaxError)):
                    save_troops(root,data['sha256'],[{
                        'recordIndex':soldier['recordIndex'],'originalId':'soldier','fields':fields}])
                self.assertEqual(source.read_bytes(),before)

    def test_nested_string_list_is_not_a_fake_troop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(NESTED_STRING_LIST)
            rows=troop_data(root)['rows']
            self.assertEqual([(row['id'],row['name']) for row in rows],[('soldier','Soldier')])
            self.assertFalse(any(row['id'].startswith('itm_') for row in rows))

    def test_duplicate_active_and_cut_ids_are_independently_editable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(DUPLICATE_ACTIVE_CUT)
            before=source.read_bytes();data=troop_data(root)
            self.assertEqual([row['id'] for row in data['rows']],['same','same'])
            active,cut=data['rows']
            self.assertEqual([active['status'],cut['status']],['active','CUT'])
            result=save_troops(root,data['sha256'],[{
                'recordIndex':cut['recordIndex'],'originalId':'same',
                'fields':{'plural':'Retired cuts'}}])
            self.assertEqual(result['saved'],1)
            reread=troop_data(root)['rows']
            self.assertEqual(reread[0]['name'],'Active')
            self.assertEqual(reread[1]['plural'],'Retired cuts')
            self.assertEqual([row['id'] for row in reread],['same','same'])
            self.assertEqual(source.with_suffix('.py.lexeditor.bak').read_bytes(),before)

    def test_ambiguous_legacy_id_edit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'module_troops.py';source.write_text(DUPLICATE_ACTIVE_CUT)
            data=troop_data(root)
            with self.assertRaisesRegex(ValueError,'ambiguous'):
                save_troops(root,data['sha256'],[{'id':'same','fields':{'name':'No'}}])


if __name__=='__main__':unittest.main()

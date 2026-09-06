"""Coverage claims must have a specific implemented interface, not just I/O."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class CoverageTests(unittest.TestCase):
    def test_ff7_same_file_different_editors_and_missing_config(self):
        from games.ff7 import server
        from tools.verify_ff7_datasets import write_kernel
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);game=root/'game';project=root/'project'
            source=game/'data/lang-en/kernel/KERNEL.BIN'
            write_kernel(source)
            # Exercise the real loader rather than mocking its removed private helper.
            with patch.object(server,'GAME_ROOT',game),patch.object(server,'PROJECT_ROOT',project):
                rows=server.data_map()['rows']
                editable=[row for row in rows if row['coverage']=='structured']
                self.assertEqual({row['target'] for row in editable},set(server.CATEGORIES))
                self.assertEqual(len({row['id'] for row in editable}),len(editable))
                self.assertTrue(all(row['status']=='partial' for row in editable))
                self.assertEqual(len({row['filename'] for row in editable}),1)
                config=next(row for row in rows if row['filename']=='FFNx.toml')
                self.assertEqual(config['coverage'],'unavailable');self.assertFalse(config['openable'])
                source.write_bytes(b'truncated fixture')
                broken=server.data_map()['rows']
                self.assertTrue(all(row['coverage']=='unavailable' for row in broken))
                self.assertTrue(all(not row['openable'] for row in broken))

    def test_ff9_dataset_target_and_missing_data(self):
        from games.ff9 import server
        fixture=[{'key':'one','tab':'characters','relativePath':'one.csv','label':'One','controls':'Starting data','available':True},
                 {'key':'two','tab':'characters','relativePath':'two.csv','label':'Two','controls':'Growth data','available':False}]
        with tempfile.TemporaryDirectory() as name,patch.object(server,'catalog',return_value=fixture),patch.object(server.paths,'GAME_ROOT',Path(name)):
            rows=server.data_map()['rows']
            self.assertEqual(rows[0]['coverage'],'structured');self.assertEqual(rows[0]['dataset'],'one')
            self.assertEqual(rows[1]['coverage'],'unavailable');self.assertEqual(rows[1]['status'],'not-integrated')
            self.assertFalse(rows[1]['openable'])

    def test_ff8_partial_fields_and_exact_navigation(self):
        from games.ff8 import formats
        with tempfile.TemporaryDirectory() as name,patch.object(formats.paths,'GAME_ROOT',Path(name)):
            rows={row['filename']:row for row in formats.data_map_rows()['rows']}
            self.assertEqual(rows['init.out']['status'],'partial')
            self.assertEqual(rows['field.fs']['targets'],['fields'])
            self.assertEqual(rows['battle/scene.out']['targets'],['encounters'])
            self.assertEqual(rows['FFNx.toml']['coverage'],'unavailable')
            self.assertTrue(all(row.get('targets') for row in rows.values() if row['coverage']=='structured'))

    def test_rdr_generated_inventory_cannot_invent_editors(self):
        from games.rdr import server
        supplied=[{'filename':'unknown.xml','status':'integrated','target':'items','openable':True,'notes':'Everything editable'}]
        rows=server._normalize_data_map_rows(supplied,interfaces={})
        self.assertEqual(rows[0]['coverage'],'unavailable');self.assertFalse(rows[0]['openable'])
        self.assertEqual(rows[0]['target'],'');self.assertEqual(rows[0]['status'],'not-integrated')

    def test_rdr_missing_files_and_nonshop_resource_not_integrated(self):
        from games.rdr import server
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'raw').mkdir();(root/'raw'/'not-a-shop.wgd').write_bytes(b'fixture')
            with patch.multiple(server,PREPARED_ROOT=root/'prepared',CONTENT_PREPARED_ROOT=root/'content',
                                GRINGO_UNPACKED_ROOT=root/'raw',GRINGO_PACKED_ROOT=root/'packed',
                                SETTINGS_FILE=root/'settings.ini',LOOT_FILE=root/'loot.json'),patch.object(server,'_map_has_shop_records',return_value=False):
                rows=server._provisional_data_map_rows()
                self.assertTrue(all(row['coverage']=='unavailable' for row in rows))
                self.assertTrue(all(not row['openable'] for row in rows))

    def test_rdr2_preservation_and_inactive_runtime_not_editing(self):
        from games.rdr2.data_map import build_data_map
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/'map.md'
            source.write_text('## Files\n- `weaponcomponents.meta` - Components\n- `catalog_sp.ymt` - Catalog\n- `unknown.bin` - Unknown\n',encoding='utf-8')
            rows={row['filename']:row for row in build_data_map(source)['rows']}
            self.assertEqual(rows['weaponcomponents.meta']['coverage'],'unavailable')
            self.assertFalse(rows['weaponcomponents.meta']['openable'])
            self.assertEqual(rows['catalog_sp.ymt']['coverage'],'structured')
            self.assertEqual(rows['catalog_sp.ymt']['status'],'partial')
            self.assertEqual(rows['projectile_speed_multipliers.csv']['coverage'],'view')
            self.assertTrue(all(row.get('target') for row in rows.values() if row['coverage']=='structured'))

    def test_all_plugins_use_shared_data_map(self):
        root=Path(__file__).resolve().parents[1]
        for game in ('blank','warband','ff7','ff8','ff9','rdr','rdr2'):
            text=(root/'games'/game/'editor.html').read_text(encoding='utf-8')
            self.assertIn('LexeditorUI.dataMap(',text,game)
        self.assertIn('games.ff7.server',(root/'games/ff7_2013/plugin.py').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()

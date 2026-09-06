"""Disposable full-cache fixture: no game install or asset editing is required."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from games.warband import model_preview as models, item_icons as icons


class IconMutationTests(unittest.TestCase):
    def test_texture_change_regenerates_pixels_and_keeps_modules_separate(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            mesh, material, tool = (root / p for p in ('mesh.brf', 'material.brf', 'reader.exe'))
            for path in (mesh, material, tool):
                path.write_bytes(b'disposable dependency fixture')
            texture = root / 'diffuse.dds'
            Image.new('RGBA', (8, 8), (220, 40, 20, 255)).save(texture, 'DDS')
            obj = root / 'sword.obj'
            obj.write_text('v -1 0 -1\nv 1 0 -1\nv 0 0 1\nvt 0 0\nvt 1 0\nvt .5 1\nvn 0 -1 0\nf 1/1/1 2/2/1 3/3/1\n')
            records = {'meshes': (mesh, {'name': 'sword', 'material': 'steel'}),
                       'materials': (material, {'name': 'steel', 'diffuseA': 'diffuse'})}
            with patch.multiple(models, CACHE_ROOT=root/'cache', MODULE_ROOT=root/'module-a',
                                BRF_SYNC=tool, MODULE_TEXTURES=root, GAME_TEXTURES=root/'unused'), \
                    patch.object(models, '_find_record', side_effect=lambda kind, name: records.get(kind)), \
                    patch.object(models, '_export_mesh', return_value=obj):
                cache = icons.IconCache()
                def generated():
                    cache.request('sword')
                    cache._queue.join()
                    path = cache.request('sword')
                    self.assertIsNotNone(path)
                    self.assertTrue(path.is_file())
                    return path
                first = generated()
                before = first.read_bytes()
                self.assertEqual(generated(), first)
                # Change real DDS pixels; all resolver, preview and icon caching stays real.
                Image.new('RGBA', (8, 8), (20, 40, 220, 255)).save(texture, 'DDS')
                changed = generated()
                self.assertNotEqual(changed, first)
                self.assertNotEqual(changed.read_bytes(), before)
                self.assertEqual(first.read_bytes(), before)
                with patch.object(models, 'MODULE_ROOT', root/'module-b'):
                    other = generated()
                    self.assertNotEqual(other, changed)
                self.assertEqual(generated(), changed)
                material.write_bytes(b'changed material dependency')
                self.assertNotEqual(generated(), changed)


if __name__ == '__main__':
    unittest.main()

"""Decode actual face coordinates and round-trip the exported GLB container."""
import struct
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.ff8 import assets,model_geometry,effect_model_textures
from plugins.ff8.vendor.ff8ue.glbbuilder import read_glb,read_accessor


def model_bytes(colored=False):
    vertices=struct.pack('<H',1)+struct.pack('<HH',0,3)+struct.pack('<9h',0,0,0,2048,0,0,0,2048,0)
    faces=struct.pack('<6H',*( (0,0,1,0,0,0) if colored else (1,0,0,0,0,0)))+struct.pack('<3H2B2BH2BH',0x8000,1,2,0,0,255,0,0,0,255,0)
    if colored: faces+=struct.pack('<I',0x20332211)
    geometry=struct.pack('<II',1,8)+vertices+faces+struct.pack('<I',3)
    sections=[bytes(16),geometry,bytes(4),b'',b'',struct.pack('<II',0,8),b'']
    cursor=4+4*(len(sections)+1)
    offsets=[cursor]
    for section in sections:
        cursor+=len(section)
        offsets.append(cursor)
    return struct.pack('<I',len(sections))+struct.pack(f'<{len(offsets)}I',*offsets)+b''.join(sections)


class ModelGeometryTests(unittest.TestCase):
    def test_motion_inventory_preserves_counts_without_decoding_poses(self):
        bones = bytes([2]) + bytes(15 + 2 * 48)
        animation = struct.pack('<3I', 2, 12, 13) + bytes([7, 19])
        data = bones + animation
        sections = [{'name': 'Skeleton', 'offset': 0, 'size': len(bones)},
                    {'name': 'Model animation', 'offset': len(bones), 'size': len(animation)}]
        self.assertEqual(assets._model_motion_info(data, sections, part=2),
                         [{'part': 2, 'bones': 2, 'animations': [{'id': 0, 'frames': 7}, {'id': 1, 'frames': 19}]}])
        for offset, value in ((len(bones), 257), (len(bones) + 4, 4), (len(bones) + 8, len(animation))):
            invalid = bytearray(data)
            struct.pack_into('<I', invalid, offset, value)
            self.assertEqual(assets._model_motion_info(invalid, sections), [])
        self.assertEqual(assets._model_motion_info(data, []), [])

    def test_diablos_parts_are_bounded_and_selected_for_export(self):
        original = model_bytes(colored=True)
        spans = assets.parse_dat_sections(original)
        sections = [original[s['offset']:s['offset'] + s['size']] for s in spans[:3]] + [b'']
        offsets = [24]
        for section in sections:
            offsets.append(offsets[-1] + len(section))
        part = struct.pack('<6I', 4, *offsets) + b''.join(sections)
        # Make the second part distinguishable in the scene and GLB.
        second = bytearray(part)
        struct.pack_into('<h', second, offsets[1] + 14, 1024)
        raw = part + second
        self.assertIsNone(assets.parse_dat_sections(raw))
        for filename in ('mag324_h.02', 'mag324_h.m00'):
            info = assets._battle_file_info(filename, raw)
            self.assertEqual(info['counts']['vertices'], 6)
            self.assertEqual(len(info['modelParts']), 2)
            with patch.object(assets, 'model_dat_bytes', return_value=raw), patch.object(effect_model_textures, 'sources', return_value={}):
                first = model_geometry.scene(filename, object_id=0)
                selected = model_geometry.scene(filename, object_id=1)
                self.assertNotEqual(first['positions'], selected['positions'])
                with tempfile.TemporaryDirectory(prefix='ff8-parts-') as directory:
                    path = Path(directory) / 'selected.glb'
                    path.write_bytes(model_geometry.glb(filename, object_id=1))
                    gltf, binary = read_glb(path)
                    positions = read_accessor(gltf, binary, gltf['meshes'][0]['primitives'][0]['attributes']['POSITION'])
                    self.assertEqual(positions, [tuple(selected['positions'][index]) for index in (2, 0, 1)])
                with self.assertRaisesRegex(ValueError, 'part'):
                    model_geometry.scene(filename, object_id=2)
            for invalid in (raw[:-1], raw + b'junk', part + b'bad header'):
                self.assertIsNone(assets.effect_model_parts(filename, invalid))
                with self.assertRaises(ValueError):
                    model_geometry.decode(filename, invalid)
        self.assertIsNone(assets.effect_model_parts('mag123_b.dat', raw))

    def test_four_section_effect_model_reuses_battle_geometry(self):
        original = model_bytes()
        spans = assets.parse_dat_sections(original)
        sections = [original[span['offset']:span['offset'] + span['size']] for span in spans[:3]] + [b'']
        offsets = [24]
        for section in sections:
            offsets.append(offsets[-1] + len(section))
        raw = struct.pack('<6I', 4, *offsets) + b''.join(sections)
        info = assets._battle_file_info('mag184_e.dat', raw)
        self.assertEqual(info['kind'], 'effect-model')
        self.assertEqual(info['counts']['vertices'], 3)
        with patch.object(assets, 'model_dat_bytes', return_value=raw), patch.object(effect_model_textures, 'sources', return_value={}):
            scene = model_geometry.scene('mag184_e.dat')
            self.assertEqual(len(scene['triangles']), 1)
            self.assertEqual(scene['textures'], [])
            self.assertEqual(model_geometry.glb('mag184_e.dat')[:4], b'glTF')
        self.assertEqual(assets._section_names('mag184_e.dat', 5), ('unmapped', None))
        self.assertEqual(assets._section_names('mag123_b.dat', 4), ('unmapped', None))

    def test_colored_primitives_are_not_dropped(self):
        with patch.object(assets,'model_dat_bytes',return_value=model_bytes(colored=True)):
            scene=model_geometry.scene('d0c000.dat')
            self.assertEqual(len(scene['triangles']),1)
            self.assertEqual(scene['triangles'][0]['texture'],-0x332211-2)
            payload=model_geometry.glb('d0c000.dat')
        with tempfile.TemporaryDirectory(prefix='ff8-colored-glb-') as directory:
            path=Path(directory)/'model.glb'
            path.write_bytes(payload)
            gltf,_=read_glb(path)
            primitive=gltf['meshes'][0]['primitives'][0]
            material=gltf['materials'][primitive['material']]
            self.assertEqual(material['pbrMetallicRoughness']['baseColorFactor'],[17/255,34/255,51/255,1.])

    @unittest.skipUnless(os.environ.get('LEXEDITOR_TEST_FF8_MODEL'),'optional installed model')
    def test_installed_model_geometry_and_animations_export(self):
        source=Path(os.environ['LEXEDITOR_TEST_FF8_MODEL'])
        raw=source.read_bytes()
        with patch.object(assets,'model_dat_bytes',return_value=raw):
            scene=model_geometry.scene(source.name)
            payload=model_geometry.glb(source.name)
        self.assertGreater(len(scene['positions']),0)
        self.assertGreater(len(scene['triangles']),0)
        sections=assets.parse_dat_sections(raw)
        self.assertEqual(assets._geometry_counts(raw,sections[1])['vertices'],len(scene['positions']))
        with tempfile.TemporaryDirectory(prefix='ff8-real-glb-') as directory:
            path=Path(directory)/'model.glb'
            path.write_bytes(payload)
            gltf,binary=read_glb(path)
            self.assertEqual(len(gltf['skins'][0]['joints']),scene['bones'])
            self.assertGreater(len(gltf['animations']),0)
            self.assertGreater(len(binary),0)
            print(f"Decoded {source.name}: {len(scene['positions'])} vertices, {len(scene['triangles'])} triangles, {scene['bones']} bones, {len(gltf['animations'])} exported animations")

    def test_scene_and_glb_share_the_decoded_geometry(self):
        raw=model_bytes()
        with patch.object(assets,'model_dat_bytes',return_value=raw):
            scene=model_geometry.scene('d0c000.dat')
            self.assertEqual(scene['positions'],[(0.0,0.0,0.0),(-1.0,0.0,0.0),(0.0,1.0,0.0)])
            self.assertEqual(tuple(scene['triangles'][0]['indices']),(2,0,1))
            payload=model_geometry.glb('d0c000.dat')
        with tempfile.TemporaryDirectory(prefix='ff8-glb-check-') as directory:
            path=Path(directory)/'model.glb'
            path.write_bytes(payload)
            gltf,binary=read_glb(path)
            primitive=gltf['meshes'][0]['primitives'][0]
            positions=read_accessor(gltf,binary,primitive['attributes']['POSITION'])
            self.assertEqual(positions,[tuple(scene['positions'][index]) for index in (2,0,1)])
            self.assertEqual(gltf['asset']['version'],'2.0')

    def test_invalid_container_and_truncated_skeleton_are_rejected(self):
        with self.assertRaises(ValueError): model_geometry.decode('d0c000.dat',b'invalid')
        raw=bytearray(model_bytes())
        # A skeleton count claiming an absent 48-byte record is rejected.
        raw[struct.unpack_from('<I',raw,4)[0]]=1
        with self.assertRaisesRegex(ValueError,'skeleton'):
            model_geometry.decode('d0c000.dat',bytes(raw))


if __name__=='__main__': unittest.main()

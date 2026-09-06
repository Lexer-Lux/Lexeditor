"""Asset-free tests for FF7 scene, kernel2, shop and independent project saves.

Synthetic executable hashes are registered only inside test patches. No runtime
bypass or fixture build is accepted by production EXE_PROFILES.
"""
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff7 import battle, extended as ex, format_codec as codec


def scene_fixture():
    scenes = []
    for scene in range(256):
        raw = bytearray(7808)
        struct.pack_into('<4H', raw, 0, scene, 65535, 65535, 65535)
        for slot in range(4):
            struct.pack_into('<H', raw, 8 + slot * 20 + 2, 65535)
            for enemy in range(6):
                struct.pack_into('<H', raw, 0x118 + slot * 96 + enemy * 16, scene if enemy == 0 else 65535)
        raw[0x298:0x2B8] = codec.encode_text(f'Enemy{scene}').ljust(32,b'\xff')
        struct.pack_into('<I', raw, 0x298 + 0xA4, 100 + scene)
        raw[0x840:0x880] = b'\xff' * 64
        struct.pack_into('<H', raw, 0x840, scene)
        raw[0x880:0x8A0] = codec.encode_text(f'Action{scene}').ljust(32,b'\xff')
        raw[0xC80:] = b'\xff' * (len(raw)-0xC80)
        struct.pack_into('<H', raw, 0xE80, 6)
        struct.pack_into('<H', raw, 0xE86+2, 32)
        raw[0xEA6:0xEA9] = bytes((0x60,scene,0x73))
        scenes.append(raw)
    output = bytearray()
    for first in range(0,256,8):
        block = bytearray(b'\xff' * 8192); pos=64
        for slot,raw in enumerate(scenes[first:first+8]):
            data=gzip.compress(bytes(raw),mtime=0)
            struct.pack_into('<I',block,slot*4,pos//4)
            block[pos:pos+len(data)]=data;pos+=(len(data)+3)&~3
        output.extend(block)
    return bytes(output)


def text_fixture():
    sections = [codec.pack_strings([f'Text {index}', 'Value '+r'\xEA\x01\xFF']) for index in range(18)]
    return codec.lzs_encode(b''.join(struct.pack('<I',len(s))+s for s in sections))


def exe_fixture(shift=0x400):
    data = bytearray(0x525000)
    data[:2] = b'MZ'; data[shift:shift+4]=b'\x55\x8b\xec\xc7'
    for i in range(10):
        at=0x5202B8+shift+i*12;data[at:at+12]=codec.encode_text(f'Name{i}').ljust(12,b'\xff')
    for i in range(2):
        at=0x520810+shift+i*132+0x10;data[at:at+12]=codec.encode_text(('Cait Sith','Vincent')[i]).ljust(12,b'\xff')
    for i in range(80):
        at=0x521A18+shift+i*84
        data[at:at+4] = bytes((0,0,1,0xAB))
        struct.pack_into('<IH',data,at+4,0,i)
        data[at+10:at+12]=b'\x12\x34'
    return bytes(data)


class CodecTests(unittest.TestCase):
    def test_lzs_roundtrips_and_bound(self):
        randomizer=random.Random(123)
        for data in (b'',b'a',b'abc'*4000,bytes(range(256))*60,randomizer.randbytes(50000),b'\0'*20000):
            self.assertEqual(codec.lzs_decode(codec.lzs_encode(data)),data)
        with self.assertRaises(ValueError):codec.lzs_decode(codec.lzs_encode(b'a'*100),limit=99)
        with self.assertRaises(ValueError):codec.lzs_decode(b'\0\0\0\0\xff')

    def test_reversible_controls_duplicates_and_invalid_text(self):
        for raw in (bytes(range(0,0xE7))+b'\xff',b'\xea\xff\x01\xf8\xff\xff',b'\xe7\xe8\xff'):
            self.assertEqual(codec.encode_text(codec.decode_text(raw)),raw)
        values=['Hello','Hello','Value '+r'\xEA\x01\xFF']
        self.assertEqual(codec.string_table(codec.pack_strings(values)),values)
        for text in ('bad😀',r'\xEA',r'\xFF',r'\xF900','a\\bad'):
            with self.subTest(text=text),self.assertRaises(ValueError):codec.encode_text(text)


class BinaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.scene=scene_fixture()

    def test_scene_noop_and_all_families(self):
        obj=battle.SceneArchive(self.scene)
        self.assertEqual({k:len(obj.records(k)) for k in battle.SCENE_CATEGORIES},{'enemies':256,'encounters':1024,'enemyAttacks':256,'enemyAI':768,'formationAI':1024})
        for key in battle.SCENE_CATEGORIES:obj.apply(key,obj.records(key))
        self.assertEqual(obj.to_bytes(),self.scene)

    def test_each_enemy_field_has_only_documented_byte_effect(self):
        for field in battle.ENEMY_FIELDS:
            obj=battle.SceneArchive(self.scene); rows=obj.records('enemies')
            value='Changed' if field['dataType']=='text' else field['maximum']
            rows[0]['values'][field['key']]=value; obj.apply('enemies',rows)
            expected=bytearray(obj.original_scenes[0])
            data=battle.write_values(expected[0x298:0x350],battle.ENEMY_FIELDS,rows[0]['values'])
            expected[0x298:0x350]=data
            self.assertEqual(obj.scenes[0],expected)
            self.assertEqual(obj.scenes[1:],list(map(bytearray,obj.original_scenes[1:])))
        reread=battle.SceneArchive(obj.to_bytes())
        self.assertEqual(reread.blocks,obj.blocks)
        self.assertEqual(reread.scenes,obj.scenes)

    def test_attack_and_third_formation_offsets(self):
        obj=battle.SceneArchive(self.scene)
        rows=obj.records('enemyAttacks'); rows[0]['values']['power']=77
        rows[0]['values']['name']='Test';obj.apply('enemyAttacks',rows)
        self.assertEqual(obj.scenes[0][0x4C0+15],77)
        rows=obj.records('encounters');rows[2]['values']['slot0_x']=-1234
        rows[2]['values']['camera1_y']=-7;obj.apply('encounters',rows)
        self.assertEqual(struct.unpack_from('<h',obj.scenes[0],0x1D8+2)[0],-1234)
        self.assertEqual(obj.scenes[0][0xC80:],obj.original_scenes[0][0xC80:])
        self.assertEqual(battle.SceneArchive(obj.to_bytes()).scenes,obj.scenes)

    def test_scene_bad_records_and_overflow_are_rejected(self):
        obj=battle.SceneArchive(self.scene);rows=obj.records('enemies')
        rows[0]['values']['hp']=True
        with self.assertRaises(ValueError):obj.apply('enemies',rows)
        self.assertEqual(obj.to_bytes(),self.scene)
        rows=obj.records('enemies');rows[-1]['id']=rows[0]['id']
        with self.assertRaises(ValueError):obj.apply('enemies',rows)
        rows=obj.records('encounters');rows[0]['values']['slot0_enemy']=30000
        with self.assertRaises(ValueError):obj.apply('encounters',rows)
        obj.scenes[0][:]=random.Random(123).randbytes(7808)
        obj.scenes[1][:]=random.Random(124).randbytes(7808)
        with self.assertRaisesRegex(ValueError,'capacity'):obj.to_bytes()

    def test_truncated_malformed_and_unsupported_scenes(self):
        for data in (self.scene[:-1],self.scene[:8192],bytes(8192)):
            with self.assertRaises(ValueError):battle.SceneArchive(data)
        data=bytearray(self.scene);struct.pack_into('<I',data,0,1)
        with self.assertRaises(ValueError):battle.SceneArchive(data)

    def test_text_noop_edit_preservation_and_limits(self):
        source=text_fixture();obj=ex.KernelText(source)
        obj.apply('texts',obj.records());self.assertEqual(obj.to_bytes(),source)
        rows=obj.records();rows[0]['values']['text']='New name'
        obj.apply('texts',rows);saved=ex.KernelText(obj.to_bytes())
        self.assertEqual(saved.records(),obj.records());self.assertEqual(saved.sections[1:],ex.KernelText(source).sections[1:])
        rows=obj.records();rows[0]['values']['text']='a'*27648;obj.apply('texts',rows)
        with self.assertRaises(ValueError):obj.to_bytes()

    def test_shop_profile_and_only_data_changes(self):
        for shift in (0x200,0x400):
            source=exe_fixture(shift);sha=hashlib.sha1(source).hexdigest().upper()
            with patch.dict(ex.EXE_PROFILES,{sha:shift}):
                obj=ex.ShopExecutable(source,source);rows=obj.records('shops')
                rows[0]['values']['item0']=17;obj.apply('shops',rows)
                prices=obj.records('prices');self.assertEqual(len(prices),416)
                prices[-1]['values']['price']=123456;obj.apply('prices',prices)
                saved=obj.to_bytes()
                changed={i for i,(a,b) in enumerate(zip(source,saved)) if a!=b}
                allowed={0x521A18+shift+8}|set(range(0x523A58+shift+95*4,0x523A58+shift+96*4))
                self.assertLessEqual(changed,allowed)
                self.assertEqual(saved[0x521A18+shift+10:0x521A18+shift+12],b'\x12\x34')
                self.assertEqual(ex.ShopExecutable(saved,source).records('prices'),obj.records('prices'))
                bad=bytearray(saved);bad[100]=1
                with self.assertRaises(ValueError):ex.ShopExecutable(bytes(bad),source)
        with self.assertRaisesRegex(ValueError,'Unsupported'):ex.ShopExecutable(source,source)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.game=self.root/'game';self.project=self.root/'project'
        self.game.mkdir()

    def write(self,relative,data):
        path=self.game/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path

    def snapshot(self,family):
        data=ex.load_extended(self.game,self.project);report=data['families'][family]
        return dict(report,family=family,records={k:data['records'][k] for k in report['categories']})

    def test_both_paths_save_backups_snapshot_and_installed_preservation(self):
        for prefix in ('','ff7/workingdir/'):
            with self.subTest(prefix=prefix):
                self.game=self.root/('game'+str(len(prefix)));self.game.mkdir()
                source=self.write(prefix+'data/lang-en/kernel/kernel2.bin',text_fixture())
                before=source.read_bytes();payload=self.snapshot('text');payload['records']['texts'][0]['values']['text']='One'
                first=ex.save_extended(self.game,self.project,payload)
                self.assertEqual(source.read_bytes(),before);self.assertIsNone(first['backup'])
                with self.assertRaisesRegex(ValueError,'outside'):ex.save_extended(self.game,self.project,payload)
                previous=Path(first['path']).read_bytes();payload=self.snapshot('text');payload['records']['texts'][0]['values']['text']='Two'
                second=ex.save_extended(self.game,self.project,payload)
                self.assertEqual(Path(second['backup']).read_bytes(),previous)
                self.assertEqual(source.read_bytes(),before)

    def test_corrupt_family_does_not_hide_other_datasets(self):
        self.write('data/battle/scene.bin',b'broken')
        self.write('data/lang-en/kernel/kernel2.bin',text_fixture())
        data=ex.load_extended(self.game,self.project)
        self.assertIn('enemies',data['errors']);self.assertIn('texts',data['records'])
        target=self.project/'data/lang-en/kernel/kernel2.bin';target.parent.mkdir(parents=True);target.write_bytes(b'broken')
        self.assertIn('texts',ex.load_extended(self.game,self.project)['errors'])

    def test_installed_or_symlink_target_and_missing_snapshot_refused(self):
        source=self.write('data/lang-en/kernel/kernel2.bin',text_fixture())
        payload=self.snapshot('text')
        with self.assertRaises(ValueError):ex.save_extended(self.game,self.game,payload)
        with self.assertRaises(ValueError):ex.save_extended(self.game,self.game/'mods',payload)
        missing=dict(payload);missing.pop('activeSha256')
        with self.assertRaises(ValueError):ex.save_extended(self.game,self.project,missing)
        target=self.project/'data/lang-en/kernel/kernel2.bin';target.parent.mkdir(parents=True)
        target.symlink_to(source)
        with self.assertRaises(ValueError):ex.save_extended(self.game,self.project,payload)
        target.unlink();os.link(source,target)
        with self.assertRaises(ValueError):ex.save_extended(self.game,self.project,payload)

    def test_external_change_during_staging_leaves_project_untouched(self):
        source=self.write('data/lang-en/kernel/kernel2.bin',text_fixture())
        payload=self.snapshot('text');payload['records']['texts'][0]['values']['text']='One'
        real=ex.os.fsync
        def intervene(fd):
            source.write_bytes(b'External change');real(fd)
        with patch.object(ex.os,'fsync',side_effect=intervene),self.assertRaisesRegex(ValueError,'while saving'):
            ex.save_extended(self.game,self.project,payload)
        self.assertFalse((self.project/'data/lang-en/kernel/kernel2.bin').exists())
        self.assertEqual(source.read_bytes(),b'External change')
        self.assertEqual(list(self.project.rglob('*.tmp')),[])

    def test_case_insensitive_discovery_and_ambiguity(self):
        self.write('Data/LANG-EN/KERNEL/KERNEL2.BIN',text_fixture())
        self.assertIn('texts',ex.load_extended(self.game,self.project)['records'])
        self.write('ff7/workingdir/data/lang-en/kernel/kernel2.bin',text_fixture())
        self.assertIn('texts',ex.load_extended(self.game,self.project)['errors'])

    def test_scene_save_restores_all_records_without_kernel_dependency(self):
        source=self.write('data/battle/scene.bin',scene_fixture());before=source.read_bytes()
        payload=self.snapshot('scene');payload['records']['enemies'][0]['values']['hp']=9876
        result=ex.save_extended(self.game,self.project,payload)
        self.assertEqual(ex.load_extended(self.game,self.project)['records']['enemies'][0]['values']['hp'],9876)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(battle.SceneArchive(Path(result['path']).read_bytes()).blocks,battle.SceneArchive(before).blocks)


if __name__=='__main__':unittest.main(verbosity=2)

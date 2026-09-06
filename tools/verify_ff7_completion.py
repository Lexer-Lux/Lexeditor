"""Synthetic regressions for the remaining FF7 editors; no game assets bundled."""
from copy import deepcopy
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from games.ff7 import ai, archives, extended as ex, datasets as ds, kernel_extra as extra
from games.ff7.format_codec import lzs_encode,lzs_decode,encode_text
from verify_ff7_datasets import write_kernel, PATHS
from verify_ff7_extended import scene_fixture,exe_fixture,text_fixture


def lgp_fixture(members):
    count=len(members);out=bytearray(b'\0\0SQUARESOFT'+struct.pack('<I',count))
    out.extend(b'\0'*(27*count+3602))
    for index,(name,raw) in enumerate(members):
        name=name.encode('ascii').ljust(20,b'\0');at=len(out)
        out[16+27*index:16+27*index+27]=name+struct.pack('<IBH',at,14,0)
        out.extend(name+struct.pack('<I',len(raw))+raw)
    return bytes(out)+b'FINAL FANTASY 7'


def table_fixture(count):
    out=bytearray(4+2*count);out[:2]=bytes((1,60))
    for i in range(count):struct.pack_into('<H',out,2+i*2,((16 if i<4 else 0)<<10)|i)
    out[-2:]=b'\xA5\x5A'
    return bytes(out)


def field_fixture():
    sections=[bytes((i,))*20 for i in range(9)]
    sections[6]=table_fixture(10)*2
    out=bytearray(b'\0\0'+struct.pack('<I',9)+b'\0'*36)
    for i,raw in enumerate(sections):
        struct.pack_into('<I',out,6+i*4,len(out));out.extend(struct.pack('<I',len(raw))+raw)
    return lzs_encode(bytes(out))


def world_fixture():
    out=bytearray(0x8A0)
    for i in range(8):struct.pack_into('<HH',out,i*4,10+i*10,100+i)
    for i in range(32):struct.pack_into('<HH',out,32+i*4,100+i,1+i%8)
    for i in range(64):out[0xA0+i*32:0xC0+i*32]=table_fixture(14)
    return bytes(out)


def pool_fixture(owners=3,size=512):
    raw=bytearray(b'\xff'*size);at=owners*2
    struct.pack_into('<H',raw,0,at);struct.pack_into('<H',raw,at+2,32)
    code=ai.assemble('LOAD8 0x20\nPUSH8 3\nEQ\nJZ other\nPUSH16 0x123\nDROP\nother:\nEND')
    raw[at+32:at+32+len(code)]=code
    return bytes(raw)


class AITests(unittest.TestCase):
    def test_opcode_and_label_roundtrip(self):
        source='LOAD24 0x4160\nPUSH24 0xABCDEF\nEQ\nJZ no\nMESSAGE "Hello"\nDEBUG 1 "number %d"\nno:\nEND'
        raw=ai.assemble(source)
        self.assertEqual(ai.assemble(ai.disassemble(raw)),raw)
        self.assertIn('JZ L',ai.disassemble(raw))

    def test_rejects_malformed_or_unsafe_structure(self):
        cases=('PUSH8 256\nEND','PUSH8 -1\nEND','JMP missing\nEND','JMP 1\nEND','PUSH8 0','END\nEND',
               'label:\nlabel:\nEND','MESSAGE "😀"\nEND','LOAD4 1\nEND','OP_04\nEND')
        for source in cases:
            with self.subTest(source=source),self.assertRaises(ValueError):ai.assemble(source)
        for raw in (b'\x60',b'\x93abc',b'\xa0\x01abc',b'\x60\x01'):
            with self.assertRaises(ValueError):ai.instructions(raw)

    def test_pool_noop_identical_and_growth_updates_only_owned_pointers(self):
        original=pool_fixture();pool=ai.Pool(original,3)
        rows=pool.records('Enemy')
        self.assertEqual(pool.apply({r['id']:r['values'] for r in rows}),original)
        rows[1]['values']['script1']='PUSH8 32\nPUSH16 256\nACTION\nEND'
        out=pool.apply({r['id']:r['values'] for r in rows})
        self.assertEqual(out[6:pool.free],original[6:pool.free])
        self.assertEqual(ai.Pool(out,3).records('Enemy')[1]['values']['script1'],ai.disassemble(ai.assemble(rows[1]['values']['script1'])))
        self.assertEqual(ai.Pool(out,3).records('Enemy')[0],rows[0])

    def test_shortening_preserves_padding_and_other_scripts(self):
        raw=pool_fixture();pool=ai.Pool(raw,3);rows=pool.records('Owner')
        rows[0]['values']['script1']='END'
        out=pool.apply({0:rows[0]['values']});start,end=pool.spans[0,1]
        self.assertEqual(out[:start],raw[:start]);self.assertEqual(out[start],0x73)
        self.assertEqual(out[start+1:],raw[start+1:])

    def test_capacity_rejection_and_shared_owner_copy_on_write(self):
        raw=bytearray(pool_fixture(size=128));struct.pack_into('<H',raw,2,6)
        pool=ai.Pool(bytes(raw),3);rows=pool.records('Owner')
        rows[1]['values']['script1']='END'
        out=pool.apply({1:rows[1]['values']})
        self.assertEqual(ai.Pool(out,3).records('Owner')[0],rows[0])
        self.assertNotEqual(struct.unpack_from('<H',out,0),struct.unpack_from('<H',out,2))
        rows[2]['values']['script1']='NOP\n'*200+'END'
        with self.assertRaises(ValueError):pool.apply({2:rows[2]['values']})
        self.assertEqual(pool.raw,bytes(raw))

    def test_scene_and_character_pools_keep_non_ai_data(self):
        archive=ex.SceneArchive(scene_fixture());before=deepcopy(archive.scenes)
        rows=archive.records('enemyAI');rows[0]['values']['script1']='PUSH8 12\nDROP\nEND'
        archive.apply('enemyAI',rows)
        self.assertEqual(archive.scenes[0][:0xE80],before[0][:0xE80]);self.assertEqual(archive.scenes[1:],before[1:])
        saved=ex.SceneArchive(archive.to_bytes());self.assertEqual(saved.records('enemyAI'),archive.records('enemyAI'))


class ArchiveTests(unittest.TestCase):
    def test_lgp_noop_append_and_alias_preservation(self):
        raw=lgp_fixture([('one',b'alpha'),('two',b'beta')]);obj=archives.LGP(raw)
        self.assertEqual(obj.to_bytes(),raw)
        obj.changes[0]=b'a longer replacement';out=obj.to_bytes();saved=archives.LGP(out)
        self.assertEqual(saved.member(0),b'a longer replacement');self.assertEqual(saved.member(1),b'beta')
        self.assertEqual(out[16+27:16+54+3602],raw[16+27:16+54+3602])
        alias=bytearray(raw);struct.pack_into('<I',alias,16+27+20,struct.unpack_from('<I',raw,36)[0])
        obj=archives.LGP(bytes(alias));obj.changes[0]=b'edited'
        saved=archives.LGP(obj.to_bytes());self.assertEqual(saved.member(1),b'alpha')

    def test_lgp_rejects_truncation_and_index_overlap(self):
        raw=lgp_fixture([('one',b'alpha')])
        for value in (raw[:-1],b'junk'):
            with self.assertRaises(ValueError):archives.LGP(value)
        bad=bytearray(raw);struct.pack_into('<I',bad,36,16)
        with self.assertRaises(ValueError):archives.LGP(bytes(bad))

    def test_field_table_edit_preserves_every_other_decoded_byte(self):
        compressed=field_fixture();source=lgp_fixture([('maplist',b'map list'),('field1',compressed),('field2',compressed)])
        obj=archives.FieldArchive(source);self.assertEqual(len(obj.records()),4)
        rows=obj.records();rows[1]['values']['battle0']=1000;obj.apply('fieldEncounters',rows)
        out=archives.LGP(obj.to_bytes());before=lzs_decode(compressed);after=lzs_decode(out.member(1));at=archives.field_encounter_offset(before)+24+2
        self.assertEqual(after[:at],before[:at]);self.assertEqual(after[at+2:],before[at+2:]);self.assertEqual(out.member(2),compressed)
        self.assertEqual(archives.FieldArchive(obj.to_bytes()).records(),obj.records())

    def test_field_invalid_member_is_reported_without_hiding_other_fields(self):
        source=lgp_fixture([('bad',b'broken'),('good',field_fixture())]);obj=archives.FieldArchive(source)
        self.assertIn('bad',obj.errors);self.assertEqual(len(obj.records()),2)
        obj.apply('fieldEncounters',obj.records());self.assertEqual(obj.to_bytes(),source)

    def test_encounter_validation_keeps_rate_and_id_bits_separate(self):
        raw=table_fixture(10);values=archives.read_encounter(raw,10)
        values['battle0']=1023;out=archives.write_encounter(raw,values,10)
        self.assertEqual(struct.unpack_from('<H',out,2)[0],(16<<10)|1023);self.assertEqual(out[-2:],raw[-2:])
        for key,value in (('rate',0),('battle0',1024),('chance0',64),('enabled',True)):
            bad=dict(values);bad[key]=value
            with self.assertRaises(ValueError):archives.write_encounter(raw,bad,10)
        bad=dict(values);bad['chance0']=15
        with self.assertRaisesRegex(ValueError,'total 64'):archives.write_encounter(raw,bad,10)

    def test_world_tables_yuffie_chocobo_roundtrip(self):
        source=lgp_fixture([('enc_w.bin',world_fixture()),('unknown',b'preserved')]);obj=archives.WorldArchive(source)
        for category,key,value in (('worldEncounters','battle13',777),('yuffieEncounters','battle',999),('chocoboRatings','rating',8)):
            rows=obj.records(category);rows[0]['values'][key]=value;obj.apply(category,rows)
        out=obj.to_bytes();saved=archives.WorldArchive(out)
        self.assertEqual(archives.LGP(out).member(1),b'preserved')
        self.assertEqual(saved.records('worldEncounters')[0]['values']['battle13'],777)
        self.assertEqual(saved.records('yuffieEncounters')[0]['values']['battle'],999)
        self.assertEqual(saved.records('chocoboRatings')[0]['values']['rating'],8)


class CompletionSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.game=self.root/'game';self.project=self.root/'project'
        self.source=self.game/PATHS[0];write_kernel(self.source)

    def test_growth_curves_names_and_ai_in_one_kernel_save(self):
        data=ds.load_datasets(self.game,self.project);before=self.source.read_bytes()
        data['records']['growthCurves'][63]['values']['base7']=-128
        data['records']['characterNames'][8]['values']['name']='Captain'
        data['records']['growthBonuses'][2]['values']['bonus11']=200
        data['records']['characterAI'][0]['values']['script1']='push8  0x20\nPUSH16 256\nACTION\nEND'
        result=ds.save_datasets(self.game,self.project,data);saved=ds.Kernel(Path(result['path']))
        self.assertEqual(saved.records('characters')[8]['name'],'Captain')
        self.assertEqual(saved.records('growthCurves')[63]['values']['base7'],-128)
        self.assertEqual(saved.records('growthBonuses')[2]['values']['bonus11'],200)
        self.assertIn('PUSH8',result['records']['characterAI'][0]['values']['script1'])
        self.assertEqual(self.source.read_bytes(),before)

    def test_every_growth_coefficient_and_bonus_only_changes_its_byte(self):
        original=ds.Kernel(self.source)
        for key in ('growthCurves','growthBonuses'):
            spec=extra.EXTRAS[key]
            for slot in (0,spec['count']-1):
                for field in spec['fields']:
                    obj=ds.Kernel(self.source);rows=obj.records(key);rows[slot]['values'][field['key']]=field['minimum'] if field['signed'] else field['maximum'];obj.apply(key,rows)
                    at=spec['offset']+slot*spec['stride']+field['offset']
                    self.assertEqual(obj.sections[2][:at],original.sections[2][:at]);self.assertEqual(obj.sections[2][at+1:],original.sections[2][at+1:])

    def test_bad_ai_does_not_hide_or_block_numeric_saves(self):
        kernel=ds.Kernel(self.source);kernel.sections[2][0x61C:0x61E]=b'\xFE\x7F';self.source.write_bytes(kernel.to_bytes())
        data=ds.load_datasets(self.game,self.project);self.assertEqual(set(data['errors']),{'characterAI'})
        data['records']['characters'][0]['values']['strength']=77;result=ds.save_datasets(self.game,self.project,data)
        self.assertEqual(ds.Kernel(Path(result['path'])).sections[2][0x61C:0x61E],b'\xFE\x7F')

    def test_kernel_mandatory_snapshots_and_backup_symlink(self):
        payload=ds.load_datasets(self.game,self.project);missing=dict(payload);missing.pop('activeSha256')
        with self.assertRaises(ValueError):ds.save_datasets(self.game,self.project,missing)
        result=ds.save_datasets(self.game,self.project,payload);before=self.source.read_bytes()
        old_backup=Path(result['path']+'.lexeditor.bak');old_backup.symlink_to(self.source)
        payload=ds.load_datasets(self.game,self.project);payload['records']['characters'][0]['values']['strength']=90
        result=ds.save_datasets(self.game,self.project,payload)
        self.assertNotEqual(Path(result['backup']),old_backup);self.assertEqual(self.source.read_bytes(),before)

    def test_recruits_and_default_names_preserve_executable_bytes(self):
        source=exe_fixture();sha=hashlib.sha1(source).hexdigest().upper()
        with patch.dict(ex.EXE_PROFILES,{sha:0x400}):
            obj=ex.ShopExecutable(source,source);rows=obj.records('recruits');rows[1]['values']['name']='Vince';rows[1]['values']['strength']=99;obj.apply('recruits',rows)
            rows=obj.records('defaultNames');rows[0]['values']['name']='Hero';obj.apply('defaultNames',rows)
            saved=ex.ShopExecutable(obj.to_bytes(),source)
            self.assertEqual(saved.records('recruits')[1]['values']['strength'],99)
            self.assertEqual(saved.records('defaultNames')[0]['values']['name'],'Hero')
            self.assertEqual(saved.data[:0x5202B8+0x400],source[:0x5202B8+0x400])

    def test_archive_source_discovery_both_editions_and_project_roundtrip(self):
        for prefix in ('','ff7/workingdir/'):
            game=self.root/('edition'+str(len(prefix)));project=self.root/('project'+str(len(prefix)))
            for path,value in (('data/field/flevel.lgp',lgp_fixture([('field1',field_fixture())])),
                               ('data/wm/world_us.lgp',lgp_fixture([('enc_w.bin',world_fixture())]))):
                target=game/(prefix+path);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
            data=ex.load_extended(game,project)
            for family,category in (('field','fieldEncounters'),('world','worldEncounters')):
                report=data['families'][family];payload=dict(report,family=family,records={k:data['records'][k] for k in report['categories']})
                payload['records'][category][0]['values']['battle0']=222
                result=ex.save_extended(game,project,payload)
                self.assertTrue(Path(result['path']).is_file())
                self.assertEqual(ex.load_extended(game,project)['records'][category][0]['values']['battle0'],222)
                with self.assertRaises(ValueError):ex.save_extended(game,project,payload)


class IntegrationTests(unittest.TestCase):
    def test_noop_cannot_bypass_integer_validation(self):
        raw=table_fixture(10);values=archives.read_encounter(raw,10);values['enabled']=True
        with self.assertRaises(ValueError):archives.write_encounter(raw,values,10)
        obj=archives.WorldArchive(lgp_fixture([('enc_w.bin',world_fixture())]))
        rows=obj.records('chocoboRatings');rows[0]['values']['rating']=True
        with self.assertRaises(ValueError):obj.apply('chocoboRatings',rows)

    def test_kernel_case_insensitive_discovery_and_snapshot_payload(self):
        from games.ff7.plugin import kernel_save_payload
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);game=root/'game';project=root/'project'
            source=game/'ff7/workingdir/Data/Lang-EN/Kernel/KERNEL.BIN';write_kernel(source)
            data=ds.load_datasets(game,project);data['kernelCategories']=list(ds.CATEGORIES)
            self.assertFalse(data['errors']);self.assertEqual(data['sourceRelativePath'],str(source.relative_to(game)).replace(chr(92),'/'))
            data['records']['outsideKernel']=[]
            payload=kernel_save_payload(data)
            self.assertNotIn('outsideKernel',payload['records']);self.assertEqual(payload['usingProject'],False)
            result=ds.save_datasets(game,project,payload)
            self.assertTrue(Path(result['path']).is_file())
            missing=dict(payload);missing.pop('usingProject')
            with self.assertRaises(ValueError):ds.save_datasets(game,project,missing)

    def test_directory_or_broken_link_is_not_silently_loaded_as_vanilla(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);game=root/'game';project=root/'project'
            source=game/PATHS[0];write_kernel(source)
            target=project/PATHS[0];target.mkdir(parents=True)
            self.assertEqual(ds.load_datasets(game,project)['records'],{})
            target.rmdir();target.symlink_to(root/'missing')
            self.assertEqual(ds.load_datasets(game,project)['records'],{})

    def test_installed_diagnostic_uses_only_disposable_output(self):
        from verify_ff7_installed import check_installation
        with tempfile.TemporaryDirectory() as name:
            game=Path(name)/'game';source=game/PATHS[0];write_kernel(source);before=source.read_bytes()
            report=check_installation(game)
            self.assertTrue(report['installedFilesUnchanged'])
            self.assertEqual(report['datasets']['characterAI']['readback'],'passed')
            self.assertIn('scene',report['errors']);self.assertFalse(report['passed'])
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual([p for p in game.rglob('*') if p.is_file()],[source])

    def test_template_and_process_identity_guards(self):
        from games.ff7 import plugin
        from games.ff7_2013 import plugin as legacy
        self.assertIn('FFVII.exe',plugin.PLUGIN.process_names)
        self.assertIn('ff7_en.exe',legacy.PLUGIN.process_names)
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);game=root/'game';source=game/PATHS[0];write_kernel(source)
            before=source.read_bytes()
            with self.assertRaises(ValueError):plugin.seed_project_layout(game,game,root/'mod')
            self.assertEqual(source.read_bytes(),before)


if __name__=='__main__':unittest.main(verbosity=2)

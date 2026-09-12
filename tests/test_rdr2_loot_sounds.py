"""Pickup sound routing preserves XML and deploys changes through the selected mod."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from games.rdr2 import loot_sounds

XML='''<?xml version="1.0"?><CLootSoundsMapCollection><!--keep--><SoundMaps><Item><SoundSets><Item key="PICKUP_CONTEXT">PICKUP_SOUNDSET</Item></SoundSets><Sounds><Item key="AMMO">AMMO</Item><Item key="WATCH">WATCH</Item><Item key="AMMO">WATCH</Item></Sounds></Item></SoundMaps><Unknown value="keep" /></CLootSoundsMapCollection>'''


class Sounds(unittest.TestCase):
    def test_duplicate_keys_are_addressed_separately_and_other_bytes_survive(self):
        rows=loot_sounds.read(XML)['rows'];self.assertEqual(len(rows),4)
        out,count=loot_sounds.apply(XML,[{'id':rows[1]['id'],'value':'WATCH'}])
        self.assertEqual(count,1)
        self.assertEqual(out,XML.replace('>AMMO</Item>','>WATCH</Item>',1))
        self.assertEqual(loot_sounds.apply(XML,[]),(XML,0))
        spaced=XML.replace('>AMMO</Item>', '> AMMO </Item>', 1)
        self.assertEqual(loot_sounds.apply(spaced,[{'id':rows[1]['id'],'value':'AMMO'}]),(spaced,0))

    def test_unknown_event_or_row_and_duplicate_edit_rejected(self):
        identity=loot_sounds.read(XML)['rows'][1]['id']
        for edits in ([{'id':identity,'value':'BRASS'}],[{'id':'missing','value':'AMMO'}],[{'id':identity,'value':'AMMO'}]*2):
            with self.assertRaises(ValueError):loot_sounds.apply(XML,edits)

    def test_server_saves_routed_mod_file_and_preserves_reference(self):
        from games.rdr2 import server
        with tempfile.TemporaryDirectory(prefix='lex-loot-sounds-') as temp:
            root=Path(temp);mod=root/'mod';ref=root/'ref';mod.mkdir();ref.mkdir()
            (mod/'install.xml').write_text('<LennyModLoader><Resources /></LennyModLoader>')
            (ref/'loot_sounds.meta').write_text(XML)
            with patch.object(server,'DATASETS',{'mine':{'dir':mod,'readonly':False},'vanilla':{'dir':ref,'readonly':True}}),patch.object(server,'EXTRACT_ROOT',ref):
                before=server.get_loot_sounds();identity=before['rows'][1]['id']
                self.assertEqual(server.save_loot_sounds([{'id':identity,'value':'WATCH'}]),1)
                self.assertEqual((ref/'loot_sounds.meta').read_text(),XML)
                self.assertEqual(server.get_loot_sounds()['rows'][1]['value'],'WATCH')
                self.assertEqual(server.install_replacements()[server.LOOT_SOUNDS_GAME_PATH],'loot_sounds.meta')
                self.assertEqual(len(list(mod.glob('tmp*'))),0)

    def test_change_between_read_and_staging_is_not_overwritten(self):
        from games.rdr2 import server
        with tempfile.TemporaryDirectory() as temp:
            mod=Path(temp);target=mod/'loot_sounds.meta';manifest=mod/'install.xml'
            target.write_text(XML)
            before=b'<LennyModLoader><Resources /></LennyModLoader>'
            manifest.write_bytes(before)
            newer=XML.replace('<!--keep-->', '<!--another editor changed this-->')
            apply=server._apply_loot_sounds
            def concurrent_edit(text, edits):
                target.write_text(newer)
                return apply(text, edits)
            with patch.object(server,'DATASETS',{'mine':{'dir':mod,'readonly':False}}),patch.object(server,'_apply_loot_sounds',concurrent_edit):
                with self.assertRaisesRegex(ValueError,'changed during save'):
                    server.save_loot_sounds([{'id':loot_sounds.read(XML)['rows'][1]['id'],'value':'WATCH'}])
            self.assertEqual(target.read_text(),newer)
            self.assertEqual(manifest.read_bytes(),before)
            self.assertFalse(list(mod.glob('.loot-sounds-*')))

    def test_failed_transaction_preserves_manifest_and_data(self):
        from games.rdr2 import server
        import os
        for existing in (False, True):
            for failure in ('write', 'routing', 'data-replace', 'manifest-replace', 'rollback'):
                with self.subTest(existing=existing, failure=failure), tempfile.TemporaryDirectory() as temp:
                    root=Path(temp);mod=root/'mod';ref=root/'ref';mod.mkdir();ref.mkdir()
                    manifest=mod/'install.xml';target=mod/'loot_sounds.meta'
                    before=b'<LennyModLoader><!--keep--><Resources /><Unknown value="keep" /></LennyModLoader>'
                    manifest.write_bytes(before);(ref/'loot_sounds.meta').write_text(XML)
                    if existing: target.write_text(XML)
                    original_write=Path.write_bytes;original_replace=os.replace
                    def write(path,data):
                        if failure=='write' and path.name=='data': raise OSError('disk full')
                        return original_write(path,data)
                    def replace(src,dst):
                        if (failure=='rollback' and Path(src).name in ('manifest','data-before')) or (failure=='data-replace' and Path(src).name=='data') or (failure=='manifest-replace' and Path(src).name=='manifest'):
                            raise OSError('replace failed')
                        return original_replace(src,dst)
                    original_route=server.ensure_file_replacement
                    def route(game,relative,path):
                        if failure=='routing':
                            path.write_text('partial routing write')
                            raise OSError('routing failed')
                        return original_route(game,relative,path)
                    with patch.object(server,'DATASETS',{'mine':{'dir':mod,'readonly':False}}),patch.object(server,'EXTRACT_ROOT',ref),patch.object(Path,'write_bytes',write),patch.object(server.os,'replace',replace),patch.object(server,'ensure_file_replacement',route):
                        with self.assertRaises(OSError): server.save_loot_sounds([{'id':loot_sounds.read(XML)['rows'][1]['id'],'value':'WATCH'}])
                    self.assertEqual(manifest.read_bytes(),before)
                    self.assertEqual(target.exists(),existing)
                    if failure=='rollback' and existing:
                        recovery=list(mod.glob('.loot-sounds-*'))
                        self.assertEqual(len(recovery),1)
                        self.assertEqual((recovery[0]/'data-before').read_text(),XML)
                        self.assertEqual((recovery[0]/'manifest-before').read_bytes(),before)
                        snapshots={p.name:p.read_bytes() for p in recovery[0].iterdir()}
                        with patch.object(server,'DATASETS',{'mine':{'dir':mod,'readonly':False}}),patch.object(server,'EXTRACT_ROOT',ref):
                            for value in ('WATCH','AMMO','WATCH'):
                                with self.assertRaisesRegex(OSError,'unresolved recovery'):
                                    server.save_loot_sounds([{'id':loot_sounds.read(XML)['rows'][1]['id'],'value':value}])
                        self.assertEqual(list(mod.glob('.loot-sounds-*')),recovery)
                        self.assertEqual({p.name:p.read_bytes() for p in recovery[0].iterdir()},snapshots)
                    else:
                        if existing: self.assertEqual(target.read_text(),XML)
                        self.assertFalse(list(mod.glob('.loot-sounds-*')))


if __name__=='__main__':unittest.main()

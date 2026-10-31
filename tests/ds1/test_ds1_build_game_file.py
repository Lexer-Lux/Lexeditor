"""Game-file builder inputs survive worker transport and cache replay."""
import json

import pytest

from core import script_mods
from plugins.ds1 import assets,deployment,tweak_mods
from test_ds1_tweak_recovery import game


def test_game_file_inputs_reuse_only_unchanged_outputs_and_game_bytes(game):
    root,library,_built = game
    relative = 'chr/c0000.anibnd.dcx'
    source = root/relative;source.parent.mkdir();source.write_bytes(b'first')
    mod = library/'reader';(mod/'script').mkdir(parents=True)
    (mod/'mod.json').write_text(json.dumps({'name':'reader','script':{'version':1}}))
    (mod/'script/__init__.py').write_text('')
    (mod/'script/tweak.py').write_text(
        'def build(settings, context):\n'
        '    return {"native/observed.txt": context.game_file("chr/c0000.anibnd.dcx")}\n')
    def build():
        return script_mods.build(mod,tweak_mods.BuildContext({},root,library),allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert not build().get('cached')
    record = json.loads((mod/script_mods.MANIFEST_FILE).read_text())['build']
    assert list(record['inputs']['file']) == [relative]
    assert build()['cached']
    source.write_bytes(b'second')
    assert not build().get('cached')
    assert (mod/'native/observed.txt').read_bytes() == b'second'
    assert build()['cached']


def test_game_file_reads_the_preserved_original_of_a_deployed_asset(game):
    from tae_fixture import build_anibnd,build_tae
    from plugins.ds1.tae import TaeDocument
    root,library,_built = game
    relative = 'chr/c0000.anibnd.dcx'
    original = build_anibnd({'a87.tae':build_tae()})
    doc = TaeDocument(build_tae());doc.edit(0,0,'judge',123)
    changed = build_anibnd({'a87.tae':doc.export()})
    target = root/relative;target.parent.mkdir();target.write_bytes(original)
    mod = library/'asset';mod.mkdir();(mod/'mod.json').write_text('{"name":"asset"}')
    deployment.apply(root,mod,composed={relative:changed})
    context = tweak_mods.BuildContext({},root,library)
    assert context.game_file(relative) == original
    assert target.read_bytes() == changed


@pytest.mark.parametrize('relative',['../outside.bin','C:/outside.bin','chr/file:stream','chr/file.','chr/file\x00'])
def test_game_file_refuses_unsafe_paths_before_reading(game,relative):
    root,library,_built = game
    with pytest.raises(tweak_mods.TweakError,match='safe relative path'):
        tweak_mods.BuildContext({},root,library).game_file(relative)


def test_game_file_read_has_a_size_bound(game,monkeypatch):
    root,library,_built = game
    source = root/'chr/c0000.anibnd.dcx';source.parent.mkdir();source.write_bytes(b'123456789')
    monkeypatch.setattr(assets,'MAX_ASSET_BYTES',8)
    with pytest.raises(tweak_mods.TweakError,match='size'):
        tweak_mods.BuildContext({},root,library).game_file('chr/c0000.anibnd.dcx')


def test_small_game_files_do_not_request_the_entire_512_mib_read_limit(game,monkeypatch):
    from pathlib import Path
    root,library,_built=game
    source=root/'chr/c0000.anibnd.dcx';source.parent.mkdir();source.write_bytes(b'small')
    original=Path.open
    class Guarded:
        def __enter__(self):
            self.stream=original(source,'rb');return self
        def __exit__(self,*_):
            self.stream.close()
        def read(self,size):
            assert 0<size<=65536,'A tiny input must not allocate the maximum asset buffer'
            return self.stream.read(size)
    monkeypatch.setattr(Path,'open',lambda path,*args,**kwargs:Guarded() if path==source else original(path,*args,**kwargs))
    assert tweak_mods.BuildContext({},root,library).game_file('chr/c0000.anibnd.dcx')==b'small'


@pytest.mark.parametrize('replacement',[b'grew past its snapshot',b'x'])
def test_changing_game_source_never_returns_a_partial_reusable_input(game,monkeypatch,replacement):
    from pathlib import Path
    root,library,_built=game
    source=root/'chr/c0000.anibnd.dcx';source.parent.mkdir();source.write_bytes(b'first')
    original=Path.open
    def changed(path,*args,**kwargs):
        if path==source and args and args[0]=='rb':
            with original(source,'wb') as stream:
                stream.write(replacement)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',changed)
    with pytest.raises(tweak_mods.TweakError,match='changed size'):
        tweak_mods.BuildContext({},root,library).game_file('chr/c0000.anibnd.dcx')

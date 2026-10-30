"""Menu edits preserve another author's installed baseline, never game files."""
import pytest

from plugins.ds1 import formats, menu_layout, menu_scripts, tweak_mods
from test_ds1_menu_layout import drb, dcx
from test_ds1_menu_scripts import archive, build_script, ANCHOR, NEW


@pytest.fixture(params=['layout','esd'])
def menu(request,tmp_path,monkeypatch):
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    if request.param == 'layout':
        managed = tweak_mods.LAYOUT
        foreign = menu_layout.Drb(drb())
        foreign.move('list_armor','text_name',[20,30,210,58])
        baseline = dcx(foreign.to_bytes())
        spec = menu_layout.validate({'version':1,'nodes':[], 'moves':[
            {'dialog':'data_simple_arms','name':'text_receive_name','rect':[370,262,487,290]}]},'Our mod')
        changed = menu_layout.compose(baseline,[spec])
        def verify(data):
            layout = menu_layout.Drb(formats.inflate(data))
            assert layout.text('list_armor','text_name')['rect'] == [20,30,210,58]
    else:
        managed = tweak_mods.ESD_INGAME
        baseline = archive({'fixture.esd':build_script().to_bytes(),'foreign.bin':b'other author'})
        spec = menu_scripts.validate({'version':1,'changes':[
            {'archive':'ingame','script':'fixture.esd','after':ANCHOR,'commands':[NEW]}]},'Our mod')
        changed = menu_scripts.compose(baseline,[spec],'ingame')
        def verify(data):
            plain = formats.inflate(data)
            entry = formats.members(plain)['foreign.bin']
            assert plain[entry.offset:entry.offset+entry.size] == b'other author'
    assert baseline != changed and not managed.vanilla(baseline)
    live = managed.live(tmp_path)
    live.parent.mkdir(parents=True,exist_ok=True)
    live.write_bytes(baseline)
    return tmp_path,managed,baseline,changed,verify


def test_apply_restore_and_reapply_keep_foreign_data(menu):
    root,managed,baseline,changed,verify = menu
    current,manifest = tweak_mods._installed(root,managed,'untouched')
    assert tweak_mods._original(root,current,manifest,managed) == baseline
    tweak_mods._write(root,current,changed,['Our mod'],managed)
    verify(managed.live(root).read_bytes())
    assert managed.backup(root).read_bytes() == baseline
    manifest = tweak_mods._manifest(root,managed)
    assert manifest['originalHash'] == tweak_mods._sha(baseline)
    assert tweak_mods._file_status(root,managed)['backupOk']
    tweak_mods._write(root,changed,baseline,[],managed)
    assert managed.live(root).read_bytes() == baseline
    current,manifest = tweak_mods._installed(root,managed,'untouched')
    assert tweak_mods._original(root,current,manifest,managed) == baseline
    tweak_mods._write(root,current,changed,['Our mod'],managed)
    verify(managed.live(root).read_bytes())
    assert managed.backup(root).read_bytes() == baseline


def test_later_external_change_is_preserved(menu):
    root,managed,baseline,changed,_verify = menu
    tweak_mods._write(root,baseline,changed,['Our mod'],managed)
    outsider = changed+b'foreign edit after install'
    managed.live(root).write_bytes(outsider)
    with pytest.raises(tweak_mods.TweakError,match='outside Lexeditor'):
        tweak_mods._installed(root,managed,'untouched')
    assert managed.live(root).read_bytes() == outsider
    assert managed.backup(root).read_bytes() == baseline


def test_corrupt_preserved_foreign_original_is_never_adopted(menu):
    root,managed,baseline,changed,_verify = menu
    tweak_mods._write(root,baseline,changed,['Our mod'],managed)
    managed.backup(root).write_bytes(b'corrupt original')
    with pytest.raises(tweak_mods.TweakError,match='original.*changed'):
        tweak_mods._original(root,changed,tweak_mods._manifest(root,managed),managed)
    assert managed.live(root).read_bytes() == changed


def test_interrupted_first_foreign_install_recovers_from_its_journal(menu,monkeypatch):
    root,managed,baseline,changed,_verify = menu
    write = tweak_mods._put
    def interrupted(game,path,data):
        write(game,path,data)
        raise OSError('interrupted')
    monkeypatch.setattr(tweak_mods,'_put',interrupted)
    with pytest.raises(OSError,match='interrupted'):
        tweak_mods._write(root,baseline,changed,['Our mod'],managed)
    current,manifest = tweak_mods._installed(root,managed,'untouched')
    assert current == changed and manifest['pending']
    assert tweak_mods._current_manifest(current,manifest,managed)['originalHash'] == tweak_mods._sha(baseline)
    assert tweak_mods._original(root,current,manifest,managed) == baseline
    monkeypatch.setattr(tweak_mods,'_put',write)
    tweak_mods._write(root,current,baseline,[],managed)
    assert managed.live(root).read_bytes() == baseline


def test_unknown_executable_and_invalid_menu_are_still_refused():
    assert not tweak_mods._owned(b'unknown executable',{},tweak_mods.EXECUTABLE)
    assert not tweak_mods._owned(b'invalid layout',{},tweak_mods.LAYOUT)
    assert not tweak_mods._owned(b'invalid scripts',{},tweak_mods.ESD_COMMON)


def test_unowned_backup_cannot_silently_replace_a_foreign_menu(menu):
    from dataclasses import replace
    root,managed,baseline,changed,_verify = menu
    # A prior restore can leave a vanilla backup with no live ownership record.
    managed = replace(managed,vanilla=lambda data:data==changed)
    managed.backup(root).write_bytes(changed)
    with pytest.raises(tweak_mods.TweakError,match='unmanaged preserved copy'):
        tweak_mods._original(root,baseline,{},managed)
    assert managed.live(root).read_bytes() == baseline
    assert managed.backup(root).read_bytes() == changed

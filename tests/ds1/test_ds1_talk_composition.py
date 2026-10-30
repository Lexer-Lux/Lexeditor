"""Bonfire mods compose independent commands, conditions and added states."""
from copy import deepcopy

from plugins.ds1 import esd, esd_merge


def command(cid, *args):
    return esd.Command(bank=1, id=cid, args=[esd.assemble(str(arg)) for arg in args])


def fixture():
    return esd.Esd(state_groups={1: {
        0: esd.State(id=0, entry_commands=[command(19, 9, 15000005, -1),
                                          command(19, 11, 15000270, -1)],
                     conditions=[esd.Condition(target_state=1, evaluator=esd.assemble('f23() == 11'))]),
        1: esd.State(id=1, entry_commands=[command(50, 0)]),
    }})


def test_hollowing_removal_and_estus_submenu_compose():
    base = fixture()
    humanity, estus = deepcopy(base), deepcopy(base)
    humanity.state_groups[1][0].entry_commands.pop()
    estus.state_groups[1][0].entry_commands.append(command(19, 723, 15000723, -1))
    estus.state_groups[1][0].conditions.append(esd.Condition(
        target_state=723, evaluator=esd.assemble('f23() == 723')))
    estus.state_groups[1][723] = esd.State(id=723, entry_commands=[command(50, 0)])
    merged, collisions = esd_merge.compose(base.to_bytes(), [
        ('Humanity', humanity.to_bytes()), ('Estus', estus.to_bytes())])
    result = esd.parse(merged)
    assert not collisions
    assert result.state_groups[1][0].entry_commands == [
        command(19, 9, 15000005, -1), command(19, 723, 15000723, -1)]
    assert result.state_groups[1][0].conditions == estus.state_groups[1][0].conditions
    assert result.state_groups[1][723] == estus.state_groups[1][723]


def test_separate_fields_of_one_condition_compose():
    base = fixture()
    a, b = deepcopy(base), deepcopy(base)
    a.state_groups[1][0].conditions[0].evaluator = esd.assemble('f23() == 12')
    b.state_groups[1][0].conditions[0].target_state = 0
    merged, collisions = esd_merge.compose(base.to_bytes(), [('A', a.to_bytes()), ('B', b.to_bytes())])
    condition = esd.parse(merged).state_groups[1][0].conditions[0]
    assert not collisions
    assert condition.evaluator == esd.assemble('f23() == 12')
    assert condition.target_state == 0


def test_different_values_of_one_argument_report_both_mods():
    base = fixture()
    a, b = deepcopy(base), deepcopy(base)
    a.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('1')
    b.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('2')
    merged, collisions = esd_merge.compose(base.to_bytes(), [('A', a.to_bytes()), ('B', b.to_bytes())])
    assert len(collisions) == 1
    assert collisions[0][1] == ['A', 'B']
    assert esd.parse(merged).state_groups[1][1].entry_commands[0].args[0] == esd.assemble('2')


def test_unchanged_and_identical_variants_preserve_bytes():
    original = fixture().to_bytes()
    assert esd_merge.compose(original, [('A', original), ('B', original)]) == (original, [])
    changed = fixture()
    changed.state_groups[1][1].entry_commands.clear()
    packed = changed.to_bytes()
    assert esd_merge.compose(original, [('A', packed), ('B', packed)]) == (packed, [])


def test_repeated_esd_merge_reuses_work_without_sharing_conflict_lists(monkeypatch):
    base = fixture()
    a, b = deepcopy(base), deepcopy(base)
    a.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('1')
    b.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('2')
    original = base.to_bytes()
    mods = [('A', a.to_bytes()), ('B', b.to_bytes())]
    esd_merge._compose.cache_clear()
    parse = esd.parse
    calls = []
    def counted(data):
        calls.append(data)
        return parse(data)
    monkeypatch.setattr(esd, 'parse', counted)
    result, conflicts = esd_merge.compose(original, mods)
    conflicts[0][1].clear()
    assert esd_merge.compose(original, mods) == (result, [(conflicts[0][0], ['A', 'B'])])
    assert len(calls) == 3
    reversed_result, _ = esd_merge.compose(original, list(reversed(mods)))
    assert parse(reversed_result).state_groups[1][1] == a.state_groups[1][1]
    assert len(calls) == 6


def test_archive_cache_tracks_contents_order_originals_and_mode(monkeypatch, tmp_path):
    from collections import OrderedDict
    from pathlib import Path
    from plugins.ds1 import mod_loader
    monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    relative = Path('script/talk/test.talkesdbnd.dcx')
    calls = []
    def composed(vanilla, mods, *, conflicts_only=False):
        calls.append(1)
        data = vanilla[relative] + b''.join(mod.files[relative] for mod in mods)
        return mod_loader.Composition({} if conflicts_only else {relative: data}, [
            mod_loader.Conflict(relative, 'choice', [mod.name for mod in mods])])
    monkeypatch.setattr(mod_loader, 'compose', composed)
    def mod(name, data):
        return mod_loader.Mod(name, tmp_path / name, {relative: data})
    mods = [mod('A', b'a'), mod('B', b'b')]
    def run(original=b'base', selected=None, inspect=False):
        return mod_loader._compose_files({relative: original}, mods if selected is None else selected, inspect)
    first = run()
    first.conflicts[0].mods.clear()
    first.files.clear()
    assert run().files[relative] == b'baseab'
    assert run().conflicts[0].mods == ['A', 'B']
    assert len(calls) == 1
    assert run(selected=list(reversed(mods))).files[relative] == b'baseba'
    assert run(selected=[mod('A', b'changed'), mods[1]]).files[relative] == b'basechangedb'
    assert run(original=b'new').files[relative] == b'newab'
    assert run(inspect=True).files == {}
    assert len(calls) == 5
    mod_loader._compose_cache.clear()
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    monkeypatch.setattr(mod_loader, '_COMPOSE_CACHE_LIMIT', 20)
    run(original=b'evict')
    assert run().files[relative] == b'baseab'
    assert len(mod_loader._compose_cache) == 1
    assert mod_loader._compose_cache_bytes <= 20
    monkeypatch.setattr(mod_loader, '_COMPOSE_CACHE_LIMIT', 1)
    retained = list(mod_loader._compose_cache)
    run(original=b'oversized')
    # Oversized results are returned but never retained.
    assert list(mod_loader._compose_cache) == retained


def test_archive_outputs_survive_restart_and_only_changed_file_rebuilds(monkeypatch, tmp_path):
    from collections import OrderedDict
    from pathlib import Path
    from plugins.ds1 import mod_loader
    monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    monkeypatch.setattr(mod_loader, '_composition_revision', lambda: b'compiler-v1')
    first, second = Path('script/talk/first.dcx'), Path('script/talk/second.dcx')
    originals = {first: b'original-a', second: b'original-b'}
    mods = [mod_loader.Mod('A', tmp_path / 'mod', {first: b'edit-a', second: b'edit-b'})]
    monkeypatch.setattr(mod_loader, 'vanilla_files', lambda game, paths: originals)
    calls = []
    def composed(vanilla, selected, *, conflicts_only=False):
        relative = next(iter(vanilla))
        calls.append(relative)
        return mod_loader.Composition({relative: vanilla[relative] + selected[0].files[relative]}, [
            mod_loader.Conflict(relative, 'field', ['A', 'B'])])
    monkeypatch.setattr(mod_loader, 'compose', composed)
    def restart():
        mod_loader._compose_cache.clear()
        monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    expected = mod_loader.compose_installed(tmp_path, mods, cache_root=tmp_path / 'cache')
    restart()
    assert mod_loader.compose_installed(tmp_path, mods, cache_root=tmp_path / 'cache') == expected
    assert calls == [first, second]
    restart()
    mods[0].files[first] = b'changed-again'
    changed = mod_loader.compose_installed(tmp_path, mods, cache_root=tmp_path / 'cache')
    assert changed.files[first] == b'original-achanged-again'
    assert changed.files[second] == expected.files[second]
    assert calls == [first, second, first]
    restart()
    monkeypatch.setattr(mod_loader, '_composition_revision', lambda: b'compiler-v2')
    mod_loader.compose_installed(tmp_path, mods, cache_root=tmp_path / 'cache')
    assert calls[-2:] == [first, second]


def test_disk_archive_cache_is_bounded_and_rejects_damaged_outputs(monkeypatch, tmp_path):
    import sqlite3
    from plugins.ds1 import composition_cache
    monkeypatch.setattr(composition_cache, 'LIMIT', 8)
    monkeypatch.setattr(composition_cache, 'ENTRIES', 2)
    composition_cache.store(tmp_path, b'a', b'aaaa')
    composition_cache.store(tmp_path, b'b', b'bbbb')
    composition_cache.store(tmp_path, b'c', b'cccc')
    assert composition_cache.load(tmp_path, b'a') is None
    assert composition_cache.load(tmp_path, b'b') == b'bbbb'
    assert composition_cache.load(tmp_path, b'c') == b'cccc'
    composition_cache.store(tmp_path, b'oversized', b'x' * 9)
    assert composition_cache.load(tmp_path, b'oversized') is None
    with sqlite3.connect(tmp_path / 'composed.sqlite3') as database:
        assert database.execute('SELECT sum(length(data)), count(*) FROM outputs').fetchone() == (8, 2)
        database.execute('UPDATE outputs SET data = ? WHERE key = ?', (b'bad', b'b'))
    assert composition_cache.load(tmp_path, b'b') is None
    # Unavailable cache directories cannot block a successful composition.
    (tmp_path / 'not-a-directory').write_bytes(b'file')
    composition_cache.store(tmp_path / 'not-a-directory', b'key', b'data')
    assert composition_cache.load(tmp_path / 'not-a-directory', b'key') is None


def test_asset_binder_reports_only_the_conflicting_esd_field():
    from pathlib import Path
    from ds1_fixture import pack_text_members
    from plugins.ds1 import formats, mod_loader
    base = fixture()
    a, b = deepcopy(base), deepcopy(base)
    a.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('1')
    b.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('2')
    def archive(script):
        return pack_text_members([(1, 't100200.esd', script.to_bytes()), (2, 'untouched.esd', base.to_bytes())])
    source = archive(base)
    combined, collisions = mod_loader._compose_anibnd(source,
        [('A', archive(a)), ('B', archive(b))], Path('script/talk/test.talkesdbnd.dcx'))
    assert len(collisions) == 1
    assert collisions[0].mods == ['A', 'B']
    assert 't100200.esd/ESD/' in collisions[0].part
    plain = formats.inflate(combined)
    member = formats.members(plain)['untouched.esd']
    assert plain[member.offset:member.offset + member.size] == base.to_bytes()


def test_installed_composition_loads_talk_originals(monkeypatch, tmp_path):
    from pathlib import Path
    from ds1_fixture import pack_text_members
    from plugins.ds1 import formats, mod_loader
    base = fixture()
    humanity, estus = deepcopy(base), deepcopy(base)
    humanity.state_groups[1][0].entry_commands.pop()
    estus.state_groups[1][723] = esd.State(id=723, entry_commands=[command(50, 0)])
    relative = Path('script/talk/test.talkesdbnd.dcx')
    def archive(script):
        return pack_text_members([(1, 'bonfire.esd', script.to_bytes())])
    def originals(game_root, extra):
        assert game_root == tmp_path
        assert relative in extra
        return {relative: archive(base)}
    monkeypatch.setattr(mod_loader, 'vanilla_files', originals)
    result = mod_loader.compose_installed(tmp_path, [
        mod_loader.Mod('Estus', tmp_path / 'estus', {relative: archive(estus)}),
        mod_loader.Mod('Humanity', tmp_path / 'humanity', {relative: archive(humanity)})])
    assert not result.conflicts
    plain = formats.inflate(result.files[relative])
    member = formats.members(plain)['bonfire.esd']
    parsed = esd.parse(plain[member.offset:member.offset + member.size])
    assert 723 in parsed.state_groups[1]
    assert parsed.state_groups[1][0].entry_commands == humanity.state_groups[1][0].entry_commands


def test_mod_activation_deploys_the_current_script_build(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from pathlib import Path
    from plugins.ds1 import mod_loader, mod_support, tweak_mods
    relative = Path('script/talk/test.talkesdbnd.dcx')
    generated = tmp_path / 'generated.dcx'
    generated.write_bytes(b'previous build')
    adapter = mod_support.Ds1ModAdapter()
    adapter.attach_context(library_root=tmp_path)
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    monkeypatch.setattr(tweak_mods, 'locked', lambda game: nullcontext())
    def prepare(game, library, **kwargs):
        generated.write_bytes(b'current settings')
        return {'files': []}
    monkeypatch.setattr(tweak_mods, 'prepare', prepare)
    monkeypatch.setattr(tweak_mods, 'commit', lambda game, plan: None)
    monkeypatch.setattr(adapter, '_mods', lambda paths: [
        mod_loader.Mod('Talk mod', tmp_path, {relative: generated.read_bytes()})])
    monkeypatch.setattr(mod_loader, 'compose_installed', lambda game, mods, **kwargs:
        mod_loader.Composition(mods[0].files, []))
    deployed = []
    monkeypatch.setattr(mod_support.deployment, 'apply',
        lambda game, folder, composed: deployed.append(composed))
    adapter.activate([tmp_path], tmp_path / 'game')
    assert deployed == [{relative: b'current settings'}]


def test_tweak_context_reads_enabled_dependency_and_builds_talk_files(tmp_path):
    import json
    from core import script_mods
    from plugins.ds1 import tweak_mods
    root = tmp_path / 'dependent'
    (root / 'script').mkdir(parents=True)
    (root / 'mod.json').write_text(json.dumps({'id': 'dependent', 'script': {'version': 1}}))
    (root / 'script/__init__.py').write_text('')
    (root / 'script/native_patch.py').write_text('ST_MP = 123\n')
    (root / 'script/tweak.py').write_text(
        'def build(settings, context):\n'
        '    return {"script/talk/test.talkesdbnd.dcx": b"talk", "msg/ENGLISH/menu.msgbnd.dcx": b"text"}\n')
    context = tweak_mods.BuildContext({'dependent': root}, tmp_path / 'game')
    assert context.game_root == tmp_path / 'game'
    assert context.module('dependent', 'native_patch').ST_MP == 123
    script_mods.build(root, context, allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert (root / 'script/talk/test.talkesdbnd.dcx').read_bytes() == b'talk'
    assert (root / 'msg/ENGLISH/menu.msgbnd.dcx').read_bytes() == b'text'


def test_same_new_menu_result_id_is_a_real_conflict():
    base = fixture()
    a, b = deepcopy(base), deepcopy(base)
    a.state_groups[1][0].entry_commands.append(command(19, 723, 15000723, -1))
    b.state_groups[1][0].entry_commands.append(command(19, 723, 15000724, -1))
    merged, collisions = esd_merge.compose(base.to_bytes(), [('A', a.to_bytes()), ('B', b.to_bytes())])
    assert len(collisions) == 1
    assert collisions[0][1] == ['A', 'B']
    result = esd.parse(merged).state_groups[1][0].entry_commands
    assert result == base.state_groups[1][0].entry_commands + [command(19, 723, 15000724, -1)]


def test_remastered_icon_catalog_preserves_pixel_rectangles(monkeypatch):
    import struct
    from types import SimpleNamespace
    from plugins.ds1 import icons
    blob = bytearray(36)
    blob[8:16] = b'\xff' * 4 + b'\0' * 4
    struct.pack_into('<4h', blob, 16, 986, 1289, 1146, 1469)
    struct.pack_into('<h', blob, 24, 0)
    class Layout:
        def nodes(self, name):
            return [SimpleNamespace(name='EquIcon_2222', shape=0)]
        def _blob(self, *args):
            return 'Sprite', bytes(blob)
    monkeypatch.setattr(icons, 'Drb', lambda data: Layout())
    monkeypatch.setattr(icons, '_texi_names', lambda layout: ['Icon21'])
    sheet, *rectangle = icons.icon_table(b'fixture')[2222]
    assert sheet == 'Icon21'
    assert tuple(value * icons.SCALE for value in rectangle) == (986, 1289, 1146, 1469)


def test_legacy_icon_record_with_tail_padding_stays_legacy(monkeypatch):
    import struct
    from types import SimpleNamespace
    from plugins.ds1 import icons
    blob = bytearray(36)
    struct.pack_into('<4h', blob, 8, 1, 1, 81, 91)
    struct.pack_into('<h', blob, 16, 0)
    class Layout:
        def nodes(self, name):
            return [SimpleNamespace(name='EquIcon_0001', shape=0)]
        def _blob(self, *args):
            return 'Sprite', bytes(blob)
    monkeypatch.setattr(icons, 'Drb', lambda data: Layout())
    monkeypatch.setattr(icons, '_texi_names', lambda layout: ['Icon00'])
    assert icons.icon_table(b'fixture')[1] == ('Icon00', 1, 1, 81, 91)


def test_missing_icon_catalog_raises_the_domain_error(tmp_path):
    import pytest
    from plugins.ds1 import icons
    with pytest.raises(icons.IconError):
        icons.load_icon_table(tmp_path)

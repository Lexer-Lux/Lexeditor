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

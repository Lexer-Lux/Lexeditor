"""Loose character scripts survive normal composition, rebuild and removal."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from ds1_fixture import make_archive
from tae_fixture import build_anibnd
from plugins.ds1 import assets, deployment, esd, mod_loader, mod_support
from plugins.ds1.formats import FormatError, deflate, inflate
from plugins.ds1.store import MARKER, RELATIVE

TEMPLATE = build_anibnd({'unused.bin': b'unchanged'})
SCRIPT = Path('chr/enemycommon.esd.dcx')
BASE = esd.Esd(state_groups={0: {
    0: esd.State(id=0, entry_commands=[esd.Command(1, 103, [esd.assemble('0')])]),
    1: esd.State(id=1, entry_commands=[esd.Command(1, 103, [esd.assemble('0')])]),
}})


def packed(document):
    return deflate(TEMPLATE, document.to_bytes())


def changed(state, value):
    document = deepcopy(BASE)
    document.state_groups[0][state].entry_commands[0].args[0] = esd.assemble(str(value))
    return packed(document)


def mod(folder, name, data, relative=SCRIPT):
    folder.mkdir(parents=True)
    (folder / MARKER).touch()
    (folder / 'mod.json').write_text(json.dumps({'name': name, 'enabled': True}))
    (folder / relative).parent.mkdir(parents=True, exist_ok=True)
    (folder / relative).write_bytes(data)
    return mod_loader.read_mod(folder, name)


@pytest.mark.parametrize('relative', [SCRIPT, Path('chr/c0000.esd.dcx')])
def test_discovery_and_vanilla_loading_include_loose_scripts(tmp_path, relative):
    game = tmp_path / 'game'
    (game / relative).parent.mkdir(parents=True)
    (game / relative).write_bytes(packed(BASE))
    carried = mod(tmp_path / 'library' / 'A', 'A', changed(0, 4), relative)
    assert carried.files == {relative: changed(0, 4)}
    assert assets.is_owned(relative)
    assert not assets.scan_project(carried.folder)
    inspected = mod_support.Ds1ModAdapter().inspect(carried.folder, [relative])
    assert inspected['valid'] and inspected['packages'] == [relative.as_posix()]
    combined, active = mod_loader.build(game, carried.folder.parent)
    assert [m.name for m in active] == ['A']
    assert combined.files[relative] == changed(0, 4)


def test_disjoint_state_changes_compose_without_whole_file_conflicts(tmp_path):
    a = mod(tmp_path / 'A', 'A', changed(0, 4))
    b = mod(tmp_path / 'B', 'B', changed(1, 8))
    result = mod_loader.compose({SCRIPT: packed(BASE)}, [a, b])
    merged = esd.parse(inflate(result.files[SCRIPT]))
    assert not result.conflicts
    assert esd.disassemble(merged.state_groups[0][0].entry_commands[0].args[0]) == '4'
    assert esd.disassemble(merged.state_groups[0][1].entry_commands[0].args[0]) == '8'


def test_actual_field_collisions_report_the_script_state_and_both_mods(tmp_path):
    a = mod(tmp_path / 'A', 'A', changed(0, 4))
    b = mod(tmp_path / 'B', 'B', changed(0, 8))
    result = mod_loader.compose({SCRIPT: packed(BASE)}, [a, b])
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.file == SCRIPT and conflict.mods == ['A', 'B']
    assert 'state_groups/0/0/entry_commands' in conflict.part
    merged = esd.parse(inflate(result.files[SCRIPT]))
    assert esd.disassemble(merged.state_groups[0][0].entry_commands[0].args[0]) == '8'


def test_character_commands_do_not_receive_talk_option_semantics(tmp_path):
    variants = []
    for name, value in [('A', 2), ('B', 3)]:
        document = deepcopy(BASE)
        document.state_groups[0][0].entry_commands.append(
            esd.Command(1, 19, [esd.assemble('1'), esd.assemble(str(value))]))
        variants.append(mod(tmp_path / name, name, packed(document)))
    result = mod_loader.compose({SCRIPT: packed(BASE)}, variants)
    assert not result.conflicts
    assert len(esd.parse(inflate(result.files[SCRIPT])).state_groups[0][0].entry_commands) == 3


def test_rebuild_restarts_from_preserved_vanilla_and_disabling_restores_exactly(tmp_path):
    game = tmp_path / 'game'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / SCRIPT).parent.mkdir(parents=True)
    original = packed(BASE)
    (game / SCRIPT).write_bytes(original)
    a = mod(tmp_path / 'library' / 'A', 'A', changed(0, 4))
    b = mod(tmp_path / 'library' / 'B', 'B', changed(1, 8))
    for _ in range(2):
        combined, active = mod_loader.build(game, a.folder.parent)
        assert {m.name for m in active} == {'A', 'B'}
        assert not combined.conflicts
        status = deployment.apply(game, a.folder, composed=combined.files)
        assert SCRIPT.name in status['chars']['applied']
        assert deployment.vanilla_source(game, SCRIPT).read_bytes() == original
        assert esd.parse(inflate((game / SCRIPT).read_bytes())).state_groups[0][0] != BASE.state_groups[0][0]
    (a.folder / 'mod.json').write_text(json.dumps({'name': 'A', 'enabled': False}))
    combined, active = mod_loader.build(game, a.folder.parent)
    assert [m.name for m in active] == ['B']
    deployment.apply(game, b.folder, composed=combined.files)
    document = esd.parse(inflate((game / SCRIPT).read_bytes()))
    assert document.state_groups[0][0] == BASE.state_groups[0][0]
    assert document.state_groups[0][1] != BASE.state_groups[0][1]
    (b.folder / 'mod.json').write_text(json.dumps({'name': 'B', 'enabled': False}))
    combined, active = mod_loader.build(game, b.folder.parent)
    assert active == []
    deployment.apply(game, b.folder, composed=combined.files)
    assert (game / SCRIPT).read_bytes() == original


def test_corrupt_character_script_is_refused_before_any_game_write(tmp_path):
    game = tmp_path / 'game'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / SCRIPT).parent.mkdir(parents=True)
    original = packed(BASE)
    (game / SCRIPT).write_bytes(original)
    a = mod(tmp_path / 'A', 'A', deflate(TEMPLATE, b'not an ESD'))
    with pytest.raises(FormatError):
        deployment.apply(game, a.folder, composed={SCRIPT: a.files[SCRIPT]})
    assert (game / SCRIPT).read_bytes() == original
    assert not deployment._backup_path(game, SCRIPT).exists()


def test_other_character_assets_still_use_the_asset_composer():
    relative = Path('chr/c0000.chrbnd.dcx')
    assert not assets.is_character_file(relative)
    assert mod_loader._is_asset(relative)

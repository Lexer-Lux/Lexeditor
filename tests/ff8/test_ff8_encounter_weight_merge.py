"""Authored fixtures prove complete-distribution composition and removal."""
from hashlib import sha256
import json

import pytest

from plugins.ff8 import encounter_chances as chances, paths, runtime_layout, world_data_merge, world_map
from test_ff8_encounter_rules import _synthetic_wmset

PATH = 'direct/world/dat/wmsetus.obj'
FIRST, LAST = [256]+[0]*7, [0]*7+[256]


def merge(base, mods):
    return world_data_merge.merge(base, mods, 'wmset', PATH)


def test_independent_groups_and_ordinary_fields_survive_both_orders():
    base = _synthetic_wmset()
    first = chances.with_weights(base, 3, {0: FIRST})
    last = bytearray(base)
    region = world_map._pointers(base)[1]
    last[region] = 7
    last = chances.with_weights(bytes(last), 3, {2: LAST})
    for mods in ([('first', first), ('last', last)], [('last', last), ('first', first)]):
        output, conflicts, reason = merge(base, mods)
        assert not conflicts and not reason
        stripped, weights = chances.read_extension(output, 3)
        assert stripped[region] == 7
        assert weights == [tuple(FIRST), chances.DEFAULT_OUTCOMES, tuple(LAST)]


def test_collisions_choose_one_complete_distribution_and_follow_order():
    base = _synthetic_wmset()
    first = chances.with_weights(base, 3, {0: FIRST})
    last = chances.with_weights(base, 3, {0: LAST})
    for mods, winner in ([('first', first), ('last', last)], 'last'), ([('last', last), ('first', first)], 'first'):
        output, conflicts, reason = merge(base, mods)
        assert not reason
        weights = chances.read_extension(output, 3)[1]
        assert weights[0] == tuple(LAST if winner == 'last' else FIRST)
        assert sum(weights[0]) == 256
        assert conflicts == [{'unit': f'{PATH}:group:0:initialOutcomes',
                              'winner': winner, 'claimants': [row[0] for row in mods]}]


def test_identical_claims_are_not_conflicts_and_removal_restores_defaults():
    base = _synthetic_wmset()
    first = chances.with_weights(base, 3, {0: FIRST})
    last = chances.with_weights(base, 3, {2: LAST})
    output, conflicts, reason = merge(base, [('one', first), ('two', first)])
    assert output == first and not conflicts and not reason
    assert merge(base, [('last', last)])[0] == last
    assert merge(base, [])[0] == base


def test_weighted_opaque_and_corrupt_inputs_report_failure():
    base = _synthetic_wmset()
    first = chances.with_weights(base, 3, {0: FIRST})
    opaque = bytearray(base)
    opaque[-1] = 1
    output, conflicts, reason = merge(base, [('first', first), ('opaque', bytes(opaque))])
    assert output is None and not conflicts and 'outside proved' in reason
    corrupt = bytearray(first)
    corrupt[-1] ^= 1
    output, conflicts, reason = merge(base, [('corrupt', bytes(corrupt))])
    assert output is None and not conflicts and 'checksum' in reason


def test_plain_oversized_files_keep_the_existing_merger():
    base = _synthetic_wmset() + bytes(chances.MAX_WMSET_SIZE)
    assert merge(base, [('same', base)]) == (base, [], '')


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    base = _synthetic_wmset()
    baseline = tmp_path/'baseline/world/wmsetus.obj'
    baseline.parent.mkdir(parents=True)
    baseline.write_bytes(base)
    game = tmp_path/'game'
    game.mkdir()
    exe = b'authored executable signature fixture'
    (game/'FF8_EN.exe').write_bytes(exe)
    monkeypatch.setattr(chances, 'SUPPORTED_EXE_SHA256', sha256(exe).hexdigest())
    monkeypatch.setattr(paths, 'GAME_ROOT', game)
    roots = []
    for index, weights in enumerate((FIRST, LAST)):
        root = tmp_path/f'mod{index}'
        data = chances.with_weights(base, 3, {index: weights})
        target = root/PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        patch = root/chances.HEXT_RELATIVE
        patch.parent.mkdir(parents=True)
        offset = chances.extension_offset(data, 3, world_map._pointers(base)[3])
        patch.write_text(chances.build_hext(exe, offset), encoding='utf-8')
        (root/'mod.json').write_text(json.dumps({'id': f'mod{index}', 'name': f'mod{index}',
                                               'enabled': True, 'order': index}), encoding='utf-8')
        roots.append(root)
    rows = runtime_layout.catalog(roots[0], tmp_path)
    active = tmp_path/'runtime'

    def compose(selected=None):
        return runtime_layout.compose(roots[0], active, rows if selected is None else selected,
                                      baseline.parent.parent)

    return base, roots, rows, active, compose


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_production_composer_orders_and_removes_weight_mods(deployment):
    base, roots, rows, active, compose = deployment
    compose()
    assert chances.read_extension((active/PATH).read_bytes(), 3)[1] == [
        tuple(FIRST), tuple(LAST), chances.DEFAULT_OUTCOMES]
    patches = sorted((active/'hext').rglob('*.txt'))
    assert len(patches) == 2 and patches[0].read_bytes() == patches[1].read_bytes()
    # A later ordinary edit still combines with the weighted mods.
    ordinary = roots[0].parent/'ordinary'
    target = ordinary/PATH
    target.parent.mkdir(parents=True)
    modified = bytearray(base)
    modified[world_map._pointers(base)[1]] = 7
    target.write_bytes(modified)
    extra = {'id': 'ordinary', 'name': 'ordinary', 'path': str(ordinary), 'enabled': True}
    compose(rows+[extra])
    assert chances.read_extension((active/PATH).read_bytes(), 3)[0] == bytes(modified)
    # Conflicting complete distributions obey the supplied low-to-high order.
    (roots[1]/PATH).write_bytes(chances.with_weights(base, 3, {0: LAST}))
    compose()
    assert chances.read_extension((active/PATH).read_bytes(), 3)[1][0] == tuple(LAST)
    compose(list(reversed(rows)))
    assert chances.read_extension((active/PATH).read_bytes(), 3)[1][0] == tuple(FIRST)
    compose([rows[0]])
    assert (active/PATH).read_bytes() == (roots[0]/PATH).read_bytes()
    assert len(list((active/'hext').rglob('*.txt'))) == 1
    compose([])
    assert not (active/PATH).exists() and not list((active/'hext').rglob('*.txt'))


@pytest.mark.parametrize('defect', ['missing-patch', 'wrong-patch', 'orphan-patch',
                                   'corrupt-weights', 'opaque-world', 'unsupported-exe', 'live-world'])
def test_bad_pairs_preserve_the_entire_previous_runtime(deployment, defect):
    base, roots, rows, active, compose = deployment
    compose()
    previous = snapshot(active)
    if defect == 'missing-patch':
        (roots[0]/chances.HEXT_RELATIVE).unlink()
    elif defect == 'wrong-patch':
        (roots[0]/chances.HEXT_RELATIVE).write_bytes(b'541E2D = 90\n')
    elif defect == 'orphan-patch':
        (roots[0]/PATH).write_bytes(base)
    elif defect == 'corrupt-weights':
        corrupt = bytearray((roots[0]/PATH).read_bytes())
        corrupt[-1] ^= 1
        (roots[0]/PATH).write_bytes(corrupt)
    elif defect == 'opaque-world':
        opaque = bytearray(base)
        opaque[-1] = 1
        (roots[1]/PATH).write_bytes(opaque)
        (roots[1]/chances.HEXT_RELATIVE).write_bytes(b'')
    elif defect == 'unsupported-exe':
        (paths.GAME_ROOT/'FF8_EN.exe').write_bytes(b'unsupported')
    else:
        candidate = roots[1]/'live'/PATH
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(base)
        (roots[1]/'mod.xml').write_text(
            '<ModInfo><Conditional Folder="live"><RuntimeVar ApplyTo="" '
            'Var="Byte:0x00DC08EB" Values="1"/></Conditional></ModInfo>', encoding='utf-8')
    reasons = {'missing-patch': 'must be paired', 'wrong-patch': 'Hext does not match',
               'orphan-patch': 'must be paired', 'corrupt-weights': 'checksum',
               'opaque-world': 'outside proved', 'unsupported-exe': 'supported English Steam',
               'live-world': 'live conditional world data'}
    with pytest.raises(ValueError, match=reasons[defect]):
        compose()
    assert snapshot(active) == previous
    assert not list(active.parent.glob('.runtime.staging-*'))

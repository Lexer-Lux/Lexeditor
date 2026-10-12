"""Animation lists, skeletons, sampled frames and skinned geometry."""
import base64
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd, build_tae
from plugins.ds1 import anim, viewport
from plugins.ds1.hkx import HkxError
from plugins.ds1.tae_store import TaeStore


def game_with_chr(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    (game / 'chr' / 'c1200.anibnd.dcx').write_bytes(build_anibnd({
        'Skeleton.hkx': build_tag0(), 'a87_3300.hkx': build_tag0(), 'a87.tae': build_tae(),
        'c1200.tae': build_tae()}))
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
    return game


def f32(blob):
    raw = base64.b64decode(blob)
    return struct.unpack('<%df' % (len(raw) // 4), raw)


def u32(blob):
    raw = base64.b64decode(blob)
    return struct.unpack('<%dI' % (len(raw) // 4), raw)


def test_list_anims_links_tae_ids(tmp_path):
    listed = anim.list_anims(game_with_chr(tmp_path), None, 'c1200')
    assert listed['skeleton'] is True
    assert listed['anims'] == [{'file': 'a87_3300.hkx', 'binder': 'c1200.anibnd.dcx',
                                'bank': 'a87', 'id': 3300, 'duration': pytest.approx(0.1),
                                'frames': 4}]


def test_anim_events_fall_back_to_chr_tae(tmp_path):
    game = game_with_chr(tmp_path)
    store = TaeStore(game)
    assert len(anim.anim_events(store, 'c1200', 'c1200.anibnd.dcx', 'a87_3300.hkx')) == 4
    assert len(anim.anim_events(store, 'c1200', 'c1200.anibnd.dcx', 'a99_3300.hkx')) == 4
    assert anim.anim_events(store, 'c1200', 'c1200.anibnd.dcx', 'a99_9999.hkx') == []


def test_skeleton_maps_flver_bones_by_name(tmp_path):
    skel = anim.skeleton(game_with_chr(tmp_path), None, 'c1200')
    assert skel['hka']['bones'] == ['root', 'child']
    assert skel['hka']['parents'] == [-1, 0]
    assert [bone['name'] for bone in skel['flver']] == ['root']
    assert skel['map'] == [0]


def test_anim_frames_sample_and_cue_events(tmp_path):
    game = game_with_chr(tmp_path)
    payload = anim.anim_frames(game, None, 'c1200', 'c1200.anibnd.dcx', 'a87_3300.hkx',
                               TaeStore(game))
    assert (payload['frames'], payload['bones']) == (4, 2)
    assert payload['motion'] is None
    trans = f32(payload['translations'])
    assert trans[0:3] == pytest.approx((0.0, 1.0, 0.0))
    assert [trans[f * 6 + 3] for f in range(4)] == pytest.approx([0.0, 1 / 3, 2 / 3, 0.0])
    quats = f32(payload['rotations'])
    assert quats[0:4] == pytest.approx((0.0, 0.0, 0.0, 1.0))
    starts = sorted(event['start'] for event in payload['events'])
    assert starts == pytest.approx([0.0, 0.0, 0.5, 1.5])


def test_anim_frames_without_store_has_no_events(tmp_path):
    payload = anim.anim_frames(game_with_chr(tmp_path), None, 'c1200',
                               'c1200.anibnd.dcx', 'a87_3300.hkx')
    assert payload['events'] == []


def test_unknown_chr_binder_and_member(tmp_path):
    game = game_with_chr(tmp_path)
    with pytest.raises(HkxError):
        anim.list_anims(game, None, 'c9999')
    with pytest.raises(HkxError):
        anim.list_anims(game, None, '../param')
    with pytest.raises(HkxError):
        anim.anim_frames(game, None, 'c1200', 'c1200.anibnd.dcx', 'Skeleton.hkx')
    with pytest.raises(HkxError):
        anim.anim_frames(game, None, 'c1200', 'c1200.anibnd.dcx', 'a87_9999.hkx')
    with pytest.raises(HkxError):
        anim.anim_frames(game, None, 'c1200', '../x.anibnd.dcx', 'a87_3300.hkx')


def test_skinned_geometry_resolves_bone_lists(tmp_path):
    geo = viewport.chr_geometry(game_with_chr(tmp_path), None, 'c1200', skin=True)
    mesh = geo['meshes'][0]
    assert mesh['verts'] == 4
    assert u32(mesh['skin_ids']) == (0,) * 16
    assert len(f32(mesh['skin_weights'])) == 16


def test_skinned_geometry_absent_without_flag(tmp_path):
    geo = viewport.chr_geometry(game_with_chr(tmp_path), None, 'c1200')
    assert 'skin_ids' not in geo['meshes'][0]


def test_list_chars_skips_variant_and_pair_binders(tmp_path):
    game = game_with_chr(tmp_path)
    (game / 'chr' / 'c1200_a00_hi.anibnd.dcx').write_bytes(b'variant')
    (game / 'chr' / 'c0000_c1200.anibnd.dcx').write_bytes(b'pair')
    assert anim.list_chars(game, None) == ['c1200']


def test_binders_rank_variants_and_skip_pairs(tmp_path):
    game = game_with_chr(tmp_path)
    (game / 'chr' / 'c1200_a00_hi.anibnd.dcx').write_bytes(b'hi')
    (game / 'chr' / 'c1200_a0x.anibnd.dcx').write_bytes(b'bank')
    (game / 'chr' / 'c1200_dlc.anibnd.dcx').write_bytes(b'dlc')
    (game / 'chr' / 'c1200_c1300.anibnd.dcx').write_bytes(b'pair')
    names = [name for name, _path in anim._binders(game, None, 'c1200')]
    assert names == ['c1200.anibnd.dcx', 'c1200_a00_hi.anibnd.dcx', 'c1200_a0x.anibnd.dcx',
                     'c1200_dlc.anibnd.dcx']


def test_list_anims_marks_broken_member(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    (game / 'chr' / 'c1200.anibnd.dcx').write_bytes(build_anibnd({
        'Skeleton.hkx': build_tag0(), 'a87_3300.hkx': build_tag0(),
        'a87_3301.hkx': b'not a havok file'}))
    listed = anim.list_anims(game, None, 'c1200')
    broken = next(entry for entry in listed['anims'] if entry['file'] == 'a87_3301.hkx')
    assert broken['available'] is False
    assert broken['reason']
    assert any(entry['file'] == 'a87_3300.hkx' and entry.get('available', True)
               for entry in listed['anims'])

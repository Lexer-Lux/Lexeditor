"""Havok TAG0 container, extraction and spline sampling on synthetic files."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkx_fixture import build_tag0
from plugins.ds1.hkx import (ARRAY, FLAG_FORMAT, HkxDocument, HkxError,
                             _TagReader, _Type, _parse_quat, _parse_vec,
                             peek_animation, sample_frames)


def test_container_reads_skeleton_anim_and_binding():
    doc = HkxDocument(build_tag0())
    assert len(doc.skeletons) == 1
    skel = doc.skeletons[0]
    assert skel['name'] == 'Master'
    assert skel['parents'] == [-1, 0]
    assert [bone['name'] for bone in skel['bones']] == ['root', 'child']
    assert skel['pose'][0]['t'] == pytest.approx([0.0, 1.0, 0.0])
    assert skel['pose'][0]['s'] == pytest.approx([2.0, 2.0, 2.0])
    kinds = sorted(anim['kind'] for anim in doc.animations)
    assert kinds == ['interleaved', 'spline']
    spline = next(anim for anim in doc.animations if anim['kind'] == 'spline')
    assert (spline['tracks'], spline['frames'], spline['blocks']) == (2, 4, 1)
    assert spline['motion'] is None
    assert [link['track_to_bone'] for link in doc.bindings] == [[0, 1], [1]]


def test_spline_sampling_statics_curve_and_scale_fallback():
    doc = HkxDocument(build_tag0())
    skel = doc.skeletons[0]
    spline = next(anim for anim in doc.animations if anim['kind'] == 'spline')
    frames = sample_frames(spline, skel, doc.bindings[0])
    assert len(frames) == 4
    for pose in frames:
        assert pose[0][0] == pytest.approx((0.0, 1.0, 0.0))
        assert pose[0][1] == pytest.approx((0.0, 0.0, 0.0, 1.0))
        # No scale channels: the skeleton's own doubled scale survives.
        assert pose[0][2] == pytest.approx((2.0, 2.0, 2.0))
        assert pose[1][1] == pytest.approx((0.0, 0.0, 0.0, 1.0))
        assert pose[1][2] == pytest.approx((1.0, 1.0, 1.0))
    assert [pose[1][0][0] for pose in frames] == pytest.approx([0.0, 1 / 3, 2 / 3, 0.0])
    assert [pose[1][0][1:] for pose in frames] == [(5.0, 6.0)] * 4


def test_interleaved_sampling_and_unmapped_bone_pose():
    doc = HkxDocument(build_tag0())
    skel = doc.skeletons[0]
    inter = next(anim for anim in doc.animations if anim['kind'] == 'interleaved')
    frames = sample_frames(inter, skel, doc.bindings[1])
    assert [pose[1][0] for pose in frames] == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    # Bone 0 has no track: it keeps the reference pose.
    assert [pose[0][0] for pose in frames] == [(0.0, 1.0, 0.0)] * 2


def test_bad_magic_truncation_and_garbage():
    with pytest.raises(HkxError):
        HkxDocument(b'NOPE' + build_tag0()[4:])
    with pytest.raises(HkxError):
        HkxDocument(build_tag0()[:100])
    with pytest.raises(HkxError):
        HkxDocument(b'\0' * 64)
    with pytest.raises(HkxError):
        HkxDocument(b'')


def test_float_tracks_refused():
    blob = bytearray(build_tag0())
    # The spline blob starts at the first 0.1 duration; its float-track
    # count sits 8 bytes in.
    spline_at = blob.index(b'\xcd\xcc\xcc\x3d')
    blob[spline_at + 8:spline_at + 12] = (1).to_bytes(4, 'little')
    with pytest.raises(HkxError, match='float tracks'):
        HkxDocument(bytes(blob))


def test_str_source_wrapped():
    with pytest.raises(HkxError):
        HkxDocument('not bytes')


def test_self_parent_and_cyclic_types_raise():
    loop = _Type()
    loop.parent = loop
    with pytest.raises(HkxError, match='loop back'):
        loop.resolve_subtype()
    first, second = _Type(), _Type()
    first.parent, second.parent = second, first
    with pytest.raises(HkxError, match='loop back'):
        first.resolve_subtype()
    with pytest.raises(HkxError, match='loop back'):
        first.resolve_size()


def test_fixed_array_length_capped():
    item = _Type()
    item.flags = FLAG_FORMAT
    item.format_info = ARRAY | 0x20 | (70000 << 8)
    reader = _TagReader(b'', 0, [], [])
    with pytest.raises(HkxError, match='too long'):
        reader._value(item, 0, 0)


def test_binding_past_tracks_refused():
    doc = HkxDocument(build_tag0())
    skel = doc.skeletons[0]
    inter = next(anim for anim in doc.animations if anim['kind'] == 'interleaved')
    with pytest.raises(HkxError, match='past its tracks'):
        sample_frames(inter, skel, {'track_to_bone': [1, 0, 0, 0]})
    spline = next(anim for anim in doc.animations if anim['kind'] == 'spline')
    with pytest.raises(HkxError, match='past its tracks'):
        sample_frames(spline, skel, {'track_to_bone': [0, 1, 0]})
    # A track aimed at no bone just leaves that bone in its reference pose.
    frames = sample_frames(inter, skel, {'track_to_bone': [0, 99]})
    assert len(frames) == 2


def test_spline_degree_capped():
    blob = struct.pack('<H', 0) + bytes([5])
    with pytest.raises(HkxError, match='too complex'):
        _parse_vec(blob, 0, 0, 1, 0, 0.0)
    with pytest.raises(HkxError, match='too complex'):
        _parse_quat(blob, 0, 0, 1, 0)


def test_block_offset_out_of_range():
    doc = HkxDocument(build_tag0())
    skel = doc.skeletons[0]
    spline = next(anim for anim in doc.animations if anim['kind'] == 'spline')
    bad = dict(spline, offsets=[len(spline['data']) + 100])
    with pytest.raises(HkxError, match='out of range'):
        sample_frames(bad, skel, doc.bindings[0])


def test_peek_animation_reads_first_headline():
    assert peek_animation(build_tag0()) == {'duration': pytest.approx(0.1), 'frames': 4}


def test_peek_animation_agrees_with_full_read():
    doc = HkxDocument(build_tag0())
    first = doc.animations[0]
    assert peek_animation(build_tag0()) == {'duration': pytest.approx(first['duration']),
                                            'frames': first['frames']}


def test_peek_animation_refuses_garbage():
    with pytest.raises(HkxError):
        peek_animation(b'not a havok file')

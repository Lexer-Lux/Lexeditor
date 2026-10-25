"""Animation recovery: odd spellings, rig fallbacks, old binders."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd, build_tae
from plugins.ds1 import anim, formats
from plugins.ds1.tae_store import TaeStore

CID = 'c1200'


def game_with(tmp_path, anibnd_members, chrbnd_extra=(), wide=True):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    (game / 'chr' / f'{CID}.anibnd.dcx').write_bytes(
        build_anibnd(anibnd_members, wide=wide))
    (game / 'chr' / f'{CID}.chrbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), CID, list(chrbnd_extra)))
    return game


def plain_of(game):
    plain, _names = anim._open(str(game / 'chr' / f'{CID}.anibnd.dcx'))
    return plain


def payloads(plain):
    return {name: bytes(plain[member.offset:member.offset + member.size])
            for name, member in formats.members(plain).items()}


def test_uppercase_skeleton_member_resolves(tmp_path):
    game = game_with(tmp_path, {'SKELETON.HKX': build_tag0(),
                                'a87_3300.hkx': build_tag0()})
    assert anim.list_anims(game, None, CID)['skeleton'] is True
    assert anim.skeleton(game, None, CID)['hka']['bones'] == ['root', 'child']


def test_missing_anibnd_skeleton_falls_back_to_chrbnd_rig(tmp_path):
    tag = build_tag0()
    game = game_with(tmp_path, {'a87_3300.hkx': tag, 'a87.tae': build_tae()},
                     [(f'{CID}.hkx', tag)])
    assert anim.list_anims(game, None, CID)['skeleton'] is True
    assert anim.skeleton(game, None, CID)['hka']['bones'] == ['root', 'child']
    payload = anim.anim_frames(game, None, CID, f'{CID}.anibnd.dcx',
                               'a87_3300.hkx', TaeStore(game))
    assert (payload['frames'], payload['bones']) == (4, 2)


def test_uppercase_motion_links_tae_and_counts_events(tmp_path):
    game = game_with(tmp_path, {'Skeleton.hkx': build_tag0(),
                                'a87_3300.HKX': build_tag0(),
                                'a87.tae': build_tae(),
                                f'{CID}.tae': build_tae()})
    listed = anim.list_anims(game, None, CID, TaeStore(game))
    motion = next(entry for entry in listed['anims']
                  if entry['file'] == 'a87_3300.HKX')
    assert (motion['bank'], motion['id']) == ('a87', 3300)
    assert (motion['tae'], motion['taeIndex']) == ('a87.tae', 0)
    assert motion['eventCount'] == 4
    assert any(orphan['tae'] == 'a87.tae' and orphan['taeIndex'] == 1
               and orphan['events'] == 0 for orphan in listed['orphans'])


def test_narrow_binder_lists_and_repacks_narrow(tmp_path):
    game = game_with(tmp_path, {'Skeleton.hkx': build_tag0(),
                                'a87_3300.hkx': build_tag0()}, wide=False)
    listed = anim.list_anims(game, None, CID)
    assert listed['skeleton'] is True
    assert [entry['file'] for entry in listed['anims']] == ['a87_3300.hkx']
    plain = plain_of(game)
    assert plain[12:16] == b'\x70\0\0\0'
    rebuilt = formats.pack(plain, payloads(plain))
    assert rebuilt[12:16] == b'\x70\0\0\0'
    assert payloads(rebuilt) == payloads(plain)


def test_duplicate_member_first_wins_and_twins_pack_together(tmp_path):
    first, second = build_tae(), build_tae() + b'\0'
    assert len(first) != len(second)
    game = game_with(tmp_path, [('a87.tae', first), ('a87.tae', second)])
    plain = plain_of(game)
    member = formats.members(plain)['a87.tae']
    assert bytes(plain[member.offset:member.offset + member.size]) == first
    rebuilt = formats.pack(plain, {'a87.tae': b'updated events'})
    count = struct.unpack_from('<I', rebuilt, 16)[0]
    assert count == 2
    spans = [struct.unpack_from('<6I', rebuilt, 32 + index * 24)[1:3]
             for index in range(count)]
    assert [bytes(rebuilt[offset:offset + size]) for size, offset in spans] == \
        [b'updated events'] * 2


def test_flver_bind_uses_havok_euler_order():
    # The bind math proven on real tusks and tails: FLVER bone angles
    # compose in YZX order, matching each mapped bone's Havok rest
    # quaternion exactly. This trips if the order ever drifts back.
    source = (ROOT / 'plugins' / 'ds1' / 'anim.js').read_text()
    assert 'Euler(rot[0], rot[1], rot[2], "YZX")' in source

"""Map pieces borrow textures from other tilesets, own first.

Kiln pieces wear m10 shared textures (m10_base_wall_01 and kin)
that live in map/m10's split archives, not the map's own map/m18
ones. The resolver used to search the map's own tileset only, so
that terrain rendered gray. Now the own tileset wins ties and every
other tileset is a fallback.
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flver_fixture import DCX_HEADER
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.viewport import _dds_png, _resolve_textures


def dcx(plain):
    header = bytearray(DCX_HEADER)
    compressed = zlib.compress(plain, 9)
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def bhf_pair(members):
    """members: [(stem, tpf bytes)] -> (bhd bytes, bdt bytes)."""
    slots, strings, bdt = [], bytearray(), bytearray()
    table_at = 28 + 24 * len(members)
    for index, (stem, tpf) in enumerate(members):
        blob = dcx(tpf)
        name = b'\\' + stem.encode('ascii') + b'.tpf\0'
        slots.append(struct.pack('<6I', 0, 64, len(blob), len(bdt), index,
                                 table_at + len(strings)))
        strings.extend(name)
        bdt.extend(blob)
    head = bytearray(28)
    head[:12] = b'BHF307D7R6\x00\x00'
    struct.pack_into('<I', head, 16, len(members))
    return bytes(head) + b''.join(slots) + bytes(strings), bytes(bdt)


def write_tileset(game, tileset, members):
    folder = game / 'map' / tileset
    folder.mkdir(parents=True)
    bhd, bdt = bhf_pair(members)
    (folder / f'{tileset}_0000.tpfbhd').write_bytes(bhd)
    (folder / f'{tileset}_0000.tpfbdt').write_bytes(bdt)


def test_piece_falls_back_to_other_tilesets(tmp_path):
    red = make_dds_rgba(2, 2, [(255, 0, 0, 255)] * 4)
    write_tileset(tmp_path, 'm10', [('m10_base_wall_01', make_tpf([('m10_base_wall_01', red)]))])
    piece = tmp_path / 'map' / 'm18_00_00_00' / 'm0000B0A18.flver.dcx'
    piece.parent.mkdir(parents=True)
    piece.touch()
    found, _notes = _resolve_textures('piece', str(piece), '', ['m10_base_wall_01'],
                                      game_root=str(tmp_path))
    assert found['m10_base_wall_01'][:8] == b'\x89PNG\r\n\x1a\n'


def test_own_tileset_wins_ties(tmp_path):
    red = make_dds_rgba(2, 2, [(255, 0, 0, 255)] * 4)
    blue = make_dds_rgba(2, 2, [(0, 0, 255, 255)] * 4)
    write_tileset(tmp_path, 'm18', [('shared_tex', make_tpf([('shared_tex', blue)]))])
    write_tileset(tmp_path, 'm10', [('shared_tex', make_tpf([('shared_tex', red)]))])
    piece = tmp_path / 'map' / 'm18_00_00_00' / 'm0000B0A18.flver.dcx'
    piece.parent.mkdir(parents=True)
    piece.touch()
    found, _notes = _resolve_textures('piece', str(piece), '', ['shared_tex'],
                                      game_root=str(tmp_path))
    assert found['shared_tex'] == _dds_png(blue)


def test_piece_finds_single_tileset_tpf(tmp_path):
    red = make_dds_rgba(2, 2, [(255, 0, 0, 255)] * 4)
    folder = tmp_path / 'map' / 'm10'
    folder.mkdir(parents=True)
    (folder / 'm10_9999.tpf.dcx').write_bytes(dcx(make_tpf([('lonely_prop', red)])))
    piece = tmp_path / 'map' / 'm18_00_00_00' / 'm0000B0A18.flver.dcx'
    piece.parent.mkdir(parents=True)
    piece.touch()
    found, _notes = _resolve_textures('piece', str(piece), '', ['lonely_prop'],
                                      game_root=str(tmp_path))
    assert found['lonely_prop'][:8] == b'\x89PNG\r\n\x1a\n'


def test_split_archive_beats_single_tpf(tmp_path):
    red = make_dds_rgba(2, 2, [(255, 0, 0, 255)] * 4)
    blue = make_dds_rgba(2, 2, [(0, 0, 255, 255)] * 4)
    write_tileset(tmp_path, 'm10', [('contested', make_tpf([('contested', red)]))])
    (tmp_path / 'map' / 'm10' / 'm10_9999.tpf.dcx').write_bytes(
        dcx(make_tpf([('contested', blue)])))
    piece = tmp_path / 'map' / 'm18_00_00_00' / 'm0000B0A18.flver.dcx'
    piece.parent.mkdir(parents=True)
    piece.touch()
    found, _notes = _resolve_textures('piece', str(piece), '', ['contested'],
                                      game_root=str(tmp_path))
    assert found['contested'] == _dds_png(red)

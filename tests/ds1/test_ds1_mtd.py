"""Material definitions decode safely and invalidate cached preview shading."""
import os
import struct
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flver_fixture import build_flver, make_chrbnd
from mtd_fixture import build_mtd
from plugins.ds1 import mtd, viewport
from plugins.ds1.formats import FormatError, members, pack

NAME = 'A10_Water_sewer[We].mtd'


def binder(color):
    raw = bytearray(make_chrbnd(b'', extra=[(NAME, build_mtd(
        {'g_WaterColor': ('float4', color), 'g_WaterWaveHeight': ('float', [2])}))], dcx=False))
    raw[12] = 0x54
    return bytes(raw)


def test_reads_finite_typed_material_parameters():
    values = {'flag': ('bool', [True]), 'count': ('int2', [-2, 7]),
        'g_WaterColor': ('float4', [0.2, 0.3, 0.1, 0.4])}
    parsed = mtd.read(build_mtd(values))
    assert parsed['shader'] == 'SyntheticWater.spx'
    assert parsed['parameters']['flag'] == [True]
    assert parsed['parameters']['count'] == [-2, 7]
    assert parsed['parameters']['g_WaterColor'] == pytest.approx([0.2, 0.3, 0.1, 0.4])


@pytest.mark.parametrize('cut', [0, 47, 100, -1])
def test_truncated_material_is_rejected(cut):
    with pytest.raises(FormatError):
        mtd.read(build_mtd()[:cut])


@pytest.mark.parametrize('damage', ['block-length', 'string-size', 'nan', 'trailing'])
def test_malformed_material_is_rejected(damage):
    raw = bytearray(build_mtd())
    if damage == 'block-length': struct.pack_into('<I', raw, 4, 0x7FFFFFFF)
    elif damage == 'string-size': struct.pack_into('<I', raw, 40, 0x7FFFFFFF)
    elif damage == 'nan':
        at = raw.index(struct.pack('<4f', 0.2, 0.3, 0.1, 0.4))
        struct.pack_into('<f', raw, at, float('nan'))
    else: raw.extend(b'junk')
    with pytest.raises(FormatError): mtd.read(bytes(raw))


def test_material_binder_format_retains_wide_records_when_repacked():
    raw = binder([0.2, 0.3, 0.1, 0.4])
    entries = members(raw)
    payloads = {name: raw[entry.offset:entry.offset+entry.size] for name, entry in entries.items()}
    payloads[NAME] = build_mtd({'g_WaterColor': ('float4', [0.4, 0.1, 0.2, 0.6])})
    rebuilt = pack(raw, payloads)
    assert rebuilt[12] == 0x54
    entry = members(rebuilt)[NAME]
    assert rebuilt[entry.offset:entry.offset+entry.size] == payloads[NAME]


def test_material_edit_refreshes_cached_geometry_and_bad_material_only_falls_back(tmp_path, monkeypatch):
    game = tmp_path/'game'
    source = game/'map'/'test'/'m10piece.flver'
    source.parent.mkdir(parents=True)
    source.write_bytes(build_flver(mtd_name=NAME))
    path = game/'mtd'/'Mtd.mtdbnd.dcx'
    path.parent.mkdir()
    path.write_bytes(binder([0.2, 0.3, 0.1, 0.4]))
    monkeypatch.setenv(viewport.MAP_CACHE_ENV, str(tmp_path/'cache'))
    viewport._cached_map.cache_clear()
    def geometry(): return viewport.model_geometry(game, None, 'test.msb', {'name':'m10piece','type':0})
    before = geometry()
    assert before['meshes'][0]['water']['color'] == pytest.approx([0.2, 0.3, 0.1, 0.4])
    patch = path.with_name('MtdPatch.mtdbnd.dcx')
    patch.write_bytes(binder([0.6, 0.2, 0.1, 0.5]))
    assert geometry()['meshes'][0]['water']['color'] == pytest.approx([0.6, 0.2, 0.1, 0.5])
    patch.unlink()
    assert geometry()['meshes'][0]['water']['color'] == pytest.approx([0.2, 0.3, 0.1, 0.4])
    old_stamp = path.stat().st_mtime_ns
    path.write_bytes(binder([0.4, 0.1, 0.2, 0.6]))
    os.utime(path, ns=(old_stamp+1000000000, old_stamp+1000000000))
    assert geometry()['meshes'][0]['water']['color'] == pytest.approx([0.4, 0.1, 0.2, 0.6])
    path.write_bytes(b'broken material binder')
    broken = geometry()
    assert broken['meshes'] and 'water' not in broken['meshes'][0]
    assert any('cannot read water material' in note for note in broken['notes'])
    assert source.read_bytes() == build_flver(mtd_name=NAME)

"""DS1 icon serving: the layout parses once per game, the PNG cache
covers the catalog, and icon bytes serve immutable.

The side-by-side half of the perf fix (only the record read takes the
server lock) is timing, not behavior: no deterministic unit test can
observe it, so the commit's measured numbers (weapons 17.9s to 1.5s)
stand for that half instead."""
import io
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from drb_fixture import make_dcx, make_drb, sprite_shape
from ds1_fixture import make_archive
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import icons
from plugins.ds1.plugin import DS1Session
from plugins.ds1.server import IMMUTABLE
from plugins.ds1.store import MARKER, RELATIVE


def write_menu(menu):
    menu.mkdir(parents=True)
    (menu / 'menu.drb').write_bytes(make_drb(['Icon00', 'Icon20'], {
        'Icon': [('EquIcon_0001', sprite_shape((0, 0, 0, 0), (0, 0, 80, 90), 0)),
                 ('EquIcon_2066', sprite_shape((0, 0, 0, 0), (0, 0, 80, 90), 0))]}))
    sheet = make_dds_rgba(160, 180, [(255, 0, 0, 255)] * (160 * 180))
    (menu / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Icon00', sheet), ('Icon20', sheet)])))


@pytest.fixture
def menu_game(tmp_path):
    icons.load_icon_table.cache_clear()
    icons.icon_png.cache_clear()
    icons.label_png.cache_clear()
    write_menu(tmp_path / 'menu')
    yield tmp_path
    icons.load_icon_table.cache_clear()
    icons.icon_png.cache_clear()
    icons.label_png.cache_clear()


def test_load_icon_table_parses_once_per_game(menu_game):
    first = icons.load_icon_table(str(menu_game))
    second = icons.load_icon_table(str(menu_game))
    assert first is second
    assert icons.load_icon_table.cache_info().hits == 1


def test_icon_png_cache_covers_the_catalog(menu_game):
    assert icons.icon_png.cache_info().maxsize == 1024
    first = icons.icon_png(str(menu_game), 1)
    second = icons.icon_png(str(menu_game), 1)
    assert first is second
    assert icons.icon_png.cache_info().hits == 1


def test_icon_png_miss_does_not_poison_the_cache(menu_game):
    with pytest.raises(icons.IconError):
        icons.icon_png(str(menu_game), 999999)
    with pytest.raises(icons.IconError):
        icons.icon_png(str(menu_game), 999999)
    info = icons.icon_png.cache_info()
    assert info.hits == 0
    assert info.misses == 2


def test_icon_and_label_bytes_serve_immutable(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive(
        field_values={'EquipParamWeapon': {100: {'iconId': 1}}}))
    write_menu(game / 'menu')
    mod.mkdir()
    (mod / MARKER).touch()
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
    try:
        session.start()
        with urllib.request.urlopen(f'{session.url}/api/icon?table=EquipParamWeapon&id=100') as reply:
            assert reply.status == 200
            assert reply.headers['Cache-Control'] == IMMUTABLE
            assert reply.headers['Content-Type'] == 'image/png'
            assert len(reply.read()) > 0
        with urllib.request.urlopen(f'{session.url}/api/label?name=humanity') as reply:
            assert reply.status == 200
            assert reply.headers['Cache-Control'] == IMMUTABLE
    finally:
        session.stop()

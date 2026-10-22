"""DS1 Data Map descriptions match behavior and read plainly.

A fake store drives payload() with no session: the names sentence
names both rename gestures and nothing else, asset rows carry no
semicolons, the treasure row drops its confusing tail, and the
theme status line pluralizes.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1 import data_map


def fake_store(tmp_path, members=('ObjActParam.param',), folders=('sound',), texts=True):
    for folder in folders:
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    fakes = SimpleNamespace(renamable=lambda table: True, describable=lambda table: True,
                            entries=[]) if texts else None
    document = SimpleNamespace(members=list(members), schemas={}, params=set(),
                               texts=fakes, menu_texts=None)
    return SimpleNamespace(get=lambda: document, source=tmp_path / 'GameParam.param',
                           text_source=None, menu_source=None, game_root=tmp_path)


def rows(store, **kwargs):
    return {row['id']: row for row in data_map.payload(store, **kwargs)['rows']}


def test_name_notes_name_both_gestures_only(tmp_path):
    store = fake_store(tmp_path, members=())
    found = rows(store)
    for table in ('EquipParamGoods', 'EquipParamWeapon', 'EquipParamProtector',
                  'EquipParamAccessory', 'Magic'):
        notes = found['name:' + table]['notes']
        assert notes == ('Rename items by double-clicking the table Name cell '
                         'or the detail heading.'), notes


def test_asset_notes_carry_no_semicolons(tmp_path):
    found = rows(fake_store(tmp_path))
    assert found['assets:sound']['notes'] == (
        'Add game files to the mod to replace them. Models and textures preview. '
        'Sounds replace without a preview. Files owned by another editor change there instead.')


def test_parts_row_matches_other_asset_rows(tmp_path):
    found = rows(fake_store(tmp_path, folders=('parts',)))
    assert ';' not in found['assets:parts']['controls']
    assert ';' not in found['assets:parts']['notes']
    assert 'Items detail' in found['assets:parts']['notes']


def test_treasure_notes_drop_the_confusing_tail(tmp_path):
    found = rows(fake_store(tmp_path))
    assert found['param:ObjActParam.param']['notes'] == \
        'Edit how treasure chests and pickups behave.'


def test_theme_status_line_pluralizes(tmp_path):
    store = fake_store(tmp_path, members=(), folders=())
    theme = {'source': 'installed-game', 'title': {'ready': True},
             'font': {'recognized': 2}, 'sfx': {'recognizedBanks': 1}}
    assert rows(store, theme=theme)['theme:installed-game']['notes'] == \
        'Title art active. 2 font sources recognized. 1 sound bank recognized.'
    assert rows(store)['theme:installed-game']['notes'] == \
        ('Theme extraction falls back safely when cosmetic source assets '
         'are unavailable.')

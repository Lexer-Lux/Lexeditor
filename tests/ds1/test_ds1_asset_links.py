"""Asset links: model and icon IDs open their game files.

An equipment row's Model ID names a member of a parts binder and its Icon
ID names a cell of a menu icon sheet. Neither names a Models/Textures row
directly, so the links open the containing file (hover only: a picked file
could never write back into a numeric ID). Consumables name no model file,
so their Model ID stays a dead number.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDITOR = (ROOT / 'plugins' / 'ds1' / 'editor.js').read_text(encoding='utf-8')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from drb_fixture import make_dcx  # noqa: E402
from tpf_fixture import make_dds_rgba, make_tpf  # noqa: E402
from plugins.ds1.formats import ItemDocument, write_field  # noqa: E402
from plugins.ds1 import icons  # noqa: E402


def put(document, table, row_id, key, value):
    _row, start, data = document._row(table, row_id)
    spec = next(f['spec'] for f in document.schemas[table]['fields'] if f['spec'].key == key)
    document.plain[start:start + len(data)] = write_field(data, spec, value, '<')


def asset_links(document, table, row_id, game_root=None):
    return [entry for entry in document.read_row(table, row_id, game_root=game_root)['recordLinks']
            if entry['kind'] == 'asset']


def test_weapon_model_id_opens_its_parts_binder():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    (entry,) = asset_links(document, 'EquipParamWeapon', 100)
    assert entry['table'] == 'Asset'
    assert entry['id'] == 'parts/WP_A_0100.partsbnd.dcx'
    assert entry['tab'] == 'models'
    assert entry['field'] == 'equipModelId'
    assert entry['resolved']


def test_armor_model_id_opens_the_first_fit_binder():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamProtector', 100, 'equipModelId', 100)
    put(document, 'EquipParamProtector', 100, 'equipModelCategory', 2)
    put(document, 'EquipParamProtector', 100, 'equipModelGender', 3)
    (entry,) = asset_links(document, 'EquipParamProtector', 100)
    assert entry['id'] == 'parts/BD_M_0100.partsbnd.dcx'
    assert entry['tab'] == 'models'


def test_faces_rings_and_consumables_have_no_model_link():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamProtector', 100, 'equipModelCategory', 3)
    assert [entry for entry in asset_links(document, 'EquipParamProtector', 100)
            if entry['field'] == 'equipModelId'] == []
    assert [entry for entry in asset_links(document, 'EquipParamAccessory', 100)
            if entry['field'] == 'equipModelId'] == []
    assert [entry for entry in asset_links(document, 'EquipParamGoods', 100)
            if entry['field'] == 'modelId'] == []


def test_icon_id_opens_the_archive_holding_its_sheet(tmp_path):
    game = tmp_path / 'game'
    (game / 'menu').mkdir(parents=True)
    red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
    (game / 'menu' / 'menu_1.tpf.dcx').write_bytes(make_dcx(make_tpf([('Icon00', red)])))
    assert icons.icon_archive(game, 5) == 'menu/menu_1.tpf.dcx'
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'iconId', 5)
    entries = [entry for entry in asset_links(document, 'EquipParamWeapon', 100, game_root=game)
               if entry['field'] == 'iconId']
    assert len(entries) == 1
    assert entries[0]['id'] == 'menu/menu_1.tpf.dcx'
    assert entries[0]['tab'] == 'textures'
    assert entries[0]['resolved']


def test_icon_id_without_game_files_stays_unlinked(tmp_path):
    assert icons.icon_archive(None, 5) is None
    assert icons.icon_archive(tmp_path / 'empty', 5) is None
    assert icons.icon_archive(tmp_path / 'empty', 999999) is None
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'iconId', 5)
    assert [entry for entry in asset_links(document, 'EquipParamWeapon', 100)
            if entry['field'] == 'iconId'] == []


def test_asset_links_leave_existing_links_alone():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    found = {entry['field']: entry
             for entry in document.read_row('EquipParamWeapon', 100)['recordLinks']}
    assert found['equipModelId']['kind'] == 'asset'
    assert 'iconId' not in found
    values, display = document.row_values('EquipParamWeapon', 100)
    assert values['equipModelId'] == 100
    assert 'equipModelId' not in display


def test_asset_links_open_through_the_field_label():
    assert 'if(link.kind==="asset")return openAsset(link);' in EDITOR
    assert re.search(r"navigate\(link\.tab===\"textures\"\?\"textures\":\"models\",\"files\",`Asset:\$\{link\.id\}`\)",
                     EDITOR) is not None
    assert 'targetType:"ds1-asset"' in EDITOR
    assert EDITOR.count('entry.kind!=="asset"') == 2
    assert 'assetPreview(row,assetLink)' in EDITOR

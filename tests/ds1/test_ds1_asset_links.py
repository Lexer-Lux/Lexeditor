"""Asset links: model and icon IDs open their game files.

An equipment row's Model ID names a member of a parts binder and its Icon
ID names a cell of a menu icon sheet. Neither names a Models/Textures row
directly, so the links open the containing file. Models are also held
and chosen in the Models tab (the binder's number writes back into the
Model ID); icons are chosen from a gallery of the menu catalog.
Consumables name no model file,
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
    (entry,) = [entry for entry in asset_links(document, 'EquipParamWeapon', 100)
                if entry['field'] == 'equipModelId']
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
    (entry,) = [entry for entry in asset_links(document, 'EquipParamProtector', 100)
                if entry['field'] == 'equipModelId']
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


def test_icon_id_without_game_files_stays_unresolved(tmp_path):
    assert icons.icon_archive(None, 5) is None
    assert icons.icon_archive(tmp_path / 'empty', 5) is None
    assert icons.icon_archive(tmp_path / 'empty', 999999) is None
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'iconId', 5)
    (entry,) = [entry for entry in asset_links(document, 'EquipParamWeapon', 100)
                if entry['field'] == 'iconId']
    assert entry['resolved'] is False
    assert entry['name'] == 'Icon 5'
    assert entry['tab'] == 'textures'
    put(document, 'EquipParamWeapon', 100, 'iconId', 0)
    (empty,) = [entry for entry in asset_links(document, 'EquipParamWeapon', 100)
                if entry['field'] == 'iconId']
    assert empty['resolved'] is False
    assert empty['name'] == 'None' 


def test_asset_links_leave_existing_links_alone():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    found = {entry['field']: entry
             for entry in document.read_row('EquipParamWeapon', 100)['recordLinks']}
    assert found['equipModelId']['kind'] == 'asset'
    assert found['iconId']['resolved'] is False
    values, display = document.row_values('EquipParamWeapon', 100)
    assert values['equipModelId'] == 100
    assert 'equipModelId' not in display


def test_asset_faces_open_their_targets():
    # Lexer: a cross-tab ID is a hoverable face plus a finder button,
    # like a record link; the label stays plain text.
    assert 'if(link.kind==="asset")return openAsset(link);' in EDITOR
    assert re.search(r"navigate\(link\.tab===\"textures\"\?\"textures\":\"models\",\"files\",`Asset:\$\{link\.id\}`\)",
                     EDITOR) is not None
    assert 'function assetFaceControl(row,field,entry){' in EDITOR
    assert 'targetType:"ds1-asset"' in EDITOR
    assert 'activate:()=>openRecord(current)' in EDITOR
    assert 'assetPreview(row,current)' in EDITOR
    assert 'content:shown,targetType:"ds1-asset"' not in EDITOR


def test_asset_faces_replace_their_number_inputs():
    # The face names the file and opens it; no number sits beside it.
    assert 'function assetFaceControl(row,field,entry){' in EDITOR
    assert 'class:"ds1-asset-field"' not in EDITOR
    assert 'function assetFace(row,field,entry){' not in EDITOR
    assert '&key=${encodeURIComponent(field.key)}&v=${value}`' in EDITOR
    assert 'targetLabel:`${current.name} in ${isIcon?"Textures":"Models"}`' in EDITOR
    assert 'class:"ds1-unset-face"' in EDITOR


def test_model_entries_carry_their_picker_type():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    (entry,) = [entry for entry in asset_links(document, 'EquipParamWeapon', 100)
                if entry['field'] == 'equipModelId']
    assert entry['pick'] == 'ds1-model-EquipParamWeapon-WP_A'
    document = ItemDocument(make_archive())
    put(document, 'EquipParamProtector', 100, 'equipModelId', 100)
    put(document, 'EquipParamProtector', 100, 'equipModelCategory', 2)
    put(document, 'EquipParamProtector', 100, 'equipModelGender', 3)
    (entry,) = [entry for entry in asset_links(document, 'EquipParamProtector', 100)
                if entry['field'] == 'equipModelId']
    assert entry['pick'] == 'ds1-model-EquipParamProtector-BD'


def test_model_pick_types_match_their_binders():
    from plugins.ds1 import viewport
    weapon = viewport.model_pick_type('EquipParamWeapon', 'WP_A')
    assert viewport.stem_model_pick('parts/WP_A_0100.partsbnd.dcx') == {'type': weapon, 'value': 100}
    armor = viewport.model_pick_type('EquipParamProtector', 'BD')
    assert viewport.stem_model_pick('parts/BD_M_0100.partsbnd.dcx') == {'type': armor, 'value': 100}
    assert viewport.stem_model_pick('parts/BD_F_0100.partsbnd.dcx') == {'type': armor, 'value': 100}
    assert viewport.stem_model_pick('parts/BD_X_0100.partsbnd.dcx') is None
    assert viewport.stem_model_pick('chr/c0000.chrbnd.dcx') is None


def test_model_picker_uses_the_shared_finder():
    assert 'function modelPicker(row,field,face,entry){' in EDITOR
    assert 'thingFinderButton({class:"ds1-find-asset"' in EDITOR
    assert 'type:entry.pick' in EDITOR
    assert 'await navigate("models","files")' in EDITOR
    assert 'if(row.modelPick)LexeditorUI.decorateSearchCandidate' in EDITOR


def test_icon_gallery_lists_the_menu_catalog():
    assert 'function openIconGallery(row,field,face){' in EDITOR
    assert '/api/icon-catalog' in EDITOR
    assert '/api/icon-art?icon=' in EDITOR
    assert 'ds1-icon-choice' in EDITOR


def test_dead_model_ids_keep_their_sliders():
    # Linked IDs have faces, not numbers; an unlinked ID is a plain
    # number with its range back.
    assert 'value:field.value,min:field.minimum,max:field.maximum' in EDITOR
    assert 'const assetId=' not in EDITOR
    assert '...(fieldAssetLink?{}:{min:field.minimum,max:field.maximum})' in EDITOR

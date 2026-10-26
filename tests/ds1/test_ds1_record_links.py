"""Record links: every reference kind resolves, validates and names itself."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive  # noqa: E402
from ds1_effects_fixture import make_effects_archive  # noqa: E402
from plugins.ds1 import texts  # noqa: E402
from plugins.ds1.formats import FormatError, ItemDocument, field_link  # noqa: E402
from plugins.ds3.formats import write_field  # noqa: E402


def poke(document, table, row_id, key, value):
    """Set one field without validation, for link-resolution setups."""
    _, start, row = document._row(table, row_id)
    field = next(item['spec'] for item in document.schemas[table]['fields']
                 if item['spec'].key == key)
    document.plain[start:start + len(row)] = write_field(row, field, value, '<')


def links(document, table, row_id):
    return {entry['field']: entry
            for entry in document.read_row(table, row_id)['recordLinks']}


def test_plain_goods_and_magic_references_link():
    document = ItemDocument(make_archive())
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 101)
    poke(document, 'EquipParamGoods', 100, 'magicId', 102)
    found = links(document, 'EquipParamGoods', 100)
    assert found['replaceItemId']['kind'] == 'goods'
    assert found['replaceItemId']['table'] == 'EquipParamGoods'
    assert found['replaceItemId']['id'] == 101
    assert found['replaceItemId']['resolved']
    assert found['magicId']['kind'] == 'catalog'
    assert found['magicId']['table'] == 'Magic'
    assert found['magicId']['id'] == 102
    row = document.read_row('EquipParamGoods', 100)
    by_key = {field['key']: field for field in row['fields']}
    assert by_key['replaceItemId']['type'] == 'enum'
    assert by_key['magicId']['type'] == 'enum'
    assert set(by_key['magicId']['enum']) >= {'-1', '100', '101', '102'}
    _values, display = document.row_values('EquipParamGoods', 100)
    assert display['magicId'] == document.display_name('Magic', 102)


def test_attacks_link_their_applied_effects():
    document = ItemDocument(make_effects_archive())
    poke(document, 'AtkParam_Npc', 100, 'spEffectId0', 40)
    poke(document, 'AtkParam_Pc', 100, 'spEffectId1', 41)
    found = links(document, 'AtkParam_Npc', 100)
    assert (found['spEffectId0']['kind'], found['spEffectId0']['table']) == ('effect', 'SpEffectParam')
    assert found['spEffectId0']['id'] == 40
    assert found['spEffectId0']['resolved']
    found = links(document, 'AtkParam_Pc', 100)
    assert (found['spEffectId1']['kind'], found['spEffectId1']['table']) == ('effect', 'SpEffectParam')
    assert found['spEffectId1']['id'] == 41
    assert found['spEffectId1']['resolved']


def test_switch_decides_the_targets_table():
    document = ItemDocument(make_effects_archive())
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 2)
    poke(document, 'EquipParamAccessory', 100, 'refId', 6890)
    found = links(document, 'EquipParamAccessory', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('effect', 'SpEffectParam')
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 1)
    poke(document, 'EquipParamAccessory', 100, 'refId', 100)
    found = links(document, 'EquipParamAccessory', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('bullet', 'Bullet')
    assert found['refId']['resolved']
    poke(document, 'EquipParamAccessory', 100, 'refId', 6890)
    found = links(document, 'EquipParamAccessory', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('bullet', 'Bullet')
    assert found['refId']['resolved'] is False
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 0)
    assert 'refId' not in links(document, 'EquipParamAccessory', 100)
    row = document.read_row('EquipParamAccessory', 100)
    assert next(field for field in row['fields'] if field['key'] == 'refId')['type'] == 'number'


def test_behavior_refid_links_attacks_projectiles_and_effects():
    document = ItemDocument(make_effects_archive())
    found = links(document, 'BehaviorParam', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('attack', 'AtkParam_Npc')
    found = links(document, 'BehaviorParam', 101)
    assert (found['refId']['kind'], found['refId']['table']) == ('bullet', 'Bullet')
    assert found['refId']['id'] == 100 and found['refId']['resolved']
    poke(document, 'BehaviorParam', 101, 'refType', 2)
    poke(document, 'BehaviorParam', 101, 'refId', 6890)
    found = links(document, 'BehaviorParam', 101)
    assert (found['refId']['kind'], found['refId']['table']) == ('effect', 'SpEffectParam')


def test_projectile_attack_falls_through_to_npc():
    document = ItemDocument(make_archive())
    poke(document, 'Bullet', 100, 'atkId_Bullet', 101)
    found = links(document, 'Bullet', 100)
    assert (found['atkId_Bullet']['kind'], found['atkId_Bullet']['table']) == ('attack', 'AtkParam_Npc')


def test_shop_and_drop_links_follow_their_category():
    document = ItemDocument(make_archive())
    poke(document, 'ItemLotParam', 100, 'lotItemCategory01', 1073741824)
    poke(document, 'ItemLotParam', 100, 'lotItemId01', 101)
    found = links(document, 'ItemLotParam', 100)
    assert (found['lotItemId01']['kind'], found['lotItemId01']['table']) == ('goods', 'EquipParamGoods')
    poke(document, 'ItemLotParam', 100, 'lotItemCategory01', 0)
    found = links(document, 'ItemLotParam', 100)
    assert (found['lotItemId01']['kind'], found['lotItemId01']['table']) == ('catalog', 'EquipParamWeapon')
    poke(document, 'ShopLineupParam', 100, 'equipType', 3)
    poke(document, 'ShopLineupParam', 100, 'equipId', 102)
    found = links(document, 'ShopLineupParam', 100)
    assert (found['equipId']['kind'], found['equipId']['table']) == ('goods', 'EquipParamGoods')
    poke(document, 'ShopLineupParam', 100, 'equipType', 1)
    poke(document, 'ShopLineupParam', 100, 'equipId', 100)
    found = links(document, 'ShopLineupParam', 100)
    assert (found['equipId']['kind'], found['equipId']['table']) == ('catalog', 'EquipParamProtector')
    poke(document, 'ShopLineupParam', 100, 'equipType', 4)
    poke(document, 'ShopLineupParam', 100, 'equipId', 101)
    found = links(document, 'ShopLineupParam', 100)
    assert (found['equipId']['kind'], found['equipId']['table']) == ('catalog', 'Magic')
    assert found['equipId']['resolved']


def test_treasure_links_follow_their_qualified_type():
    document = ItemDocument(make_effects_archive())
    poke(document, 'ObjActParam', 100, 'spQualifiedType', 1)
    poke(document, 'ObjActParam', 100, 'spQualifiedId', 101)
    found = links(document, 'ObjActParam', 100)
    assert (found['spQualifiedId']['kind'], found['spQualifiedId']['table']) == ('goods', 'EquipParamGoods')
    poke(document, 'ObjActParam', 100, 'spQualifiedType', 2)
    poke(document, 'ObjActParam', 100, 'spQualifiedId', 6890)
    found = links(document, 'ObjActParam', 100)
    assert (found['spQualifiedId']['kind'], found['spQualifiedId']['table']) == ('effect', 'SpEffectParam')


def test_missing_targets_stay_visible_but_unresolved():
    document = ItemDocument(make_effects_archive())
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 400)
    found = links(document, 'EquipParamGoods', 100)
    assert found['replaceItemId']['resolved'] is False
    assert found['replaceItemId']['name'] == 'Missing item 400'
    _values, display = document.row_values('EquipParamGoods', 100)
    assert display['replaceItemId'] == 'Unknown (400)'


def test_none_values_link_unresolved():
    # None values emit an unresolved entry, so the field keeps its face
    # and finder instead of falling back to a full-table select (Lexer:
    # unset drop tables showed a dropdown of every lot in the game).
    document = ItemDocument(make_effects_archive())
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', -1)
    poke(document, 'EquipParamGoods', 100, 'magicId', 0)
    found = links(document, 'EquipParamGoods', 100)
    assert found['replaceItemId']['resolved'] is False
    assert found['replaceItemId']['name'] == 'None'
    assert found['magicId']['resolved'] is False
    assert found['magicId']['name'] == 'None'


def test_linked_writes_accept_only_existing_targets_or_none():
    document = ItemDocument(make_effects_archive())
    document.edit('EquipParamGoods', 100, 'replaceItemId', 101)
    document.edit('EquipParamGoods', 100, 'magicId', -1)
    document.edit('BehaviorParam', 100, 'refId', 102)
    with pytest.raises(FormatError):
        document.edit('EquipParamGoods', 100, 'replaceItemId', 400)
    with pytest.raises(FormatError):
        document.edit('EquipParamGoods', 100, 'magicId', 400)
    with pytest.raises(FormatError):
        document.edit('BehaviorParam', 100, 'refId', 400)
    with pytest.raises(FormatError):
        document.edit('EquipParamAccessory', 100, 'refId', 400)


def test_dialog_link_shows_the_yes_no_prompt():
    document = ItemDocument(make_archive())
    document.menu_texts = texts.MenuDocument(make_menu_archive(
        extra={'Event_text_.fmg': {10010710: 'Return to the last bonfire?'}}))
    assert document.menu_texts.event_text(10010710) == 'Return to the last bonfire?'
    assert document.menu_texts.event_text(999) is None
    poke(document, 'EquipParamGoods', 100, 'yesNoDialogMessageId', 10010710)
    dialogs = document.read_row('EquipParamGoods', 100)['dialogLinks']
    assert dialogs == [{'field': 'yesNoDialogMessageId', 'id': 10010710,
                        'text': 'Return to the last bonfire?',
                        'table': 'Event_text_.fmg', 'sub': 'fmg-event-text'}]
    poke(document, 'EquipParamGoods', 101, 'yesNoDialogMessageId', 0)
    assert document.read_row('EquipParamGoods', 101)['dialogLinks'] == [
        {'field': 'yesNoDialogMessageId', 'id': 0, 'text': '',
         'table': 'Event_text_.fmg', 'sub': 'fmg-event-text'}]
    # Spells ask too: two vanilla scrolls reuse the bonfire prompt.
    poke(document, 'Magic', 100, 'yesNoDialogMessageId', 10010710)
    assert document.read_row('Magic', 100)['dialogLinks'] == [
        {'field': 'yesNoDialogMessageId', 'id': 10010710,
         'text': 'Return to the last bonfire?',
         'table': 'Event_text_.fmg', 'sub': 'fmg-event-text'}]


def test_field_link_ignores_unlinked_tables():
    document = ItemDocument(make_archive())
    schemas = document.schemas['EquipParamAccessory']['fields']
    spec = next(item['spec'] for item in schemas if item['spec'].key == 'refId')
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 0)
    assert field_link(document, 'EquipParamAccessory', 100, spec) is None


def test_gear_upgrade_fields_link_to_stats_records():
    # materialSetId and reinforceTypeId name Stats-tab records, so they show
    # what they point to, preview it and open it (kind "stat"), never a bare ID.
    document = ItemDocument(make_archive(table_ids={
        'EquipMtrlSetParam': [1000, 1001], 'ReinforceParamWeapon': [0, 100],
        'ReinforceParamProtector': [0, 200]}))
    for table, set_id, reinforce_id, reinforce_table, noun in (
            ('EquipParamWeapon', 1000, 100, 'ReinforceParamWeapon', 'weapon upgrade table'),
            ('EquipParamProtector', 1001, 200, 'ReinforceParamProtector', 'armor upgrade table')):
        poke(document, table, 100, 'materialSetId', set_id)
        poke(document, table, 100, 'reinforceTypeId', reinforce_id)
        found = links(document, table, 100)
        assert (found['materialSetId']['kind'], found['materialSetId']['table']) == ('stat', 'EquipMtrlSetParam')
        assert found['materialSetId']['id'] == set_id and found['materialSetId']['resolved']
        assert found['materialSetId']['name'] == document.display_name('EquipMtrlSetParam', set_id)
        assert (found['reinforceTypeId']['kind'], found['reinforceTypeId']['table']) == ('stat', reinforce_table)
        assert found['reinforceTypeId']['resolved']
        assert document.link_noun('stat', reinforce_table) == noun
        by_key = {field['key']: field for field in document.read_row(table, 100)['fields']}
        assert by_key['materialSetId']['type'] == by_key['reinforceTypeId']['type'] == 'enum'
        assert str(set_id) in by_key['materialSetId']['enum']
        _values, display = document.row_values(table, 100)
        assert display['reinforceTypeId'] == document.display_name(reinforce_table, reinforce_id)
        with pytest.raises(FormatError):
            document._write(table, 100, 'materialSetId', 5555)


def test_weapon_scaling_curves_link_to_stats_curves():
    document = ItemDocument(make_archive(table_ids={'CalcCorrectGraph': [0, 5]}))
    poke(document, 'EquipParamWeapon', 100, 'correctType', 5)
    found = links(document, 'EquipParamWeapon', 100)
    assert (found['correctType']['kind'], found['correctType']['table']) == ('stat', 'CalcCorrectGraph')
    assert found['correctType']['resolved']


def test_projectile_calls_link_to_the_projectiles_tab():
    # Goods, ring and spell refId at refCategory 1 names a projectile,
    # so it shows what it points to like any other reference (kind
    # "bullet") instead of a bare number.
    document = ItemDocument(make_archive())
    for table in ('EquipParamGoods', 'EquipParamAccessory', 'Magic'):
        poke(document, table, 100, 'refCategory', 1)
        poke(document, table, 100, 'refId', 101)
        found = links(document, table, 100)
        assert (found['refId']['kind'], found['refId']['table']) == ('bullet', 'Bullet')
        assert found['refId']['id'] == 101 and found['refId']['resolved']
        assert found['refId']['name'] == document.display_name('Bullet', 101)
        assert document.link_noun('bullet', 'Bullet') == 'projectile'
        by_key = {field['key']: field for field in document.read_row(table, 100)['fields']}
        assert by_key['refId']['type'] == 'enum'
        assert '101' in by_key['refId']['enum']
        _values, display = document.row_values(table, 100)
        assert display['refId'] == document.display_name('Bullet', 101)
        with pytest.raises(FormatError):
            document._write(table, 100, 'refId', 5555)


def test_spell_calls_link_to_player_attacks():
    # Magic refId at refCategory 0 names a player attack. Behavior and
    # projectile references name the player table too but keep
    # preferring the enemy one (see the attack tests above).
    document = ItemDocument(make_archive())
    poke(document, 'Magic', 100, 'refCategory', 0)
    poke(document, 'Magic', 100, 'refId', 101)
    found = links(document, 'Magic', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('attack', 'AtkParam_Pc')
    assert found['refId']['resolved']
    assert document.link_noun('attack', 'AtkParam_Pc') == 'attack'
    by_key = {field['key']: field for field in document.read_row('Magic', 100)['fields']}
    assert by_key['refId']['type'] == 'enum'
    assert '101' in by_key['refId']['enum']
    with pytest.raises(FormatError):
        document._write('Magic', 100, 'refId', 5555)


def test_projectile_hit_id_links_to_child_projectiles():
    document = ItemDocument(make_archive())
    found = links(document, 'Bullet', 100)
    assert (found['HitBulletID']['kind'], found['HitBulletID']['table']) == ('bullet', 'Bullet')
    assert found['HitBulletID']['id'] == 101 and found['HitBulletID']['resolved']
    assert found['HitBulletID']['name'] == document.display_name('Bullet', 101)
    assert document.link_noun('bullet', 'Bullet') == 'projectile'
    by_key = {field['key']: field for field in document.read_row('Bullet', 100)['fields']}
    assert by_key['HitBulletID']['type'] == 'enum'
    assert set(by_key['HitBulletID']['enum']) >= {'-1', '100', '101', '102'}
    _values, display = document.row_values('Bullet', 100)
    assert display['HitBulletID'] == document.display_name('Bullet', 101)
    document.edit('Bullet', 100, 'HitBulletID', 102)
    with pytest.raises(FormatError):
        document.edit('Bullet', 100, 'HitBulletID', 999999)


def test_effect_behavior_links_npc_and_pc_behaviors():
    document = ItemDocument(make_effects_archive())
    poke(document, 'SpEffectParam', 6890, 'stateInfo', 142)
    poke(document, 'SpEffectParam', 6890, 'behaviorId', 101)
    found = links(document, 'SpEffectParam', 6890)
    assert (found['behaviorId']['kind'], found['behaviorId']['table']) == ('behavior', 'BehaviorParam')
    assert found['behaviorId']['id'] == 101 and found['behaviorId']['resolved']
    assert document.link_noun('behavior', 'BehaviorParam') == 'behavior'
    by_key = {field['key']: field for field in document.read_row('SpEffectParam', 6890)['fields']}
    assert by_key['behaviorId']['type'] == 'enum'
    document.edit('SpEffectParam', 6890, 'behaviorId', 100)
    with pytest.raises(FormatError):
        document.edit('SpEffectParam', 6890, 'behaviorId', 999999)
    poke(document, 'SpEffectParam', 6890, 'stateInfo', 171)
    found = links(document, 'SpEffectParam', 6890)
    assert (found['behaviorId']['kind'], found['behaviorId']['table']) == ('behavior', 'BehaviorParam_PC')
    assert found['behaviorId']['id'] == 100 and found['behaviorId']['resolved']


def test_magic_replace_id_links_to_spells():
    document = ItemDocument(make_archive())
    poke(document, 'Magic', 100, 'replaceMagicId', 101)
    found = links(document, 'Magic', 100)
    assert (found['replaceMagicId']['kind'], found['replaceMagicId']['table']) == ('catalog', 'Magic')
    assert found['replaceMagicId']['id'] == 101 and found['replaceMagicId']['resolved']
    _values, display = document.row_values('Magic', 100)
    assert display['replaceMagicId'] == document.display_name('Magic', 101)
    document.edit('Magic', 100, 'replaceMagicId', 102)
    with pytest.raises(FormatError):
        document.edit('Magic', 100, 'replaceMagicId', 999999)


def test_spell_and_treasure_dialogs_preview_event_text():
    document = ItemDocument(make_archive())
    document.menu_texts = texts.MenuDocument(make_menu_archive(
        extra={'Event_text_.fmg': {10010500: 'Kick ladder',
                                   10010710: 'Return to the last bonfire?'}}))
    poke(document, 'Magic', 100, 'yesNoDialogMessageId', 10010710)
    poke(document, 'ObjActParam', 100, 'actionEnableMsgId', 10010500)
    poke(document, 'ObjActParam', 100, 'actionFailedMsgId', 10010710)
    assert document.read_row('Magic', 100)['dialogLinks'] == [
        {'field': 'yesNoDialogMessageId', 'id': 10010710,
         'text': 'Return to the last bonfire?',
         'table': 'Event_text_.fmg', 'sub': 'fmg-event-text'}]
    assert document.read_row('ObjActParam', 100)['dialogLinks'] == [
        {'field': 'actionEnableMsgId', 'id': 10010500, 'text': 'Kick ladder',
         'table': 'Event_text_.fmg', 'sub': 'fmg-event-text'},
        {'field': 'actionFailedMsgId', 'id': 10010710,
         'text': 'Return to the last bonfire?',
         'table': 'Event_text_.fmg', 'sub': 'fmg-event-text'}]


def test_upgrade_material_summarizes_the_whole_path():
    # The base set alone is empty for most gear, which read as if upgrades
    # cost nothing. The face names every level the reinforce rows reach,
    # grouped by material, and carries the per-level table for the preview.
    document = ItemDocument(make_archive(table_ids={
        'EquipMtrlSetParam': [1000, 1001, 1002],
        'ReinforceParamWeapon': [100, 101, 102],
        'ReinforceParamProtector': [200, 201, 202]}))
    for row_id, offset in ((100, 0), (101, 1), (102, 2), (200, 0), (201, 1), (202, 2)):
        table = 'ReinforceParamWeapon' if row_id < 200 else 'ReinforceParamProtector'
        poke(document, table, row_id, 'materialSetId', offset)
    for set_id in (1000, 1001, 1002):
        for slot in ('01', '02', '03', '04', '05'):
            poke(document, 'EquipMtrlSetParam', set_id, 'materialId' + slot, -1)
            poke(document, 'EquipMtrlSetParam', set_id, 'itemNum' + slot, -1)
    poke(document, 'EquipMtrlSetParam', 1001, 'materialId01', 100)
    poke(document, 'EquipMtrlSetParam', 1001, 'itemNum01', 1)
    poke(document, 'EquipMtrlSetParam', 1002, 'materialId01', 100)
    poke(document, 'EquipMtrlSetParam', 1002, 'itemNum01', 2)
    expected = '+1-2: White Sign Soapstone 1/2'
    for table, reinforce_id in (('EquipParamWeapon', 100), ('EquipParamProtector', 200)):
        poke(document, table, 100, 'materialSetId', 1000)
        poke(document, table, 100, 'reinforceTypeId', reinforce_id)
        found = links(document, table, 100)
        assert (found['materialSetId']['kind'], found['materialSetId']['table']) == ('stat', 'EquipMtrlSetParam')
        assert found['materialSetId']['id'] == 1000 and found['materialSetId']['resolved']
        assert found['materialSetId']['name'] == expected
        path = found['materialSetId']['path']
        assert [(entry['level'], entry['setId']) for entry in path] == [(1, 1001), (2, 1002)]
        assert [entry['description'] for entry in path] == [
            'White Sign Soapstone x 1', 'White Sign Soapstone x 2']
        _values, display = document.row_values(table, 100)
        assert display['materialSetId'] == expected
        by_key = {field['key']: field for field in document.read_row(table, 100)['fields']}
        assert isinstance(by_key['materialSetId'].get('vanillaDisplay'), str)


def test_source_id_help_names_derivation():
    # Source IDs name what the blacksmith treats the level as derived from;
    # they usually name the item itself, which is not a per-level record.
    document = ItemDocument(make_archive())
    for table, key in (('EquipParamProtector', 'originEquipPro'),
                       ('EquipParamWeapon', 'originEquipWep')):
        description = next(item['spec'].description
                           for item in document.schemas[table]['fields'] if item['spec'].key == key)
        assert 'blacksmith' in description
        assert 'not separate records' in description


def test_reinforce_effect_offsets_stay_numbers():
    # Stats upgrade Effect #1-3 are NOT effect IDs: From's own PARAMDEF
    # calls them additive correction values, added to the gear's base
    # effect at that level. A stored 40 means base+40, never effect 40,
    # so no record link is emitted (linking would name the wrong effect
    # and the finder could not write a real ID into a u8 anyway).
    document = ItemDocument(make_effects_archive(table_ids={
        'ReinforceParamWeapon': [100], 'ReinforceParamProtector': [200]}))
    cases = (('ReinforceParamWeapon', 100, 'spEffectId1'),
             ('ReinforceParamWeapon', 100, 'spEffectId2'),
             ('ReinforceParamWeapon', 100, 'spEffectId3'),
             ('ReinforceParamWeapon', 100, 'residentSpEffectId1'),
             ('ReinforceParamProtector', 200, 'residentSpEffectId2'))
    for table, row_id, key in cases:
        poke(document, table, row_id, key, 40)
        assert key not in links(document, table, row_id)
        field = next(item for item in document.read_row(table, row_id)['fields']
                     if item['key'] == key)
        assert field['type'] == 'number'
        assert 'Offset' in field['label']


def test_a_link_pointing_at_none_is_emitted_unresolved():
    # Lexer: unset drop tables showed a dropdown of every lot in the game.
    # The entry is still emitted, so the field keeps its face and finder
    # instead of falling back to a full-table select.
    document = ItemDocument(make_archive())
    poke(document, 'EquipParamGoods', 100, 'magicId', -1)
    found = links(document, 'EquipParamGoods', 100)
    assert (found['magicId']['kind'], found['magicId']['table']) == ('catalog', 'Magic')
    assert found['magicId']['id'] == -1
    assert found['magicId']['resolved'] is False
    assert found['magicId']['name'] == 'None'
    poke(document, 'EquipParamGoods', 100, 'magicId', 102)
    found = links(document, 'EquipParamGoods', 100)
    assert found['magicId']['resolved'] is True

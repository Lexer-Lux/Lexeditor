"""Field icons: statuses and starting-class stats resolve to glyph kinds."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from ds1_effects_fixture import make_effects_archive  # noqa: E402
from ds1_stats_fixture import make_stats_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402


def icons(document, table, row_id):
    return {field['key']: field.get('icon')
            for field in document.read_row(table, row_id)['fields']}


def test_armor_status_resists_have_icons():
    found = icons(ItemDocument(make_archive()), 'EquipParamProtector', 100)
    assert found['resistPoison'] == 'poison'
    assert found['resistDisease'] == 'toxic'
    assert found['resistBlood'] == 'bleed'
    assert found['resistCurse'] == 'curse'


def test_weapon_and_enemy_guard_resists_have_icons():
    found = icons(ItemDocument(make_archive()), 'EquipParamWeapon', 100)
    assert found['poisonGuardResist'] == 'poison'
    assert found['diseaseGuardResist'] == 'toxic'
    assert found['bloodGuardResist'] == 'bleed'
    assert found['curseGuardResist'] == 'curse'
    npc = ItemDocument(make_archive())
    rows = npc._rows_by_id['NpcParam']
    assert rows, 'enemy fixture rows are required'
    found = icons(npc, 'NpcParam', next(iter(rows)))
    assert found['poisonGuardResist'] == 'poison'
    assert found['curseGuardResist'] == 'curse'


def test_effect_status_fields_have_icons():
    found = icons(ItemDocument(make_effects_archive()), 'SpEffectParam', 6890)
    assert found['registBlood'] == 'bleed'
    assert found['registCurse'] == 'curse'
    assert found['registBloodChangeRate'] == 'bleed'
    assert found['registCurseChangeRate'] == 'curse'
    assert found['bloodDamageRate'] == 'bleed'
    assert found['disablePoison'] == 'poison'
    assert found['disableDisease'] == 'toxic'
    assert found['disableBlood'] == 'bleed'
    assert found['disableCurse'] == 'curse'


def test_starting_class_stats_have_icons():
    found = icons(ItemDocument(make_stats_archive()), 'CharaInitParam', 2000)
    assert found['baseVit'] == 'vit'
    assert found['baseWil'] == 'wil'
    assert found['baseEnd'] == 'end'
    assert found['baseStr'] == 'str'
    assert found['baseDex'] == 'dex'
    assert found['baseMag'] == 'int'
    assert found['baseFai'] == 'faith'
    assert found['baseLuc'] == 'luc'
    assert found['baseHp'] == 'vit'
    assert found['baseMp'] == 'wil'
    assert found['baseSp'] == 'end'
    assert found['soulLv'] is None

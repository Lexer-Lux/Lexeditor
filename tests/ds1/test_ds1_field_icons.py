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
    assert found['baseWil'] == 'att'
    assert found['baseEnd'] == 'end'
    assert found['baseStr'] == 'str'
    assert found['baseDex'] == 'dex'
    assert found['baseMag'] == 'int'
    assert found['baseFai'] == 'faith'
    assert found['baseDurability'] == 'res'
    assert found['baseHp'] == 'hp'
    assert found['baseMp'] == 'mp'
    assert found['baseSp'] == 'stamina'
    assert found['soulLv'] == 'soulLv'
    assert found['soul'] == 'souls'


def test_unnamed_class_values_carry_no_icon():
    found = icons(ItemDocument(make_stats_archive()), 'CharaInitParam', 2000)
    assert found['baseLuc'] is None
    assert found['baseHeroPoint'] is None


def test_souls_fields_have_icons():
    found = icons(ItemDocument(make_stats_archive()), 'CharaInitParam', 2000)
    assert found['soul'] == 'souls'
    npc = ItemDocument(make_archive())
    rows = npc._rows_by_id['NpcParam']
    found = icons(npc, 'NpcParam', next(iter(rows)))
    assert found['getSoul'] == 'souls'
    found = icons(ItemDocument(make_effects_archive()), 'SpEffectParam', 6890)
    assert found['soulRate'] == 'souls'
    assert found['soul'] == 'souls'
    assert found['haveSoulRate'] == 'souls'
    assert found['soulStealRate'] == 'souls'
    assert found['clearSoul'] == 'souls'


def test_poise_and_humanity_fields_have_icons():
    npc = ItemDocument(make_archive())
    rows = npc._rows_by_id['NpcParam']
    found = icons(npc, 'NpcParam', next(iter(rows)))
    assert found['superArmorDurability'] == 'poise'
    assert found['superArmorRecoverCorrection'] == 'poise'
    assert found['superArmorBrakeKnockbackDist'] == 'poise'
    assert found['humanityLotId'] == 'humanity'
    assert found['staminaGuardDef'] == 'stability'
    found = icons(ItemDocument(make_effects_archive()), 'SpEffectParam', 6890)
    assert found['changeSuperArmorPoint'] == 'poise'


def test_enemy_vitals_have_stat_icons():
    npc = ItemDocument(make_archive())
    rows = npc._rows_by_id['NpcParam']
    found = icons(npc, 'NpcParam', next(iter(rows)))
    assert found['hp'] == 'hp'
    assert found['mp'] == 'mp'
    assert found['stamina'] == 'stamina'
    assert found['staminaRecoverBaseVel'] == 'stamina'


def test_magic_slot_length_has_icon():
    found = icons(ItemDocument(make_archive()), 'Magic', 100)
    assert found['slotLength'] == 'slot'


def test_item_humanity_fields_have_icons():
    found = icons(ItemDocument(make_archive()), 'EquipParamGoods', 100)
    assert found['consumeHeroPoint'] == 'humanity'
    found = icons(ItemDocument(make_archive()), 'Magic', 100)
    assert found['heroPoint'] == 'humanity'
    found = icons(ItemDocument(make_archive()), 'EquipParamWeapon', 100)
    assert found['isLuckCorrect'] == 'humanity'


def test_slash_strike_and_thrust_reuse_the_physical_shield():
    # Slash, strike and thrust have no menu cell of their own, so their
    # rows reuse the physical shield game art (Lexer: the geometric
    # slash/strike/thrust glyphs read as made-up icons next to it).
    found = icons(ItemDocument(make_archive()), 'EquipParamWeapon', 100)
    assert found['slashGuardCutRate'] == 'physicalDef'
    assert found['blowGuardCutRate'] == 'physicalDef'
    assert found['thrustGuardCutRate'] == 'physicalDef'
    found = icons(ItemDocument(make_archive()), 'EquipParamProtector', 100)
    assert found['defenseSlash'] == 'physicalDef'
    assert found['defenseBlow'] == 'physicalDef'
    assert found['defenseThrust'] == 'physicalDef'
    npc = ItemDocument(make_archive())
    found = icons(npc, 'NpcParam', next(iter(npc._rows_by_id['NpcParam'])))
    assert found['def_slash'] == 'physicalDef'
    assert found['def_blow'] == 'physicalDef'
    assert found['def_thrust'] == 'physicalDef'
    assert found['slashGuardCutRate'] == 'physicalDef'
    found = icons(ItemDocument(make_effects_archive()), 'SpEffectParam', 6890)
    assert found['slashDamageCutRate'] == 'physicalDef'
    assert found['blowDamageCutRate'] == 'physicalDef'
    assert found['thrustDamageCutRate'] == 'physicalDef'
    armored = ItemDocument(make_archive(table_ids={'ReinforceParamProtector': [200]}))
    found = icons(armored, 'ReinforceParamProtector', 200)
    assert found['slashDefRate'] == 'physicalDef'
    assert found['blowDefRate'] == 'physicalDef'
    assert found['thrustDefRate'] == 'physicalDef'
    from plugins.ds1.formats import ABSORPTION_ICONS
    assert ABSORPTION_ICONS['slashDamageCutRate'] == 'physicalDef'
    assert ABSORPTION_ICONS['blowDamageCutRate'] == 'physicalDef'
    assert ABSORPTION_ICONS['thrustDamageCutRate'] == 'physicalDef'


def test_divine_and_occult_fields_have_icons():
    found = icons(ItemDocument(make_archive()), 'EquipParamWeapon', 100)
    assert found['antSaintDamageRate'] == 'divine'
    assert found['antWeakA_DamageRate'] == 'occult'
    npc = ItemDocument(make_archive())
    rows = npc._rows_by_id['NpcParam']
    found = icons(npc, 'NpcParam', next(iter(rows)))
    assert found['isWeakSaint'] == 'divine'
    assert found['isWeakA'] == 'occult'

"""DS1 menu icons on synthetic files: DRB catalog, DLC grid, crops, labels."""
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from PIL import Image
from drb_fixture import make_dcx, make_drb, sprite_shape
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import formats, icons, menu_layout


def catalog_drb():
    return make_drb(['Icon00', 'Icon30'], {
        'Icon': [
            ('EquIcon_0001', sprite_shape((0, 0, 0, 0), (83, 1, 163, 91), 0)),
            ('EquIcon_7000', sprite_shape((0, 0, 0, 0), (1, 737, 81, 827), 1)),
            ('icon_save_0', sprite_shape((0, 0, 0, 0), (1, 555, 81, 635), 0)),
            ('EquIcon_9999', sprite_shape((0, 0, 0, 0), (1, 1, 81, 91), 9)),
        ],
    })


def test_icon_table_reads_equicon_sprites_only():
    assert icons.icon_table(catalog_drb()) == {
        1: ('Icon00', 83, 1, 163, 91),
        7000: ('Icon30', 1, 737, 81, 827),
    }


def test_icon_table_without_catalog_fails():
    with pytest.raises(icons.IconError):
        icons.icon_table(make_drb(['Icon00'], {'Other': []}))


def test_icon_rect_prefers_mapped_over_grid():
    table = {1: ('Icon00', 83, 1, 163, 91)}
    assert icons.icon_rect(1, table) == ('Icon00', 83, 1, 163, 91)


def test_icon_rect_continues_each_sheet_grid():
    # DLC overflow past the mapped icons: Stone Greataxe (198) on Icon01,
    # Bloated Head (1314) on Icon12.
    assert icons.icon_rect(198, {}) == ('Icon01', 493, 461, 573, 551)
    assert icons.icon_rect(1314, {}) == ('Icon12', 165, 369, 245, 459)
    assert icons.icon_rect(999999, {}) is None


def quadrant_dds():
    pixels = []
    for y in range(360):
        for x in range(320):
            pixels.append((255, 0, 0, 255) if x < 160 and y < 180
                          else (0, 255, 0, 255) if x >= 160 and y < 180
                          else (0, 0, 255, 255) if x < 160
                          else (255, 255, 255, 255))
    return make_dds_rgba(320, 360, pixels)


def test_crop_png_scales_layout_pixels():
    png = icons.crop_png(quadrant_dds(), (40, 45, 120, 135))
    with Image.open(io.BytesIO(png)) as image:
        image.load()
        assert image.size == (160, 180)
        shot = image.copy()
    assert shot.getpixel((0, 0)) == (255, 0, 0, 255)
    assert shot.getpixel((159, 0)) == (0, 255, 0, 255)
    assert shot.getpixel((0, 179)) == (0, 0, 255, 255)
    assert shot.getpixel((159, 179)) == (255, 255, 255, 255)


def test_crop_png_outside_texture_fails():
    with pytest.raises(icons.IconError):
        icons.crop_png(make_dds_rgba(4, 4, [(0, 0, 0, 255)] * 16), (0, 0, 80, 90))


def test_label_cells_cover_the_equipment_screen():
    assert set(icons.LABELS) == {'physical', 'magic', 'fire', 'lightning', 'critical',
                                 'physicalDef', 'magicDef', 'fireDef', 'lightningDef',
                                 'str', 'dex', 'int', 'faith', 'weight', 'durability',
                                 'poison', 'toxic', 'bleed', 'curse', 'poise',
                                 'vit', 'att', 'end', 'res', 'soulLv', 'souls', 'slot',
                                 'hp', 'stamina', 'mp', 'divine', 'occult', 'stability'}
    assert icons.LABELS['physical'] == (127, 302, 169, 344)
    assert icons.LABELS['magic'] == (126, 387, 168, 429)
    assert icons.LABELS['fire'] == (126, 345, 168, 387)
    assert icons.LABELS['lightning'] == (126, 430, 168, 472)
    assert icons.LABELS['poison'] == (83, 43, 125, 85)
    assert icons.LABELS['toxic'] == (83, 86, 125, 128)
    assert icons.LABELS['bleed'] == (83, 0, 125, 42)
    assert icons.LABELS['curse'] == (83, 129, 125, 171)
    assert icons.LABELS['poise'] == (213, 259, 255, 301)
    assert icons.LABELS['souls'] == (169, 44, 211, 86)
    assert icons.LABELS['vit'] == (83, 172, 125, 214)
    assert icons.LABELS['att'] == (83, 215, 125, 257)
    assert icons.LABELS['end'] == (83, 301, 125, 343)
    assert icons.LABELS['res'] == (82, 344, 124, 386)
    assert icons.LABELS['soulLv'] == (125, 129, 167, 171)
    assert icons.LABELS['slot'] == (125, 215, 167, 257)
    assert icons.LABELS['hp'] == (126, 172, 168, 214)
    assert icons.LABELS['stamina'] == (126, 258, 168, 300)
    assert icons.LABELS['mp'] == icons.LABELS['stamina']
    assert icons.LABELS['divine'] == (126, 473, 168, 512)
    assert icons.LABELS['occult'] == (83, 473, 125, 512)

def test_item_art_labels_name_catalog_icons():
    assert icons.ICON_LABELS == {'humanity': 2066}


def test_label_png_serves_item_art_labels(tmp_path):
    menu = tmp_path / 'menu'
    menu.mkdir()
    (menu / 'menu.drb').write_bytes(make_drb(['Icon20'], {
        'Icon': [('EquIcon_2066', sprite_shape((0, 0, 0, 0), (0, 0, 80, 90), 0))]}))
    (menu / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Icon20', quadrant_dds())])))
    with Image.open(io.BytesIO(icons.label_png(str(tmp_path), 'humanity'))) as image:
        image.load()
        assert image.size == (160, 180)
    with pytest.raises(icons.IconError):
        icons.label_png(str(tmp_path), 'missing-kind')


def test_client_label_kinds_cover_every_game_art_kind():
    editor = (Path(__file__).resolve().parents[2] / 'plugins' / 'ds1' / 'editor.js').read_text(encoding='utf-8')
    match = re.search(r'ds1LabelKinds\s*=\s*new Set\(\[(.*?)\]\)', editor, re.S)
    assert match, 'the client label-kind set moved'
    client = set(re.findall(r'"([^"]+)"', match[1]))
    assert set(icons.LABELS) | set(icons.ICON_LABELS) <= client


def test_field_icons_follow_damage_defense_and_stats():
    found = formats._FIELD_ICONS
    assert found[('NpcParam', 'def_phys')] == 'physicalDef'
    assert found[('NpcParam', 'physGuardCutRate')] == 'physicalDef'
    assert found[('NpcParam', 'def_slash')] == 'physicalDef'
    assert found[('NpcParam', 'blowGuardCutRate')] == 'physicalDef'
    assert found[('EquipParamWeapon', 'slashGuardCutRate')] == 'physicalDef'
    assert found[('EquipParamProtector', 'defenseThrust')] == 'physicalDef'
    assert found[('AtkParam_Npc', 'atkThun')] == 'lightning'
    assert found[('EquipParamWeapon', 'attackBasePhysics')] == 'physical'
    assert found[('EquipParamWeapon', 'thunGuardCutRate')] == 'lightningDef'
    assert found[('EquipParamWeapon', 'properAgility')] == 'dex'
    assert found[('EquipParamWeapon', 'correctFaith')] == 'faith'
    assert found[('EquipParamWeapon', 'weight')] == 'weight'
    assert found[('EquipParamProtector', 'defenseMagic')] == 'magicDef'
    assert found[('EquipParamProtector', 'durabilityMax')] == 'durability'
    assert found[('Magic', 'requirementIntellect')] == 'int'
    assert found[('NpcParam', 'resist_poison')] == 'poison'
    assert found[('NpcParam', 'resist_desease')] == 'toxic'
    assert found[('NpcParam', 'resist_blood')] == 'bleed'
    assert found[('NpcParam', 'resist_curse')] == 'curse'
    assert found[('NpcParam', 'isWeakSaint')] == 'divine'
    assert found[('NpcParam', 'isWeakA')] == 'occult'
    assert found[('EquipParamWeapon', 'antSaintDamageRate')] == 'divine'
    assert found[('EquipParamWeapon', 'antWeakA_DamageRate')] == 'occult'
    for table, key in (('NpcParam', 'staminaGuardDef'), ('EquipParamWeapon', 'staminaGuardDef'),
                       ('ReinforceParamWeapon', 'staminaGuardDefRate'),
                       ('SpEffectParam', 'guardStaminaCutRate'),
                       ('AtkParam_Npc', 'guardStaminaCutRate'), ('AtkParam_Pc', 'guardStaminaCutRate')):
        assert found[(table, key)] == 'stability', (table, key)
    assert icons.LABELS['stability'] == (169, 87, 211, 129)
    assert formats.ABSORPTION_ICONS['thunderDamageCutRate'] == 'lightningDef'
    assert formats.ABSORPTION_ICONS['slashDamageCutRate'] == 'physicalDef'
    assert found[('NpcParam', 'mp')] == 'mp'
    assert found[('CharaInitParam', 'baseMp')] == 'mp'
    assert found[('CharaInitParam', 'baseWil')] == 'att'
    assert found[('CharaInitParam', 'baseDurability')] == 'res'
    assert found[('CharaInitParam', 'soulLv')] == 'soulLv'


def test_mp_label_tints_the_stamina_frame_blue(tmp_path):
    # Vanilla has no MP bar frame, so the MP label reuses the
    # stamina cell with its green interior mapped to mana-mod
    # blue; the gold outline (red-dominant) stays untouched.
    menu = tmp_path / 'menu'
    menu.mkdir()
    green = make_dds_rgba(336, 608, [(10, 200, 10, 255)] * (336 * 608))
    (menu / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Menu04_2', green)])))
    with Image.open(io.BytesIO(icons.label_png(str(tmp_path), 'mp'))) as image:
        image.load()
        assert image.size == (84, 84)
        shot = image.copy()
    red, green, blue, _alpha = shot.getpixel((42, 42))
    assert blue > green and blue > red, (red, green, blue)


def test_status_icons_reuse_shared_fallback_glyphs():
    """Every icon kind renders: game art from icons.py, else a shared glyph.

    The detail field draws `field.icon` through the shared typeGlyph helper,
    which shows nothing for an unknown kind. Kinds with menu art are
    replaced by DS1 label art; the rest must name a shared glyph. Statuses
    keep their shared glyphs for installs without menu files.
    """
    framework = (Path(__file__).resolve().parents[2] / "ui" / "framework.js").read_text(encoding="utf-8")
    block = framework.split("const TYPE_GLYPHS = {", 1)[1].split("\n  };", 1)[0]
    shared = set(re.findall(r"^\s*(\w+):", block, re.M))
    assert {"poison", "toxic", "bleed", "curse"} <= shared
    assert {"poison", "toxic", "bleed", "curse"} <= set(icons.LABELS)
    art = set(icons.LABELS) | set(icons.ICON_LABELS)
    for kind in set(formats._FIELD_ICONS.values()) | set(formats.ABSORPTION_ICONS.values()):
        assert kind in art or kind in shared, kind


def test_sheet_bytes_finds_texture_across_archives(tmp_path):
    dds = quadrant_dds()
    (tmp_path / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Title', dds)])))
    (tmp_path / 'menu_3.tpf.dcx').write_bytes(make_dcx(make_tpf([('Icon00', dds)])))
    assert icons.sheet_bytes(tmp_path, 'Icon00') == dds
    with pytest.raises(icons.IconError):
        icons.sheet_bytes(tmp_path, 'Missing')


def test_label_png_serves_divine_and_occult(tmp_path):
    menu = tmp_path / 'menu'
    menu.mkdir()
    dds = make_dds_rgba(512, 1024, [(10, 20, 30, 255)] * (512 * 1024))
    (menu / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Menu04_2', dds)])))
    for kind in ('divine', 'occult'):
        with Image.open(io.BytesIO(icons.label_png(str(tmp_path), kind))) as image:
            image.load()
            assert image.size == (84, 78)

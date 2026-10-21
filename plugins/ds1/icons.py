"""DS1 menu icons: item pictures and label art, decoded from the game.

Item icons live on the Icon00-Icon50 texture sheets in menu_0/menu_3, and the
menu layout's Icon dialog maps each icon ID to its sheet and pixel rectangle
(EquIcon_0001 sits at (83,1)-(163,91) on Icon00). The layout predates the
Remaster's doubled textures, so every rectangle is scaled by two. A few DLC
icons have no entry; they continue their sheet's 12-column grid, which the
game's own numbering confirms (Stone Greataxe at 198, Bloated Head at 1314).

Damage, defense and stat labels reuse the menus' own small icons from
Menu04_2: the equipment screen's swords and shields, the armor screen's
tolerance icons (poison, toxic, bleed, curse, poise), the level-up
screen's stat and souls icons, and the attune screen's slot icon. Every
rectangle is the layout's own sprite rect, read from menu.drb.
Humanity rides the item-icon catalog (the Humanity goods picture).
The sheet's bottom row holds white, black and gold rings: divine takes
the white ring and occult the black one. Luck stays unmapped: no
invented glyphs, and no cure-item icons that would read as the item.
"""
from __future__ import annotations

import io
import re
import struct
from functools import lru_cache
from pathlib import Path

from .assets import parse_tpf
from .formats import FormatError, inflate
from .menu_layout import Drb

MENU_FILES = ('menu_0.tpf.dcx', 'menu_1.tpf.dcx', 'menu_2.tpf.dcx',
              'menu_3.tpf.dcx', 'menu_4.tpf.dcx', 'menu_5.tpf.dcx')
# The layout's rectangles are in pre-Remaster pixels; the shipped textures
# are doubled.
SCALE = 2
# A sheet's grid, measured from the Icon dialog: 12 columns, 82x92 stride,
# 80x90 cells. Used only past each sheet's last mapped icon (DLC overflow).
GRID_COLS, GRID_DX, GRID_DY, GRID_W, GRID_H = 12, 82, 92, 80, 90
SHEET_BASES = {'Icon00': 0, 'Icon01': 132, 'Icon10': 1000, 'Icon11': 1132,
               'Icon12': 1264, 'Icon20': 2000, 'Icon21': 2132, 'Icon30': 3000,
               'Icon40': 4000}
# Icon ranges each sheet owns, in icon-ID order: DLC overflow past a sheet's
# mapped icons continues its grid instead of naming a new sheet.
SHEET_RANGES = (('Icon00', 0, 132), ('Icon01', 132, 205), ('Icon10', 1000, 1132),
                ('Icon11', 1132, 1264), ('Icon12', 1264, 1316),
                ('Icon20', 2000, 2132), ('Icon21', 2132, 2221),
                ('Icon30', 3000, 3072), ('Icon40', 4000, 4043))
# Label art on Menu04_2, in layout pixels: the menus' own cells, each the
# layout's sprite rect. Tolerance icons are the armor screen's
# icon_tolerance_* nodes; vit/att/end/res/souls are the level-up
# screen's rows; slot is the attune screen's slot icon; souls doubles
# as the shop price icon (icon_price). Vanilla has no MP frame, so mp
# reuses the stamina cell and label_png tints it mana-mod blue.
LABELS = {
    'physical': (127, 302, 169, 344), 'magic': (126, 387, 168, 429),
    'fire': (126, 345, 168, 387), 'lightning': (126, 430, 168, 472),
    'critical': (213, 345, 255, 387),
    'physicalDef': (212, 1, 254, 43), 'magicDef': (212, 87, 254, 129),
    'fireDef': (212, 44, 254, 86), 'lightningDef': (213, 129, 255, 171),
    'str': (82, 387, 124, 429), 'dex': (83, 430, 125, 472),
    'int': (126, 0, 168, 42), 'faith': (83, 258, 125, 300),
    'weight': (169, 1, 211, 43), 'durability': (169, 431, 211, 473),
    'poison': (83, 43, 125, 85), 'toxic': (83, 86, 125, 128),
    'bleed': (83, 0, 125, 42), 'curse': (83, 129, 125, 171),
    'poise': (213, 259, 255, 301),
    'stability': (169, 87, 211, 129),
    'vit': (83, 172, 125, 214), 'att': (83, 215, 125, 257),
    'end': (83, 301, 125, 343), 'res': (82, 344, 124, 386),
    'hp': (126, 172, 168, 214), 'stamina': (126, 258, 168, 300),
    'mp': (126, 258, 168, 300),
    'souls': (169, 44, 211, 86), 'slot': (125, 215, 167, 257),
    'divine': (126, 473, 168, 512), 'occult': (83, 473, 125, 512),
}
# Label kinds served from the item-icon catalog instead of the label
# sheet: the Humanity goods picture (EquipParamGoods row 350).
ICON_LABELS = {'humanity': 2066}
LABEL_SHEET = 'Menu04_2'
EQUICON = re.compile(r'EquIcon_(\d+)')


class IconError(ValueError):
    """An icon was asked for that the game files cannot supply."""


def _menu(menu_dir, name):
    path = Path(menu_dir) / name
    if not path.is_file():
        raise IconError(f'The menu archive {name} is not installed')
    try:
        return inflate(path.read_bytes())
    except FormatError as error:
        raise IconError(f'The menu archive {name} cannot be read') from error


def sheet_bytes(menu_dir, sheet):
    """One named texture's DDS bytes, from whichever menu archive holds it."""
    for name in MENU_FILES:
        try:
            plain = _menu(menu_dir, name)
        except IconError:
            continue
        for texture in parse_tpf(plain):
            if texture['name'] == sheet:
                return plain[texture['offset']:texture['offset'] + texture['size']]
    raise IconError(f'The menu texture {sheet} is not installed')


@lru_cache(maxsize=8)
def _sheet_archives(game_root):
    """menu/<archive> holding each icon sheet: {'Icon00': 'menu/menu_1.tpf.dcx'}."""
    found = {}
    menu = Path(game_root) / 'menu'
    for name in MENU_FILES:
        try:
            plain = _menu(menu, name)
        except IconError:
            continue
        for texture in parse_tpf(plain):
            found.setdefault(texture['name'], f'menu/{name}')
    return found


@lru_cache(maxsize=512)
def icon_archive(game_root, icon_id):
    """The menu archive holding one icon ID's sheet, else None.

    Range-covered IDs resolve from the static sheet map; anything
    else needs the installed layout. Either way each archive is
    read once per game and cached, so row loads stay cheap.
    """
    if game_root is None:
        return None
    sheet = next((name for name, first, last in SHEET_RANGES if first <= icon_id < last), None)
    if sheet is None:
        try:
            found = load_icon_table(game_root).get(icon_id)
        except IconError:
            return None
        if found is None:
            return None
        sheet = found[0]
    try:
        return _sheet_archives(game_root).get(sheet)
    except (OSError, IconError, ValueError, struct.error):
        return None


def _texi_names(drb):
    data, count = drb.sections['TEXI']
    names = []
    for index in range(count):
        base, _path, _zero, _other = struct.unpack_from('<4i', data, index * 16)
        names.append(drb.string(base))
    return names


def icon_table(drb_plain):
    """Each mapped icon ID's sheet and layout-pixel rectangle.

    Reads the Icon dialog's EquIcon sprites: 28-byte shapes carry the
    rectangle at bytes 8-15 and the texture index at bytes 16-17.
    """
    drb = Drb(bytes(drb_plain))
    sheets = _texi_names(drb)
    try:
        nodes = drb.nodes('Icon')
    except ValueError as error:
        raise IconError('The menu layout has no icon catalog') from error
    table = {}
    for node in nodes:
        match = EQUICON.fullmatch(node.name)
        if not match:
            continue
        kind, blob = drb._blob('SHAP', 'SHPR', node.shape)
        if kind != 'Sprite' or len(blob) < 24:
            continue
        left, top, right, bottom = struct.unpack_from('<4h', blob, 8)
        index = struct.unpack_from('<h', blob, 16)[0]
        if not 0 <= index < len(sheets) or left < 0 or top < 0 or right <= left or bottom <= top:
            continue
        table[int(match[1])] = (sheets[index], left, top, right, bottom)
    if not table:
        raise IconError('The menu layout names no icons')
    return table


@lru_cache(maxsize=8)
def load_icon_table(game_root):
    """The installed game's icon catalog: layout first, then its archive.

    Parsed once per game: the parse costs a second and every icon needs it.
    """
    menu = Path(game_root) / 'menu'
    plain = menu / 'menu.drb'
    if plain.is_file():
        return icon_table(plain.read_bytes())
    return icon_table(_menu(menu, 'menu.drb.dcx'))


def icon_rect(icon_id, table):
    """One icon's sheet and layout-pixel rectangle.

    Mapped icons come from the layout; the few unmapped DLC icons continue
    their sheet's grid. Anything else has no icon.
    """
    if icon_id in table:
        return table[icon_id]
    for sheet, first, last in SHEET_RANGES:
        if first <= icon_id < last:
            base = SHEET_BASES[sheet]
            slot = icon_id - base
            left = 1 + (slot % GRID_COLS) * GRID_DX
            top = 1 + (slot // GRID_COLS) * GRID_DY
            return sheet, left, top, left + GRID_W, top + GRID_H
    return None


def crop_png(dds, rect):
    """A layout-pixel rectangle of a DDS texture as PNG bytes."""
    from PIL import Image  # noqa: PLC0415 (Pillow ships with the app's previews)
    left, top, right, bottom = (value * SCALE for value in rect)
    with Image.open(io.BytesIO(bytes(dds))) as image:
        image.load()
        if right > image.width or bottom > image.height:
            raise IconError('That icon rectangle falls outside its texture')
        out = io.BytesIO()
        image.crop((left, top, right, bottom)).save(out, format='PNG')
        return out.getvalue()


@lru_cache(maxsize=1024)
def icon_png(game_root, icon_id):
    """One icon ID's picture as PNG bytes. The cache covers the catalog."""
    table = load_icon_table(game_root)
    found = icon_rect(icon_id, table)
    if found is None:
        raise IconError(f'Icon {icon_id} has no picture in the menu files')
    sheet, *rect = found
    menu = Path(game_root) / 'menu'
    return crop_png(sheet_bytes(menu, sheet), rect)


def _mp_bar(png):
    """The stamina bar frame with its green interior mapped to blue.

    Only green-dominant pixels move; the gold outline stays."""
    from PIL import Image  # noqa: PLC0415 (Pillow ships with the app's previews)
    with Image.open(io.BytesIO(bytes(png))) as image:
        frame = image.convert('RGBA')
    pixels = frame.load()
    for y in range(frame.height):
        for x in range(frame.width):
            red, green, blue, alpha = pixels[x, y]
            if green > red and green > blue:
                pixels[x, y] = (red, blue, green, alpha)
    out = io.BytesIO()
    frame.save(out, format='PNG')
    return out.getvalue()


@lru_cache(maxsize=32)
def label_png(game_root, name):
    """One label kind's menu art as PNG bytes."""
    if name in ICON_LABELS:
        return icon_png(game_root, ICON_LABELS[name])
    if name not in LABELS:
        raise IconError(f'There is no label art for {name}')
    menu = Path(game_root) / 'menu'
    png = crop_png(sheet_bytes(menu, LABEL_SHEET), LABELS[name])
    return _mp_bar(png) if name == 'mp' else png

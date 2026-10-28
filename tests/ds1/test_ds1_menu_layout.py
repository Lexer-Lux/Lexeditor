"""DS1 menu layout: a tweak adds text and icon nodes, and nothing else moves.

Uses a synthetic DRB built here with the measured Remastered encodings
(16-byte section headers, 46-byte dynamic and 50-byte message-text shapes,
32-byte objects, 64-byte dialogs), so no game files are needed.
"""
from __future__ import annotations

import struct
import unittest
import zlib

from plugins.ds1 import formats, menu_layout


class Builder:
    def __init__(self):
        self.strings = bytearray()
        self.names = {}

    def name(self, text):
        if text not in self.names:
            self.names[text] = len(self.strings)
            self.strings += text.encode("utf-16-le") + b"\0\0"
        return self.names[text]


def text_shape(rect, *, kind, length=16, message=0, align=8, colour=b"\xff\x9c\xb9\xca"):
    prefix = struct.pack("<4h", *rect) + b"\xff\xff\xff\xff" + b"\0" * 4 + b"\x01\x01\0\0"
    prefix += struct.pack("<i", 7) + colour + b"\x07\x00" + bytes([align])
    if kind == "dynamic":
        return prefix + bytes([2]) + struct.pack("<ii", 0x1C, length) + b"\0" * 6
    return prefix + bytes([1]) + struct.pack("<iii", 0x1C, 0x4C, message) + b"\0" * 6


def pad(data):
    return bytes(data) + b"\0" * (-len(data) % 16)


# Two dialogs, so the second one's object offset must move when the first grows.
DIALOGS = {
    "data_simple_arms": [
        ("text_receive_name", "Text", text_shape((364, 262, 481, 290), kind="message", message=102125)),
        ("text_param_receive", "Text", text_shape((515, 262, 615, 290), kind="dynamic", length=64, align=9)),
        ("icon_receive", "Sprite", struct.pack("<4h", 332, 262, 360, 290) + b"\0" * 16),
    ],
    "list_armor": [
        ("text_name", "Text", text_shape((10, 10, 200, 38), kind="dynamic")),
        # The armour screen's poise icon, as measured: rectangle, then the
        # texture region and index, flags, and an untinted colour (alpha, blue, green, red).
        ("icon_tolerance_sa", "Sprite", struct.pack("<4h", 332, 111, 360, 139)
         + bytes.fromhex("ffffffff00000000aa010602fe015a020a00000100000000ffffffff")),
    ],
}


def drb(dialogs=DIALOGS):
    """Shapes and controls in vanilla order: each dialog's own, then its objects'."""
    builder = Builder()
    shapes, controls, objects, entries = bytearray(), bytearray(), bytearray(), bytearray()
    shap, ctrl = [], []

    def entry(kind, blob, control=("Static", b"\0" * 4)):
        shap.append((builder.name(kind), len(shapes)))
        shapes.extend(blob)
        ctrl.append((builder.name(control[0]), len(controls)))
        controls.extend(control[1])
        return (len(shap) - 1) * 8

    for dialog, nodes in dialogs.items():
        own = entry("Null", b"\0" * 16)
        start = len(objects)
        for row in nodes:
            name, kind, blob = row[:3]
            at = entry(kind, blob, *row[3:4])
            objects += struct.pack("<iii", builder.name(name), at, at) + b"\0" * 20
        row = struct.pack("<iii", builder.name(dialog), own, own)
        row += b"\0" * 20 + struct.pack("<ii", len(nodes), start) + struct.pack("<ihh", 0, 636, 483)
        entries += row.ljust(menu_layout.DLG_SIZE, b"\0")
    sections = {
        "STR": (builder.strings, len(builder.names)), "SHPR": (shapes, 1), "CTPR": (controls, 1),
        "SHAP": (b"".join(struct.pack("<ii", *item) for item in shap), len(shap)),
        "CTRL": (b"".join(struct.pack("<ii", *item) for item in ctrl), len(ctrl)),
        "DLGO": (objects, len(objects) // menu_layout.DLGO_SIZE),
        "DLG": (entries, len(entries) // menu_layout.DLG_SIZE),
    }
    out = bytearray(b"DRB\0" + b"\0" * 12)
    for tag in menu_layout.SECTIONS:
        data, count = sections.get(tag, (b"", 0))
        data = pad(data)
        out += tag.encode("ascii").ljust(4, b"\0") + struct.pack("<iii", len(data), count, 0) + data
    return bytes(out)


def dcx(plain):
    compressed = zlib.compress(plain, 9)
    header = (b"DCX\0" + bytes.fromhex("000100000000001800000024000000240000002c") + b"DCS\0"
              + struct.pack(">II", len(plain), len(compressed)) + b"DCP\0" + b"DFLT"
              + bytes.fromhex("00000020090000000000000000000000000000000001010000000000")[:24]
              + b"DCA\0\0\0\0\x08")
    assert len(header) == 76
    return header + compressed


STAMINA = [
    {"dialog": "data_simple_arms", "name": "text_lexeditor_stamina", "lookLike": "text_receive_name",
     "dy": 30, "length": 32},
    {"dialog": "data_simple_arms", "name": "text_param_lexeditor_stamina", "lookLike": "text_param_receive",
     "dy": 30, "length": 16},
]


def shape_order(layout):
    """Shape references in serialization order: each dialog's own, then its objects'."""
    data, count = layout.sections["DLG"]
    result = []
    for index in range(count):
        dialog = layout.string(struct.unpack_from("<i", data, index * menu_layout.DLG_SIZE)[0])
        result.append(struct.unpack_from("<i", data, index * menu_layout.DLG_SIZE + 4)[0])
        result += [node.shape for node in layout.nodes(dialog)]
    return result


def snapshot(layout):
    return {dialog: [(node.name, layout._blob("SHAP", "SHPR", node.shape), layout._blob("CTRL", "CTPR", node.control))
                     for node in layout.nodes(dialog)] for dialog in layout.dialogs()}


class LayoutTests(unittest.TestCase):
    def test_an_unchanged_layout_writes_back_exactly(self):
        plain = drb()
        self.assertEqual(menu_layout.Drb(plain).to_bytes(), plain)

    def test_new_nodes_look_like_their_row_and_hold_dynamic_text(self):
        layout = menu_layout.Drb(drb())
        before = snapshot(layout)
        for node in STAMINA:
            layout.add_text(node["dialog"], node["name"], node["lookLike"], node["dy"], node["length"])
        again = menu_layout.Drb(layout.to_bytes())
        self.assertEqual(again.to_bytes(), layout.to_bytes())
        self.assertEqual(again.text("data_simple_arms", "text_lexeditor_stamina"),
                         {"rect": [364, 292, 481, 320], "align": 8, "type": 2, "length": 32})
        self.assertEqual(again.text("data_simple_arms", "text_param_lexeditor_stamina"),
                         {"rect": [515, 292, 615, 320], "align": 9, "type": 2, "length": 16})
        # Font, colour and alignment come from the row it looks like.
        label = again._blob("SHAP", "SHPR", again.node("data_simple_arms", "text_lexeditor_stamina").shape)[1]
        source = again._blob("SHAP", "SHPR", again.node("data_simple_arms", "text_receive_name").shape)[1]
        self.assertEqual(label[8:31], source[8:31])
        # The measured dynamic-text encoding; the last blob also reaches into padding.
        self.assertEqual(label[31:46], bytes([2]) + struct.pack("<ii", 0x1C, 32) + b"\0" * 6)
        self.assertFalse(any(label[46:]))
        after = snapshot(again)
        self.assertEqual(after["data_simple_arms"][:-2], before["data_simple_arms"])
        self.assertEqual(after["list_armor"], before["list_armor"], "a later dialog keeps its objects")
        # Vanilla's order survives: every shape once, in object order, controls parallel.
        order = shape_order(again)
        self.assertEqual(order, [index * 8 for index in range(again.sections["SHAP"][1])])
        objects, count = again.sections["DLGO"]
        self.assertTrue(all(struct.unpack_from("<i", objects, index * 32 + 4)
                            == struct.unpack_from("<i", objects, index * 32 + 8) for index in range(count)))

    def test_refuses_what_it_cannot_add_safely(self):
        layout = menu_layout.Drb(drb())
        bad = (("missing_dialog", "x", "text_receive_name", 30, 16),
               ("data_simple_arms", "text_receive_name", "text_receive_name", 30, 16),
               ("data_simple_arms", "new", "icon_receive", 30, 16),
               ("data_simple_arms", "new", "nothing", 30, 16),
               ("data_simple_arms", "bad name", "text_receive_name", 30, 16),
               ("data_simple_arms", "new", "text_receive_name", 30, 0),
               ("data_simple_arms", "new", "text_receive_name", True, 16),
               ("data_simple_arms", "new", "text_receive_name", 40000, 16))
        plain = layout.to_bytes()
        for args in bad:
            with self.subTest(args=args), self.assertRaises(menu_layout.LayoutError):
                layout.add_text(*args)
        self.assertEqual(layout.to_bytes(), plain)

    def test_damaged_layouts_are_refused(self):
        plain = drb()
        for damaged in (b"DRX" + plain[3:], plain + b"\0" * 16, plain[:-16],
                        plain[:20] + struct.pack("<i", 0x7FFFFFF0) + plain[24:]):
            with self.subTest(size=len(damaged)), self.assertRaises(menu_layout.LayoutError):
                menu_layout.Drb(damaged)

    def test_compose_adds_every_tweak_and_refuses_overlaps(self):
        original = dcx(drb())
        self.assertEqual(menu_layout.compose(original, []), original)
        spec = menu_layout.validate({"version": 1, "nodes": STAMINA}, "Better Details")
        result = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [spec])))
        self.assertEqual([node.name for node in result.nodes("data_simple_arms")][-2:],
                         ["text_lexeditor_stamina", "text_param_lexeditor_stamina"])
        other = menu_layout.validate({"version": 1, "nodes": STAMINA[:1]}, "Other")
        with self.assertRaisesRegex(menu_layout.LayoutError, "Other and Better Details|Better Details and Other"):
            menu_layout.compose(original, [spec, other])

    def test_patch_descriptions_are_strict(self):
        for spec in (None, {}, {"version": 2, "nodes": STAMINA}, {"version": 1, "nodes": []},
                     {"version": 1, "nodes": STAMINA, "extra": 1},
                     {"version": 1, "nodes": [{**STAMINA[0], "colour": 1}]},
                     {"version": 1, "nodes": [{**STAMINA[0], "name": ""}]}):
            with self.subTest(spec=spec), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate(spec, "Mod")



class IconTests(unittest.TestCase):
    """Better Details' Poise DMG icon: the armour poise icon, red, in a weapon row."""

    def test_a_sprite_is_copied_placed_and_tinted_and_its_source_is_untouched(self):
        layout = menu_layout.Drb(drb())
        before = snapshot(layout)
        layout.add_sprite("data_simple_arms", "icon_lexeditor_poise", ("list_armor", "icon_tolerance_sa"),
                          "icon_receive", 30, "ffff4040")
        again = menu_layout.Drb(layout.to_bytes())
        kind, blob = again._blob("SHAP", "SHPR", again.node("data_simple_arms", "icon_lexeditor_poise").shape)
        source = dict((name, shape) for name, shape, _control in before["list_armor"])["icon_tolerance_sa"][1]
        self.assertEqual(kind, "Sprite")
        self.assertEqual(struct.unpack_from("<4h", blob), (332, 292, 360, 320))
        self.assertEqual(blob[8:32], source[8:32])  # the same picture
        self.assertEqual(blob[32:36], bytes.fromhex("ffff4040"))
        self.assertEqual(snapshot(again)["list_armor"], before["list_armor"])

    def test_a_text_node_can_be_widened_leftwards(self):
        layout = menu_layout.Drb(drb())
        layout.add_text("data_simple_arms", "text_param_wide", "text_param_receive", 30, 32, left=400)
        self.assertEqual(layout.text("data_simple_arms", "text_param_wide")["rect"], [400, 292, 615, 320])
        with self.assertRaises(menu_layout.LayoutError):
            layout.add_text("data_simple_arms", "text_param_bad", "text_param_receive", 30, 32, left=700)

    def test_bad_sprites_are_refused(self):
        layout = menu_layout.Drb(drb())
        for source, colour in ((("data_simple_arms", "text_receive_name"), "ffff4040"),
                               (("list_armor", "icon_tolerance_sa"), "red"),
                               (("list_armor", "icon_tolerance_sa"), "ffff40")):
            with self.subTest(source=source, colour=colour), self.assertRaises(menu_layout.LayoutError):
                layout.add_sprite("data_simple_arms", "icon_x", source, "icon_receive", 30, colour)

    def test_a_patch_may_mix_text_and_sprites(self):
        spec = {"version": 1, "nodes": [*STAMINA, {
            "dialog": "data_simple_arms", "name": "icon_lexeditor_poise", "sprite": ["list_armor", "icon_tolerance_sa"],
            "lookLike": "icon_receive", "dy": 30, "color": "ffff4040"}]}
        composed = menu_layout.compose(dcx(drb()), [menu_layout.validate(spec, "Details")])
        layout = menu_layout.Drb(formats.inflate(composed))
        self.assertEqual([node.name for node in layout.nodes("data_simple_arms")][-3:],
                         ["text_lexeditor_stamina", "text_param_lexeditor_stamina", "icon_lexeditor_poise"])


MOVES = [
    {"dialog": "data_simple_arms", "name": "text_receive_name", "rect": [100, 100, 217, 128]},
    {"dialog": "data_simple_arms", "name": "icon_receive", "rect": [68, 100, 96, 128]},
]


class MoveTests(unittest.TestCase):
    """The UI rework's grid: existing rows move into denser positions."""

    def test_a_move_rewrites_only_its_rectangle(self):
        layout = menu_layout.Drb(drb())
        before = layout.to_bytes()
        layout.move("data_simple_arms", "text_receive_name", [100, 100, 217, 128])
        self.assertEqual(layout.text("data_simple_arms", "text_receive_name")["rect"], [100, 100, 217, 128])
        again = menu_layout.Drb(layout.to_bytes())
        self.assertEqual(again.to_bytes(), layout.to_bytes())
        changed = [index for index, (old, new) in enumerate(zip(before, layout.to_bytes())) if old != new]
        self.assertEqual(changed, list(range(changed[0], changed[0] + 8)))
        # Style bytes survive; every other node keeps its bytes.
        moved = again._blob("SHAP", "SHPR", again.node("data_simple_arms", "text_receive_name").shape)[1]
        source = menu_layout.Drb(before)._blob(
            "SHAP", "SHPR", menu_layout.Drb(before).node("data_simple_arms", "text_receive_name").shape)[1]
        self.assertEqual(moved[8:], source[8:])
        untouched = snapshot(again)
        del untouched["data_simple_arms"][0]
        first = snapshot(menu_layout.Drb(before))
        del first["data_simple_arms"][0]
        self.assertEqual(untouched, first)

    def test_bad_moves_are_refused_and_change_nothing(self):
        layout = menu_layout.Drb(drb())
        plain = layout.to_bytes()
        bad = [("missing_dialog", "text_receive_name", [0, 0, 10, 10]),
               ("data_simple_arms", "missing_node", [0, 0, 10, 10]),
               ("data_simple_arms", "text_receive_name", (0, 0, 10, 10)),
               ("data_simple_arms", "text_receive_name", [0, 0, 10]),
               ("data_simple_arms", "text_receive_name", [0, 0, True, 10]),
               ("data_simple_arms", "text_receive_name", [0, 10, 10, 10]),
               ("data_simple_arms", "text_receive_name", [10, 0, 0, 10]),
               ("data_simple_arms", "text_receive_name", [-40000, 0, 10, 10])]
        for args in bad:
            with self.subTest(args=args), self.assertRaises(menu_layout.LayoutError):
                layout.move(*args)
        self.assertEqual(layout.to_bytes(), plain)

    def test_patch_moves_are_strict(self):
        good = menu_layout.validate({"version": 1, "moves": MOVES}, "Grid")
        self.assertEqual(good["moves"], MOVES)
        self.assertEqual(good["nodes"], [])
        mixed = menu_layout.validate({"version": 1, "nodes": STAMINA[:1], "moves": MOVES[:1]}, "Grid")
        self.assertEqual((len(mixed["nodes"]), len(mixed["moves"])), (1, 1))
        for spec in ({"version": 1}, {"version": 1, "nodes": [], "moves": []},
                     {"version": 1, "moves": [{**MOVES[0], "rect": [0, 0, 0, 10]}]},
                     {"version": 1, "moves": [{**MOVES[0], "name": ""}]},
                     {"version": 1, "moves": [{**MOVES[0], "dy": 1}]},
                     {"version": 1, "moves": "left"}):
            with self.subTest(spec=spec), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate(spec, "Grid")

    def test_compose_moves_merge_and_conflicts_refuse(self):
        original = dcx(drb())
        first = menu_layout.validate({"version": 1, "moves": MOVES[:1]}, "One")
        second = menu_layout.validate({"version": 1, "moves": MOVES[1:]}, "Two")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [first, second])))
        self.assertEqual(layout.text("data_simple_arms", "text_receive_name")["rect"], [100, 100, 217, 128])
        clash = menu_layout.validate({"version": 1, "moves": MOVES[:1]}, "Clash")
        with self.assertRaisesRegex(menu_layout.LayoutError, "both move"):
            menu_layout.compose(original, [first, clash])
        added = menu_layout.validate({"version": 1, "nodes": STAMINA[:1]}, "Adder")
        stray = menu_layout.validate({"version": 1, "moves": [
            {"dialog": "data_simple_arms", "name": "text_lexeditor_stamina", "rect": [0, 0, 10, 10]}]}, "Mover")
        with self.assertRaisesRegex(menu_layout.LayoutError, "not in the original layout"):
            menu_layout.compose(original, [added, stray])

    def test_a_move_can_set_a_text_font_step(self):
        original = dcx(drb())
        spec = menu_layout.validate({"version": 1, "moves": [{**MOVES[0], "font": 5}]}, "Font")
        self.assertEqual(spec["moves"][0]["font"], 5)
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [spec])))
        node = layout.node(MOVES[0]["dialog"], MOVES[0]["name"])
        _kind, blob = layout._blob("SHAP", "SHPR", node.shape)
        # Fixed format offsets, independent of the writer's constants: the
        # old implementation wrote the palette and its test repeated it.
        self.assertEqual(struct.unpack_from('<h', blob, 28)[0], 5)
        self.assertEqual(blob[8:28], DIALOGS['data_simple_arms'][0][2][8:28])
        self.assertEqual(blob[30:], DIALOGS['data_simple_arms'][0][2][30:])
        sprite = menu_layout.validate({"version": 1, "moves": [
            {"dialog": "data_simple_arms", "name": "icon_receive", "rect": [0, 0, 10, 10], "font": 5}]}, "Sprite")
        with self.assertRaisesRegex(menu_layout.LayoutError, "not text"):
            menu_layout.compose(original, [sprite])
        self.assertEqual(menu_layout.validate({"version": 1, "moves": [{**MOVES[0], "font": 0}]}, "Zero")
                         ["moves"][0]["font"], 0)
        for font in (-1, 13, "5", 5.0):
            with self.subTest(font=font), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate({"version": 1, "moves": [{**MOVES[0], "font": font}]}, "Bad")

    def test_scroll_text_font_preserves_its_scroll_and_binding_fields(self):
        # Remastered guide shape: the TextBase font is followed by the
        # ScrollText-specific binding and timing fields. Only the font changes.
        blob = bytes.fromhex('0000000028011900ffffffff000000000101000007000000'
                             'ff9cb9ca060004021c000000000100000000000000000000'
                             '64000000000000000000')
        original = dcx(drb({'guide': [('prompt', 'ScrollText', blob)]}))
        before = menu_layout.Drb(formats.inflate(original))
        _, blob = before._blob('SHAP', 'SHPR', before.node('guide', 'prompt').shape)
        spec = menu_layout.validate({'version': 1, 'moves': [
            {'dialog': 'guide', 'name': 'prompt', 'font': 3}]}, 'Prompt')
        result = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [spec])))
        node = result.node('guide', 'prompt')
        kind, actual = result._blob('SHAP', 'SHPR', node.shape)
        self.assertEqual(kind, 'ScrollText')
        self.assertEqual(actual[:28], blob[:28])
        self.assertEqual(actual[28:30], b'\x03\x00')
        self.assertEqual(actual[30:], blob[30:])

    def test_combined_ui_can_add_more_than_one_menus_nodes(self):
        nodes = [{"dialog": "data_simple_arms", "name": f"cell_{i}",
                  "clone": "icon_receive", "rect": [0, 0, 20, 20]} for i in range(160)]
        spec = menu_layout.validate({"version": 1, "nodes": nodes}, "Combined UI")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(dcx(drb()), [spec])))
        self.assertEqual(len(layout.nodes("data_simple_arms")), 163)
        with self.assertRaises(menu_layout.LayoutError):
            menu_layout.validate({"version": 1, "nodes": nodes * 4}, "Too many")

    def test_independent_geometry_and_color_combine_without_precedence(self):
        original = dcx(drb())
        geometry = menu_layout.validate({"version": 1, "moves": [MOVES[0]]}, "Geometry")
        tint_move = {key: MOVES[0][key] for key in ("dialog", "name")}
        tint_move["color"] = "ff40a0ff"
        tint = menu_layout.validate({"version": 1, "moves": [tint_move]}, "Color")
        forward = menu_layout.compose(original, [geometry, tint])
        self.assertEqual(forward, menu_layout.compose(original, [tint, geometry]))
        layout = menu_layout.Drb(formats.inflate(forward))
        node = layout.node(tint_move['dialog'], tint_move['name'])
        _, blob = layout._blob('SHAP', 'SHPR', node.shape)
        self.assertEqual(list(struct.unpack_from('<4h', blob)), MOVES[0]['rect'])
        self.assertEqual(blob[24:28], bytes.fromhex(tint_move['color']))
        with self.assertRaisesRegex(menu_layout.LayoutError, 'both move.*color'):
            menu_layout.compose(original, [tint, tint])

    def test_a_move_can_tint_a_text_node(self):
        original = dcx(drb())
        spec = menu_layout.validate({"version": 1, "moves": [{**MOVES[0], "color": "ff40a0ff"}]}, "Tint")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [spec])))
        node = layout.node(MOVES[0]["dialog"], MOVES[0]["name"])
        _kind, blob = layout._blob("SHAP", "SHPR", node.shape)
        self.assertEqual(blob[24:28], bytes.fromhex("ff40a0ff"))
        self.assertEqual(struct.unpack_from('<i', blob, 20)[0], 0)
        self.assertEqual(blob[8:20], DIALOGS['data_simple_arms'][0][2][8:20])
        self.assertEqual(blob[28:], DIALOGS['data_simple_arms'][0][2][28:])
        sprite = menu_layout.validate({"version": 1, "moves": [
            {"dialog": "data_simple_arms", "name": "icon_receive", "rect": [0, 0, 10, 10], "color": "ffffffff"}]},
            "Sprite")
        with self.assertRaisesRegex(menu_layout.LayoutError, "not text"):
            menu_layout.compose(original, [sprite])
        for color in ("fff", "gg000000", 255):
            with self.subTest(color=color), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate({"version": 1, "moves": [{**MOVES[0], "color": color}]}, "Bad")

    def test_optional_moves_follow_other_tweaks_nodes_or_skip(self):
        original = dcx(drb())
        added = menu_layout.validate({"version": 1, "nodes": STAMINA[:1]}, "Adder")
        mover = menu_layout.validate({"version": 1, "moves": [
            {"dialog": "data_simple_arms", "name": "text_lexeditor_stamina", "rect": [5, 6, 70, 34],
             "optional": True}]}, "Mover")
        self.assertEqual(mover["moves"][0]["optional"], True)
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [added, mover])))
        self.assertEqual(layout.text("data_simple_arms", "text_lexeditor_stamina")["rect"], [5, 6, 70, 34])
        # Without the adder the optional move is skipped, and nothing changes.
        self.assertEqual(menu_layout.compose(original, [mover]), original)
        for bad in ({**MOVES[0], "optional": False}, {**MOVES[0], "optional": 1}):
            with self.subTest(move=bad), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate({"version": 1, "moves": [bad]}, "Bad")


CLONES = {
    "data_simple_arms": [
        ("text_receive_name", "Text", text_shape((364, 262, 481, 290), kind="message", message=102125)),
        ("icon_receive", "Sprite", struct.pack("<4h", 332, 262, 360, 290) + b"\0" * 16),
        ("cursor_receive", "Null", b"\0" * 8),
        ("short_receive", "Null", b"\0" * 4),
        ("live_receive", "Null", b"\0" * 8, ("Button", b"\1" * 4)),
    ],
    "later_dialog": [
        ("text_name", "Text", text_shape((10, 10, 200, 38), kind="dynamic")),
    ],
}


class CloneTests(unittest.TestCase):
    """The UI rework's grid: new cells copy their row's own cell."""

    def test_a_clone_copies_bytes_new_name_and_rect(self):
        layout = menu_layout.Drb(drb(CLONES))
        before = snapshot(layout)
        layout.add_clone("data_simple_arms", "cursor_new", "cursor_receive", [100, 100, 200, 130])
        layout.add_clone("data_simple_arms", "icon_new", "icon_receive", [68, 100, 96, 128])
        again = menu_layout.Drb(layout.to_bytes())
        self.assertEqual(again.to_bytes(), layout.to_bytes())
        kind, blob = again._blob("SHAP", "SHPR", again.node("data_simple_arms", "cursor_new").shape)
        self.assertEqual((kind, struct.unpack_from("<4h", blob)), ("Null", (100, 100, 200, 130)))
        _kind, control = again._blob("CTRL", "CTPR", again.node("data_simple_arms", "cursor_new").control)
        self.assertEqual(control[:4], b"\0" * 4)
        self.assertFalse(any(control[4:]))
        kind, blob = again._blob("SHAP", "SHPR", again.node("data_simple_arms", "icon_new").shape)
        source = dict((name, shape) for name, shape, _control in before["data_simple_arms"])["icon_receive"][1]
        self.assertEqual(kind, "Sprite")
        self.assertEqual(struct.unpack_from("<4h", blob), (68, 100, 96, 128))
        self.assertEqual(blob[8:len(source)], source[8:])
        self.assertFalse(any(blob[len(source):]))
        after = snapshot(again)
        self.assertEqual(after["data_simple_arms"][:-2], before["data_simple_arms"])
        self.assertEqual(after["later_dialog"], before["later_dialog"], "a later dialog keeps its objects")
        order = shape_order(again)
        self.assertEqual(order, [index * 8 for index in range(again.sections["SHAP"][1])])

    def test_bad_clones_are_refused_and_change_nothing(self):
        layout = menu_layout.Drb(drb(CLONES))
        plain = layout.to_bytes()
        bad = [("missing_dialog", "new", "cursor_receive", [0, 0, 10, 10]),
               ("data_simple_arms", "cursor_receive", "cursor_receive", [0, 0, 10, 10]),
               ("data_simple_arms", "new", "missing_node", [0, 0, 10, 10]),
               ("data_simple_arms", "bad name", "cursor_receive", [0, 0, 10, 10]),
               ("data_simple_arms", "new", "cursor_receive", (0, 0, 10, 10)),
               ("data_simple_arms", "new", "cursor_receive", [0, 0, 10]),
               ("data_simple_arms", "new", "cursor_receive", [0, 0, True, 10]),
               ("data_simple_arms", "new", "cursor_receive", [0, 10, 10, 10]),
               ("data_simple_arms", "new", "cursor_receive", [10, 0, 0, 10]),
               ("data_simple_arms", "new", "cursor_receive", [-40000, 0, 10, 10]),
               ("data_simple_arms", "new", "short_receive", [0, 0, 10, 10]),
               ("data_simple_arms", "new", "live_receive", [0, 0, 10, 10])]
        for args in bad:
            with self.subTest(args=args), self.assertRaises(menu_layout.LayoutError):
                layout.add_clone(*args)
        self.assertEqual(layout.to_bytes(), plain)

    def test_patch_clones_are_strict(self):
        good = {"dialog": "data_simple_arms", "name": "cursor_new", "clone": "cursor_receive",
                "rect": [100, 100, 200, 130]}
        validated = menu_layout.validate({"version": 1, "nodes": [good]}, "Grid")
        self.assertEqual(validated["nodes"], [good])
        for spec in ({"version": 1, "nodes": [{**good, "rect": [0, 0, 0, 10]}]},
                     {"version": 1, "nodes": [{**good, "clone": ""}]},
                     {"version": 1, "nodes": [{**good, "lookLike": "cursor_receive"}]},
                     {"version": 1, "nodes": [{**good, "rect": "left"}]}):
            with self.subTest(spec=spec), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate(spec, "Grid")

    def test_a_text_clone_can_point_at_another_menu_text_entry(self):
        node = {"dialog": "data_simple_arms", "name": "text_mp", "clone": "text_receive_name",
                "rect": [364, 292, 481, 320], "textId": 201081}
        spec = menu_layout.validate({"version": 1, "nodes": [node]}, "Mod")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(dcx(drb()), [spec])))
        _kind, blob = layout._blob("SHAP", "SHPR", layout.node("data_simple_arms", "text_mp").shape)
        _kind, source = layout._blob("SHAP", "SHPR", layout.node("data_simple_arms", "text_receive_name").shape)
        self.assertEqual(struct.unpack_from("<i", blob, 40)[0], 201081)
        self.assertEqual(struct.unpack_from("<i", source, 40)[0], 102125, "the source keeps its text")
        # Dynamic text has no entry to repoint, and the id is a number.
        with self.assertRaises(menu_layout.LayoutError):
            menu_layout.Drb(drb()).add_clone("data_simple_arms", "x", "text_param_receive",
                                             [515, 292, 615, 320], 5)
        for bad in (-1, "201081", True):
            with self.subTest(bad=bad), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate({"version": 1, "nodes": [{**node, "textId": bad}]}, "Mod")

    def test_compose_merges_clones_and_refuses_overlaps(self):
        original = dcx(drb(CLONES))
        first = menu_layout.validate({"version": 1, "nodes": [
            {"dialog": "data_simple_arms", "name": "cursor_new", "clone": "cursor_receive",
             "rect": [100, 100, 200, 130]}]}, "One")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(original, [first])))
        self.assertIn("cursor_new", [node.name for node in layout.nodes("data_simple_arms")])
        clash = menu_layout.validate({"version": 1, "nodes": [
            {"dialog": "data_simple_arms", "name": "cursor_new", "clone": "cursor_receive",
             "rect": [0, 0, 10, 10]}]}, "Clash")
        with self.assertRaisesRegex(menu_layout.LayoutError, "both add"):
            menu_layout.compose(original, [first, clash])


class OffsetTests(unittest.TestCase):
    """Warp tabs: nodes move horizontally (dx) and sprites resize (size)."""

    def test_dx_moves_text_and_sprites_horizontally(self):
        layout = menu_layout.Drb(drb())
        layout.add_text("data_simple_arms", "text_moved", "text_receive_name", 30, 16, dx=100)
        self.assertEqual(layout.text("data_simple_arms", "text_moved")["rect"], [464, 292, 581, 320])
        layout.add_sprite("data_simple_arms", "icon_moved", ("list_armor", "icon_tolerance_sa"),
                          "icon_receive", 30, "ffffffff", dx=-20)
        kind, blob = layout._blob("SHAP", "SHPR", layout.node("data_simple_arms", "icon_moved").shape)
        self.assertEqual(struct.unpack_from("<4h", blob), (312, 292, 340, 320))

    def test_text_can_borrow_a_node_from_another_dialog(self):
        layout = menu_layout.Drb(drb())
        source = layout._blob("SHAP", "SHPR", layout.node("list_armor", "text_name").shape)[1]
        layout.add_text("data_simple_arms", "text_borrowed", "text_name", 100, 24, dx=300,
                        source_dialog="list_armor")
        again = menu_layout.Drb(layout.to_bytes())
        self.assertEqual(again.text("data_simple_arms", "text_borrowed"),
                         {"rect": [310, 110, 500, 138], "align": source[30], "type": 2, "length": 24})
        self.assertEqual([node.name for node in again.nodes("list_armor")],
                         [node.name for node in menu_layout.Drb(drb()).nodes("list_armor")])
        spec = menu_layout.validate({"version": 1, "nodes": [
            {"dialog": "data_simple_arms", "name": "text_borrowed", "from": "list_armor",
             "lookLike": "text_name", "dy": 100, "dx": 300, "length": 24}]}, "Borrow")
        composed = menu_layout.compose(dcx(drb()), [spec])
        self.assertEqual(menu_layout.Drb(formats.inflate(composed)).text(
            "data_simple_arms", "text_borrowed")["rect"], [310, 110, 500, 138])
        with self.assertRaises(menu_layout.LayoutError):
            layout.add_text("data_simple_arms", "text_missing", "text_name", 0, 8)
        with self.assertRaises(menu_layout.LayoutError):
            menu_layout.validate({"version": 1, "nodes": [{**spec["nodes"][0], "from": ""}]}, "Bad")

    def test_before_inserts_under_a_named_node(self):
        layout = menu_layout.Drb(drb())
        before = snapshot(layout)
        first = layout.nodes("data_simple_arms")[0].name
        layout.add_sprite("data_simple_arms", "icon_under", ("list_armor", "icon_tolerance_sa"),
                          "icon_receive", 0, "ffffffff", before=first)
        layout.add_clone("data_simple_arms", "text_cloned", "text_name", [1, 2, 30, 40],
                         source_dialog="list_armor", before="icon_receive")
        again = menu_layout.Drb(layout.to_bytes())
        names = [node.name for node in again.nodes("data_simple_arms")]
        self.assertEqual(names[0], "icon_under")
        self.assertEqual(names.index("text_cloned") + 1, names.index("icon_receive"))
        self.assertEqual(again.text("data_simple_arms", "text_cloned")["rect"], [1, 2, 30, 40])
        # Every other node keeps its own shape and control; serialization order holds.
        after = snapshot(again)
        for dialog, rows in before.items():
            kept = [row for row in after[dialog] if row[0] not in ("icon_under", "text_cloned")]
            self.assertEqual(kept, rows, dialog)
        self.assertEqual(shape_order(again), sorted(shape_order(again)))
        spec = menu_layout.validate({"version": 1, "nodes": [
            {"dialog": "data_simple_arms", "name": "icon_under", "sprite": ["list_armor", "icon_tolerance_sa"],
             "lookLike": "icon_receive", "dy": 0, "color": "ffffffff", "before": first},
            {"dialog": "data_simple_arms", "name": "text_cloned", "clone": "text_name", "from": "list_armor",
             "rect": [1, 2, 30, 40], "before": "icon_receive"}]}, "Under")
        composed = menu_layout.Drb(formats.inflate(menu_layout.compose(dcx(drb()), [spec])))
        self.assertEqual([node.name for node in composed.nodes("data_simple_arms")], names)
        with self.assertRaises(menu_layout.LayoutError):
            layout.add_sprite("data_simple_arms", "icon_lost", ("list_armor", "icon_tolerance_sa"),
                              "icon_receive", 0, "ffffffff", before="missing")
        with self.assertRaises(menu_layout.LayoutError):
            menu_layout.validate({"version": 1, "nodes": [{**spec["nodes"][0], "textId": 5}]}, "Bad")

    def test_left_applies_after_dx(self):
        layout = menu_layout.Drb(drb())
        layout.add_text("data_simple_arms", "text_wide", "text_param_receive", 30, 32, left=400, dx=50)
        self.assertEqual(layout.text("data_simple_arms", "text_wide")["rect"], [400, 292, 665, 320])
        with self.assertRaises(menu_layout.LayoutError):
            layout.add_text("data_simple_arms", "text_bad", "text_param_receive", 30, 32,
                            left=700, dx=50)

    def test_sprite_size_sets_dimensions(self):
        layout = menu_layout.Drb(drb())
        layout.add_sprite("data_simple_arms", "icon_panel", ("list_armor", "icon_tolerance_sa"),
                          "icon_receive", -11, "ff2a2622", dx=422, size=[620, 349])
        kind, blob = layout._blob("SHAP", "SHPR", layout.node("data_simple_arms", "icon_panel").shape)
        self.assertEqual(kind, "Sprite")
        self.assertEqual(struct.unpack_from("<4h", blob), (754, 251, 1374, 600))
        self.assertEqual(blob[32:36], bytes.fromhex("ff2a2622"))

    def test_bad_offsets_and_sizes_are_refused(self):
        layout = menu_layout.Drb(drb())
        plain = layout.to_bytes()
        with self.assertRaises(menu_layout.LayoutError):
            layout.add_text("data_simple_arms", "t1", "text_receive_name", 30, 16, dx=True)
        with self.assertRaises(menu_layout.LayoutError):
            layout.add_text("data_simple_arms", "t2", "text_receive_name", 30, 16, dx=40000)
        for size in ([0, 10], [10], [10, 5000], [True, 10], "wide"):
            with self.subTest(size=size), self.assertRaises(menu_layout.LayoutError):
                layout.add_sprite("data_simple_arms", "icon_x", ("list_armor", "icon_tolerance_sa"),
                                  "icon_receive", 30, "ffffffff", size=size)
        # Rectangles must stay inside the layout's int16 range.
        blob = struct.pack("<4h", 32000, 0, 32100, 100) + b"\0" * 24
        with self.assertRaises(menu_layout.LayoutError):
            menu_layout.Drb._moved(blob, 0, 800)
        with self.assertRaises(menu_layout.LayoutError):
            menu_layout.Drb._moved(blob, 0, 0, size=[4000, 4000])
        self.assertEqual(layout.to_bytes(), plain)

    def test_patch_descriptions_accept_dx_and_size(self):
        nodes = [{**STAMINA[0], "dx": 100},
                 {**STAMINA[1], "dx": -50, "left": 400},
                 {"dialog": "data_simple_arms", "name": "icon_panel",
                  "sprite": ["list_armor", "icon_tolerance_sa"], "lookLike": "icon_receive",
                  "dy": 30, "color": "ffffffff", "dx": 10, "size": [620, 349]}]
        spec = menu_layout.validate({"version": 1, "nodes": nodes}, "Mod")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(dcx(drb()), [spec])))
        self.assertEqual(layout.text("data_simple_arms", "text_lexeditor_stamina")["rect"],
                         [464, 292, 581, 320])
        kind, blob = layout._blob("SHAP", "SHPR", layout.node("data_simple_arms", "icon_panel").shape)
        self.assertEqual(struct.unpack_from("<4h", blob), (342, 292, 962, 641))
        for bad in ({**STAMINA[0], "dx": "1"},
                    {"dialog": "data_simple_arms", "name": "icon_x",
                     "sprite": ["list_armor", "icon_tolerance_sa"], "lookLike": "icon_receive",
                     "dy": 30, "color": "ffffffff", "size": [10]},
                    {"dialog": "data_simple_arms", "name": "text_x", "lookLike": "text_receive_name",
                     "dy": 30, "length": 16, "size": [10, 10]}):
            with self.subTest(bad=bad), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate({"version": 1, "nodes": [bad]}, "Mod")

    def test_sprite_uv_repoints_the_texture_region(self):
        node = {"dialog": "data_simple_arms", "name": "icon_strip",
                "sprite": ["list_armor", "icon_tolerance_sa"], "lookLike": "icon_receive",
                "dy": 30, "color": "ffffffff", "uv": [6, 516, 138, 540]}
        spec = menu_layout.validate({"version": 1, "nodes": [node]}, "Mod")
        layout = menu_layout.Drb(formats.inflate(menu_layout.compose(dcx(drb()), [spec])))
        _kind, blob = layout._blob("SHAP", "SHPR", layout.node("data_simple_arms", "icon_strip").shape)
        _kind, source = layout._blob("SHAP", "SHPR", layout.node("list_armor", "icon_tolerance_sa").shape)
        self.assertEqual(struct.unpack_from("<4h", blob, 16), (6, 516, 138, 540))
        self.assertEqual(blob[24:32], source[24:32])
        for uv in ([6, 516, 138], [138, 516, 6, 540], [6, -1, 138, 540], [6, 516, 138, True], "blue"):
            with self.subTest(uv=uv), self.assertRaises(menu_layout.LayoutError):
                menu_layout.validate({"version": 1, "nodes": [{**node, "uv": uv}]}, "Mod")


if __name__ == "__main__":
    unittest.main()

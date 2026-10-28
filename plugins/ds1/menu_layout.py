"""DS1 menu layout (DRB): add text, sprite or clone nodes to a dialog, or move existing nodes.

Dark Souls Remastered draws its menus from menu/menu.drb.dcx, a DCX holding
one DRB. A DRB is a run of tagged sections, each a 16-byte header (tag,
length, count, 0) and its data: UTF-16 names in STR, shape and control
blobs in SHPR and CTPR, one 8-byte (type name, blob) entry per object in SHAP
and CTRL, 32-byte dialog objects in DLGO and 64-byte dialogs in DLG. A dialog
owns a contiguous run of DLGO entries (count and offset at fields 8 and 9).

Every reference is a byte offset into its own section, so appending to STR,
SHPR and CTPR moves nothing. Vanilla keeps SHAP and CTRL in object order and
parallel, so a new entry is inserted after its dialog's last one and the
objects' and dialogs' references after it shift. Inserting DLGO entries moves
the entries after them; only DLG points into DLGO, so those offsets shift.

A tweak mod asks for a node as `look like` one text node (its rectangle,
moved by `dy` and `dx`, its font, colour and alignment) and `hold` dynamic
text of a
given length, empty until the game or a hook sets it; `left` widens the
rectangle leftwards, and `from` borrows the text node from another dialog
when the target has none to look like. Any new node may name `before`, an
existing node of its dialog it goes in front of in the dialog's order, so
it is drawn under that node instead of over everything. It can also copy an existing sprite (an icon) from any
dialog, placed like a node moved by `dy` and `dx`, tinted, and optionally
resized with `size` [width, height]: a sprite's last four
bytes (32-35) are its colour: alpha, blue, green, red (vanilla icons are
ffffffff, untinted; "blackout" overlays dc282828; the boss HP bar 960080ff is
red). Read as alpha-red-green-blue, a red tint came out blue in the game. A tweak can also move an existing
node: rewrite its rectangle in place, which shifts no offsets. It can also clone an existing node: the same shape and
control bytes under a new name and rectangle, so a grid gains cells of the
same kind its rows already use. A clone shares its source's content reference,
which suits grid cells but not strips whose reference varies per index
(data_tab); those are not cloned. It cannot remove a node or restyle one
beyond its rectangle.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from . import formats
from core.mod_builds import ModBuildError

RELATIVE = Path("menu/menu.drb.dcx")
# The Steam Remastered build that exe_patches supports; measured from the install.
VANILLA_SIZE = 194527
VANILLA_SHA256 = "b7c52d98de6fc85d95cde97c3611c43fca91e2992ac5e589a99a91c03310cb96"
SECTIONS = ("STR", "TEXI", "SHPR", "CTPR", "ANIP", "INTP", "SCDP", "SHAP", "CTRL",
            "ANIK", "ANIO", "ANIM", "SCDK", "SCDO", "SCDL", "DLGO", "DLG", "END")
DLGO_SIZE = 32
DLG_SIZE = 64
TEXT_PREFIX = 31  # rectangle, scaling, palette, colour, font size, alignment
DYNAMIC = 2
TEXT_ID_AT = 40  # a menu-text node's entry in the menu text archive
FONT_AT = 28  # int16 font-size index, after the Remastered scaling header
MIN_FONT, MAX_FONT = 0, 12
TEXT_PALETTE = 20  # int32; zero selects the custom colour
TEXT_COLOUR = 24  # four bytes: alpha, blue, green, red
# Moves rewrite bytes in place and never grow the file: a menu rework that
# re-lays several detail panels (each ~50-80 nodes) fits.
MAX_MOVES = 1024
MAX_NODES = 512  # one combined UI mod can extend several menus


def _color(value, owner: str) -> bytes:
    """Eight hex digits (alpha, blue, green, red) as four bytes."""
    if not isinstance(value, str) or len(value) != 8:
        raise LayoutError(f"{owner}: a colour is eight hex digits: alpha, blue, green, red")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise LayoutError(f"{owner}: a colour is eight hex digits: alpha, blue, green, red") from error
TEXT_TAIL = 0x1C
MAX_TEXT = 256
MAX_SIZE = 4096
SPRITE_SIZE = 36
SPRITE_COLOUR = 32  # four bytes: alpha, blue, green, red


class LayoutError(ModBuildError):
    """The layout or a requested change is not acceptable; nothing changed."""

    def __init__(self, message: str, *, folders=()):
        super().__init__(folders, message)


@dataclass
class Node:
    name: str
    offset: int  # into DLGO
    shape: int  # into SHAP
    control: int  # into CTRL


class Drb:
    """One DRB, kept as its sections so an unchanged file writes back exactly."""

    def __init__(self, plain: bytes):
        if plain[:16] != b"DRB\0" + b"\0" * 12:
            raise LayoutError("Expected a DS1 menu layout (DRB)")
        self.sections: dict[str, list] = {}
        at = 16
        for tag in SECTIONS:
            if plain[at:at + 4] != tag.encode("ascii").ljust(4, b"\0"):
                raise LayoutError(f"Expected the {tag} section at {at:#x}")
            length, count, zero = struct.unpack_from("<iii", plain, at + 4)
            if length < 0 or count < 0 or zero or length % 16 or at + 16 + length > len(plain):
                raise LayoutError(f"The {tag} section header is invalid")
            self.sections[tag] = [bytearray(plain[at + 16:at + 16 + length]), count]
            at += 16 + length
        if at != len(plain):
            raise LayoutError("The layout has data after its END section")
        for tag, size in (("SHAP", 8), ("CTRL", 8), ("DLGO", DLGO_SIZE), ("DLG", DLG_SIZE)):
            data, count = self.sections[tag]
            if count * size > len(data):
                raise LayoutError(f"The {tag} section is shorter than its count")

    def to_bytes(self) -> bytes:
        out = bytearray(b"DRB\0" + b"\0" * 12)
        for tag in SECTIONS:
            data, count = self.sections[tag]
            out += tag.encode("ascii").ljust(4, b"\0") + struct.pack("<iii", len(data), count, 0) + data
        return bytes(out)

    # --- reading ------------------------------------------------------------

    def string(self, offset: int) -> str:
        data = self.sections["STR"][0]
        if not 0 <= offset < len(data) or offset % 2:
            raise LayoutError(f"Name offset {offset:#x} is outside the name table")
        end = offset
        while end + 1 < len(data) and data[end:end + 2] != b"\0\0":
            end += 2
        return data[offset:end].decode("utf-16-le")

    def _entry(self, tag: str, offset: int) -> tuple[int, int]:
        data, count = self.sections[tag]
        if offset % 8 or not 0 <= offset < count * 8:
            raise LayoutError(f"{tag} offset {offset:#x} is invalid")
        return struct.unpack_from("<ii", data, offset)

    def _span(self, tag: str, blob_tag: str, offset: int) -> tuple[str, int, int]:
        """One shape or control's type name and data span, bounded by the next blob."""
        kind, start = self._entry(tag, offset)
        data, count = self.sections[tag]
        starts = sorted({struct.unpack_from("<ii", data, index * 8)[1] for index in range(count)})
        blobs = self.sections[blob_tag][0]
        later = [item for item in starts if item > start]
        end = later[0] if later else len(blobs)
        if not 0 <= start < end <= len(blobs):
            raise LayoutError(f"{tag} data at {start:#x} is outside {blob_tag}")
        return self.string(kind), start, end

    def _blob(self, tag: str, blob_tag: str, offset: int) -> tuple[str, bytes]:
        """The type name and data of one shape or control, bounded by the next blob."""
        kind, start, end = self._span(tag, blob_tag, offset)
        return kind, bytes(self.sections[blob_tag][0][start:end])

    def dialogs(self) -> dict[str, int]:
        """Dialog names mapped to their DLG offsets."""
        data, count = self.sections["DLG"]
        result = {}
        for index in range(count):
            result.setdefault(self.string(struct.unpack_from("<i", data, index * DLG_SIZE)[0]), index * DLG_SIZE)
        return result

    def _dialog(self, name: str) -> int:
        offset = self.dialogs().get(name)
        if offset is None:
            raise LayoutError(f"The menu layout has no dialog {name}")
        return offset

    def nodes(self, dialog: str) -> list[Node]:
        data = self.sections["DLG"][0]
        objects, total = self.sections["DLGO"]
        count, start = struct.unpack_from("<ii", data, self._dialog(dialog) + 32)
        if count < 0 or start % DLGO_SIZE or start + count * DLGO_SIZE > total * DLGO_SIZE:
            raise LayoutError(f"{dialog} lists objects outside DLGO")
        result = []
        for index in range(count):
            at = start + index * DLGO_SIZE
            name, shape, control = struct.unpack_from("<iii", objects, at)
            result.append(Node(self.string(name), at, shape, control))
        return result

    def node(self, dialog: str, name: str) -> Node:
        found = [item for item in self.nodes(dialog) if item.name == name]
        if len(found) != 1:
            raise LayoutError(f"{dialog} has {len(found) or 'no'} node{'s' if found else ''} named {name}")
        return found[0]

    def text(self, dialog: str, name: str) -> dict:
        """A text node's rectangle, alignment and kind, as tests and callers check it."""
        item = self.node(dialog, name)
        kind, blob = self._blob("SHAP", "SHPR", item.shape)
        if kind != "Text" or len(blob) <= TEXT_PREFIX:
            raise LayoutError(f"{dialog}/{name} is a {kind}, not text")
        left, top, right, bottom = struct.unpack_from("<4h", blob)
        result = {"rect": [left, top, right, bottom], "align": blob[30], "type": blob[31]}
        if blob[31] == DYNAMIC:
            result["length"] = struct.unpack_from("<i", blob, 36)[0]
        return result

    # --- changing -----------------------------------------------------------

    def _append(self, tag: str, data: bytes) -> int:
        section = self.sections[tag]
        offset = len(section[0])
        section[0] += data
        return offset

    def _pad(self, tag: str) -> None:
        data = self.sections[tag][0]
        data += b"\0" * (-len(data) % 16)

    def _trim(self, tag: str, used: int) -> None:
        """Drop the padding after a section's used bytes before appending to it."""
        data = self.sections[tag][0]
        if any(data[used:]):
            raise LayoutError(f"The {tag} section has data after its last entry")
        del data[used:]

    def _check_name(self, dialog: str, name: str) -> None:
        if not name or len(name) > 64 or not name.isascii() or not name.replace("_", "").isalnum():
            raise LayoutError(f"{name!r} is not a usable node name")
        if any(item.name == name for item in self.nodes(dialog)):
            raise LayoutError(f"{dialog} already has a node named {name}")

    def _check_new(self, dialog: str, name: str, dy: int, dx: int = 0) -> None:
        self._check_name(dialog, name)
        if type(dy) is not int or not -2000 <= dy <= 2000:
            raise LayoutError("dy must be a whole number of layout units")
        if type(dx) is not int or not -2000 <= dx <= 2000:
            raise LayoutError("dx must be a whole number of layout units")

    @staticmethod
    def _moved(blob: bytes, dy: int, dx: int = 0, left: int | None = None,
               size: list | tuple | None = None) -> bytearray:
        """A shape with its rectangle moved by (dx, dy), its left edge set, resized."""
        shape = bytearray(blob)
        x0, top, right, bottom = struct.unpack_from("<4h", shape)
        x0, right, top, bottom = x0 + dx, right + dx, top + dy, bottom + dy
        if not (-32768 <= x0 and right <= 32767 and -32768 <= top and bottom <= 32767):
            raise LayoutError("The moved rectangle is outside the layout's range")
        if left is not None:
            if type(left) is not int or not -32768 <= left < right:
                raise LayoutError("left must be a whole number left of the rectangle's right edge")
            x0 = left
        if size is not None:
            try:
                width, height = size
            except (TypeError, ValueError):
                width = height = 0
            if (type(width) is not int or type(height) is not int
                    or not 1 <= width <= MAX_SIZE or not 1 <= height <= MAX_SIZE):
                raise LayoutError(f"size must be two whole numbers between 1 and {MAX_SIZE}")
            right, bottom = x0 + width, top + height
            if not (right <= 32767 and bottom <= 32767):
                raise LayoutError("The sized rectangle is outside the layout's range")
        struct.pack_into("<4h", shape, 0, x0, top, right, bottom)
        return shape

    def _static_control(self, dialog: str, node: Node) -> tuple[int, bytes]:
        control_kind, control = self._blob("CTRL", "CTPR", node.control)
        if control_kind != "Static":
            raise LayoutError(f"{dialog}/{node.name} has a {control_kind} control, not a static one")
        return struct.unpack_from("<i", self.sections["CTRL"][0], node.control)[0], control

    def add_sprite(self, dialog: str, name: str, sprite: tuple[str, str], place_like: str, dy: int,
                   color: str, dx: int = 0, size: list | tuple | None = None,
                   uv: list | tuple | None = None, before: str | None = None) -> None:
        """A copy of an existing sprite, placed like `place_like` moved by (dx, dy), tinted.

        `uv` [left, top, right, bottom] repoints the copy at another region of
        the same texture (bytes 16-23), such as an atlas strip no vanilla node
        draws."""
        self._check_new(dialog, name, dy, dx)
        if not isinstance(color, str) or len(color) != 8:
            raise LayoutError("A sprite colour is eight hex digits: alpha, blue, green, red")
        try:
            tint = bytes.fromhex(color)
        except ValueError as error:
            raise LayoutError("A sprite colour is eight hex digits: alpha, blue, green, red") from error
        source_dialog, source_name = sprite
        source = self.node(source_dialog, source_name)
        kind, blob = self._blob("SHAP", "SHPR", source.shape)
        # The last shape in SHPR reads with the section's padding after it.
        if kind != "Sprite" or len(blob) < SPRITE_SIZE or any(blob[SPRITE_SIZE:]):
            raise LayoutError(f"{source_dialog}/{source_name} is a {kind}, not an icon sprite")
        place = self.node(dialog, place_like)
        _kind, place_blob = self._blob("SHAP", "SHPR", place.shape)
        shape = bytearray(blob[:SPRITE_SIZE])
        shape[0:8] = self._moved(place_blob[:8], dy, dx, size=size)[0:8]
        shape[SPRITE_COLOUR:SPRITE_SIZE] = tint
        if uv is not None:
            struct.pack_into("<4h", shape, 16, *uv)
        sprite_type = struct.unpack_from("<i", self.sections["SHAP"][0], source.shape)[0]
        self._insert(dialog, name, sprite_type, bytes(shape), *self._static_control(dialog, place),
                     before=before)

    def add_text(self, dialog: str, name: str, look_like: str, dy: int, length: int,
                 left: int | None = None, dx: int = 0, source_dialog: str | None = None,
                 before: str | None = None) -> None:
        """Dynamic text styled and placed like `look_like`, moved by (dx, dy).

        `source_dialog` names another dialog holding `look_like`, for a
        dialog with no text node of its own (the start menu's R00-00); the
        offsets then move the source's rectangle into this dialog's space."""
        self._check_new(dialog, name, dy, dx)
        if type(length) is not int or not 1 <= length <= MAX_TEXT:
            raise LayoutError(f"Text length must be between 1 and {MAX_TEXT}")
        source_dialog = dialog if source_dialog is None else source_dialog
        source = self.node(source_dialog, look_like)
        kind, blob = self._blob("SHAP", "SHPR", source.shape)
        if kind != "Text" or len(blob) <= TEXT_PREFIX:
            raise LayoutError(f"{source_dialog}/{look_like} is a {kind}, not text")
        static_type, control = self._static_control(source_dialog, source)
        shape = self._moved(blob[:TEXT_PREFIX], dy, dx, left)
        shape += bytes([DYNAMIC]) + struct.pack("<ii", TEXT_TAIL, length) + b"\0" * 6
        text_type = struct.unpack_from("<i", self.sections["SHAP"][0], source.shape)[0]
        self._insert(dialog, name, text_type, bytes(shape), static_type, control, before=before)

    def add_clone(self, dialog: str, name: str, source: str, rect, text_id: int | None = None,
                  source_dialog: str | None = None, before: str | None = None) -> None:
        """A copy of an existing node under a new name and rectangle.

        The clone shares its source's shape and control bytes (and so a
        Dialog node's content reference): a grid cell copies its row's own
        cell, never a strip whose reference varies per index. `text_id`
        repoints a menu-text node (not dynamic text) at another menu text
        entry (shape bytes 40-43), such as a template whose <?tag?> the
        game fills. `source_dialog` takes the source from another dialog,
        as text's does.
        """
        self._check_name(dialog, name)
        if not isinstance(rect, list) or len(rect) != 4 or any(type(value) is not int for value in rect):
            raise LayoutError(f"{dialog}/{name} needs a rectangle of four whole numbers")
        left, top, right, bottom = rect
        if not all(-32768 <= value <= 32767 for value in rect) or not left < right or not top < bottom:
            raise LayoutError(f"{dialog}/{name} has a rectangle outside the layout's range")
        source_dialog = dialog if source_dialog is None else source_dialog
        node = self.node(source_dialog, source)
        _kind, blob = self._blob("SHAP", "SHPR", node.shape)
        if len(blob) < 8:
            raise LayoutError(f"{source_dialog}/{source} has no rectangle to place")
        shape = bytearray(blob)
        struct.pack_into("<4h", shape, 0, left, top, right, bottom)
        if text_id is not None:
            if _kind != "Text" or len(blob) < TEXT_ID_AT + 4 or blob[31] == DYNAMIC:
                raise LayoutError(f"{source_dialog}/{source} is not a menu-text node, so it has no text id")
            struct.pack_into("<i", shape, TEXT_ID_AT, text_id)
        shape_type = struct.unpack_from("<i", self.sections["SHAP"][0], node.shape)[0]
        control_kind, control = self._blob("CTRL", "CTPR", node.control)
        if control_kind == "DmeCtrlScrollText":
            # Native key guides use a ScrollTextDummy: one zero int32 and
            # no object references. Preserve that control when cloning a guide.
            if len(control) < 4 or any(control):
                raise LayoutError(f"{dialog}/{name}: unsupported scrolling-text control data")
            control_type = struct.unpack_from("<i", self.sections["CTRL"][0], node.control)[0]
            cloned_control = (control_type, b"\0" * 4)
        else:
            cloned_control = self._static_control(source_dialog, node)
        self._insert(dialog, name, shape_type, bytes(shape), *cloned_control, before=before)

    def move(self, dialog: str, name: str, rect) -> None:
        """Reposition and resize an existing node, rewriting its rectangle in place."""
        if not isinstance(rect, list) or len(rect) != 4 or any(type(value) is not int for value in rect):
            raise LayoutError(f"{dialog}/{name} needs a rectangle of four whole numbers")
        left, top, right, bottom = rect
        if not all(-32768 <= value <= 32767 for value in rect) or not left < right or not top < bottom:
            raise LayoutError(f"{dialog}/{name} has a rectangle outside the layout's range")
        item = self.node(dialog, name)
        _kind, start, end = self._span("SHAP", "SHPR", item.shape)
        if end - start < 8:
            raise LayoutError(f"{dialog}/{name} has no rectangle to move")
        struct.pack_into("<4h", self.sections["SHPR"][0], start, left, top, right, bottom)

    def set_font(self, dialog: str, name: str, size: int) -> None:
        """Set the int16 font-size index without changing the colour palette.

        Remastered adds eight scaling bytes after the rectangle. Its text
        payload starts at 16: blend flags, line spacing, palette, custom
        colour, then the font index at 28 (SoulsFormats DRB.TextBase).
        """
        if type(size) is not int or not MIN_FONT <= size <= MAX_FONT:
            raise LayoutError(f"{dialog}/{name}: font is a text style id from {MIN_FONT} to {MAX_FONT}")
        item = self.node(dialog, name)
        kind, start, end = self._span("SHAP", "SHPR", item.shape)
        if kind not in ("Text", "ScrollText") or end - start <= TEXT_PREFIX:
            raise LayoutError(f"{dialog}/{name} is a {kind}, not text, so it has no font")
        struct.pack_into("<h", self.sections["SHPR"][0], start + FONT_AT, size)

    def set_text_color(self, dialog: str, name: str, color: str) -> None:
        """Set a text node's custom colour at bytes 24-27, selecting palette 0.

        Vanilla's parchment text is ff9cb9ca and the invasion message's red is
        ff0000ff. The game may still recolour text it fills at run time (the
        stat comparison's blue and red).
        """
        tint = _color(color, f"{dialog}/{name}")
        item = self.node(dialog, name)
        kind, start, end = self._span("SHAP", "SHPR", item.shape)
        if kind != "Text" or end - start <= TEXT_PREFIX:
            raise LayoutError(f"{dialog}/{name} is a {kind}, not text, so it has no text colour")
        struct.pack_into("<i", self.sections["SHPR"][0], start + TEXT_PALETTE, 0)
        self.sections["SHPR"][0][start + TEXT_COLOUR:start + TEXT_COLOUR + 4] = tint

    def _insert(self, dialog: str, name: str, shape_type: int, shape: bytes,
                control_type: int, control: bytes, before: str | None = None) -> None:
        """One new object at the end of a dialog, or just before its node
        `before` (drawn under it): its name, shape and control."""
        if self.sections["SHAP"][1] != self.sections["CTRL"][1]:
            raise LayoutError("Shape and control tables are not parallel")
        dlg = self._dialog(dialog)
        count, start = struct.unpack_from("<ii", self.sections["DLG"][0], dlg + 32)
        anchor = None if before is None else self.node(dialog, before)
        if anchor is not None and anchor.shape != anchor.control:
            raise LayoutError(f"{dialog}/{before} has unpaired shape and control entries")

        # Names, shape and control data go at the ends of their sections.
        self._trim("STR", self._strings_end())
        name_offset = self._append("STR", name.encode("utf-16-le") + b"\0\0")
        self.sections["STR"][1] += 1
        self._pad("STR")
        self._trim("SHPR", self._blobs_end("SHAP", "SHPR"))
        shape_data = self._append("SHPR", bytes(shape))
        self._pad("SHPR")
        self._trim("CTPR", self._blobs_end("CTRL", "CTPR"))
        control_data = self._append("CTPR", control)
        self._pad("CTPR")
        # Vanilla stores shapes and controls in object order (a dialog's own,
        # then each of its objects'), so the new entry goes right after the
        # dialog's last one and every later reference moves along.
        owned = [struct.unpack_from("<i", self.sections["DLG"][0], dlg + 4)[0]]
        owned += [item.shape for item in self.nodes(dialog)]
        entry = max(owned) + 8 if anchor is None else anchor.shape
        self._shift_entries(entry)
        for tag, kind, data in (("SHAP", shape_type, shape_data), ("CTRL", control_type, control_data)):
            self._trim(tag, self.sections[tag][1] * 8)
            self.sections[tag][0][entry:entry] = struct.pack("<ii", kind, data)
            self.sections[tag][1] += 1
            self._pad(tag)
        shape_entry = control_entry = entry

        # The object goes after the dialog's last one; later dialogs move along.
        objects = self.sections["DLGO"]
        self._trim("DLGO", objects[1] * DLGO_SIZE)
        insert = start + count * DLGO_SIZE if anchor is None else anchor.offset
        objects[0][insert:insert] = struct.pack("<iii", name_offset, shape_entry, control_entry) + b"\0" * 20
        objects[1] += 1
        self._pad("DLGO")
        dialogs = self.sections["DLG"][0]
        for index in range(self.sections["DLG"][1]):
            at = index * DLG_SIZE
            other_count, other_start = struct.unpack_from("<ii", dialogs, at + 32)
            if at == dlg:
                struct.pack_into("<i", dialogs, at + 32, count + 1)
            elif other_start >= insert and (other_count or other_start > insert):
                struct.pack_into("<i", dialogs, at + 36, other_start + DLGO_SIZE)

    def _shift_entries(self, at: int) -> None:
        """Move every object's and dialog's shape and control reference at or after `at`."""
        for tag, size in (("DLGO", DLGO_SIZE), ("DLG", DLG_SIZE)):
            data, count = self.sections[tag]
            for index in range(count):
                for field in (4, 8):
                    value = struct.unpack_from("<i", data, index * size + field)[0]
                    if value >= at:
                        struct.pack_into("<i", data, index * size + field, value + 8)

    def _strings_end(self) -> int:
        data, count = self.sections["STR"]
        at = 0
        for _ in range(count):
            while data[at:at + 2] != b"\0\0":
                at += 2
                if at >= len(data):
                    raise LayoutError("The name table is shorter than its count")
            at += 2
        return at

    def _blobs_end(self, tag: str, blob_tag: str) -> int:
        data, count = self.sections[tag]
        if not count:
            return 0
        last = max(struct.unpack_from("<ii", data, index * 8)[1] for index in range(count))
        offset = next(index * 8 for index in range(count) if struct.unpack_from("<ii", data, index * 8)[1] == last)
        return last + len(self._blob(tag, blob_tag, offset)[1])


# --- tweak patch descriptions ------------------------------------------------

def validate(spec: object, owner: str) -> dict:
    """A tweak's layout/<id>.json: {"version": 1, "nodes": [...], "moves": [...]}."""
    if not isinstance(spec, dict) or spec.get("version") != 1 or set(spec) - {"version", "nodes", "moves"}:
        raise LayoutError(f"{owner}: a layout patch needs version 1 with nodes and moves")
    nodes = spec.get("nodes", [])
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise LayoutError(f"{owner}: list between 0 and {MAX_NODES} layout nodes")
    moves = spec.get("moves", [])
    # Moves rewrite eight bytes each and never grow the file, so a grid
    # rework touching every row of several lists fits.
    if not isinstance(moves, list) or len(moves) > MAX_MOVES:
        raise LayoutError(f"{owner}: list between 0 and {MAX_MOVES} layout moves")
    if not nodes and not moves:
        raise LayoutError(f"{owner}: a layout patch needs nodes or moves")
    text = {"dialog", "name", "lookLike", "dy", "length"}
    sprite = {"dialog", "name", "sprite", "lookLike", "dy", "color"}
    clone = {"dialog", "name", "clone", "rect"}
    optional = {"text": {"left", "dx", "from", "before"},
                "sprite": {"dx", "size", "uv", "before"},
                "clone": {"textId", "from", "before"}}
    clean = []
    for node in nodes:
        keys = set(node) if isinstance(node, dict) else set()
        kind = "sprite" if "sprite" in keys else "clone" if "clone" in keys else "text"
        required = {"text": text, "sprite": sprite, "clone": clone}[kind]
        if not required <= keys or keys - required - optional[kind]:
            raise LayoutError(f"{owner}: a layout node is text "
                              f"({', '.join(sorted(text))}, optional left, dx, from and before), "
                              f"a sprite ({', '.join(sorted(sprite))}, optional dx, size, uv and before) "
                              f"or a clone ({', '.join(sorted(clone))}, optional textId, from and before)")
        if not all(isinstance(node[key], str) and node[key] for key in ("dialog", "name")):
            raise LayoutError(f"{owner}: layout node names must be text")
        for key in ("lookLike", "clone", "from", "before"):
            if key in node and not (isinstance(node[key], str) and node[key]):
                raise LayoutError(f"{owner}: layout node names must be text")
        if "rect" in node:
            rect = node["rect"]
            if (not isinstance(rect, list) or len(rect) != 4 or any(type(value) is not int for value in rect)
                    or not all(-32768 <= value <= 32767 for value in rect)
                    or not rect[0] < rect[2] or not rect[1] < rect[3]):
                raise LayoutError(f"{owner}: a layout clone rect is four whole numbers, left < right, top < bottom")
        if "sprite" in node and (not isinstance(node["sprite"], list) or len(node["sprite"]) != 2
                                 or not all(isinstance(part, str) and part for part in node["sprite"])):
            raise LayoutError(f"{owner}: a sprite names its source as [dialog, node]")
        if "size" in node and (not isinstance(node["size"], list) or len(node["size"]) != 2
                               or not all(type(part) is int for part in node["size"])):
            raise LayoutError(f"{owner}: a sprite size is [width, height] as whole numbers")
        if "uv" in node:
            uv = node["uv"]
            if (not isinstance(uv, list) or len(uv) != 4 or any(type(value) is not int for value in uv)
                    or not all(0 <= value <= 32767 for value in uv) or not uv[0] < uv[2] or not uv[1] < uv[3]):
                raise LayoutError(f"{owner}: a sprite uv is four whole texture coordinates, "
                                  "left < right, top < bottom")
        if "textId" in node and (type(node["textId"]) is not int or not 0 <= node["textId"] <= 0x7FFFFFFF):
            raise LayoutError(f"{owner}: a clone textId is a menu text entry number")
        if "dx" in node and type(node["dx"]) is not int:
            raise LayoutError(f"{owner}: dx must be a whole number of layout units")
        clean.append(dict(node))
    clean_moves = []
    for move in moves:
        keys = set(move) if isinstance(move, dict) else set()
        if (not {"dialog", "name"} <= keys or not keys & {"rect", "font", "color"}
                or keys - {"dialog", "name", "rect", "optional", "font", "color"}):
            raise LayoutError(f"{owner}: a layout move names dialog, name and at least one of rect, font, color")
        if "optional" in move and move["optional"] is not True:
            raise LayoutError(f"{owner}: a layout move's optional is true or absent")
        if "font" in move and (type(move["font"]) is not int or not MIN_FONT <= move["font"] <= MAX_FONT):
            raise LayoutError(f"{owner}: a layout move's font is a text style id from {MIN_FONT} to {MAX_FONT}")
        if "color" in move:
            _color(move["color"], f"{owner}: a layout move")
        if not all(isinstance(move[key], str) and move[key] for key in ("dialog", "name")):
            raise LayoutError(f"{owner}: layout move names must be text")
        rect = move.get("rect")
        if "rect" in move and (not isinstance(rect, list) or len(rect) != 4 or any(type(value) is not int for value in rect)
                or not all(-32768 <= value <= 32767 for value in rect)
                or not rect[0] < rect[2] or not rect[1] < rect[3]):
            raise LayoutError(f"{owner}: a layout move rect is four whole numbers, left < right, top < bottom")
        entry = {"dialog": move["dialog"], "name": move["name"]}
        if "rect" in move:
            entry["rect"] = list(rect)
        if move.get("optional"):
            entry["optional"] = True
        for key in ("font", "color"):
            if key in move:
                entry[key] = move[key]
        clean_moves.append(entry)
    return {"owner": owner, "nodes": clean, "moves": clean_moves}


def compose(original: bytes, specs: list[dict]) -> bytes:
    """Every enabled tweak's nodes and moves applied to the original layout."""
    nodes = [(spec["owner"], spec.get("folder"), node) for spec in specs for node in spec["nodes"]]
    moves = [(spec["owner"], spec.get("folder"), move) for spec in specs for move in spec["moves"]]
    if not nodes and not moves:
        return original
    layout = Drb(formats.inflate(original))
    placed = {(dialog, node.name) for dialog in layout.dialogs() for node in layout.nodes(dialog)}
    seen = {}
    for owner, folder, node in nodes:
        key = (node["dialog"], node["name"])
        if key in seen:
            previous, previous_folder = seen[key]
            folders = [folder, previous_folder] if folder and previous_folder else []
            raise LayoutError(f"{owner} and {previous} both add {node['dialog']}/{node['name']}", folders=folders)
        seen[key] = (owner, folder)
        try:
            if "clone" in node:
                layout.add_clone(node["dialog"], node["name"], node["clone"], node["rect"],
                                 node.get("textId"), node.get("from"), node.get("before"))
            elif "sprite" in node:
                layout.add_sprite(node["dialog"], node["name"], tuple(node["sprite"]), node["lookLike"],
                                  node["dy"], node["color"], node.get("dx", 0), node.get("size"),
                                  node.get("uv"), node.get("before"))
            else:
                layout.add_text(node["dialog"], node["name"], node["lookLike"], node["dy"], node["length"],
                                node.get("left"), node.get("dx", 0), node.get("from"), node.get("before"))
        except LayoutError as error:
            raise LayoutError(f"{owner}: {error}", folders=[folder] if folder else []) from error
    moved = {}
    for owner, folder, move in moves:
        key = (move["dialog"], move["name"])
        if move.get("optional"):
            # An optional move may re-place a node another tweak added (a
            # panel rework moving a stats mod's rows) and is skipped when
            # neither the original layout nor any tweak has that node.
            if key not in placed and key not in seen:
                continue
        elif key not in placed:
            raise LayoutError(f"{owner} moves {move['dialog']}/{move['name']}, which is not in the original layout",
                              folders=[folder] if folder else [])
        for field in ("rect", "font", "color"):
            if field not in move:
                continue
            property_key = (*key, field)
            if property_key in moved:
                previous, previous_folder = moved[property_key]
                folders = [folder, previous_folder] if folder and previous_folder else []
                raise LayoutError(f"{owner} and {previous} both move {move['dialog']}/{move['name']} ({field})",
                                  folders=folders)
            moved[property_key] = (owner, folder)
        try:
            if "rect" in move:
                layout.move(move["dialog"], move["name"], move["rect"])
            if "font" in move:
                layout.set_font(move["dialog"], move["name"], move["font"])
            if "color" in move:
                layout.set_text_color(move["dialog"], move["name"], move["color"])
        except LayoutError as error:
            raise LayoutError(f"{owner}: {error}", folders=[folder] if folder else []) from error
    return formats.deflate(original, layout.to_bytes())


def is_vanilla(data: bytes) -> bool:
    return len(data) == VANILLA_SIZE and hashlib.sha256(data).hexdigest() == VANILLA_SHA256

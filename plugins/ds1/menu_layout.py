"""DS1 menu layout (DRB): add text nodes to a dialog, nothing else.

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
moved by `dy`, its font, colour and alignment) and `hold` dynamic text of a
given length, empty until the game or a hook sets it; `left` widens the
rectangle leftwards. It can also copy an existing sprite (an icon) from any
dialog, placed like a node moved by `dy` and tinted: a sprite's last four
bytes (32-35) are its colour, alpha first (vanilla icons are ffffffff, untinted;
"blackout" overlays dc282828). It cannot remove, move or restyle an
existing node.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from . import formats

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
TEXT_TAIL = 0x1C
MAX_TEXT = 256
SPRITE_SIZE = 36
SPRITE_COLOUR = 32  # four bytes, alpha first


class LayoutError(ValueError):
    """The layout or a requested change is not acceptable; nothing changed."""


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

    def _blob(self, tag: str, blob_tag: str, offset: int) -> tuple[str, bytes]:
        """The type name and data of one shape or control, bounded by the next blob."""
        kind, start = self._entry(tag, offset)
        data, count = self.sections[tag]
        starts = sorted({struct.unpack_from("<ii", data, index * 8)[1] for index in range(count)})
        blobs = self.sections[blob_tag][0]
        later = [item for item in starts if item > start]
        end = later[0] if later else len(blobs)
        if not 0 <= start < end <= len(blobs):
            raise LayoutError(f"{tag} data at {start:#x} is outside {blob_tag}")
        return self.string(kind), bytes(blobs[start:end])

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

    def _check_new(self, dialog: str, name: str, dy: int) -> None:
        if not name or len(name) > 64 or not name.isascii() or not name.replace("_", "").isalnum():
            raise LayoutError(f"{name!r} is not a usable node name")
        if any(item.name == name for item in self.nodes(dialog)):
            raise LayoutError(f"{dialog} already has a node named {name}")
        if type(dy) is not int or not -2000 <= dy <= 2000:
            raise LayoutError("dy must be a whole number of layout units")

    @staticmethod
    def _moved(blob: bytes, dy: int, left: int | None = None) -> bytearray:
        """A shape with its rectangle moved down by dy (and its left edge set)."""
        shape = bytearray(blob)
        x0, top, right, bottom = struct.unpack_from("<4h", shape)
        if left is not None:
            if type(left) is not int or not -32768 <= left < right:
                raise LayoutError("left must be a whole number left of the rectangle's right edge")
            x0 = left
        if not (-32768 <= top + dy and bottom + dy <= 32767):
            raise LayoutError("The moved rectangle is outside the layout's range")
        struct.pack_into("<4h", shape, 0, x0, top + dy, right, bottom + dy)
        return shape

    def _static_control(self, dialog: str, node: Node) -> tuple[int, bytes]:
        control_kind, control = self._blob("CTRL", "CTPR", node.control)
        if control_kind != "Static":
            raise LayoutError(f"{dialog}/{node.name} has a {control_kind} control, not a static one")
        return struct.unpack_from("<i", self.sections["CTRL"][0], node.control)[0], control

    def add_sprite(self, dialog: str, name: str, sprite: tuple[str, str], place_like: str, dy: int,
                   color: str) -> None:
        """A copy of an existing sprite, placed like `place_like` moved by dy, tinted."""
        self._check_new(dialog, name, dy)
        if not isinstance(color, str) or len(color) != 8:
            raise LayoutError("A sprite colour is eight hex digits, alpha first")
        try:
            tint = bytes.fromhex(color)
        except ValueError as error:
            raise LayoutError("A sprite colour is eight hex digits, alpha first") from error
        source_dialog, source_name = sprite
        source = self.node(source_dialog, source_name)
        kind, blob = self._blob("SHAP", "SHPR", source.shape)
        # The last shape in SHPR reads with the section's padding after it.
        if kind != "Sprite" or len(blob) < SPRITE_SIZE or any(blob[SPRITE_SIZE:]):
            raise LayoutError(f"{source_dialog}/{source_name} is a {kind}, not an icon sprite")
        place = self.node(dialog, place_like)
        _kind, place_blob = self._blob("SHAP", "SHPR", place.shape)
        shape = bytearray(blob[:SPRITE_SIZE])
        shape[0:8] = self._moved(place_blob[:8], dy)[0:8]
        shape[SPRITE_COLOUR:SPRITE_SIZE] = tint
        sprite_type = struct.unpack_from("<i", self.sections["SHAP"][0], source.shape)[0]
        self._insert(dialog, name, sprite_type, bytes(shape), *self._static_control(dialog, place))

    def add_text(self, dialog: str, name: str, look_like: str, dy: int, length: int,
                 left: int | None = None) -> None:
        self._check_new(dialog, name, dy)
        if type(length) is not int or not 1 <= length <= MAX_TEXT:
            raise LayoutError(f"Text length must be between 1 and {MAX_TEXT}")
        source = self.node(dialog, look_like)
        kind, blob = self._blob("SHAP", "SHPR", source.shape)
        if kind != "Text" or len(blob) <= TEXT_PREFIX:
            raise LayoutError(f"{dialog}/{look_like} is a {kind}, not text")
        static_type, control = self._static_control(dialog, source)
        shape = self._moved(blob[:TEXT_PREFIX], dy, left)
        shape += bytes([DYNAMIC]) + struct.pack("<ii", TEXT_TAIL, length) + b"\0" * 6
        text_type = struct.unpack_from("<i", self.sections["SHAP"][0], source.shape)[0]
        self._insert(dialog, name, text_type, bytes(shape), static_type, control)

    def _insert(self, dialog: str, name: str, shape_type: int, shape: bytes,
                control_type: int, control: bytes) -> None:
        """One new object at the end of a dialog: its name, shape and control."""
        if self.sections["SHAP"][1] != self.sections["CTRL"][1]:
            raise LayoutError("Shape and control tables are not parallel")
        dlg = self._dialog(dialog)
        count, start = struct.unpack_from("<ii", self.sections["DLG"][0], dlg + 32)

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
        entry = max(owned) + 8
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
        insert = start + count * DLGO_SIZE
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
    """A tweak's layout/<id>.json: {"version": 1, "nodes": [...]}."""
    if not isinstance(spec, dict) or spec.get("version") != 1 or set(spec) - {"version", "nodes"}:
        raise LayoutError(f"{owner}: a layout patch needs version 1 and nodes")
    nodes = spec.get("nodes", [])
    if not isinstance(nodes, list) or not nodes or len(nodes) > 64:
        raise LayoutError(f"{owner}: list between 1 and 64 layout nodes")
    text = {"dialog", "name", "lookLike", "dy", "length"}
    sprite = {"dialog", "name", "sprite", "lookLike", "dy", "color"}
    clean = []
    for node in nodes:
        keys = set(node) if isinstance(node, dict) else set()
        if keys not in (text, text | {"left"}, sprite):
            raise LayoutError(f"{owner}: a layout node is text ({', '.join(sorted(text))}, optional left) "
                              f"or a sprite ({', '.join(sorted(sprite))})")
        if not all(isinstance(node[key], str) and node[key] for key in ("dialog", "name", "lookLike")):
            raise LayoutError(f"{owner}: layout node names must be text")
        if "sprite" in node and (not isinstance(node["sprite"], list) or len(node["sprite"]) != 2
                                 or not all(isinstance(part, str) and part for part in node["sprite"])):
            raise LayoutError(f"{owner}: a sprite names its source as [dialog, node]")
        clean.append(dict(node))
    return {"owner": owner, "nodes": clean}


def compose(original: bytes, specs: list[dict]) -> bytes:
    """Every enabled tweak's nodes added to the vanilla layout, or the vanilla bytes."""
    nodes = [(spec["owner"], node) for spec in specs for node in spec["nodes"]]
    if not nodes:
        return original
    layout = Drb(formats.inflate(original))
    seen = {}
    for owner, node in nodes:
        key = (node["dialog"], node["name"])
        if key in seen:
            raise LayoutError(f"{owner} and {seen[key]} both add {node['dialog']}/{node['name']}")
        seen[key] = owner
        try:
            if "sprite" in node:
                layout.add_sprite(node["dialog"], node["name"], tuple(node["sprite"]), node["lookLike"],
                                  node["dy"], node["color"])
            else:
                layout.add_text(node["dialog"], node["name"], node["lookLike"], node["dy"], node["length"],
                                node.get("left"))
        except LayoutError as error:
            raise LayoutError(f"{owner}: {error}") from error
    return formats.deflate(original, layout.to_bytes())


def is_vanilla(data: bytes) -> bool:
    return len(data) == VANILLA_SIZE and hashlib.sha256(data).hexdigest() == VANILLA_SHA256

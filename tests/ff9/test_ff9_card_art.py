"""Synthetic card-art fixture; no game asset is committed."""
import struct

from PIL import Image

from plugins.ff9 import card_art
from plugins.ff9.battle_scene import UnityObject


def _string(text):
    raw = text.encode()
    return struct.pack("<I", len(raw)) + raw + b"\0" * (-len(raw) % 4)


class FakeArchive:
    def __init__(self, blobs):
        self.data = b"".join(blob for _obj, blob in blobs)
        self.objects, offset = [], 0
        for (info, type_id, name), blob in blobs:
            self.objects.append(UnityObject(info, offset, len(blob), type_id, 0, 0, name))
            offset += len(blob)


def _archive():
    width, height = 8, 4
    # Bottom row first, ARGB: the top-left pixel of the image is the last row.
    top = bytes([255, 255, 0, 0]) * width
    bottom = bytes([255, 0, 0, 255]) * width
    pixels = bottom * (height // 2) + top * (height // 2)
    texture = (_string("quadmist_image1")
               + struct.pack("<14i", width, height, len(pixels), 5, 1, 256, 1, 2, 0, 0, 0, 0, 0, 0)
               + struct.pack("<i", len(pixels)) + pixels)
    material = _string(card_art.MATERIAL_NAME)
    sprite = lambda name, x, y, w, h: _string(name) + struct.pack("<12i", x, y, w, h, *([0] * 8))
    atlas = (b"\0" * 28 + _string("") + struct.pack("<iq", 0, 7) + struct.pack("<I", 2)
             + sprite("card_00", 0, 0, 4, 2) + sprite("card_01", 4, 2, 4, 2))
    return FakeArchive([((5, 28, "quadmist_image1"), texture), ((7, 21, card_art.MATERIAL_NAME), material),
                        ((9, 2**32 - 1, ""), atlas)])


def test_atlas_rects_name_each_card_by_id():
    assert card_art.atlas_sprites(_archive()) == {0: (0, 0, 4, 2), 1: (4, 2, 4, 2)}


def test_faces_are_cut_from_the_top_left_origin(tmp_path):
    faces = card_art.cut_cards(_archive())
    for card, colour in ((0, (255, 0, 0, 255)), (1, (0, 0, 255, 255))):
        target = tmp_path / f"{card}.png"
        target.write_bytes(faces[card])
        with Image.open(target) as image:
            assert image.size == (4, 2)
            assert image.getpixel((0, 0)) == colour

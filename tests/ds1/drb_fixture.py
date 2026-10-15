"""Tiny DRB/DCX builders: synthetic menu layouts for icon tests."""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugins.ds1 import menu_layout


def make_dcx(plain):
    compressed = zlib.compress(bytes(plain), 9)
    header = (b'DCX\0' + bytes.fromhex('000100000000001800000024000000240000002c') + b'DCS\0'
              + struct.pack('>II', len(plain), len(compressed)) + b'DCP\0' + b'DFLT'
              + bytes.fromhex('00000020090000000000000000000000000000000001010000000000')[:24]
              + b'DCA\0\0\0\0\x08')
    assert len(header) == 76
    return header + compressed


class Strings:
    def __init__(self):
        self.data = bytearray()
        self.offsets = {}

    def put(self, text):
        if text not in self.offsets:
            self.offsets[text] = len(self.data)
            self.data += text.encode('utf-16-le') + b'\0\0'
        return self.offsets[text]


def sprite_shape(rect, uv, texi):
    return (struct.pack('<4h', *rect) + struct.pack('<4h', *uv)
            + struct.pack('<hh', texi, 256) + b'\xff\xff\xff\xff' + b'\0' * 4)


def make_drb(texi_names, dialogs):
    """A minimal DRB: texture names plus dialogs of (name, shape) sprites."""
    strings = Strings()
    texi = bytearray()
    for name in texi_names:
        texi += struct.pack('<4i', strings.put(name), strings.put('N:\\' + name), 0, 0)
    shapes, objects, entries = bytearray(), bytearray(), bytearray()
    shap = []
    for dialog, nodes in dialogs.items():
        own = len(shap)
        shap.append((strings.put('Null'), len(shapes)))
        shapes += b'\0' * 16
        start = len(objects)
        for name, blob in nodes:
            at = len(shap)
            shap.append((strings.put('Sprite'), len(shapes)))
            shapes += blob
            objects += struct.pack('<iii', strings.put(name), at * 8, 0) + b'\0' * 20
        row = struct.pack('<iii', strings.put(dialog), own * 8, 0) + b'\0' * 20
        row += struct.pack('<ii', len(nodes), start) + struct.pack('<ihh', 0, 636, 483)
        entries += row.ljust(menu_layout.DLG_SIZE, b'\0')
    controls = b'\0' * 4
    sections = {
        'STR': (bytes(strings.data), len(strings.offsets)),
        'TEXI': (bytes(texi), len(texi_names)),
        'SHPR': (bytes(shapes), 1), 'CTPR': (controls, 1),
        'SHAP': (b''.join(struct.pack('<ii', *item) for item in shap), len(shap)),
        'CTRL': (struct.pack('<ii', strings.put('Static'), 0), 1),
        'DLGO': (bytes(objects), len(objects) // menu_layout.DLGO_SIZE),
        'DLG': (bytes(entries), len(entries) // menu_layout.DLG_SIZE),
    }
    out = bytearray(b'DRB\0' + b'\0' * 12)
    for tag in menu_layout.SECTIONS:
        data, count = sections.get(tag, (b'', 0))
        data = bytes(data) + b'\0' * (-len(data) % 16)
        out += tag.encode('ascii').ljust(4, b'\0') + struct.pack('<iii', len(data), count, 0) + data
    return bytes(out)

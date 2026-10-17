"""An undecoded battle file says what its bytes provably hold.

Lexer: "models: 90% of things here have no preview, say "locked", and have
basically nothing in their details panel. what gives?" Most battle files
decode now; for the rest, a one-number file shows its number and a container
lists its parts, without claiming what either means.
"""
import struct

from plugins.ff8.assets import _undecoded_layout


def test_a_four_byte_file_is_one_number():
    assert _undecoded_layout(struct.pack("<I", 140)) == {"value": 140}


def test_a_count_and_offset_table_is_a_container():
    body = b"A" * 10 + b"B" * 6
    data = struct.pack("<3I", 2, 12, 22) + body
    layout = _undecoded_layout(data)
    assert layout["sections"] == [
        {"index": 0, "name": "Part 1", "offset": 12, "size": 10},
        {"index": 1, "name": "Part 2", "offset": 22, "size": 6},
    ]


def test_anything_else_claims_nothing():
    assert _undecoded_layout(bytes(32768)) == {}
    assert _undecoded_layout(b"SMN\x01" + bytes(60)) == {}
    # Offsets that leave the file, or run backwards, are not a container.
    assert _undecoded_layout(struct.pack("<3I", 2, 40, 12) + bytes(20)) == {}

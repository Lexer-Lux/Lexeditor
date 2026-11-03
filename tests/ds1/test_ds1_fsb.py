"""FSB4 interface banks: stream tables and seek-read extraction.

Probed from the installed frpg_sm banks: FSB4 magic, a stream count,
then 80-byte sample headers (name, sample count, byte size, rate),
then the MP3 payloads back to back. Banks reach 126 MB, so the table
reads headers only and streams are seek-read one at a time.
"""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ds1 import fsb  # noqa: E402


def bank_bytes(streams):
    """An FSB4 bank from (name, samples, rate, payload) tuples."""
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(streams), 0, 0) + bytes(32))
    for name, samples, rate, payload in streams:
        head = bytearray(80)
        struct.pack_into("<H", head, 0, 80)
        encoded = name.encode("ascii")
        head[2:2 + len(encoded)] = encoded
        struct.pack_into("<II", head, 32, samples, len(payload))
        struct.pack_into("<I", head, 52, rate)
        data += head
    for _name, _samples, _rate, payload in streams:
        data += payload
    return bytes(data)


def test_stream_table_names_offsets_and_durations(tmp_path):
    bank = tmp_path / "test.fsb"
    bank.write_bytes(bank_bytes([
        ("o7230.wav", 380160, 44100, b"A" * 172928),
        ("silen.wav", 44100, 44100, b"B" * 20000),
    ]))
    table = fsb.parse_table(bank)
    assert [(entry["name"], entry["size"]) for entry in table] == [
        ("o7230.wav", 172928), ("silen.wav", 20000)]
    assert table[0]["offset"] == 48 + 2 * 80
    assert table[1]["offset"] == 48 + 2 * 80 + 172928
    assert table[0]["duration"] == pytest.approx(380160 / 44100)
    assert table[1]["duration"] == pytest.approx(1.0)
    assert fsb.read_stream(bank, table[0]) == b"A" * 172928
    assert fsb.read_stream(bank, table[1]) == b"B" * 20000


def test_extract_mp3_strips_primer_padding_and_filler(tmp_path):
    frame = bytes.fromhex("fffba060") + bytes(522 - 4)
    primer = bytes.fromhex("0a00fffb") + bytes(12)
    bank = tmp_path / "pad.fsb"
    bank.write_bytes(bank_bytes([("o1.wav", 2304, 44100, primer + frame + b"\0\0" + frame + b"\0")]))
    (entry,) = fsb.parse_table(bank)
    assert fsb.extract_mp3(bank, entry) == frame + frame
    bank.write_bytes(bank_bytes([("o2.wav", 2304, 44100, primer + frame + frame[:100])]))
    (entry,) = fsb.parse_table(bank)
    assert fsb.extract_mp3(bank, entry) == frame
    bank.write_bytes(bank_bytes([("o3.wav", 2304, 44100, primer + frame + b"\xff\xfb" + frame + b"\0")]))
    (entry,) = fsb.parse_table(bank)
    assert fsb.extract_mp3(bank, entry) == frame + frame
    bank.write_bytes(bank_bytes([("o4.wav", 2304, 44100, primer + frame + b"\xff")]))
    (entry,) = fsb.parse_table(bank)
    assert fsb.extract_mp3(bank, entry) == frame
    bank.write_bytes(bank_bytes([("o5.wav", 2304, 44100, frame + b"\0" + frame)]))
    (entry,) = fsb.parse_table(bank)
    assert fsb.extract_mp3(bank, entry) == frame + frame


def test_unproven_banks_raise(tmp_path):
    bank = tmp_path / "bad.fsb"
    bank.write_bytes(b"not a bank")
    with pytest.raises(fsb.FsbError):
        fsb.parse_table(bank)
    bank.write_bytes(struct.pack("<4sIII", b"FSB4", 0, 0, 0) + bytes(32))
    with pytest.raises(fsb.FsbError):
        fsb.parse_table(bank)
    bank.write_bytes(struct.pack("<4sIII", b"FSB4", 1, 0, 0) + bytes(32) + bytes(79))
    with pytest.raises(fsb.FsbError):
        fsb.parse_table(bank)


def test_extract_mp3_reads_mpeg2_layer3_frames(tmp_path):
    """CURSOL_SELECT is MPEG-2 Layer III: 160 kbps at 22050 Hz."""
    frame = bytes.fromhex("fff3e0c0") + bytes(522 - 4)
    bank = tmp_path / "mpeg2.fsb"
    bank.write_bytes(bank_bytes([("sel.wav", 6912, 22050, frame + b"\0\0" + frame)]))
    (entry,) = fsb.parse_table(bank)
    assert fsb.extract_mp3(bank, entry) == frame + frame

"""DS1 flattens every FSB bank's streams into per-kind sound lists."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ds1 import assets  # noqa: E402


def bank_bytes(streams):
    """A header-only FSB4 bank: [(name, samples, size, rate)]."""
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(streams), 0, 0) + bytes(32))
    for name, samples, size, rate in streams:
        head = bytearray(80)
        struct.pack_into("<H", head, 0, 80)
        encoded = name.encode("ascii")
        head[2:2 + len(encoded)] = encoded
        struct.pack_into("<II", head, 32, samples, size)
        struct.pack_into("<I", head, 52, rate)
        data += head
    return bytes(data)


def test_list_streams_splits_kinds_and_reports_durations(tmp_path):
    game = tmp_path / "game"
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "sfx_core.fsb").write_bytes(bank_bytes([
        ("hit.wav", 44100, 1000, 44100), ("miss.wav", 22050, 500, 44100)]))
    (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes([
        ("boss.wav", 88200, 2000, 44100)]))
    (game / "sound" / "notes.fsb").write_bytes(b"not a bank")
    (game / "sound" / "sfx_test.fev").write_bytes(b"not a bank")
    found = assets.list_streams(game, None)
    assert [entry["name"] for entry in found["sound"]] == ["hit.wav", "miss.wav"]
    assert found["sound"][0]["duration"] == 1.0
    assert found["sound"][0]["bank"] == "sound/sfx_core.fsb"
    assert found["sound"][0]["size"] == 1000
    assert [entry["name"] for entry in found["music"]] == ["boss.wav"]
    assert found["unreadable"] == ["sound/notes.fsb"]


def test_list_streams_prefers_mod_override(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "mod"
    (game / "sound").mkdir(parents=True)
    (project / "sound").mkdir(parents=True)
    (game / "sound" / "sfx_core.fsb").write_bytes(bank_bytes([("old.wav", 44100, 100, 44100)]))
    (project / "sound" / "sfx_core.fsb").write_bytes(bank_bytes([("new.wav", 44100, 100, 44100)]))
    found = assets.list_streams(game, project)
    assert [entry["name"] for entry in found["sound"]] == ["new.wav"]

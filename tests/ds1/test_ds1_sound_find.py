"""Play-sound resolution: stream numbers derive their bank by search.

A TAE Play-sound event stores only a sound number; the bank holding
that stream is found across the installed banks (o7230.wav answers
7230), so the reader picks sounds, never banks. Numbers no bank holds
stay unresolved links, never errors.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tae_fixture import build_anibnd, build_tae  # noqa: E402
from test_ds1_sound_bank import bank_bytes  # noqa: E402
from plugins.ds1 import assets  # noqa: E402
from plugins.ds1.store import MARKER  # noqa: E402
from plugins.ds1.tae_store import CHR_DIR, TaeStore  # noqa: E402

BINDER = "c1200.anibnd.dcx"
TAE = "a87.tae"


def test_stream_number_answers_bare_numbers_only():
    assert assets.stream_number("o7230.wav") == 7230
    assert assets.stream_number("v713000400.wav") == 713000400
    assert assets.stream_number("m100100000.wav") == 100100000
    assert assets.stream_number("scn120000.wav") == 120000
    assert assets.stream_number("7230.wav") == 7230
    assert assets.stream_number("birds.wav") is None
    assert assets.stream_number("silen.wav") is None
    assert assets.stream_number("o1201open.wav") is None
    assert assets.stream_number("o1201close.wav") is None
    assert assets.stream_number("m14drone.wav") is None
    assert assets.stream_number("CURSOL_MOVE.wav") is None
    assert assets.stream_number("") is None
    assert assets.stream_number(None) is None


def setup(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / CHR_DIR).mkdir(parents=True)
    (game / CHR_DIR / BINDER).write_bytes(build_anibnd({TAE: build_tae()}))
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "frpg_se0.fsb").write_bytes(
        bank_bytes(("o7230.wav", "o7250.wav", "silen.wav")))
    (game / "sound" / "frpg_sm10.fsb").write_bytes(bank_bytes(("v713000400.wav",)))
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_find_sound_derives_bank_and_sub(tmp_path):
    game, mod = setup(tmp_path)
    found = assets.find_sound(game, mod, 7230)
    assert found == [{"bank": "sound/frpg_se0.fsb", "stream": "o7230.wav",
                      "sub": "sfx", "duration": found[0]["duration"],
                      "size": found[0]["size"], "overridden": False}]
    assert found[0]["duration"] > 0 and found[0]["size"] > 0
    music = assets.find_sound(game, mod, 713000400)
    assert [(entry["bank"], entry["sub"]) for entry in music] == [
        ("sound/frpg_sm10.fsb", "music")]
    assert assets.find_sound(game, mod, 999) == []
    assert assets.find_sound(game, mod, -1) == []
    assert assets.find_sound(game, mod, True) == []


def test_find_sound_prefers_the_mod_bank(tmp_path):
    game, mod = setup(tmp_path)
    (mod / "sound").mkdir(parents=True)
    (mod / "sound" / "frpg_se0.fsb").write_bytes(bank_bytes(("o9999.wav",)))
    assert assets.find_sound(game, mod, 7230) == []
    found = assets.find_sound(game, mod, 9999)
    assert [(entry["bank"], entry["overridden"]) for entry in found] == [
        ("sound/frpg_se0.fsb", True)]


def test_tae_read_links_the_derived_sound(tmp_path):
    game, mod = setup(tmp_path)
    store = TaeStore(game, mod, False, None)
    row = store.add_event(BINDER, TAE, 0, 128, 0.25, 0.75,
                          {"soundType": 1, "soundId": 7230})
    assert row["recordLinks"] == [{
        "kind": "sound", "table": "SoundStream", "id": 7230,
        "field": "soundId", "resolved": True, "name": "o7230.wav",
        "bank": "sound/frpg_se0.fsb", "stream": "o7230.wav", "sub": "sfx",
        "duration": row["recordLinks"][0]["duration"],
        "size": row["recordLinks"][0]["size"]}]
    missing = store.add_event(BINDER, TAE, 0, 128, 0.0, 1.0,
                              {"soundType": 1, "soundId": 999})
    assert missing["recordLinks"] == [{
        "kind": "sound", "table": "SoundStream", "id": 999,
        "field": "soundId", "resolved": False, "name": "Unknown sound 999"}]
    attack = store.read(BINDER, f"ev:{TAE}|0|0")
    assert attack["recordLinks"] == []

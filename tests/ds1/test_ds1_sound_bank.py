"""DS1 sound banks list their streams and serve them as MPEG over HTTP."""
import json
import struct
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1.store import MARKER  # noqa: E402


def bank_bytes(names=("o7230.wav", "silen.wav")):
    """An FSB4 bank with framed MPEG payloads, one stream per name."""
    frame = bytes.fromhex("fffba060") + bytes(522 - 4)
    primer = bytes.fromhex("0a00fffb") + bytes(12)
    payloads = [primer + frame + b"\0\0" + frame for _ in names]
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(names), 0, 0) + bytes(32))
    for name, payload in zip(names, payloads):
        head = bytearray(80)
        struct.pack_into("<H", head, 0, 80)
        encoded = name.encode("ascii")
        head[2:2 + len(encoded)] = encoded
        struct.pack_into("<II", head, 32, 2304, len(payload))
        struct.pack_into("<I", head, 52, 44100)
        data += head
    for payload in payloads:
        data += payload
    return bytes(data)


def session_for(game, project=None):
    env = {"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1"}
    if project is not None:
        env = {"LEXEDITOR_DS1_ROOT": str(game),
               "LEXEDITOR_DS1_PROJECT": str(project)}
        (project / MARKER).touch()
        (project / "mod.json").write_text('{"name": "test"}', encoding="utf-8")
    session = DS1Session(env)
    assert session.start()["pluginId"] == "ds1"
    return session


def get(session, route):
    with urlopen(session.url.rstrip("/") + route) as reply:
        return reply.status, reply.headers.get_content_type(), reply.read()


def test_bank_lists_streams(tmp_path):
    game = tmp_path / "game"
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes())
    session = session_for(game)
    try:
        status, _kind, body = get(session, "/api/sound/bank?file=" + quote("sound/frpg_main.fsb"))
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["source"] == "game"
        assert [(entry["name"], round(entry["duration"], 2)) for entry in payload["streams"]] == [
            ("o7230.wav", round(2304 / 44100, 2)), ("silen.wav", round(2304 / 44100, 2))]
        assert all(entry["size"] > 0 for entry in payload["streams"])
    finally:
        session.stop()
        assert session.wait_closed()


def test_stream_serves_mpeg(tmp_path):
    game = tmp_path / "game"
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes())
    session = session_for(game)
    try:
        status, kind, body = get(session, "/api/sound/stream?file="
                                 + quote("sound/frpg_main.fsb") + "&stream=o7230.wav")
        assert status == 200
        assert kind == "audio/mpeg"
        assert body[:2] == bytes.fromhex("fffb")
        assert len(body) > 500
    finally:
        session.stop()
        assert session.wait_closed()


def test_unknown_stream_is_a_400(tmp_path):
    game = tmp_path / "game"
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes())
    session = session_for(game)
    try:
        try:
            get(session, "/api/sound/stream?file=" + quote("sound/frpg_main.fsb") + "&stream=nope.wav")
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("unknown stream served")
    finally:
        session.stop()
        assert session.wait_closed()


def test_non_bank_files_and_traversal_are_400(tmp_path):
    game = tmp_path / "game"
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "notes.txt").write_bytes(b"not a bank")
    session = session_for(game)
    try:
        for route in ("/api/sound/bank?file=" + quote("sound/notes.txt"),
                      "/api/sound/bank?file=" + quote("../outside.fsb")):
            try:
                get(session, route)
            except HTTPError as error:
                assert error.code == 400, route
            else:
                raise AssertionError(f"served {route}")
    finally:
        session.stop()
        assert session.wait_closed()


def test_mod_bank_wins_over_the_installed_bank(tmp_path):
    game = tmp_path / "game"
    (game / "sound").mkdir(parents=True)
    (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes())
    project = tmp_path / "project"
    (project / "sound").mkdir(parents=True)
    (project / "sound" / "frpg_main.fsb").write_bytes(bank_bytes(("custom.wav",)))
    session = session_for(game, project)
    try:
        _status, _kind, body = get(session, "/api/sound/bank?file=" + quote("sound/frpg_main.fsb"))
        payload = json.loads(body.decode("utf-8"))
        assert payload["source"] == "mod"
        assert [entry["name"] for entry in payload["streams"]] == ["custom.wav"]
    finally:
        session.stop()
        assert session.wait_closed()

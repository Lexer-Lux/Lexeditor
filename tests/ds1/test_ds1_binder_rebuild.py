"""Binder rebuilds: resized members merge instead of falling back to whole file.

Two mods resizing different animation files in one binder both apply, down
to the rebuilt byte layout. Synthetic binders only.
"""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tae_fixture import build_anibnd, build_tae
from plugins.ds1 import mod_loader
from plugins.ds1.formats import FormatError, inflate, members, pack
from plugins.ds1.tae_store import CHR_DIR

TAE = build_tae()
VANILLA = build_anibnd({"a87.tae": TAE, "a88.tae": TAE, "a00_empty.txt": b""})
BINDER = CHR_DIR / "c1200.anibnd.dcx"
GAME = {BINDER: VANILLA}


def mod(name, *binders):
    return mod_loader.Mod(name, Path(name), dict(binders))


def grown(member, extra):
    members_out = {"a87.tae": TAE, "a88.tae": TAE, "a00_empty.txt": b""}
    members_out[member] = members_out[member] + extra
    return build_anibnd(members_out)


def payload(payload_bytes, member):
    plain = inflate(payload_bytes)
    entry = members(plain)[member]
    return bytes(plain[entry.offset:entry.offset + entry.size])


def entry_ids(plain):
    count = struct.unpack_from("<I", plain, 16)[0]
    return [struct.unpack_from("<I", plain, 32 + index * 24 + 12)[0]
            for index in range(count)]


def test_rebuild_with_same_bytes_is_byte_identical():
    plain = inflate(VANILLA)
    items = {name: bytes(plain[entry.offset:entry.offset + entry.size])
             for name, entry in members(plain).items()}
    assert pack(plain, items) == plain


def test_rebuild_with_resized_members_keeps_every_payload():
    plain = inflate(VANILLA)
    items = {name: bytes(plain[entry.offset:entry.offset + entry.size])
             for name, entry in members(plain).items()}
    items["a87.tae"] += b"\0" * 20
    items["a88.tae"] = items["a88.tae"][:-7]
    rebuilt = pack(plain, items)
    owned = members(rebuilt)
    assert set(owned) == set(items)
    for name, data in items.items():
        entry = owned[name]
        assert bytes(rebuilt[entry.offset:entry.offset + entry.size]) == data
        if data:
            assert entry.offset % 16 == 0
    assert entry_ids(rebuilt) == entry_ids(plain)
    assert pack(rebuilt, items) == rebuilt


def test_rebuild_rejects_a_changed_member_set():
    plain = inflate(VANILLA)
    items = {name: b"x" for name in members(plain)}
    try:
        pack(plain, {**items, "a89.tae": b"x"})
    except FormatError:
        pass
    else:
        raise AssertionError("Expected an added member to fail")
    try:
        pack(plain, {name: data for name, data in items.items()
                     if name != "a88.tae"})
    except FormatError:
        pass
    else:
        raise AssertionError("Expected a removed member to fail")
    try:
        pack(b"not a binder", items)
    except FormatError:
        pass
    else:
        raise AssertionError("Expected a foreign template to fail")


def test_an_undecodable_member_name_is_a_format_error():
    plain = bytearray(inflate(VANILLA))
    at = bytes(plain).find(b"a87.tae")
    plain[at] = 0x80
    try:
        members(bytes(plain))
    except FormatError:
        pass
    else:
        raise AssertionError("Expected an undecodable name to fail")


def test_resized_members_from_two_mods_both_apply():
    a = mod("A", (BINDER, grown("a87.tae", b"A" * 20)))
    b = mod("B", (BINDER, grown("a88.tae", b"B" * 30)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert payload(result.files[BINDER], "a87.tae") == TAE + b"A" * 20
    assert payload(result.files[BINDER], "a88.tae") == TAE + b"B" * 30


def test_a_resized_member_conflicts_and_the_later_mod_is_used():
    a = mod("A", (BINDER, grown("a87.tae", b"A" * 20)))
    b = mod("B", (BINDER, grown("a87.tae", b"B" * 30)))
    result = mod_loader.compose(GAME, [a, b])
    assert payload(result.files[BINDER], "a87.tae") == TAE + b"B" * 30
    assert [(c.part, c.mods) for c in result.conflicts] == [("a87.tae", ["A", "B"])]

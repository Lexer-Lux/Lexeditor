"""Synthetic ESD builder for unit tests (no game data)."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugins.ds1.esd import Command, Condition, Esd, State, assemble


def build_esd():
    """Two state groups exercising every record shape the format has.

    Group 0 holds one state (so no dummy copy is written): entry, exit
    and while commands, string/int/float/call arguments, a plain
    condition and a condition with pass commands, subconditions and no
    target. Group 5 holds two states (so a dummy copy is written) and a
    state without conditions.
    """
    plain = Condition(0, assemble("f22() == 1"))
    sub = Condition(None, assemble("r0 != 0"), [Command(1, 7, [])],
                    [Condition(0, assemble("1"))])
    with_subs = Condition(0, assemble("(r0 := f38(2, 0)) == 1..."),
                          [Command(1, 29, [assemble('"hi"')])], [sub])
    first = State(0, [Command(1, 3, [assemble('"Ins_X"'), assemble("1")])],
                  [Command(1, 5, [])],
                  [Command(7, 9, [assemble("i32(1004)"), assemble("f32(0.5)"),
                                   assemble("f64(-2.0)"), assemble('"日本"')])],
                  [plain, with_subs])
    lone = State(4, [], [], [], [])
    other = State(6, [Command(5, 1, [assemble("margs(0)")])], [], [],
                  [Condition(4, assemble("mstat() == ongoing()"))])
    return Esd({0: {0: first}, 5: {4: lone, 6: other}}, "t999999",
               1, True, (1, 2, 3, 4))


def make_bnd(members):
    """A synthetic BND3: {base name: payload}, shaped like the game ships."""
    entries = sorted(members.items())
    encoded = [name.encode("shift_jis") + b"\0" for name, _ in entries]
    directory_end = 32 + len(entries) * 24
    names_end = directory_end + sum(map(len, encoded))
    plain = bytearray(names_end)
    plain[:4] = b"BND3"
    plain[4:12] = b"TEST0000"
    plain[12] = 0x74
    struct.pack_into("<II", plain, 16, len(entries), names_end)
    name_offset = directory_end
    for index, ((name, payload), raw) in enumerate(zip(entries, encoded)):
        data_offset = len(plain)
        struct.pack_into("<6I", plain, 32 + index * 24, 0x40, len(payload),
                         data_offset, index, name_offset, len(payload))
        plain[name_offset:name_offset + len(raw)] = raw
        name_offset += len(raw)
        plain.extend(payload)
    return bytes(plain)

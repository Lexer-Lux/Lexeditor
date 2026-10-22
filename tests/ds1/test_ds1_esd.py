"""ESD reader/writer and expression codec on a synthetic file (no game data)."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from esd_fixture import build_esd
from plugins.ds1.esd import Command, Esd, EsdError, assemble, disassemble, parse


def test_round_trip_reproduces_bytes():
    raw = build_esd().to_bytes()
    assert parse(raw).to_bytes() == raw


def test_round_trip_recovers_model():
    doc = parse(build_esd().to_bytes())
    assert doc == build_esd()
    assert doc.name == "t999999"
    assert sorted(doc.state_groups) == [0, 5]
    first = doc.state_groups[0][0]
    assert [command.id for command in first.entry_commands] == [3]
    assert [command.id for command in first.exit_commands] == [5]
    assert [command.id for command in first.while_commands] == [9]
    assert [cond.target_state for cond in first.conditions] == [0, 0]
    assert first.conditions[1].subconditions[0].target_state is None


def test_appended_command_reparses():
    raw = build_esd().to_bytes()
    doc = parse(raw)
    state = doc.state_groups[5][6]
    state.entry_commands.append(Command(1, 999, [assemble("1"), assemble('"x"')]))
    changed = doc.to_bytes()
    assert changed != raw
    again = parse(changed)
    assert again == doc
    assert [command.id for command in again.state_groups[5][6].entry_commands] == [1, 999]


ROUND_TRIPS = [
    ("0", "40 a1"),
    ("-3", "3d a1"),
    ("63", "7f a1"),
    ("-64", "00 a1"),
    ("100", "82 64 00 00 00 a1", "i32(100)"),
    ("i32(1004)", "82 ec 03 00 00 a1"),
    ("i32(-2147483648)", "82 00 00 00 80 a1"),
    ("f32(0.5)", "80 00 00 00 3f a1"),
    ("f64(-2.0)", "81 00 00 00 00 00 00 00 c0 a1"),
    ('"hi"', "a5 68 00 69 00 00 00 a1"),
    ('"a\\"b\\\\c日本"', None),
    ("f22()", "56 84 a1"),
    ("f38(2, 0)", "66 42 40 86 a1"),
    ("f1(2, 3) == f32(1.5)", "41 42 43 86 80 00 00 c0 3f 95 a1"),
    ("1 + 2 * 3 == 7", "41 42 43 8f 8c 47 95 a1"),
    ("f1() == 1 and f2() == 2 or f3() == 3", None),
    ("((r0 := f22()) == 1)... and (r1 := f21()) == 0", None),
    ("(r0 == 0)! and r1 == 0", "af 40 95 b7 b0 40 95 98 a1"),
    ("f25(53)... == 0! and f15(i32(764))... == 0", None),
    ("neg(f22())", "56 84 8d a1"),
    ("margs(0)", "40 b8 a1"),
    ("mstat() == 1", "b9 41 95 a1"),
    ("ongoing() != 0", "ba 40 96 a1"),
    ("f32() == 1", "60 84 41 95 a1"),
    ("f32(2) == 2", "60 42 85 42 95 a1"),
]


def test_unary_minus_folds_into_literals():
    assert assemble("-f32(1.5)") == assemble("f32(-1.5)")
    assert assemble("-100") == assemble("i32(-100)")
    assert disassemble(assemble("-f32(1.5)")) == "f32(-1.5)"


def test_expression_round_trips():
    for entry in ROUND_TRIPS:
        text, raw = entry[0], entry[1]
        shown = entry[2] if len(entry) > 2 else text
        data = assemble(text)
        if raw is not None:
            assert data.hex(" ") == raw
        assert disassemble(data) == shown
        assert assemble(shown) == data


def test_expression_rejects_bad_input():
    for bad in ["", "1 2", "f1(1, 2, 3, 4, 5, 6, 7, 8)", "1 < 2 < 3",
                "-f1()", "foo(1)", "r9", "(r0 := 1", '"abc', "1 +"]:
        with pytest.raises(EsdError):
            assemble(bad)
    for bad in [b"", b"\x41", b"\x41\x42\xa1", b"\x41\x95\xa1",
                b"\x83\xa1", b"\x82\x01\xa1", b"\x41\xa1\x41\xa1",
                b"\x84\xa1"]:
        with pytest.raises(EsdError):
            disassemble(bad)


def test_container_rejects_bad_input():
    with pytest.raises(EsdError):
        parse(b"fSSL" + bytes(200))
    with pytest.raises(EsdError):
        parse(build_esd().to_bytes()[:50])
    doc = build_esd()
    doc.state_groups[0][0].entry_commands.append(Command(9, 1, []))
    with pytest.raises(EsdError):
        doc.to_bytes()

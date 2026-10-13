"""The Party Switch hook logs every close path and keeps the native controller alive.

The selector used to flash and vanish with no log line: the silent
``active != slot`` / KO-bit guard and the mode-exit resets closed it on the
next tick, and the hook starved the native command controller while open so
the engine-side slot could flicker and trip that guard. Every close path now
traces, and the open selector ticks the native controller with
command-accepting input suppressed, the way the pending path already does.
"""
from pathlib import Path

import plugins.ff8 as ff8


SOURCE = (Path(ff8.__file__).parent / "ffnx_party_switch" / "ffnx-src"
          / "lexeditor_ff8_party_switch.cpp").read_text(encoding="utf-8")


def test_silent_close_paths_trace():
    assert "selector auto-closed; active=%d slot=%d ko=%u" in SOURCE
    assert "selector closed; reserve %d ineligible" in SOURCE
    assert SOURCE.count("selector state reset by mode exit") == 2


def test_open_selector_ticks_native_with_suppressed_input():
    opened = SOURCE.partition("if(opened) {")[2].partition("if((edge&4)")[0]
    assert "mem<std::uint16_t>(context+0x10)=0;" in opened
    assert "mem<std::uint16_t>(context+0x12)=0;" in opened
    assert "mem<std::uint16_t>(context+0x14)=0;" in opened
    assert "original();" in opened
    assert "mem<std::uint16_t>(context+0x10)=held16;" in opened
    assert "active=mem<std::int8_t>(0x1D76844);" in opened


def test_guard_close_no_longer_double_ticks():
    assert "close_menu(); original(); return;" not in SOURCE

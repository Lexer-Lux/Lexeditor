"""A crashed game Windows still lists is named before the executable is written.

The process has no threads, so it is not running, but it keeps
DarkSoulsRemastered.exe locked; replacing the file would fail halfway with a
bare "Access is denied". Only putting back an executable an earlier
Lexeditor patched writes it, so only that waits on such a game: the loader's
own files are not locked by it.
"""
from unittest import mock

import pytest

from core import process_probe
from plugins.ds1 import tweak_mods

STUCK = [{"name": "DarkSoulsRemastered.exe", "pid": "1"}]


def test_a_listed_closed_game_is_named_before_the_executable_is_written():
    with mock.patch.object(tweak_mods.os, "name", "nt"), \
            mock.patch.object(process_probe, "zombie_processes", return_value=STUCK):
        with pytest.raises(tweak_mods.TweakError, match="restart Windows"):
            tweak_mods._ensure_executable_free()


def test_it_does_not_stop_anything_else():
    with mock.patch.object(tweak_mods.os, "name", "nt"), \
            mock.patch.object(tweak_mods, "live_processes", return_value=[]), \
            mock.patch.object(process_probe, "zombie_processes", return_value=STUCK):
        tweak_mods.ensure_game_closed()

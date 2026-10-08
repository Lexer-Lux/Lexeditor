"""A crashed game Windows still lists stops a tweak before anything is written.

The process has no threads, so it is not running, but it keeps
DarkSoulsRemastered.exe locked; replacing the file would fail halfway with a
bare "Access is denied". Lexeditor says what is wrong first.
"""
from unittest import mock

import pytest

from core import process_probe
from plugins.ds1 import tweak_mods


def test_a_listed_closed_game_is_named_before_any_write():
    with mock.patch.object(tweak_mods.os, "name", "nt"), \
            mock.patch.object(tweak_mods, "live_processes", return_value=[]), \
            mock.patch.object(process_probe, "zombie_processes",
                              return_value=[{"name": "DarkSoulsRemastered.exe", "pid": "1"}]):
        with pytest.raises(tweak_mods.TweakError, match="restart Windows"):
            tweak_mods.ensure_game_closed()

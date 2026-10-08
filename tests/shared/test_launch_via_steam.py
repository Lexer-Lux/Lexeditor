"""A game whose executable cannot be started on its own is launched by Steam.

Play did nothing for Dark Souls Remastered: its plugin cannot start the
executable, so the button stayed greyed out. Such a game is now asked of
Steam (steam://rungameid/<app id>) whenever its installation names an app.
"""
from unittest import mock

import pytest

from core import desktop_host
from core.desktop_host import HostApi
from plugins.ds1.plugin import PLUGIN


def host():
    api = HostApi.__new__(HostApi)
    api._plugins = {PLUGIN.plugin_id: PLUGIN}
    return api


def test_play_asks_steam_for_a_game_it_cannot_start():
    assert PLUGIN.can_launch is False and PLUGIN.installation.steam_app_id == "570940"
    with mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(desktop_host.os, "startfile", create=True) as start:
        result = host().launch_game(PLUGIN.plugin_id)
    start.assert_called_once_with("steam://rungameid/570940")
    assert result["viaSteam"] is True


def test_a_game_without_a_steam_app_still_says_how_to_start_it():
    api = host()
    with mock.patch.object(HostApi, "_steam_app_id", return_value=""):
        with pytest.raises(ValueError, match="from Steam"):
            api.launch_game(PLUGIN.plugin_id)

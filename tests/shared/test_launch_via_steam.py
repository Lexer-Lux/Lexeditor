"""A game whose executable cannot be started on its own is launched by Steam.

Play did nothing for Dark Souls Remastered: its plugin cannot start the
executable, so the button stayed greyed out. Such a game is now asked of
Steam (steam://rungameid/<app id>) whenever its installation names an app.
"""
import dataclasses
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
            mock.patch.object(HostApi, "_deploy_before_launch") as deploy, \
            mock.patch.object(desktop_host.os, "startfile", create=True) as start:
        result = host().launch_game(PLUGIN.plugin_id)
    start.assert_called_once_with("steam://rungameid/570940")
    deploy.assert_called_once_with(PLUGIN.plugin_id)
    assert result["viaSteam"] is True


def test_play_installs_the_enabled_mods_as_they_are_now_before_steam_starts(tmp_path):
    """A tweak rebuilt while it stayed enabled reached DS1 only after a mod switch."""
    import threading
    api = host()
    api._mod_library_lock = threading.Lock()
    api._installations = mock.Mock(snapshot=mock.Mock(return_value={"root": str(tmp_path / "game")}))
    adapter = mock.Mock(deploys_on_launch=True, active_mod_ids=mock.Mock(return_value=["a", "b"]))
    order = []
    adapter.activate.side_effect = lambda *args: order.append("deploy")
    api._plugins = {PLUGIN.plugin_id: dataclasses.replace(PLUGIN, mod_adapter=adapter)}
    with mock.patch.object(HostApi, "_mod_adapter", return_value=adapter), \
            mock.patch.object(HostApi, "game_process_status", return_value={"running": False}), \
            mock.patch.object(HostApi, "mod_library_status", return_value={"root": str(tmp_path / "library")}), \
            mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(desktop_host.os, "startfile", create=True,
                              side_effect=lambda url: order.append("steam")):
        api.launch_game(PLUGIN.plugin_id)
    assert order == ["deploy", "steam"]
    roots, game = adapter.activate.call_args[0]
    assert [path.name for path in roots] == ["a", "b"] and game.name == "game"


def test_play_does_not_touch_files_under_a_running_game(tmp_path):
    api = host()
    api._installations = mock.Mock(snapshot=mock.Mock(return_value={"root": str(tmp_path)}))
    adapter = mock.Mock(deploys_on_launch=True)
    api._plugins = {PLUGIN.plugin_id: dataclasses.replace(PLUGIN, mod_adapter=adapter)}
    with mock.patch.object(HostApi, "game_process_status", return_value={"running": True}), \
            mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(desktop_host.os, "startfile", create=True):
        api.launch_game(PLUGIN.plugin_id)
    adapter.activate.assert_not_called()


def test_only_ds1_asks_to_be_installed_on_launch():
    assert PLUGIN.mod_adapter.deploys_on_launch is True


def test_a_game_without_a_steam_app_still_says_how_to_start_it():
    api = host()
    with mock.patch.object(HostApi, "_steam_app_id", return_value=""):
        with pytest.raises(ValueError, match="from Steam"):
            api.launch_game(PLUGIN.plugin_id)

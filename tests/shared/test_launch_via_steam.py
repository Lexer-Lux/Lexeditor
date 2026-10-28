"""A game whose executable cannot be started on its own is launched by Steam.

Play did nothing for Dark Souls Remastered: its plugin cannot start the
executable, so the button stayed greyed out. Such a game is now asked of
Steam (steam://rungameid/<app id>) whenever its installation names an app.
"""
import dataclasses
from pathlib import Path
from unittest import mock

import pytest

from core import desktop_host
from core.desktop_host import HostApi
from plugins.ds1.plugin import PLUGIN


def host():
    api = HostApi.__new__(HostApi)
    api._plugins = {PLUGIN.plugin_id: PLUGIN}
    api._launch_notice = mock.Mock(return_value="")
    return api


def test_play_asks_steam_for_a_game_it_cannot_start():
    assert PLUGIN.can_launch is False and PLUGIN.installation.steam_app_id == "570940"
    with mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(desktop_host.os, "startfile", create=True) as start:
        result = host().launch_game(PLUGIN.plugin_id)
    start.assert_called_once_with("steam://rungameid/570940")
    assert result["viaSteam"] is True


def test_play_launches_without_rebuilding_or_deploying_mods(tmp_path):
    api = host()
    api._installations = mock.Mock(snapshot=mock.Mock(return_value={"root": str(tmp_path / "game")}))
    adapter = mock.Mock()
    adapter.activate.side_effect = ValueError("A broken mod must not block Play")
    api._plugins = {PLUGIN.plugin_id: dataclasses.replace(PLUGIN, mod_adapter=adapter)}
    with mock.patch.object(HostApi, "_mod_adapter", return_value=adapter), \
            mock.patch.object(HostApi, "game_process_status", return_value={"running": False}), \
            mock.patch.object(HostApi, "mod_library_status", return_value={"root": str(tmp_path / "library")}), \
            mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(desktop_host.os, "startfile", create=True) as start:
        api.launch_game(PLUGIN.plugin_id)
    start.assert_called_once_with("steam://rungameid/570940")
    adapter.activate.assert_not_called()


def test_play_does_not_touch_files_under_a_running_game(tmp_path):
    api = host()
    api._installations = mock.Mock(snapshot=mock.Mock(return_value={"root": str(tmp_path)}))
    adapter = mock.Mock()
    api._plugins = {PLUGIN.plugin_id: dataclasses.replace(PLUGIN, mod_adapter=adapter)}
    with mock.patch.object(HostApi, "game_process_status", return_value={"running": True}), \
            mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(desktop_host.os, "startfile", create=True):
        api.launch_game(PLUGIN.plugin_id)
    adapter.activate.assert_not_called()


def test_a_game_without_a_steam_app_still_says_how_to_start_it():
    api = host()
    with mock.patch.object(HostApi, "_steam_app_id", return_value=""):
        with pytest.raises(ValueError, match="from Steam"):
            api.launch_game(PLUGIN.plugin_id)


def test_steam_games_never_start_the_executable_directly():
    api = host()
    api._plugins = {PLUGIN.plugin_id: dataclasses.replace(PLUGIN, can_launch=True)}
    with mock.patch.object(desktop_host.os, "name", "nt"), \
            mock.patch.object(HostApi, "_launch_notice", return_value=""), \
            mock.patch.object(desktop_host.os, "startfile", create=True) as start, \
            mock.patch.object(desktop_host.subprocess, "Popen") as direct:
        api.launch_game(PLUGIN.plugin_id)
    start.assert_called_once_with("steam://rungameid/570940")
    direct.assert_not_called()


@pytest.mark.parametrize("outcome", ["timeout", "started", "failed", "request_timeout"])
def test_steam_wait_feedback_and_late_start(tmp_path, outcome):
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[2]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.route("http://fixture/**", lambda route: route.fulfill(
                body='''<body><div id="lexeditor-shell"></div><main id="main">
                  <section style="display:grid;grid-template-columns:1fr 2fr;gap:12px;height:100%">
                    <div style="background:var(--lex-panel);padding:16px"><h2>Mods</h2>
                      <table><tr><th>Name</th><th>On</th></tr>
                      <tr><td>Lexeditor Loader</td><td><input type="checkbox" checked></td></tr>
                      <tr><td>Better Attunement</td><td><input type="checkbox" checked></td></tr></table></div>
                    <div style="background:var(--lex-panel);padding:16px"><h2>Better Attunement</h2>
                      <nav><button>Details</button><button>Files</button></nav>
                      <label>Description <textarea>Mod settings and description</textarea></label>
                      <div style="margin-top:20px;background:#a4824c;height:140px;padding:12px">Preview</div>
                    </div>
                  </section></main></body>''',
                content_type="text/html"))
            page.goto("http://fixture/")
            page.clock.install()
            page.add_style_tag(path=str(root / "ui/framework.css"))
            page.add_style_tag(path=str(root / "plugins/ds1/editor.css"))
            page.evaluate('''() => {
              window.running = false; window.launches = 0; window.afterLaunches = 0;
              window.pywebview = {api: new Proxy({
                loading_quote: async () => ({quote: ''}),
                lexeditor_settings: async () => ({loadingTransitionMinimumSeconds: 0}),
                default_views: async () => ({views: {}}),
                game_process_status: async () => ({running: window.running}),
                launch_game: () => { window.launches++;
                  return new Promise((resolve, reject) => {
                    window.finishLaunch = resolve; window.failLaunch = reject;
                  }); },
                stop_game: async () => {window.running = false; return {running: false};},
              }, {get: (target, key) => target[key] || (async () => ({}))})};
            }''')
            page.add_script_tag(path=str(root / "ui/framework.js"))
            page.evaluate('''() => {
              LexeditorUI.mountShell({host: '#lexeditor-shell',
                plugin: {id: 'ds1', name: 'Dark Souls Remastered'},
                tabs: [{id: 'mods', label: 'Mods'}], activeTab: () => 'mods',
                navigate: () => {}, afterLaunch: () => window.afterLaunches++,
                dirtyCount: () => 1, save: () => new Promise(resolve => {window.finishSave = resolve})});
              LexeditorUI.finishPluginLoading();
            }''')
            page.clock.run_for(500)
            page.clock.resume()
            page.wait_for_selector('#global-game-process')
            if outcome == "started":
                page.locator('#global-save').evaluate('(button) => button.click()')
                assert page.evaluate('document.body.inert')
                assert page.evaluate('getComputedStyle(document.querySelector("#main")).filter') == 'grayscale(1) brightness(0.45)'
                assert page.locator('#global-save').evaluate('(button) => getComputedStyle(button).filter') == 'none'
                page.screenshot(path=str(tmp_path / 'saving.png'))
                page.evaluate('window.finishSave()')
                page.wait_for_function('!document.body.inert', polling=100)
            button = page.locator('#global-game-process')
            button.evaluate('(button) => button.click()')
            assert button.get_attribute('aria-label') == 'Preparing game…'
            assert page.evaluate('document.body.inert')
            assert button.locator('.lex-save-throbber').is_visible()
            assert page.evaluate('getComputedStyle(document.querySelector("#main")).filter') == 'grayscale(1) brightness(0.45)'
            page.screenshot(path=str(tmp_path / 'preparing.png'))
            if outcome == "request_timeout":
                page.clock.run_for(30100)
                assert not page.evaluate('document.body.inert')
                assert not button.is_disabled()
                assert page.get_by_text('Could not launch the game', exact=True).is_visible()
                page.evaluate('window.running = true; window.finishLaunch({running: false, viaSteam: true})')
                page.clock.run_for(2100)
                assert button.get_attribute('aria-label') == 'Stop game'
                return
            if outcome == "failed":
                page.evaluate('window.failLaunch(new Error("Steam could not be opened"))')
                page.wait_for_function("!document.body.inert", polling=100)
                assert page.get_by_text('Could not launch the game', exact=True).is_visible()
                assert not button.is_disabled()
                assert button.get_attribute('aria-busy') == 'false'
                return
            page.evaluate('window.finishLaunch({running: false, viaSteam: true})')
            page.wait_for_function("!document.body.inert", polling=100)
            assert button.get_attribute('aria-label') == 'Waiting for Steam to start the game…'
            assert button.is_disabled()
            page.screenshot(path=str(tmp_path / 'steam-wait.png'))
            button.evaluate('(button) => button.onclick()')
            assert page.evaluate('window.launches') == 1
            if outcome == "started":
                page.evaluate('window.running = true')
                page.clock.run_for(2100)
                assert button.get_attribute('aria-label') == 'Stop game'
                assert not button.is_disabled()
                assert page.evaluate('window.afterLaunches') == 1
                page.clock.run_for(30100)
                assert page.get_by_text('Game launch timed out', exact=True).count() == 0
                assert page.evaluate('window.afterLaunches') == 1
                button.evaluate('(button) => button.click()')
                page.wait_for_function("!window.running", polling=100)
                assert button.get_attribute('aria-label') == 'Launch game'
                return
            page.clock.run_for(30100)
            assert page.get_by_text('Game launch timed out', exact=True).is_visible()
            assert not button.is_disabled()
            assert page.evaluate('window.launches') == 1
            page.evaluate('window.running = true')
            page.clock.run_for(2100)
            assert button.get_attribute('aria-label') == 'Stop game'
            # A late launch is detected even after the timeout was dismissed.
            assert page.evaluate('window.afterLaunches') == 1
        finally:
            browser.close()

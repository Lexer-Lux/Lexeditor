"""Verify automatic startup discovery and current FF7 Steam detection."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game_installation import GameInstallationManager  # noqa: E402
from desktop_host import HostApi  # noqa: E402
from games.ff7.plugin import PLUGIN as FF7_PLUGIN  # noqa: E402
from plugin_api import GameInstallSpec, GamePlugin  # noqa: E402


def wait_for_scans(manager: GameInstallationManager, plugin_ids: tuple[str, ...]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not any(manager.snapshot(plugin_id)["scanInProgress"] for plugin_id in plugin_ids):
            return
        time.sleep(0.05)
    raise AssertionError("Automatic installation scans did not finish")


def fake_plugin(plugin_id: str, root: Path, prepare=None) -> GamePlugin:
    return GamePlugin(
        plugin_id=plugin_id,
        name=plugin_id.title(),
        subtitle=plugin_id.upper(),
        description="Automatic discovery verifier",
        accent="#ffffff",
        check=lambda: [],
        launch=lambda: 0,
        installation=GameInstallSpec(
            root_env=f"LEXEDITOR_{plugin_id.upper()}_ROOT",
            required_paths=("required.bin",),
            steam_app_id="999999999",
            install_dir_names=(plugin_id,),
            default_roots=(root,),
            prepare=prepare,
        ),
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-auto-discovery-", ignore_cleanup_errors=True) as temp_name:
        temp = Path(temp_name)
        installed_root = temp / "installed-game"
        installed_root.mkdir()
        (installed_root / "required.bin").write_bytes(b"verified")
        config = temp / "game-installations.json"
        prepare_calls: list[Path] = []

        def prepare(root: Path, _data: Path, progress) -> dict:
            prepare_calls.append(root)
            progress(1, 1, "Prepared")
            return {"prepared": True}

        plugins = {
            "installed": fake_plugin("installed", installed_root, prepare),
            "missing": fake_plugin("missing", temp / "missing-game"),
        }
        manager = GameInstallationManager(
            plugins,
            config_path=config,
            data_root=temp / "data",
            auto_scan=True,
        )
        wait_for_scans(manager, tuple(plugins))
        installed = manager.snapshot("installed")
        missing = manager.snapshot("missing")
        assert installed["status"] == "added" and installed["canOpen"], installed
        assert Path(installed["root"]) == installed_root.resolve(), installed
        assert missing["status"] == "not-added" and not missing["canOpen"], missing
        assert not prepare_calls, "Startup discovery performed expensive plugin preparation"
        saved = json.loads(config.read_text(encoding="utf-8"))
        assert saved["games"]["installed"]["root"] == str(installed_root.resolve()), saved
        assert "missing" not in saved["games"], saved
        manager.prepare("installed")
        assert prepare_calls == [installed_root.resolve()], prepare_calls
        assert manager.snapshot("installed")["canOpen"]

        specification = FF7_PLUGIN.installation
        assert specification is not None
        assert specification.steam_app_id == "3837340", specification
        assert specification.required_paths == (
            "FFVII_LAUNCHER.exe",
            "ff7/workingdir/data/lang-en/kernel/kernel.bin",
        ), specification
        assert specification.install_dir_names == ("FINAL FANTASY VII Steam Edition",), specification

        ff7_config = temp / "ff7-installations.json"
        ff7_manager = GameInstallationManager(
            {"ff7": FF7_PLUGIN},
            config_path=ff7_config,
            data_root=temp / "ff7-data",
            auto_scan=True,
        )
        wait_for_scans(ff7_manager, ("ff7",))
        ff7 = ff7_manager.snapshot("ff7")
        assert ff7["status"] == "added" and ff7["canOpen"], ff7
        assert Path(ff7["root"]) / "FFVII_LAUNCHER.exe" == Path(
            r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII Steam Edition\FFVII_LAUNCHER.exe"
        ), ff7
        assert (Path(ff7["root"]) / "FFVII_LAUNCHER.exe").is_file(), ff7
        assert (Path(ff7["root"]) /
                "ff7/workingdir/data/lang-en/kernel/kernel.bin").is_file(), ff7
        host = HostApi(
            {"ff7": FF7_PLUGIN},
            installation_manager=ff7_manager,
            auto_scan=False,
        )
        opened = host.open_plugin("ff7")
        try:
            assert opened["identity"]["pluginId"] == "ff7", opened
        finally:
            host.stop()
        print({
            "newInstallDiscovered": installed["root"],
            "missingSettled": missing["status"],
            "ff7Discovered": ff7["root"],
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

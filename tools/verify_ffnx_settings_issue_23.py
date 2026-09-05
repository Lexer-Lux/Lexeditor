"""Temporary-directory contract for Lexeditor issue 23."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8.ffnx_manager import ensure_ffnx, status  # noqa: E402
from settings_manager import SettingsStore  # noqa: E402


def make_archive(path: Path, marker: bytes) -> str:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AF3DN.P", marker * (1_100_000 // len(marker) + 1))
        archive.writestr("AF4DN.P", b"driver-4")
        archive.writestr("FFNx.toml", 'direct_mode_path = "direct"\nrenderer_backend = 0\n')
        archive.writestr("COPYING.TXT", "GNU GENERAL PUBLIC LICENSE\n")
        archive.writestr("hext/ff8/en/.keep", "")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release(version: str, digest: str) -> dict:
    return {
        "tag_name": version,
        "published_at": "2026-08-29T00:00:00Z",
        "assets": [{
            "name": f"FFNx-Steam-v{version}.0.zip",
            "browser_download_url": f"https://example.invalid/{version}.zip",
            "digest": f"sha256:{digest}",
        }],
    }


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    chooser = (ROOT / "ui" / "chooser.html").read_text(encoding="utf-8")
    desktop = (ROOT / "desktop_host.py").read_text(encoding="utf-8")
    assert "Update check frequency" in framework
    assert "Menu bar height" in framework
    assert "lex-setting-default-control" in framework
    assert 'options.settings || openSettings' in framework
    assert "chooser-settings" in chooser
    assert "def save_lexeditor_settings" in desktop

    with tempfile.TemporaryDirectory(prefix="lexeditor-ffnx-contract-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        game = root / "game"; direct = root / "project" / "direct"
        game.mkdir(); direct.mkdir(parents=True)
        (game / "FF8_EN.exe").write_bytes(b"game")
        vanilla = b"vanilla-driver"
        (game / "AF3DN.P").write_bytes(vanilla)
        (game / "AF4DN.P").write_bytes(b"vanilla-driver-4")
        archive1 = root / "one.zip"; digest1 = make_archive(archive1, b"one")
        state_path = root / "state.json"; cache = root / "cache"; backups = root / "backups"
        settings = SettingsStore(root / "settings.json")
        settings.save("daily")

        def download_one(_url: str, target: Path, _progress) -> None:
            shutil.copy2(archive1, target)

        first = ensure_ffnx(
            game, direct, settings=settings, state_path=state_path,
            cache_root=cache, backup_root=backups,
            fetch_json=lambda _url: release("1.0", digest1), fetch_file=download_one,
            game_running=lambda: False,
        )
        assert first["installed"] and first["version"] == "1.0"
        assert (game / "COPYING.TXT").is_file()
        assert any(path.read_bytes() == vanilla for path in backups.rglob("AF3DN.P"))
        config = game / "FFNx.toml"
        config_text = config.read_text(encoding="utf-8")
        assert 'direct_mode_path = "lexeditor-direct"' in config_text
        assert (game / "lexeditor-direct").resolve() == direct.resolve()
        assert (direct.parent / "hext").resolve().as_posix() in config_text

        config.write_text(config.read_text(encoding="utf-8") + "custom_flag = true\n", encoding="utf-8")
        settings.save("every-launch")
        archive2 = root / "two.zip"; digest2 = make_archive(archive2, b"two")

        def download_two(_url: str, target: Path, _progress) -> None:
            shutil.copy2(archive2, target)

        second = ensure_ffnx(
            game, direct, settings=settings, state_path=state_path,
            cache_root=cache, backup_root=backups,
            fetch_json=lambda _url: release("2.0", digest2), fetch_file=download_two,
            game_running=lambda: False,
        )
        assert second["installed"] and second["version"] == "2.0"
        config_text = config.read_text(encoding="utf-8")
        assert "custom_flag = true" in config_text
        assert (direct.parent / "hext").resolve().as_posix() in config_text

        settings.save("daily")
        config.write_text(
            config_text.replace(
                (direct.parent / "hext").resolve().as_posix(), "hext",
            ),
            encoding="utf-8",
        )
        ensure_ffnx(
            game, direct, settings=settings, state_path=state_path,
            cache_root=cache, backup_root=backups,
            fetch_json=lambda _url: (_ for _ in ()).throw(AssertionError("not due")),
            game_running=lambda: False,
        )
        assert (direct.parent / "hext").resolve().as_posix() in config.read_text(encoding="utf-8")

        offline_game = root / "offline-game"; offline_game.mkdir()
        (offline_game / "FF8_EN.exe").write_bytes(b"game")
        offline_state = root / "offline-state.json"
        offline = ensure_ffnx(
            offline_game, direct, settings=settings, state_path=offline_state,
            cache_root=root / "offline-cache", backup_root=root / "offline-backups",
            fetch_json=lambda _url: (_ for _ in ()).throw(OSError("offline")),
            game_running=lambda: False,
        )
        assert not offline["installed"]
        assert "Setup failed: offline" in json.loads(offline_state.read_text())["lastResult"]

        assert status(game, state_path)["managed"]
        assert settings.snapshot()["updateCheckFrequency"] == "daily"

    with tempfile.TemporaryDirectory(prefix="lexeditor-user-defaults-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        defaults = root / "defaults.json"
        defaults.write_text(json.dumps({
            "updateCheckFrequency": "daily",
            "developerMode": False,
            "hoverableAltClick": False,
            "selectionHoldMs": 650,
            "tableRowsPerPage": 15,
            "panelGapPercent": 1.0,
            "residentHandleWidthPercent": 5.0,
            "mainMenuHeightPercent": 9.0,
            "absentGameDesaturationPercent": 75.0,
            "globalMessageRarity": 3.0,
            "loadingTransitionMinimumSeconds": 1.5,
        }), encoding="utf-8")
        store = SettingsStore(root / "settings.json", defaults)
        store.save("daily", main_menu_height_percent=10.0)
        store.save_lexer_defaults({"mainMenuHeightPercent": 12.0})
        snapshot = store.snapshot()
        assert snapshot["mainMenuHeightPercent"] == 10.0, snapshot
        assert snapshot["defaultValues"]["mainMenuHeightPercent"] == 12.0, snapshot
        store.save_lexer_defaults({"absentGameDesaturationPercent": 140.0})
        snapshot = store.snapshot()
        assert snapshot["absentGameDesaturationPercent"] == 100.0, snapshot
        assert snapshot["defaultValues"]["absentGameDesaturationPercent"] == 100.0, snapshot
        store.save_lexer_defaults({"globalMessageRarity": 0.25})
        snapshot = store.snapshot()
        assert snapshot["globalMessageRarity"] == 1.0, snapshot
        assert snapshot["defaultValues"]["globalMessageRarity"] == 1.0, snapshot
        store.save_lexer_defaults({"loadingTransitionMinimumSeconds": 14.0})
        snapshot = store.snapshot()
        assert snapshot["loadingTransitionMinimumSeconds"] == 10.0, snapshot
        assert snapshot["defaultValues"]["loadingTransitionMinimumSeconds"] == 10.0, snapshot

    print("Shared settings and verified FFNx install/update contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

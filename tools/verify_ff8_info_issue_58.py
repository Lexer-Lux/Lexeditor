"""API, readiness, and host contracts for the FF8 Info page (GitHub #58)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop_host import HostApi  # noqa: E402
from games.ff8 import extractor, paths, server  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_readiness() -> None:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-ready-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        target = root / "baseline" / "en" / "main" / "kernel.bin"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"kernel")
        manifest = {
            "format": extractor.BASELINE_FORMAT,
            "source": extractor.source_fingerprint(),
            "files": {"en/main/kernel.bin": {"size": 6}},
        }
        extractor.manifest_path(root).write_text(json.dumps(manifest), encoding="utf-8")
        require(extractor.baseline_ready(root),
                "A valid manifest-relative FF8 baseline is reported missing")
        target.unlink()
        require(not extractor.baseline_ready(root),
                "A baseline with a missing manifest file is reported ready")


def verify_dashboard() -> None:
    payload = server.dashboard()
    require(payload["game"]["root"] == str(paths.GAME_ROOT),
            "The dashboard does not expose the configured FF8 game root")
    require(payload["baseline"]["ready"],
            "The live extracted FF8 baseline is falsely reported unavailable")
    require(payload["runtime"]["installed"] and payload["runtime"]["version"],
            "The installed FFNx version is missing from the dashboard")
    require("Project" not in payload and "paths" not in payload,
            "The dashboard still exposes internal/project path filler")


def verify_host_folder_action() -> None:
    class Installations:
        def snapshot(self, plugin_id: str) -> dict:
            require(plugin_id == "ff8", "The host requested the wrong plugin")
            return {"root": str(paths.GAME_ROOT)}

    host = HostApi.__new__(HostApi)
    host._plugins = {"ff8": object()}
    host._installations = Installations()
    with patch("os.startfile") as start:
        result = host.open_game_folder("ff8")
        start.assert_called_once_with(str(paths.GAME_ROOT.resolve()))
    require(result["opened"] and result["path"] == str(paths.GAME_ROOT.resolve()),
            "The host did not report the configured game folder")


def verify_source() -> None:
    editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    framework = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
    # The page now uses the shared information panel rather than bespoke cards.
    require('lex-information-panel ff8-information' in editor,
            "The FF8 Info page does not use the shared information panel")
    require(all(f'title:"{name}"' in editor
                for name in ("GAME", "GAME DATA", "FFNX")),
            "The FF8 Info page has no game, baseline, and FFNx sections")
    require('openGameFolder("ff8")' in editor,
            "The folder button does not use the plugin-scoped host action")
    require("folderIcon" in framework and "openGameFolder" in framework,
            "The shared framework has no folder icon and host action")
    require("FF8 plugin and runtime status" not in editor,
            "The old toolbar caption remains")


def main() -> None:
    verify_readiness()
    verify_dashboard()
    verify_host_folder_action()
    verify_source()
    print("FF8 Info issue #58 contracts passed")


if __name__ == "__main__":
    main()

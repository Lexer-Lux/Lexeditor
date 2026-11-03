"""Stage source mods through the real adapter for an isolated native-loader probe.

The selected installation is read-only. Writes are confined to a data directory
under %TEMP%/lexeditor-dev, never the player's native data or installation. The
process probe is stubbed only inside that verified private-data boundary, so a
running player's separate game cannot prevent preparing a headless fixture.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.native_source_mods import NativeSourceModAdapter
from plugins.kings_field3.model import MODEL


def prepare(game_root: Path, data_root: Path, mods: list[Path]) -> dict:
    game_root, data_root = game_root.resolve(), data_root.resolve()
    scratch = (Path(tempfile.gettempdir()) / "lexeditor-dev").resolve()
    player = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Verdite3").resolve()
    if data_root == scratch or not data_root.is_relative_to(scratch) or data_root == player:
        raise ValueError("The fixture data directory must be below %TEMP%/lexeditor-dev")
    if data_root == game_root or data_root.is_relative_to(game_root):
        raise ValueError("The fixture data directory must be outside the selected installation")
    data_root.mkdir(parents=True, exist_ok=True)
    settings_path = data_root / "settings.json"
    settings_before = settings_path.read_bytes() if settings_path.exists() else None
    with patch.dict(os.environ, {MODEL.native["dataEnv"]: str(data_root)}), \
            patch("core.native_port_settings.live_processes", return_value=[]):
        adapter = NativeSourceModAdapter(MODEL)
        native = data_root / "mods"
        native.mkdir(exist_ok=True)
        sources = []
        for path in mods:
            folder = native / ("lexeditor-" + path.name)
            shutil.copytree(path, folder)
            sources.append(folder)
        result = adapter.activate(sources, game_root)
        settings_after = settings_path.read_bytes() if settings_path.exists() else None
        if settings_after != settings_before:
            raise AssertionError("Source-mod deployment changed the fixture's runtime settings.json")
        result["interface"] = str(data_root / "interface.ini")
        result["settingsJsonTouched"] = False
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--mod", type=Path, action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(prepare(args.game_root, args.data_root, args.mod), indent=2))


if __name__ == "__main__":
    main()

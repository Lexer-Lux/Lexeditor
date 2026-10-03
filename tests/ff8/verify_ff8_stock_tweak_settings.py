"""Stock-cap settings persist and compose through fixture tweak mods.

Only comment payloads are generated; gameplay patch tests belong to the mods.
The library, trust store, game and runtime all live in a temporary directory.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import script_mods
from plugins.ff8 import gameplay_settings as settings
from plugins.ff8.ffnx_issue_51 import runtime_config


def make(library, mod_id, fields):
    root = library / mod_id
    (root / "script").mkdir(parents=True)
    (root / "script/__init__.py").write_text("", encoding="utf-8")
    (root / "script/tweak.py").write_text(
        'def build(settings, context):\n'
        f'    return {{context.HEXT + "/{mod_id}.txt": "# fixture\\n"}}\n', encoding="utf-8")
    (root / "mod.json").write_text(json.dumps({"id": mod_id, "name": mod_id,
        "enabled": False, "script": {"version": 1}}), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps({"fields": fields}), encoding="utf-8")
    script_mods.set_trusted(root, True)


def run():
    with tempfile.TemporaryDirectory(prefix="ff8-stock-settings-") as directory:
        root = Path(directory)
        project, game, runtime = root / "project", root / "game", root / "runtime"
        library = project / ".lexeditor-mods"
        game.mkdir()
        with patch.dict(os.environ, {script_mods.TRUST_ENV: str(root / "trust.json")}):
            make(library, "max-spell", [{"key": "limit", "type": "int", "min": 1, "max": 255, "default": 100}])
            for mod_id in ("no-magic-consumption", "drops-after-mug"):
                make(library, mod_id, [])
            make(library, settings.SHARED_MAGIC_MOD, [])
            settings.initialize_project(project)
            assert all(not row["enabled"] for row in settings.load(project, game)["tweaks"])
            for cap in (1, 2, 10, 99, 100, 127, 128, 150, 254, 255):
                for shared in (False, True):
                    for consume in (False, True):
                        enabled = {"max-spell": True, "drops-after-mug": True, "no-magic-consumption": consume,
                                   settings.SHARED_MAGIC_MOD: shared}
                        changes = {key: {"enabled": value} for key, value in enabled.items()}
                        changes["max-spell"]["values"] = {"limit": cap}
                        settings.save({"tweaks": changes},
                                      game, project, runtime_root=runtime)
                        saved = settings.load(project, game)
                        assert {row["id"]: row["enabled"] for row in saved["tweaks"]} == enabled
                        assert next(row for row in saved["tweaks"] if row["id"] == "max-spell")["values"]["limit"] == cap
                        config = tomllib.loads(runtime_config.path(project).read_text())
                        assert config["sharedMagicInventory"] is shared and config["magicStockLimit"] == cap
                        for key, on in enabled.items():
                            patches = settings.materialized_tweak_patches(runtime, {key})
                            assert len(patches) == int(on)
                            if on:
                                assert patches[0].read_text() == "# fixture\n"
            for cap in (0, 256, True, "100"):
                try:
                    settings.save({"tweaks": {"max-spell": {"values": {"limit": cap}}}}, game, project, runtime_root=runtime)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"Invalid stock cap accepted: {cap!r}")
            settings.save({"tweaks": {key: {"enabled": False} for key in enabled}}, game, project, runtime_root=runtime)
            assert tomllib.loads(runtime_config.path(project).read_text())["magicStockLimit"] == 100
            assert tomllib.loads(runtime_config.path(project).read_text())["sharedMagicInventory"] is False
            assert not settings.materialized_tweak_patches(runtime, set(enabled))
            assert script_mods.values(library / "max-spell")["limit"] == 255
            assert list(game.iterdir()) == []
            # The no-consumption mod owns the patch; the driver's duplicate
            # implementation must remain off when resetting managed switches.
            assert settings.FFNX_DEFAULTS["enable_ff8_no_magic_consumption"] is False
    print("PASS: 40 isolated stock-cap saves/compositions, strict bounds and disabled reset")


if __name__ == "__main__":
    run()

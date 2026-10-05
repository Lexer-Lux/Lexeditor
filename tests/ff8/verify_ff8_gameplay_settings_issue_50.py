"""Gameplay settings lifecycle after tweaks moved into library mods.

Patch algorithms are tested with their owning mods. This check covers the
editor's strict inputs, vanilla defaults, composition, cleanup and rollback.
No installed game or real mod library is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import script_mods
from plugins.ff8 import gameplay_settings as settings, runtime_layout
from plugins.ff8.ffnx_issue_51 import runtime_config
from tests.ff8.verify_ff8_iroj_loader import _archive


def make_mod(library: Path) -> Path:
    mod = library / "Fixture"
    (mod / "script").mkdir(parents=True)
    (mod / "script" / "__init__.py").write_text("", encoding="utf-8")
    (mod / "script" / "tweak.py").write_text(
        'def build(settings, context):\n'
        '    return {context.HEXT + "/Fixture.txt": "# amount=" + str(settings["amount"]) + "\\n"}\n',
        encoding="utf-8",
    )
    (mod / "mod.json").write_text(json.dumps({
        "id": "fixture", "name": "Fixture", "enabled": False, "script": {"version": 1},
    }), encoding="utf-8")
    (mod / "settings.schema.json").write_text(json.dumps({"fields": [
        {"key": "amount", "type": "int", "min": 1, "max": 255, "default": 100},
    ]}), encoding="utf-8")
    script_mods.set_trusted(mod, True)
    return mod


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ff8-settings-lifecycle-") as name:
        root = Path(name)
        project, game = root / "project", root / "game"
        library = project / ".lexeditor-mods"
        library.mkdir(parents=True)
        game.mkdir()
        with patch.dict(os.environ, {script_mods.TRUST_ENV: str(root / "trust.json")}):
            mod = make_mod(library)
            legacy = [settings.patch_path(project), settings.legacy_patch_path(project),
                      settings.obsolete_english_patch_path(project)]
            for path in legacy:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("obsolete", encoding="utf-8")
            settings.initialize_project(project)
            assert not any(path.exists() for path in legacy)
            loaded = settings.load(project, game)
            assert loaded["gfSpellbooksEnabled"] is False
            assert loaded["sharedMagicInventory"] is False
            assert loaded["singleGf"] is False
            assert len(loaded["tweaks"]) == 1 and loaded["tweaks"][0]["enabled"] is False
            assert json.loads(settings.settings_path(project).read_text()) == {"gfSpellbooksEnabled": False}

            result = settings.save({"tweaks": {"fixture": {
                "enabled": True, "values": {"amount": 200},
            }}}, game, project)
            assert result["saved"] == 1
            assert script_mods.values(mod) == {"amount": 200}
            runtime = project / ".lexeditor-runtime"
            generated = settings.materialized_tweak_patches(runtime, {"fixture"})
            assert len(generated) == 1 and generated[0].read_text() == "# amount=200\n"
            assert list(game.iterdir()) == [], "Saving a mod must not write the game"
            assert not any(path.exists() for path in legacy)

            # configure() also writes metadata for ordinary archive mods. Its
            # sidecar must roll back with the tweak switches on a later error.
            archive = library / "packed.iroj"
            _archive(archive, [("mod.xml", b"<ModInfo><ID>packed</ID><Name>Packed</Name></ModInfo>", 0)])
            sidecar = runtime_layout._metadata_path(archive)
            sidecar.write_text('{"enabled": false, "order": 9999}\n', encoding="utf-8")

            watched = [mod / "mod.json", mod / "settings.json", settings.settings_path(project),
                       runtime_config.path(project), generated[0], sidecar]
            before = {path: path.read_bytes() for path in watched}
            for invalid in (
                {"gfSpellbooksEnabled": 1}, {"sharedMagicInventory": "true"},
                {"tweaks": []}, {"tweaks": {"unknown": {"enabled": True}}},
                {"tweaks": {"fixture": {"enabled": 1}}},
                {"tweaks": {"fixture": {"other": True}}},
                {"tweaks": {"fixture": {"values": {"amount": 256}}}},
                {"tweaks": {"fixture": {"values": {"unknown": 1}}}},
            ):
                try:
                    settings.save(invalid, game, project)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"Accepted invalid request: {invalid!r}")
                assert {path: path.read_bytes() for path in watched} == before

            # Failure after building changed values must rebuild the old
            # output, not merely restore settings JSON.
            real_atomic = settings._atomic_text
            def fail_settings(target, text):
                if target == settings.settings_path(project):
                    raise OSError("injected settings failure")
                return real_atomic(target, text)
            with patch.object(settings, "_atomic_text", side_effect=fail_settings):
                try:
                    settings.save({"tweaks": {"fixture": {"enabled": True, "values": {"amount": 42}}}}, game, project)
                except OSError as error:
                    assert "injected settings failure" in str(error)
                else:
                    raise AssertionError("Injected failure was swallowed")
            assert {path: path.read_bytes() for path in watched} == before
            assert (mod / "hext/ff8/en_nv/Fixture.txt").read_text() == "# amount=200\n"

            settings.save({"tweaks": {"fixture": {"enabled": False}}}, game, project)
            assert not generated[0].exists()
            assert script_mods.values(mod) == {"amount": 200}
            assert settings.load(project, game)["tweaks"][0]["enabled"] is False

            config = game / "FFNx.toml"
            config.write_text('custom_option = 17\n', encoding="utf-8")
            for enabled in (True, False):
                values = {**settings.FFNX_DEFAULTS, "enable_ff8_modern_controls": enabled,
                          "enable_ff8_party_switch": enabled}
                settings._set_ffnx_keys(config, values)
                text = config.read_text()
                assert "custom_option = 17" in text
                for key in values:
                    assert text.count(key + " =") == 1
                for key in ("enable_ff8_modern_controls", "enable_ff8_party_switch"):
                    assert f"{key} = {str(enabled).lower()}" in text
    print("PASS: FF8 tweak-mod defaults, validation, composition, cleanup and rollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

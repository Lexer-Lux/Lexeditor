"""FFNx effective Hext path and runtime-log contract for FF8 gameplay patches."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import ffnx_manager, gameplay_settings  # noqa: E402


def main() -> int:
    upstream = ROOT / "_scratch" / "ffnx-upstream" / "src" / "cfg.cpp"
    source = upstream.read_text(encoding="utf-8")
    assert 'hext_patching_path += "/ff8"' in source
    assert 'hext_patching_path += "/en"' in source
    assert 'case VERSION_FF8_12_US_NV:' in source
    assert 'hext_patching_path += "/en_nv"' in source

    with tempfile.TemporaryDirectory(prefix="lexeditor-ffnx-gameplay-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        project = root / "project"
        runtime = root / "runtime"
        game = root / "game"
        game.mkdir()
        config = game / "FFNx.toml"
        config.write_text(
            'hext_patching_path = "hext"\n'
            'direct_mode_path = "direct"\n',
            encoding="utf-8",
        )
        ffnx_manager._set_project_paths(config, runtime / "direct")
        config_text = config.read_text(encoding="utf-8")
        assert 'direct_mode_path = "lexeditor-direct"' in config_text
        assert (game / "lexeditor-direct").resolve() == (runtime / "direct").resolve()
        assert (game / "lexeditor-direct").resolve() != (project / "direct").resolve()
        assert f'hext_patching_path = "{(runtime / "hext").as_posix()}"' in config_text
        for folder in ("textures", "sfx", "voice", "ambient", "override", "save"):
            assert (game / f"lexeditor-{folder}").resolve() == (runtime / folder).resolve()
        assert 'mod_path = "lexeditor-textures"' in config_text
        assert 'external_sfx_path = "lexeditor-sfx"' in config_text
        assert 'external_voice_path = "lexeditor-voice"' in config_text
        assert 'external_ambient_path = "lexeditor-ambient"' in config_text
        assert 'override_path = "lexeditor-override"' in config_text
        assert 'save_path = "lexeditor-save"' in config_text
        assert "use_external_sfx = false" in config_text
        (runtime / "sfx" / "1.ogg").write_bytes(b"audio")
        ffnx_manager._set_project_paths(config, runtime / "direct")
        assert "use_external_sfx = true" in config.read_text(encoding="utf-8")

        source_patch = project / "hext" / "ff8" / "en_nv" / gameplay_settings.PATCH_NAME
        expected = runtime / "hext" / "ff8" / "en_nv" / gameplay_settings.PATCH_NAME
        obsolete = project / "hext" / gameplay_settings.PATCH_NAME
        wrong_edition = project / "hext" / "ff8" / "en" / gameplay_settings.PATCH_NAME
        assert gameplay_settings.patch_path(project) == source_patch
        assert gameplay_settings.runtime_patch_path(runtime) == expected
        assert source_patch != expected, "editable mod and active runtime were collapsed again"
        assert gameplay_settings.legacy_patch_path(project) == obsolete
        assert gameplay_settings.obsolete_english_patch_path(project) == wrong_edition

        expected.parent.mkdir(parents=True)
        expected.write_text("# test\n", encoding="utf-8")
        gameplay_settings._last_activation_ns = time.time_ns()
        log = game / "FFNx.log"
        log.write_text(
            f"[00000000] TRACE: Applied Hext patch: {expected}\n",
            encoding="utf-8",
        )
        current = time.time_ns() + 2_000_000_000
        os.utime(log, ns=(current, current))
        loaded = gameplay_settings.runtime_status(
            game, project, runtime_root=runtime, game_running=lambda: True,
        )
        assert loaded["loaded"] is True, loaded
        assert loaded["logReady"] is True, loaded

        log.write_text(
            "[00000000] TRACE: Metadata: Initializing manager.\n",
            encoding="utf-8",
        )
        os.utime(log, ns=(current, current))
        incomplete = gameplay_settings.runtime_status(
            game, project, runtime_root=runtime, game_running=lambda: True,
        )
        assert incomplete["loaded"] is False, incomplete
        assert incomplete["logReady"] is False, incomplete
        assert incomplete["startupIncomplete"] is True, incomplete

        stopped = gameplay_settings.runtime_status(
            game, project, runtime_root=runtime, game_running=lambda: False,
        )
        assert stopped["loaded"] is False, stopped
        assert stopped["logReady"] is True, stopped
        assert "before FFNx reached Hext" in stopped["message"], stopped

        log.write_text(
            f"[00000000] TRACE: Applied Hext patch: {obsolete}\n",
            encoding="utf-8",
        )
        os.utime(log, ns=(current, current))
        wrong = gameplay_settings.runtime_status(
            game, project, runtime_root=runtime, game_running=lambda: True,
        )
        assert wrong["loaded"] is False, wrong
        assert wrong["logReady"] is False, wrong
        assert wrong["startupIncomplete"] is True, wrong

        wrong_stopped = gameplay_settings.runtime_status(
            game, project, runtime_root=runtime, game_running=lambda: False,
        )
        assert wrong_stopped["loaded"] is False, wrong_stopped
        assert wrong_stopped["logReady"] is True, wrong_stopped
        assert "did not apply" in wrong_stopped["message"], wrong_stopped

    print("FFNx effective Hext path and exact runtime log marker passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

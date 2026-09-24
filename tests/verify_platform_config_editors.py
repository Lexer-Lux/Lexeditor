"""Verify typed and lossless FFNx and Memoria configuration edits."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_config import load_config, save_config


FFNX = """# FFNx config file\n\n## DISPLAY\n#[FULLSCREEN]\n# If off, it will run in window mode.\nfullscreen = false\n\n#[RENDERING BACKEND]\n# Available choices are:\n# - 0: Auto\n# - 3: Direct3D11\nrenderer_backend = 0\n\n#[RESOLUTION]\n# Valid range: 0..7680\nwindow_size_x = 0\n\n#[MOD EXTENSIONS]\nmod_ext = [\"dds\", \"png\"]\n"""

MEMORIA = """; Memoria configuration\n[Graphics]\n; Enables widescreen rendering.\nEnabled = 1\n; 0: Off\n; 1: Fast\n; 2: Best\nMode = 1\n; Valid range: 30..240\nFrameRate = 60\n\n[Audio]\nVolume = 0.5\n"""


def fields(payload: dict) -> dict:
    return {field["id"]: field for section in payload["sections"] for field in section["fields"]}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lexeditor-platform-config-", ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        ffnx = root / "FFNx.toml"
        ffnx.write_text(FFNX, encoding="utf-8", newline="")
        before = ffnx.read_text(encoding="utf-8")
        payload = load_config(ffnx, "FFNx", "toml")
        parsed = fields(payload)
        assert parsed["fullscreen"]["kind"] == "boolean"
        assert parsed["renderer_backend"]["kind"] == "enum"
        assert parsed["window_size_x"]["maximum"] == 7680
        result = save_config(ffnx, "FFNx", "toml", payload["sha256"], {
            "fullscreen": True, "renderer_backend": 3, "window_size_x": 1920,
            "mod_ext": ["dds", "png", "webp"],
        })
        after = ffnx.read_text(encoding="utf-8")
        assert result["saved"] == 4 and ffnx.with_name("FFNx.toml.lexeditor.bak").is_file()
        assert "# If off, it will run in window mode." in after
        assert "fullscreen = true" in after and "renderer_backend = 3" in after
        assert "mod_ext = [\"dds\", \"png\", \"webp\"]" in after
        assert ffnx.with_name("FFNx.toml.lexeditor.bak").read_text(encoding="utf-8") == before
        try:
            save_config(ffnx, "FFNx", "toml", payload["sha256"], {"window_size_x": 3000})
        except RuntimeError:
            pass
        else:
            raise AssertionError("A stale FFNx write was accepted")

        memoria = root / "Memoria.ini"
        memoria.write_text(MEMORIA, encoding="utf-8", newline="")
        payload = load_config(memoria, "Memoria", "ini")
        parsed = fields(payload)
        assert parsed["Graphics.Enabled"]["kind"] == "boolean"
        assert parsed["Graphics.Mode"]["kind"] == "enum"
        assert parsed["Graphics.FrameRate"]["maximum"] == 240
        result = save_config(memoria, "Memoria", "ini", payload["sha256"], {
            "Graphics.Enabled": False, "Graphics.Mode": 2, "Graphics.FrameRate": 120,
            "Audio.Volume": 0.25,
        })
        after = memoria.read_text(encoding="utf-8")
        assert result["saved"] == 4
        assert "; Enables widescreen rendering." in after
        assert "Enabled = 0" in after and "Mode = 2" in after and "FrameRate = 120" in after
        assert "Volume = 0.25" in after
        print("platform config editors: PASS")


if __name__ == "__main__":
    main()

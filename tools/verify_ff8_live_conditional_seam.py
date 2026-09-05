"""Prove the exact FFNx seams needed by Lexeditor live conditional folders."""

from pathlib import Path

import verify_ff8_live_variant_composer


ROOT = Path(__file__).resolve().parents[1]
FFNX = ROOT / "_scratch" / "issue51-ffnx-build-c056db2"
JUNCTION = ROOT / "_scratch" / "junction-viii"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    ff8_file = (FFNX / "src" / "ff8" / "file.cpp").read_text(encoding="utf-8")
    ff8_hooks = (FFNX / "src" / "ff8_opengl.cpp").read_text(encoding="utf-8")
    audio = (FFNX / "src" / "audio.cpp").read_text(encoding="utf-8")
    junction_vfile = (JUNCTION / "AppWrapper" / "VFile.cs").read_text(encoding="utf-8-sig")
    junction_vars = (JUNCTION / "AppWrapper" / "RuntimeVar.cs").read_text(encoding="utf-8-sig")

    require("bool set_direct_path(" in ff8_file, "FFNx Direct Mode resolver is missing")
    require("if (set_direct_path(fullpath, direct_path" in ff8_file,
            "archive-backed reads do not pass through set_direct_path")
    require("replace_function(ff8_externals.fopen, ff8_fopen)" in ff8_hooks,
            "FF8's low-level fopen replacement is missing")
    require("replace_function(common_externals.open_file, ff8_open_file)" in ff8_hooks,
            "FF8's archive/open-file replacement is missing")
    require("bool NxAudioEngine::getFilenameFullPath" in audio and
            "if (fileExists(_out))" in audio,
            "external SFX/voice/ambient filename seam is missing")

    require("re-evaluate" in junction_vfile and
            "of.CFolder.IsActive(of.CName)" in junction_vfile,
            "Junction evidence no longer evaluates a condition at file-read time")
    for token in ("VarType.Byte", "VarType.Short", "VarType.Int",
                  "VarType.FFString", "VarType.Counter", "VarType.Random"):
        require(token in junction_vars, f"Junction runtime source lost {token}")

    # Run the bounded composer contract. This proves complete final variants,
    # semantic preservation, priority collision handling, hard limits, atomic
    # output, and the absence of raw-candidate runtime redirection.
    require(verify_ff8_live_variant_composer.main() == 0,
            "bounded live-variant behavior failed")

    # Guard the architecture decision. Junction is evidence for condition
    # syntax only. Lexeditor remains the loader and composition owner.
    layout = (ROOT / "games" / "ff8" / "runtime_layout.py").read_text(encoding="utf-8")
    require('"liveConditionalRoutes": live_routes' in layout and
            "LIVE_CONDITIONAL_MANIFEST" in layout,
            "composition no longer emits its bounded runtime manifest")
    require("_precompose_live_routes(" in layout and
            '"ready: final variants precomposed"' in layout,
            "live routes are not bounded complete compositions")
    require('"candidates": []' not in layout and
            'variant["asset"] = asset' in layout,
            "raw package candidates could be exposed as runtime targets")
    require("MapFile(" not in layout and "ModLoadOrder" not in layout,
            "Junction loader behavior leaked into Lexeditor composition")

    print("FF8 live-condition lookup seams and fail-closed composition boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Issue #481: deterministic smooth-HP source and interpolation checks.

No game process or installation is touched.  --compile executes a tiny harness
against the production interpolation header with the compiler already present
in the caller's environment.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_hp_colors.h"
SOURCE = ROOT / "games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp"
PREPARE = ROOT / "tools/prepare_ff8_native_build.py"
SETTINGS = ROOT / "games/ff8/gameplay_settings.py"
EDITOR = ROOT / "games/ff8/editor.html"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def static_contract() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    prepare = PREPARE.read_text(encoding="utf-8")
    settings = SETTINGS.read_text(encoding="utf-8")
    editor = EDITOR.read_text(encoding="utf-8")
    for token in (
        "lexeditor_ff8_hp_should_tint",
        "g_better_hp_runtime_ready",
        "FF8_US_VERSION",
        "0x004B17D5",
        "0x004B1100",
        "0x004B127B",
        "kCharacterWidget = 0x004C0780",
        "kHpNumberRenderer = 0x004A3530",
        "stack[3] != g_menu_hp.packed_position",
        "unreplace_function(g_hp_number_replace_id)",
        "rereplace_function(g_hp_number_replace_id)",
        "TEXTCOLOR_WHITE",
        "TEXTCOLOR_YELLOW",
        "v.r != 255 || v.g != 255 || v.b != 255",
        "common_draw_paletted2D",
    ):
        require(token in source, f"runtime contract missing {token}")
    require("enable_ff8_better_hp_colors = false" in prepare,
            "combined FFNx candidate must default Better HP Colors off")
    require(
        "enable_ff8_better_hp_colors ? lexeditor_ff8_hp_colors_draw_paletted2D : common_draw_paletted2D"
        in prepare,
        "disabled candidate must select FFNx's unmodified paletted draw function",
    )
    require("DEFAULT_BETTER_HP_COLORS = False" in settings,
            "Lexeditor Better HP Colors must default off")
    require('"betterHpColors"' in settings and '"Better HP Colors"' in settings,
            "Lexeditor persistence/validation registration is missing")
    require('("enable_ff8_better_hp_colors", better_hp_colors)' in settings,
            "FFNx config writer is missing Better HP Colors")
    require('"aria-label":"Better HP Colors"' in editor and 'row("BETTER HP COLORS"' in editor,
            "FF8 Tweaks UI is missing Better HP Colors")


def compile_contract(compiler: str) -> None:
    harness = r"""
#include <cassert>
#include "lexeditor_ff8_hp_colors.h"

void check(unsigned current, unsigned maximum, int r, int g, int b)
{
    const auto c = lexeditor_ff8_hp_rgb(current, maximum);
    assert(c.r == r && c.g == g && c.b == b);
}
int main()
{
    check(100, 100, 255, 255, 255);
    check(75, 100, 255, 255, 128);
    check(50, 100, 255, 255, 0);
    check(375, 1000, 255, 192, 0);
    check(25, 100, 255, 128, 0);
    check(125, 1000, 255, 64, 0);
    check(0, 100, 255, 0, 0);
    check(120, 100, 255, 255, 255);
    check(0, 0, 255, 255, 255);
    assert(!lexeditor_ff8_hp_should_tint(100, 100));
    assert(lexeditor_ff8_hp_should_tint(99, 100));
    assert(lexeditor_ff8_hp_should_tint(50, 100));
    assert(lexeditor_ff8_hp_should_tint(25, 100));
    assert(lexeditor_ff8_hp_should_tint(1, 100));
    assert(!lexeditor_ff8_hp_should_tint(0, 100)); // KO is native.
    assert(!lexeditor_ff8_hp_should_tint(0, 0));
}
"""
    with tempfile.TemporaryDirectory(prefix="ff8-hp-colors-") as directory:
        temp = Path(directory)
        (temp / "lexeditor_ff8_hp_colors.h").write_bytes(HEADER.read_bytes())
        (temp / "check.cpp").write_text(harness, encoding="utf-8")
        command = [compiler, "/nologo", "/EHsc", "/std:c++17", "check.cpp", "/Fe:check.exe"]
        result = subprocess.run(command, cwd=temp, capture_output=True, text=True)
        require(result.returncode == 0, "HP interpolation compile failed:\n" + result.stdout + result.stderr)
        result = subprocess.run([str(temp / "check.exe")], cwd=temp, capture_output=True, text=True)
        require(result.returncode == 0, "HP interpolation execution failed:\n" + result.stdout + result.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--compiler", default="cl")
    args = parser.parse_args()
    static_contract()
    if args.compile:
        compile_contract(args.compiler)
    print("PASS: FF8 issue #481 interpolation, KO, fail-closed and vanilla-disable contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Static and mutation checks for the isolated FF8 FFNx status-bar extension."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pefile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE_DIR = ROOT / "games/ff8/ffnx_status_bars"
SOURCE = MODULE_DIR / "ffnx-src/lexeditor_ff8_bars.cpp"
APPLICATOR = MODULE_DIR / "apply_to_ffnx.py"
FFNX = ROOT / "_scratch/ffnx-upstream"
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva : rva + length]


def relative_target(pe: pefile.PE, address: int) -> int:
    instruction = image_bytes(pe, address, 5)
    require(instruction[0] == 0xE8, f"0x{address:X} is not a relative CALL")
    return address + 5 + struct.unpack("<i", instruction[1:])[0]


def source_contract(text: str) -> None:
    required = (
        "ff8_externals.menu_callbacks[16].func",
        "ff8_externals.menu_callbacks[5].func",
        "battle_menu_sub_4A3D20 + 0x139",
        "static_cast<std::uint8_t *>(state) + 0x36",
        "result_state + 0x234 + slot * sizeof(std::uint32_t)",
        "g_result_state(0)",
        "result_state[0x38] != 0",
        "ff8_externals.get_char_level_4961D0",
        "offsetof(savemap_ff8_character, exp) == 4",
        "mode->driver_mode != MODE_BATTLE",
        "ff8_externals.char_comp_stats_1CFF000.size() != 3",
        "mode->driver_mode == MODE_MENU",
        "g_capture = {};",
    )
    for token in required:
        require(token in text, f"source contract is missing {token}")
    require("common_externals.get_game_object()" not in text,
            "EXP totals belong to result menu state, not the graphics object")
    require("patch_code_byte" not in text, "extension must not apply an executable byte patch")
    require("Hext" not in text, "extension must not use Hext")



def verify_projection_execution(applicator) -> None:
    """Compile the actual injected C++ method with renderer-state fixtures."""
    vcvars = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat")
    require(vcvars.is_file(), "MSVC environment is required for the projection execution test")
    harness = r"""
#include <array>
#include <cassert>
#include <cmath>
bool widescreen_enabled = false;
float wide_viewport_x=-106, wide_viewport_width=852, wide_game_width=852, wide_game_height=480;
float game_width=640, game_height=480;
constexpr int AR_STRETCH=1;
int aspect_ratio=0;
struct Renderer {
    float framebufferVertexOffsetX=0, framebufferVertexWidth=640;
    std::array<float,2> projectGamePointToScreen(float,float) const;
};
""" + applicator.PROJECT_GAME_POINT_SOURCE + r"""
void check(Renderer &r, float x, float y, float ex, float ey) {
    const auto p=r.projectGamePointToScreen(x,y);
    assert(std::abs(p[0]-ex)<0.00001f && std::abs(p[1]-ey)<0.00001f);
}
int main() {
    Renderer r;
    check(r,0,0,0,0); check(r,640,480,1,1);
    // 4:3 framebuffer centered in a 16:9 window.
    r.framebufferVertexOffsetX=80; r.framebufferVertexWidth=480;
    check(r,0,0,.125f,0); check(r,640,480,.875f,1); check(r,320,240,.5f,.5f);
    // Stretch must ignore pillarbox state, as renderFrame does.
    aspect_ratio=AR_STRETCH; check(r,0,0,0,0);check(r,640,480,1,1);
    // Widescreen backend has a negative left edge, not zero.
    aspect_ratio=0;widescreen_enabled=true;
    r.framebufferVertexOffsetX=0;r.framebufferVertexWidth=852;
    check(r,-106,0,0,0);check(r,746,480,1,1);check(r,320,240,.5f,.5f);
    // Center that widescreen output in a still wider window.
    r.framebufferVertexOffsetX=71;r.framebufferVertexWidth=710;
    check(r,-106,0,71.f/852,0);check(r,746,480,781.f/852,1);
    wide_viewport_width=0;check(r,320,240,0,0);
}
"""
    with tempfile.TemporaryDirectory(prefix="ff8-projection-") as name:
        temp = Path(name)
        (temp / "projection.cpp").write_text(harness, encoding="utf-8")
        (temp / "run.cmd").write_text(
            f'@call "{vcvars}" >nul\n'
            '@cl /nologo /EHsc /std:c++17 projection.cpp /Fe:projection.exe >build.log 2>&1\n'
            '@if errorlevel 1 (type build.log & exit /b 1)\n'
            '@projection.exe\n', encoding="utf-8")
        result = subprocess.run(["cmd.exe", "/c", str(temp / "run.cmd")], cwd=temp,
                                capture_output=True, text=True)
        require(result.returncode == 0, "projection C++ execution failed: " + result.stdout + result.stderr)

def make_fixture(destination: Path) -> None:
    for relative in (
        "src/cfg.cpp",
        "src/cfg.h",
        "src/ff8_opengl.cpp",
        "src/overlay.cpp",
        "src/renderer.cpp",
        "src/renderer.h",
        "misc/FFNx.toml",
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FFNX / relative, target)


def verify_applied_tree(root: Path) -> None:
    cfg = (root / "src/cfg.cpp").read_text(encoding="utf-8")
    renderer = (root / "src/renderer.cpp").read_text(encoding="utf-8")
    overlay = (root / "src/overlay.cpp").read_text(encoding="utf-8")
    hooks = (root / "src/ff8_opengl.cpp").read_text(encoding="utf-8")
    toml = (root / "misc/FFNx.toml").read_text(encoding="utf-8")
    for key in ("enable_ff8_xp_bars", "enable_ff8_hp_bars"):
        require(f'{key} = config["{key}"].value_or(false);' in cfg,
                f"{key} must fail closed")
        require(f"{key} = false" in toml, f"{key} must be off in packaged TOML")
    require(renderer.count("if (enable_devtools || lexeditor_ff8_bars_enabled())") == 3,
            "all overlay init, draw, and destroy gates must include the bars")
    require("lexeditor_ff8_bars_draw();" in overlay, "bar draw call is missing")
    require("visible = enable_devtools;" in overlay,
            "the bars must not expose the DevTools window")
    require("if (enable_devtools && e.keyValue == devtools_hotkey)" in overlay,
            "the DevTools hotkey must stay disabled with DevTools")
    require("lexeditor_ff8_bars_install();" in hooks, "FF8 hook install call is missing")


def mutation_checks(source: str, applied: Path) -> None:
    mutations = (
        (" + 0x36", " + 0x35"),
        (" + 0x234 +", " + 0x230 +"),
        ("result_state[0x38] != 0", "false"),
        ("mode->driver_mode != MODE_BATTLE", "false"),
        ("mode->driver_mode == MODE_MENU", "true"),
        ("g_capture = {};", "// capture retained"),
    )
    for old, new in mutations:
        # The title-menu guard and the end-of-frame expiry both clear capture.
        # Remove both when testing that the expiry contract is meaningful.
        mutated = source.replace(old, new) if old == "g_capture = {};" else source.replace(old, new, 1)
        try:
            source_contract(mutated)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"source mutation was not rejected: {old}")

    cfg_path = applied / "src/cfg.cpp"
    original = cfg_path.read_text(encoding="utf-8")
    cfg_path.write_text(
        original.replace(
            'enable_ff8_xp_bars = config["enable_ff8_xp_bars"].value_or(false);',
            'enable_ff8_xp_bars = config["enable_ff8_xp_bars"].value_or(true);',
            1,
        ),
        encoding="utf-8",
    )
    try:
        verify_applied_tree(applied)
    except AssertionError:
        pass
    else:
        raise AssertionError("default-on setting mutation was not rejected")


def main() -> int:
    require(EXE.is_file(), "supported FF8_EN.exe is missing")
    require(hashlib.sha256(EXE.read_bytes()).hexdigest() == EXE_SHA256,
            "installed FF8_EN.exe is not the supported Steam English build")
    pe = pefile.PE(str(EXE), fast_load=True)

    # Native callback and renderer identities.
    require(struct.unpack("<I", image_bytes(pe, 0x00B87F00, 4))[0] == 0x004CDFA0,
            "menu callback 5 no longer selects the Status callback")
    require(struct.unpack("<I", image_bytes(pe, 0x00B87F58, 4))[0] == 0x004E67C0,
            "menu callback 16 no longer selects the main-menu callback")
    require(image_bytes(pe, 0x004CDFA0, 4) == bytes.fromhex("53 56 68 F0"),
            "Status callback prologue changed")
    require(struct.unpack("<I", image_bytes(pe, 0x004CDFA3, 4))[0] == 0x004CECF0,
            "Status callback renderer changed")
    require(image_bytes(pe, 0x004E67C0, 4) == bytes.fromhex("53 56 68 50"),
            "main-menu callback prologue changed")
    require(struct.unpack("<I", image_bytes(pe, 0x004E67C3, 4))[0] == 0x004E5550,
            "main-menu callback renderer changed")
    require(image_bytes(pe, 0x004CEF92, 10) == bytes.fromhex("33 C0 8A 47 36 8D 0C C0 8D 14"),
            "Status selected-character read changed")
    require(image_bytes(pe, 0x004CEFA5, 7) == bytes.fromhex("8D 0C D5 E8 E0 CF 01"),
            "Status savemap-character address formation changed")
    require(relative_target(pe, 0x004A3E59) == 0x004A4950,
            "post-battle renderer call changed")
    require(relative_target(pe, 0x004A4959) == 0x00403E00,
            "result renderer must resolve its own state accessor")
    require(image_bytes(pe, 0x004A4957, 2) == bytes.fromhex("6A 00"),
            "result state accessor must receive slot zero")
    require(image_bytes(pe, 0x004A4BA7, 6) == bytes.fromhex("8A 47 38 83 F8 03"),
            "result page selector changed")
    require(relative_target(pe, 0x004A4461) == 0x00496CB0,
            "post-battle XP updater call changed")
    require(image_bytes(pe, 0x004A4485, 5) == bytes.fromhex("89 0F 89 47 F4"),
            "post-battle running-XP initialization changed")
    require(image_bytes(pe, 0x004A48AD, 6) == bytes.fromhex("8B 0F 03 C8 89 0F"),
            "post-battle running-XP animation changed")

    source = SOURCE.read_text(encoding="utf-8")
    source_contract(source)
    ff8_data = (FFNX / "src/ff8_data.cpp").read_text(encoding="utf-8")
    save_header = (FFNX / "src/ff8/save_data.h").read_text(encoding="utf-8")
    require("ff8_externals.menu_callbacks =" in ff8_data,
            "official FFNx no longer resolves the menu callback table")
    require("ff8_externals.savemap =" in ff8_data,
            "official FFNx no longer resolves the savemap")
    require("ff8_externals.get_char_level_4961D0 =" in ff8_data,
            "official FFNx no longer resolves the native level function")
    require("ff8_externals.char_comp_stats_1CFF000 = std::span" in ff8_data,
            "official FFNx no longer exposes the three battle stat records")
    require("struct savemap_ff8_character" in save_header and "uint32_t exp;" in save_header,
            "official FFNx character XP layout changed")

    spec = importlib.util.spec_from_file_location("apply_ffnx_bars", APPLICATOR)
    require(spec is not None and spec.loader is not None, "cannot load applicator")
    applicator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(applicator)
    verify_projection_execution(applicator)
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Path(temporary)
        make_fixture(fixture)
        applicator.apply(fixture, check_revision=False)
        verify_applied_tree(fixture)
        mutation_checks(source, fixture)

    from games.ff8 import gameplay_settings

    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        gameplay_settings.settings_path(project).write_text(
            '{"flyingEvaBonus": 25, "xpBars": true, "hpBars": true}',
            encoding="utf-8",
        )
        loaded = gameplay_settings.load(project, game_root=project / "missing-game")
        require(loaded["xpBars"] is True and loaded["hpBars"] is True,
                "per-mod XP/HP settings did not load")
        config = project / "FFNx.toml"
        config.write_text("enable_devtools = false\n", encoding="utf-8")
        gameplay_settings._set_ffnx_runtime_tweaks(
            config, xp_bars=True, hp_bars=False, better_targeting=False,
        )
        configured = config.read_text(encoding="utf-8")
        require(configured.count("enable_ff8_xp_bars = true") == 1,
                "XP bar activation was not written exactly once")
        require(configured.count("enable_ff8_hp_bars = false") == 1,
                "HP bar activation was not written exactly once")
        gameplay_settings._set_ffnx_runtime_tweaks(
            config, xp_bars=False, hp_bars=True, better_targeting=False,
        )
        configured = config.read_text(encoding="utf-8")
        require(configured.count("enable_ff8_xp_bars = false") == 1,
                "XP bar activation was not replaced")
        require(configured.count("enable_ff8_hp_bars = true") == 1,
                "HP bar activation was not replaced")

    gameplay_source = (ROOT / "games/ff8/gameplay_settings.py").read_text(encoding="utf-8")
    editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    for key, label in (("xpBars", "XP BARS"), ("hpBars", "HP BARS")):
        require(f'"{key}": False' in gameplay_source,
                f"new mods do not default {key} off")
        require(f'{key}:state.data.settings.{key}' in editor,
                f"{key} is absent from the save payload")
        require(f'checked:settings.{key}' in editor,
                f"{key} does not have a checkbox")
        require(label in editor, f"{label} is absent from Tweaks")
    require("main menu, Status screen, and post-battle report" in editor,
            "XP Bars description does not state every rendered surface")
    require("bottom-right during battle" in editor,
            "HP Bars description does not state its battle placement")

    print("FF8 FFNx XP/HP bars: executable, source, integration, and mutations verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

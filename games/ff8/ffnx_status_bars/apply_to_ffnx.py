"""Apply Lexeditor's FF8 status-bar source extension to pinned FFNx source."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


PROJECT_GAME_POINT_SOURCE = 'std::array<float, 2> Renderer::projectGamePointToScreen(float x, float y) const\n{\n    // Apply the same two orthographic projections and framebuffer quad as\n    // calcBackendProjMatrix() and renderFrame(). Return window fractions.\n    const float left = widescreen_enabled ? wide_viewport_x : 0.0f;\n    const float width = widescreen_enabled ? wide_viewport_width : game_width;\n    const float height = widescreen_enabled ? wide_game_height : game_height;\n    const float outputWidth = widescreen_enabled ? wide_game_width : game_width;\n    const float outputHeight = widescreen_enabled ? wide_game_height : game_height;\n    if (width <= 0.0f || height <= 0.0f || outputWidth <= 0.0f || outputHeight <= 0.0f) return {0.0f, 0.0f};\n    const float quadLeft = aspect_ratio == AR_STRETCH ? 0.0f : framebufferVertexOffsetX;\n    const float quadWidth = aspect_ratio == AR_STRETCH ? game_width : framebufferVertexWidth;\n    if (quadWidth <= 0.0f) return {0.0f, 0.0f};\n    const float screenX = (quadLeft + (x - left) * quadWidth / width) / outputWidth;\n    const float screenY = (y * game_height / height) / outputHeight;\n    return {screenX, screenY};\n}\n\n'


PINNED_FFNX_REVISION = "1e291885da4ddb482188b81a5198d56a1915fde6"


def replace_once(path: Path, old: bytes, new: bytes) -> None:
    data = path.read_bytes()
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one integration anchor in {path}, found {count}")
    path.write_bytes(data.replace(old, new, 1))


def verify_revision(root: Path) -> None:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if revision != PINNED_FFNX_REVISION:
        raise RuntimeError(
            f"Unsupported FFNx revision {revision}; expected {PINNED_FFNX_REVISION}"
        )


def apply(root: Path, *, check_revision: bool = True) -> None:
    root = root.resolve()
    if check_revision:
        verify_revision(root)
    source = Path(__file__).resolve().parent / "ffnx-src"
    for name in ("lexeditor_ff8_bars.cpp", "lexeditor_ff8_bars.h"):
        destination = root / "src" / name
        if destination.exists():
            raise RuntimeError(f"Refusing to overwrite existing {destination}")
        shutil.copyfile(source / name, destination)

    replace_once(
        root / "src/cfg.cpp",
        b"bool enable_devtools;\r\n",
        b"bool enable_devtools;\r\nbool enable_ff8_xp_bars;\r\nbool enable_ff8_hp_bars;\r\nbool enable_ff8_gf_hp_bars;\r\n",
    )
    replace_once(
        root / "src/cfg.cpp",
        b'\tenable_devtools = config["enable_devtools"].value_or(false);\r\n',
        b'\tenable_devtools = config["enable_devtools"].value_or(false);\r\n'
        b'\tenable_ff8_xp_bars = config["enable_ff8_xp_bars"].value_or(false);\r\n'
        b'\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);\r\n'
        b'\tenable_ff8_gf_hp_bars = config["enable_ff8_gf_hp_bars"].value_or(false);\r\n',
    )
    replace_once(
        root / "src/cfg.h",
        b"extern bool enable_devtools;\r\n",
        b"extern bool enable_devtools;\r\nextern bool enable_ff8_xp_bars;\r\nextern bool enable_ff8_hp_bars;\r\nextern bool enable_ff8_gf_hp_bars;\r\n",
    )
    replace_once(
        root / "misc/FFNx.toml",
        b"enable_devtools = false\r\n",
        b"enable_devtools = false\r\n\r\n"
        b"# Draw level-progress bars in FF8's main, Status, and post-battle screens.\r\n"
        b"enable_ff8_xp_bars = false\r\n\r\n"
        b"# Draw current/max HP bars for FF8's three active battle characters.\r\n"
        b"enable_ff8_hp_bars = false\r\n\r\n"
        b"# Draw blue junctioned-GF HP bars above the FF8 party names.\r\n"
        b"enable_ff8_gf_hp_bars = false\r\n",
    )
    replace_once(
        root / "src/ff8_opengl.cpp",
        b'#include "ff8/save_data.h"\r\n',
        b'#include "ff8/save_data.h"\r\n#include "lexeditor_ff8_bars.h"\r\n',
    )
    replace_once(
        root / "src/ff8_opengl.cpp",
        b"void ff8_init_hooks(struct game_obj *_game_object)\r\n{\r\n",
        b"void ff8_init_hooks(struct game_obj *_game_object)\r\n{\r\n\tlexeditor_ff8_bars_install();\r\n",
    )
    replace_once(
        root / "src/overlay.cpp",
        b'#include "lighting_debug.h"\r\n',
        b'#include "lighting_debug.h"\r\n#include "lexeditor_ff8_bars.h"\r\n',
    )
    replace_once(
        root / "src/overlay.cpp",
        b"    ImGui::NewFrame();\r\n",
        b"    ImGui::NewFrame();\r\n    lexeditor_ff8_bars_draw();\r\n",
    )
    replace_once(
        root / "src/overlay.cpp",
        b"    mem_edit.Open = false;\r\n",
        b"    mem_edit.Open = false;\r\n"
        b"    // Status bars share ImGui, but only DevTools may show this window.\r\n"
        b"    visible = enable_devtools;\r\n",
    )
    replace_once(
        root / "src/overlay.cpp",
        b"    if (e.keyValue == devtools_hotkey)\r\n",
        b"    if (enable_devtools && e.keyValue == devtools_hotkey)\r\n",
    )
    replace_once(
        root / "src/renderer.cpp",
        b'#include "utils.h"\r\n',
        b'#include "utils.h"\r\n#include "lexeditor_ff8_bars.h"\r\n',
    )
    replace_once(
        root / "src/renderer.h",
        b"    // Internal coord calculation\r\n",
        b"    // Game coordinates to normalized window coordinates.\r\n"
        b"    std::array<float, 2> projectGamePointToScreen(float x, float y) const;\r\n\r\n"
        b"    // Internal coord calculation\r\n",
    )
    replace_once(
        root / "src/renderer.cpp",
        b"void Renderer::renderFrame()\r\n",
        PROJECT_GAME_POINT_SOURCE.replace("\n", "\r\n").encode() + b"void Renderer::renderFrame()\r\n",
    )
    data = (root / "src/renderer.cpp").read_bytes()
    old = b"if (enable_devtools)"
    if data.count(old) != 3:
        raise RuntimeError("Expected the three FFNx overlay lifecycle gates")
    (root / "src/renderer.cpp").write_bytes(
        data.replace(old, b"if (enable_devtools || lexeditor_ff8_bars_enabled())")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ffnx_source", type=Path)
    args = parser.parse_args()
    apply(args.ffnx_source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

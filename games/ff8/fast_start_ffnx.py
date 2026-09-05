"""Apply the FF8-only Fast Start logo gate to the pinned FFNx source."""
from pathlib import Path
from games.ff8.ffnx_status_bars.apply_to_ffnx import verify_revision


STARTUP_FRAME_GATE = 'bool lexeditor_ff8_hide_startup_frame()\n{\n    static bool finished = false;\n    if (!ff8 || !enable_ff8_fast_start || finished) return false;\n    VOBJ(game_obj, game_object, common_externals.get_game_object());\n    const auto loop = reinterpret_cast<uintptr_t>(VREF(game_object, game_loop_obj).main_loop);\n    if (loop == ff8_externals.main_menu_main_loop) {\n        finished = true;\n        return false;\n    }\n    const bool startup = loop == ff8_externals.pubintro_main_loop ||\n        loop == ff8_externals.credits_main_loop ||\n        loop == ff8_externals.go_to_main_menu_main_loop;\n    // An alternate direct-to-game launch also ends the one-time startup gate.\n    const auto *mode = getmode_cached();\n    if (!startup && mode != nullptr && (mode->driver_mode == MODE_FIELD ||\n        mode->driver_mode == MODE_WORLDMAP || mode->driver_mode == MODE_BATTLE ||\n        mode->driver_mode == MODE_MENU)) finished = true;\n    return startup;\n}\n\n'
STARTUP_FRAME_MASK = '    // Keep startup initialization and rendering work, but do not present logos.\n    if (lexeditor_ff8_hide_startup_frame()) {\n        ++backendViewId;\n        bgfx::setViewFrameBuffer(backendViewId, BGFX_INVALID_HANDLE);\n        bgfx::setViewRect(backendViewId, 0, 0, window_size_x, window_size_y);\n        bgfx::setViewClear(backendViewId, BGFX_CLEAR_COLOR | BGFX_CLEAR_DEPTH, 0x000000FF, 1.0f);\n        bgfx::touch(backendViewId);\n        return;\n    }\n'


def apply(root: Path, *, check_revision: bool = True) -> None:
    root = Path(root)
    if check_revision:
        verify_revision(root)
    replacements = {
        'src/cfg.cpp': [
            ('bool enable_devtools;', 'bool enable_devtools;\nbool enable_ff8_fast_start;'),
            ('\tenable_devtools = config["enable_devtools"].value_or(false);',
             '\tenable_devtools = config["enable_devtools"].value_or(false);\n\tenable_ff8_fast_start = config["enable_ff8_fast_start"].value_or(false);'),
        ],
        'src/cfg.h': [('extern bool enable_devtools;', 'extern bool enable_devtools;\nextern bool enable_ff8_fast_start;')],
        'misc/FFNx.toml': [('enable_devtools = false', 'enable_devtools = false\n\n# Skip the FFNx startup logo in FF8. Used with the native credits completion patch.\nenable_ff8_fast_start = false')],
        'src/renderer.cpp': [
            ('#include "utils.h"\n', '#include "utils.h"\nbool lexeditor_ff8_hide_startup_frame();\n'),
            ('void Renderer::renderFrame()\n{\n', 'void Renderer::renderFrame()\n{\n' + STARTUP_FRAME_MASK),
        ],
        'src/ff8_opengl.cpp': [
            ('uint32_t ff8_credits_main_loop_gfx_begin_scene(', STARTUP_FRAME_GATE + 'uint32_t ff8_credits_main_loop_gfx_begin_scene('),
            ('uint32_t ff8_credits_main_loop_gfx_begin_scene(uint32_t unknown, struct game_obj *game_object)\n{',
             'uint32_t ff8_credits_main_loop_gfx_begin_scene(uint32_t unknown, struct game_obj *game_object)\n{\n\t// The logo gate otherwise prevents the native completion check from running.\n\tif (enable_ff8_fast_start) stopDrawFFNxLogo();'),
        ],
    }
    # Validate every anchor before changing any file. Preserve source newlines.
    outputs = {}
    for name, edits in replacements.items():
        path = root / name
        raw = path.read_bytes()
        newline = b'\r\n' if b'\r\n' in raw else b'\n'
        text = raw.decode().replace('\r\n', '\n')
        for old, new in edits:
            if text.count(old) != 1 or new in text:
                raise RuntimeError(f'Unexpected or already patched Fast Start source: {name}')
            text = text.replace(old, new, 1)
        outputs[path] = text.encode().replace(b'\n', newline)
    for path, data in outputs.items():
        path.write_bytes(data)

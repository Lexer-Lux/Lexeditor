"""Apply the FF8-only Fast Start logo gate to the pinned FFNx source."""
from pathlib import Path
from games.ff8.ffnx_status_bars.apply_to_ffnx import verify_revision


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
        'src/ff8_opengl.cpp': [
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

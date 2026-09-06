"""Add world-only two-axis manual analog camera controls to the supported FFNx tree."""
from pathlib import Path
from games.ff8.ffnx_status_bars.apply_to_ffnx import verify_revision


def apply(root: Path, *, check_revision: bool = True) -> None:
    root = Path(root)
    if check_revision:
        verify_revision(root)
    changes = {
        'src/cfg.cpp': [
            ('bool enable_devtools;', 'bool enable_devtools;\nbool enable_ff8_modern_controls;'),
            ('\tenable_devtools = config["enable_devtools"].value_or(false);',
             '\tenable_devtools = config["enable_devtools"].value_or(false);\n\tenable_ff8_modern_controls = config["enable_ff8_modern_controls"].value_or(false);'),
        ],
        'src/cfg.h': [('extern bool enable_devtools;', 'extern bool enable_devtools;\nextern bool enable_ff8_modern_controls;')],
        'misc/FFNx.toml': [('enable_devtools = false', 'enable_devtools = false\n\n# Manual two-axis analog world-map camera. Battle inputs are unchanged.\nenable_ff8_modern_controls = false')],
        'src/ff8_opengl.cpp': [
            ('#include "ff8.h"', '#include "ff8.h"\n#include "lexeditor_ff8_modern_controls.h"'),
            ('void ff8_init_hooks(struct game_obj *_game_object)\n{',
             'void ff8_init_hooks(struct game_obj *_game_object)\n{\n\tlexeditor_ff8_modern_controls_install();'),
            ('LPDIJOYSTATE2 ff8_update_gamepad_status()\n{',
             'LPDIJOYSTATE2 ff8_update_gamepad_status()\n{\n'
             '\t// A disconnected or blocked controller must not leave a stale camera axis.\n'
             '\tif (lexeditor_ff8_modern_controls_world_active()) right_stick_x = right_stick_y = 128;'),
            ('\treturn ff8_externals.dinput_gamepad_state;\n}',
             '\t// Keep native right-stick digital aliases out of world movement/zoom.\n'
             '\tif (lexeditor_ff8_modern_controls_world_active()) {\n'
             '\t\tff8_externals.dinput_gamepad_state->lRx = 0;\n'
             '\t\tff8_externals.dinput_gamepad_state->lRy = 0;\n\t}\n'
             '\treturn ff8_externals.dinput_gamepad_state;\n}'),
            ('+ (FF8_US_VERSION ? 0xE2 : 0xDF), ff8_get_analog_value); // rX',
             '+ (FF8_US_VERSION ? 0xE2 : 0xDF), lexeditor_ff8_modern_world_axis); // rX'),
            ('+ (FF8_US_VERSION ? 0xF2 : 0xEF), ff8_get_analog_value); // rY',
             '+ (FF8_US_VERSION ? 0xF2 : 0xEF), lexeditor_ff8_modern_world_axis); // rY'),
        ],
    }
    outputs = {}
    for name, edits in changes.items():
        path = root / name
        raw = path.read_bytes()
        newline = b'\r\n' if b'\r\n' in raw else b'\n'
        content = raw.decode().replace('\r\n', '\n')
        for old, new in edits:
            if content.count(old) != 1 or new in content:
                raise RuntimeError(f'Unexpected or already patched Modern Controls source: {name}')
            content = content.replace(old, new, 1)
        outputs[path] = content.encode().replace(b'\n', newline)
    for name in ('camera_axis.h', 'lexeditor_ff8_modern_controls.h', 'lexeditor_ff8_modern_controls.cpp'):
        target = root / 'src' / name
        if target.exists():
            raise RuntimeError(f'Refusing to replace existing source: {target}')
        outputs[target] = Path(__file__).with_name(name).read_bytes()
    for path, content in outputs.items():
        path.write_bytes(content)

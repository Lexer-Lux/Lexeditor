"""Install native Party Switch extension into FFNx source (no game files)."""
from pathlib import Path
import shutil

def apply(root):
    root=Path(root)
    source=Path(__file__).parent/'ffnx-src'
    for path in source.iterdir():
        shutil.copyfile(path,root/'src'/path.name)
    def change(file,old,new):
        p=root/file
        text=p.read_text(encoding='utf-8')
        if new in text:return
        if text.count(old)!=1:raise RuntimeError(f'{file}: expected one anchor: {old!r}')
        p.write_text(text.replace(old,new,1),encoding='utf-8',newline='\r\n')
    change('src/cfg.h','extern bool enable_devtools;','extern bool enable_devtools;\nextern bool enable_ff8_party_switch;')
    change('src/cfg.cpp','bool enable_devtools;','bool enable_devtools;\nbool enable_ff8_party_switch;')
    change('src/cfg.cpp','\tenable_devtools = config["enable_devtools"].value_or(false);','\tenable_devtools = config["enable_devtools"].value_or(false);\n\tenable_ff8_party_switch = config["enable_ff8_party_switch"].value_or(false);')
    change('src/ff8_opengl.cpp','#include "ff8/save_data.h"','#include "ff8/save_data.h"\n#include "lexeditor_ff8_party_switch.h"')
    change('src/ff8_opengl.cpp','void ff8_init_hooks(struct game_obj *_game_object)\n{','void ff8_init_hooks(struct game_obj *_game_object)\n{\n\tlexeditor_ff8_party_switch_install();')
    change('src/common.cpp','void common_flip(struct game_obj *game_object)\n{','void common_flip(struct game_obj *game_object)\n{\n\tlexeditor_ff8_party_switch_tick();')
    change('src/common.cpp','#include "ff8.h"','#include "ff8.h"\n#include "lexeditor_ff8_party_switch.h"')
    change('misc/FFNx.toml','enable_devtools = false','enable_devtools = false\n\n# Look Left opens the reserve party selector during an active battle turn.\nenable_ff8_party_switch = false')

if __name__=='__main__':
    import sys
    apply(sys.argv[1])


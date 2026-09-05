"""Verify the FFNx Fast Start source gate without modifying build sources."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sys
import subprocess
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8.fast_start_ffnx import apply, STARTUP_FRAME_GATE

with TemporaryDirectory(prefix='ff8-fast-start-') as tmp:
    root = Path(tmp)
    for name in ('src/cfg.cpp', 'src/cfg.h', 'src/ff8_opengl.cpp', 'src/renderer.cpp', 'misc/FFNx.toml'):
        target = root / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / '_scratch/ffnx-upstream' / name, target)
    apply(root, check_revision=False)
    callback = (root / 'src/ff8_opengl.cpp').read_text()
    start = callback.index('uint32_t ff8_credits_main_loop_gfx_begin_scene(')
    stop = callback.index('int credits_controller_music_play', start)
    callback = callback[start:stop]
    assert callback.index('if (enable_ff8_fast_start) stopDrawFFNxLogo();') < callback.index('drawFFNxLogoFrame(game_object)')
    assert 'return common_begin_scene(unknown, game_object);' in callback
    baseline = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    try:
        apply(root, check_revision=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Repeated source extension was accepted')
    assert all(p.read_bytes() == data for p, data in baseline.items())
print('FF8 Fast Start source integration contract passed; runtime not tested')

# Compile the actual callback gate with native-loop identities. Each process
# receives fresh startup state; after title/gameplay, later credits stay visible.
harness = r"""
#include <cstdint>
#include <cassert>
using std::uintptr_t;
struct game_obj { struct { void (*main_loop)(); } game_loop_obj; } object;
#define VOBJ(type,name,value) auto *name = value
#define VREF(object,field) object->field
struct { game_obj* (*get_game_object)(); } common_externals{[](){return &object;}};
struct { uintptr_t main_menu_main_loop=4,pubintro_main_loop=1,credits_main_loop=2,go_to_main_menu_main_loop=3; } ff8_externals;
enum { MODE_FIELD=1,MODE_WORLDMAP=2,MODE_BATTLE=3,MODE_MENU=4 };
struct game_mode { int driver_mode=0; } mode;
game_mode *getmode_cached(){return &mode;}
bool ff8=true,enable_ff8_fast_start=false;
""" + STARTUP_FRAME_GATE + r"""
int main(int argc,char**) {
 object.game_loop_obj.main_loop=reinterpret_cast<void(*)()>(1);
 assert(!lexeditor_ff8_hide_startup_frame());enable_ff8_fast_start=true;
 for(uintptr_t loop=1;loop<=3;loop++) {object.game_loop_obj.main_loop=reinterpret_cast<void(*)()>(loop);assert(lexeditor_ff8_hide_startup_frame());}
 object.game_loop_obj.main_loop=reinterpret_cast<void(*)()>(argc>1?7:4);
 if(argc>1)mode.driver_mode=MODE_FIELD;
 assert(!lexeditor_ff8_hide_startup_frame());
 mode.driver_mode=0;object.game_loop_obj.main_loop=reinterpret_cast<void(*)()>(2);
 assert(!lexeditor_ff8_hide_startup_frame());
}
"""
with TemporaryDirectory(prefix='ff8-startup-gate-') as tmp:
 root=Path(tmp);(root/'gate.cpp').write_text(harness)
 vcvars=r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat'
 (root/'run.cmd').write_text(f'@call "{vcvars}" >nul\n@cl /nologo /EHsc /std:c++17 gate.cpp /Fe:gate.exe >build.log 2>&1\n@if errorlevel 1 (type build.log & exit /b 1)\n@gate.exe\n@if errorlevel 1 exit /b 1\n@gate.exe direct\n')
 result=subprocess.run(['cmd.exe','/c',str(root/'run.cmd')],cwd=root,capture_output=True,text=True)
 assert result.returncode==0,result.stdout+result.stderr
print('Actual C++ startup gate sequence passed for publisher/credits/title and direct gameplay; later credits unmasked')

# Execute the native callback scheduler: it queues the transition instead of
# replacing the current descriptor before the final startup frame presents.
import struct,pefile
try: import unicorn
except ImportError: sys.path.insert(0,str(ROOT/'_scratch/gf-spellbooks-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP
image=pefile.PE(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe').get_memory_mapped_image()
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x2600000);u.mem_write(0x400000,image)
obj=0x2700000;descriptor=0x2710000;stack=0x2908000;stop=0x2800000
current=bytes(range(28));pending=struct.pack('<7I',0,0,0x470440,0x56d970,0x470520,0,0)
u.mem_write(obj+0xB30,current);u.mem_write(descriptor,pending)
u.reg_write(UC_X86_REG_ESP,stack);u.mem_write(stack,struct.pack('<III',stop,descriptor,obj))
u.emu_start(0x409A57,stop,count=100)
assert bytes(u.mem_read(obj+0xB30,28))==current
assert bytes(u.mem_read(obj+0xB4C,28))==pending
assert bytes(u.mem_read(obj+0xA64,4))==b'\1\0\0\0'
print('Native startup scheduler preserves the active descriptor through current-frame presentation')

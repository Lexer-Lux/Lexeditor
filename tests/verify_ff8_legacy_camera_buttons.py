"""Execute native camera input branches and compile the production toggle wrapper."""
from pathlib import Path
import struct
import subprocess
import tempfile
from verify_ff8_world_camera_native_seam import EXE, machine, put
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ESI

ROOT = Path(__file__).resolve().parents[1]
raw = EXE.read_bytes()
for address in (0x53FD4A, 0x54111A):
    code = raw[address-0x400000:address-0x400000+5]
    assert code[0] == 0xE8
    assert address+5+struct.unpack('<i',code[1:])[0] == 0x54A7F0
assert raw[0x54A845-0x400000:0x54A847-0x400000] == bytes.fromhex('A8 02')
for keys, expected in ((0,0),(4,127),(8,129),(12,0)):
    m=machine(raw)
    m.reg_write(UC_X86_REG_ESI,0x203ED50)
    m.reg_write(UC_X86_REG_EBX,keys)
    m.reg_write(UC_X86_REG_EAX,keys)
    m.emu_start(0x557515,0x557530,count=30)
    assert m.mem_read(0x203ED5E,1)[0] == expected

source=(ROOT/'plugins/ff8/ffnx_modern_controls/lexeditor_ff8_modern_controls.cpp').read_text()
wrapper=source[source.index('std::uint32_t __cdecl world_actions()'):source.index('void __cdecl update_battle_camera()')]
old='reinterpret_cast<std::uint32_t(__cdecl *)()>(0x0054A7F0)'
assert wrapper.count(old)==1
wrapper=wrapper.replace(old,'&native_actions')
harness=r'''
#include <cstdint>
#include <cassert>
bool active=true; std::int16_t parity=0; std::uint32_t keys[2]={};
const auto kWorldInputParity=reinterpret_cast<std::uintptr_t>(&parity);
const auto kWorldInputStates=reinterpret_cast<std::uintptr_t>(keys);
constexpr std::uint32_t kR2=2;
bool lexeditor_ff8_modern_controls_world_active(){return active;}
unsigned calls=0,seen=0;
std::uint32_t native_actions(){++calls;seen=keys[parity];keys[parity]|=0x100;return 73;}
''' + wrapper + r'''
int main(){
 for(parity=0;parity<2;++parity) for(unsigned held=0;held<256;++held){
   active=true; keys[parity]=held;
   assert(world_actions()==73);assert(seen==(held&~2u));
   assert(keys[parity]==(held|0x100)); // Restore R2, keep native unrelated changes.
   active=false;keys[parity]=held;
   assert(world_actions()==73);assert(seen==held);
 }
 assert(calls==1024);
}
'''
vcvars=Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat')
with tempfile.TemporaryDirectory(prefix='ff8-camera-buttons-') as directory:
    root=Path(directory)
    (root/'test.cpp').write_text(harness)
    (root/'run.cmd').write_text(f'@call "{vcvars}" >nul\n@cl /nologo /EHsc /std:c++17 test.cpp /Fe:test.exe >build.log 2>&1\n@if errorlevel 1 (type build.log & exit /b 1)\n@test.exe\n')
    result=subprocess.run(['cmd.exe','/c',str(root/'run.cmd')],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
print('PASS: native turn inputs and overhead toggle sites; 1,024 compiled enabled/disabled wrapper cases')

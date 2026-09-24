"""Execute the production clock hooks without opening a game window."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp').read_text()
hooks = source[source.index('using ClockRenderer'):source.index('// Capture native widget coordinates')]
harness = r'''
#include <cstdint>
#include <ctime>
#include <cassert>
struct Mode {int driver_mode;};
constexpr int MODE_MENU=1;
Mode mode{MODE_MENU};bool available=true,enable_ff8_ingame_time=true,clock_ok=true;
Mode* getmode_cached(){return available?&mode:nullptr;}
int fixture_localtime(std::tm* local,const std::time_t*){
 if(!clock_ok)return 1;local->tm_hour=12;local->tm_min=34;local->tm_sec=56;return 0;
}
#define localtime_s fixture_localtime
''' + hooks + r'''
std::uint32_t label_seen,seconds_seen,selector_seen;
std::uint32_t __cdecl label_renderer(std::uint32_t display,std::uint32_t cursor,
 std::uint32_t label,std::uint32_t x,std::uint32_t y,std::uint32_t texture,std::uint32_t flags){
 assert(display==1&&cursor==2&&x==3&&y==4&&texture==5&&flags==6);
 label_seen=label;return 99;
}
std::uint32_t __cdecl clock_renderer(void* state,std::uint32_t display,std::uint32_t cursor,
 std::uint32_t x,std::uint32_t y,std::uint32_t seconds,std::uint32_t selector){
 assert(state==nullptr);seconds_seen=seconds;selector_seen=selector;
 return clock_label_hook(display,cursor,selector?0x142:0x146,x,y,5,6);
}
int main(){
 g_clock_renderer=clock_renderer;g_clock_label_renderer=label_renderer;
 for(int bits=0;bits<64;++bits){
  enable_ff8_ingame_time=bits&1;available=bits&2;mode.driver_mode=(bits&4)?MODE_MENU:2;
  clock_ok=bits&8;const unsigned selector=(bits&16)?1:0;g_show_clock_time_label=bits&32;
  const bool previous=g_show_clock_time_label;
  const bool active=enable_ff8_ingame_time&&available&&mode.driver_mode==MODE_MENU&&clock_ok&&selector;
  assert(main_menu_clock_hook(nullptr,1,2,3,4,123,selector)==99);
  assert(seconds_seen==(active?45296:123));assert(selector_seen==selector);
  assert(label_seen==(active||!selector?0x146:0x142));assert(g_show_clock_time_label==previous);
  clock_label_hook(1,2,0x145,3,4,5,6);assert(label_seen==0x145);
 }
}
'''
vcvars = Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat')
with tempfile.TemporaryDirectory(prefix='ff8-clock-label-') as directory:
    temp = Path(directory)
    (temp/'check.cpp').write_text(harness)
    (temp/'run.cmd').write_text(f'@call "{vcvars}" >nul\n@cl /nologo /EHsc /std:c++17 check.cpp /Fe:check.exe >build.log 2>&1\n@if errorlevel 1 (type build.log & exit /b 1)\n@check.exe\n')
    result = subprocess.run(['cmd.exe','/c',str(temp/'run.cmd')],cwd=temp,capture_output=True,text=True)
    assert result.returncode == 0,result.stdout+result.stderr
print('PASS: 64 production clock-hook cases; TIME scope, countdown preservation, failure fallback, return and argument forwarding')

"""Compile and execute production menu XP capture/projection without a game window."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp').read_text()
capture = source[source.index('struct MenuXpRow'):source.index('float gf_xp_fraction')]
draw = source[source.index('void draw_menu_xp()'):source.index('void draw_after_battle_xp()')]
harness = r'''
#include <array>
#include <cassert>
#include <cstddef>
#include <vector>
struct sprite_viewport {float scale_x,scale_y,offset_x,offset_y;};
struct Mode {int driver_mode;};
constexpr int MODE_MENU=1;
Mode mode{MODE_MENU}; bool has_mode=true;
bool enable_ff8_hp_bars=false, enable_ff8_xp_bars=true;
Mode *getmode_cached(){return has_mode?&mode:nullptr;}
sprite_viewport viewport{2,2,80,0};
sprite_viewport *active=&viewport, **g_active_viewport=&active;
#define IM_COL32(r,g,b,a) 0
std::vector<std::array<float,5>> bars;
void draw_gauge(float x,float y,float w,float h,float f,unsigned){bars.push_back({x,y,w,h,f});}
''' + capture + draw + r'''
int main(){
 capture_menu_xp(79,88,70,.75f);
 viewport={3,3,10,20}; // The capture owns the viewport from its native draw.
 draw_menu_xp();
 assert((bars[0]==std::array<float,5>{238,176,140,2,.75f}));
 assert(g_menu_xp_count==0);
 draw_menu_xp(); assert(bars.size()==1); // No stale bar on the next frame.
 capture_menu_xp(4,5,36,.25f); draw_menu_xp();
 assert((bars[1]==std::array<float,5>{22,35,108,3,.25f}));
 mode.driver_mode=2;capture_menu_xp(0,0,1,1);assert(g_menu_xp_count==0);
 mode.driver_mode=MODE_MENU;active=nullptr;capture_menu_xp(0,0,1,1);assert(g_menu_xp_count==0);
 active=&viewport;has_mode=false;capture_menu_xp(0,0,1,1);assert(g_menu_xp_count==0);
 has_mode=true;for(int i=0;i<40;++i)capture_menu_xp(0,0,1,1);
 assert(g_menu_xp_count==32);draw_menu_xp();assert(bars.size()==34);
 enable_ff8_xp_bars=false;enable_ff8_hp_bars=true;
 capture_menu_xp(44,138,48,.5f);
 capture_menu_xp(164,55,92,.635f,true);
 draw_menu_xp();assert(bars.size()==35);
 assert((bars.back()==std::array<float,5>{502,185,276,3,.635f}));
 enable_ff8_xp_bars=true;
 capture_menu_xp(114,55,46,.5f);
 capture_menu_xp(164,55,92,.635f,true);
 draw_menu_xp();assert(bars.size()==37);
 assert(bars[35][0]+bars[35][2]<bars[36][0]); // XP and HP bars must not touch.
 enable_ff8_hp_bars=false;
 capture_menu_xp(162,55,94,.635f,true);draw_menu_xp();assert(bars.size()==37);
}
'''
vcvars = Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat')
with tempfile.TemporaryDirectory(prefix='ff8-menu-xp-') as directory:
    temp = Path(directory)
    (temp/'check.cpp').write_text(harness)
    (temp/'run.cmd').write_text(f'@call "{vcvars}" >nul\n@cl /nologo /EHsc /std:c++17 check.cpp /Fe:check.exe >build.log 2>&1\n@if errorlevel 1 (type build.log & exit /b 1)\n@check.exe\n')
    result = subprocess.run(['cmd.exe','/c',str(temp/'run.cmd')],cwd=temp,capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr
print('PASS: compiled menu XP viewport capture, projection, frame clearing, mode guards and capacity')

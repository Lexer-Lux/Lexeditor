"""Check the measured vanilla five-row gauge profile and fill direction."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp').read_text()
gauge=source[source.index('void draw_gauge('):source.index('int level_for_exp(')]
harness=r'''
#include <algorithm>
#include <cassert>
#include <vector>
using ImU32=unsigned;
struct ImVec2 {float x,y;ImVec2(float a,float b):x(a),y(b){}};
struct Rect {ImVec2 from,to;unsigned color;};
struct ImDrawList {std::vector<Rect> rects;
 void AddRectFilled(ImVec2 a,ImVec2 b,unsigned color){rects.push_back({a,b,color});}};
ImDrawList list;
namespace ImGui {ImDrawList *GetForegroundDrawList(){return &list;}}
#define IM_COL32(r,g,b,a) ((unsigned)(r)|((unsigned)(g)<<8)|((unsigned)(b)<<16)|((unsigned)(a)<<24))
#define IM_COL32_A_MASK 0xff000000u
#define IM_COL32_A_SHIFT 24
float scale=1;
float scale_x(float x){return scale*x;}
float scale_y(float y){return scale*y;}
''' + gauge + r'''
int main(){
 for(float factor : {1.f,3.f,5.5f}) for(bool reverse : {false,true}) {
   scale=factor;list.rects.clear();
   draw_gauge(44,138,48,1,.25f,IM_COL32(236,0,0,255),reverse);
   assert(list.rects.size()==8);
   const unsigned alpha[]={255,133,255,43};
   const int rows[]={0,1,3,4};
   for(int i=0;i<4;++i) {
     const auto &a=list.rects[2*i], &b=list.rects[2*i+1];
     assert(a.from.x==44*factor && b.to.x==92*factor);
     assert(a.to.x==(reverse?80:56)*factor && a.to.x==b.from.x);
     assert(a.from.y==138*factor+rows[i]*factor/5.5f);
     assert((a.color>>24)==alpha[i] && (b.color>>24)==alpha[i]);
     assert((a.color&0xffffff)==(reverse?0:236));
     assert((b.color&0xffffff)==(reverse?236:0));
   }
   if(factor==5.5f) {
     // Pixel colors over the reference's gray panel: rows 54..58.
     const int expected[]={236,170,98,236,121};
     for(int row=0;row<5;++row) {
       const int coverage=row==0||row==3?255:row==1?133:row==4?43:0;
       assert((236*coverage+98*(255-coverage)+127)/255==expected[row]);
     }
   }
 }
}
'''
vcvars=Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat')
with tempfile.TemporaryDirectory(prefix='ff8-gauge-') as directory:
    root=Path(directory);(root/'test.cpp').write_text(harness)
    (root/'run.cmd').write_text(f'@call "{vcvars}" >nul\n@cl /nologo /EHsc /std:c++17 test.cpp /Fe:test.exe >build.log 2>&1\n@if errorlevel 1 (type build.log & exit /b 1)\n@test.exe\n')
    result=subprocess.run(['cmd.exe','/c',str(root/'run.cmd')],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
print('PASS: measured vanilla pixel profile, clear center, endpoints and both fill directions at three scales')

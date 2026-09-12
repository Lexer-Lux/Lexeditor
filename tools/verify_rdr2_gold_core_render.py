"""Execute the production core/bar render dispatch with controlled native calls."""
from pathlib import Path
import argparse
import subprocess
import tempfile

PRELUDE = r'''
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
#define sprintf_s std::snprintf
#define CHECK(x) do {if(!(x)) return __LINE__;} while(0)
constexpr bool FALSE=false;
struct ReferenceCanvas {float originX=0,scale=1,screenWidth=1920,screenHeight=1080;};
struct MeterSeat {float x=100,y=100;} g_seats[5];
float g_boxWidth=.0242f,g_boxHeight=.043f,g_nudgeX=0,g_nudgeY=0,g_barRingScale=1.05f;
bool g_showBars=true,g_showCores=true,loaded=true;
int g_spentBarR=229,g_spentBarG=229,g_spentBarB=229,g_spentBarA=255;
int g_goldR=255,g_goldG=196,g_goldB=64,g_goldA=255,requests=0;
std::vector<float> arcs;
std::vector<std::string> sprites;
void drawAuthoredArc(const ReferenceCanvas&,const MeterSeat&,float,float f,int,int,int,int){arcs.push_back(f);}
namespace TXD {
bool HAS_STREAMED_TEXTURE_DICT_LOADED(const char*){return loaded;}
void REQUEST_STREAMED_TEXTURE_DICT(const char*,bool){++requests;}
}
namespace GRAPHICS {
void DRAW_SPRITE(const char*,const char* name,float,float,float,float,float,int,int,int,int,bool){sprites.push_back(name);}
}
'''
TESTS = r'''
int main(){ReferenceCanvas canvas;
 drawMeter(0,0,.5f,canvas);CHECK(arcs.empty());CHECK(sprites.size()==2);
 CHECK(sprites[0]=="lex_gold_core_health_base" && sprites[1]=="lex_gold_core_health_8");
 sprites.clear();drawMeter(1,.2f,0,canvas);CHECK(sprites.empty());
 CHECK(arcs.size()==2 && arcs[1]==.2f);
 arcs.clear();drawMeter(4,.2f,.8f,canvas);
 CHECK(arcs.size()==2 && arcs[1]==.2f);
 CHECK(sprites.size()==2 && sprites[1]=="lex_gold_core_horse_stamina_12");
 sprites.clear();arcs.clear();g_showCores=false;drawMeter(2,0,1,canvas);
 CHECK(sprites.empty() && arcs.empty());g_showCores=true;
 loaded=false;drawMeter(3,.3f,.4f,canvas);
 CHECK(sprites.empty() && requests==1 && arcs.size()==2);
 sprites.clear();arcs.clear();loaded=true;g_showBars=false;
 drawMeter(3,1,.001f,canvas);CHECK(arcs.empty() && sprites.size()==1);
 CHECK(sprites[0]=="lex_gold_core_horse_health_base");
}
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/fortification_hud.cpp').read_text('utf-8')
    code=source[source.index('static const char* kCoreTextureNames'):source.index('static void updateCalibration')]
    variants={'production':code,
              'mixed-timers':code.replace('g_barRingScale, bar,','g_barRingScale, (std::max)(bar,coreFill),'),
              'no-white-base':code.replace('229, 229, 229, 255','229, 229, 229, 0'),
              'missing-load-gate':code.replace('if (!TXD::HAS_STREAMED_TEXTURE_DICT_LOADED(kCoreDictionary))','if (false)')}
    # Record only visible sprites, to reject loss of the opaque white base.
    prelude=PRELUDE.replace('int,int,int,int,bool){sprites.push_back(name);}',
                            'int,int,int,int alpha,bool){if(alpha) sprites.push_back(name);}')
    vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory(prefix='lex-core-render-') as temp:
        folder=Path(temp).resolve()
        assert folder.parent==Path(tempfile.gettempdir()).resolve()
        for name, body in variants.items():
            assert name=='production' or body!=code
            cpp=folder/'test.cpp';exe=folder/'test.exe';batch=folder/'compile.cmd'
            cpp.write_text((prelude+body+TESTS).replace('sprintf_s(texture,','sprintf_s(texture, sizeof(texture),'),'utf-8')
            batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n','utf-8')
            built=subprocess.run(['cmd','/d','/c',str(batch)],cwd=folder,capture_output=True,text=True,timeout=60)
            assert built.returncode==0,built.stdout+built.stderr
            run=subprocess.run([str(exe)],cwd=folder,timeout=10)
            assert (run.returncode==0)==(name=='production'),(name,run.returncode)
            print(('PASS ' if name=='production' else 'REJECTED ')+name)
    print('Independent core/bar draw calls checked; in-game geometry remains unverified.')

if __name__=='__main__':main()

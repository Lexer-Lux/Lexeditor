"""Execute actual camera authoring: time-scaled nudges and failed INI writes."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants
PRELUDE=r'''
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <sstream>
#include <string>
using DWORD=uint32_t;
constexpr int GT_INFO=0,GT_WARN=1,VK_NUMPAD4=4,VK_NUMPAD6=6,VK_NUMPAD8=8,VK_NUMPAD2=2,VK_NUMPAD7=7,VK_NUMPAD5=5;
template<size_t N,class...A>void sprintf_s(char(&b)[N],const char*f,A...a){snprintf(b,N,f,a...);}
std::string g_iniPath="fixture",logs,hud;bool g_gameplayCameraHorizontalClampLogged=false;
bool keys[10]={},edges[10]={},fine=false;int writeCount=0,failAt=-1;
namespace EditorNumpadInput{bool held(int k){return keys[k];}bool pressed(int k){return edges[k];}bool fineStepHeld(){return fine;}}
void gtLog(const char*,int,const std::string&s){logs+=s;}
void drawReconText(const char*s,float,float y){if(y<.8f)hud=s;}
int WritePrivateProfileStringA(const char*,const char*,const char*,const char*){return ++writeCount!=failAt;}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
TESTS=r'''
int main(){
 // Exactly one simulated second, independent of rendered frame frequency.
 DWORD base=1000;
 for(int fps:{30,60,144}){
 auto&p=g_cameraProfiles[0];p.horizontal=1;p.distance=2;p.dirty=false;
 keys[6]=false;calibrateGameplayCamera(p,base,GameplayCameraMode::Standing,false);
 keys[6]=true;for(int i=1;i<=fps;++i)calibrateGameplayCamera(p,base+(1000*i)/fps,GameplayCameraMode::Standing,false);
 CHECK(std::fabs(p.horizontal-4.125f)<.0001f&&p.dirty&&p.distance==2);base+=10000;
 }
 auto&p=g_cameraProfiles[0];float before=p.horizontal;
 calibrateGameplayCamera(p,base,GameplayCameraMode::Standing,false);CHECK(std::fabs(p.horizontal-before-.05f)<.0001f);
 keys[6]=false;keys[2]=true;fine=true;before=p.distance;
 for(int i=1;i<=30;++i)calibrateGameplayCamera(p,base+(1000*i)/30,GameplayCameraMode::Standing,false);
 CHECK(std::fabs(p.distance-before-.3125f)<.0001f);
 keys[2]=false;fine=false;
 // Every failed field must keep that entire profile dirty, while other
 // successful profiles release their reload protection. Writes never short circuit.
 const int n=(int)GameplayCameraMode::Count;
 for(int failed=1;failed<=n*3;++failed){for(auto&v:g_cameraProfiles)v.dirty=true;
 writeCount=0;failAt=failed;logs.clear();CHECK(!saveGameplayCameraProfiles());CHECK(writeCount==n*3);
 for(int i=0;i<n;++i)CHECK(g_cameraProfiles[i].dirty==(i==(failed-1)/3));
 CHECK(logs.find("profiles saved to INI")==std::string::npos);
 writeCount=0;failAt=-1;CHECK(saveGameplayCameraProfiles());for(auto&v:g_cameraProfiles)CHECK(!v.dirty);
 }
 edges[5]=true;writeCount=0;failAt=1;calibrateGameplayCamera(p,base+2000,GameplayCameraMode::Standing,false);
 CHECK(hud.find("save failed")!=std::string::npos&&p.dirty);
 writeCount=0;failAt=-1;calibrateGameplayCamera(p,base+2016,GameplayCameraMode::Standing,false);
 CHECK(hud=="all camera mode values saved"&&!p.dirty);
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'));a=p.parse_args()
    source=(a.runtime_root/'GameplayTweaks/modules/gameplay_camera.cpp').read_text('utf-8')
    structs=source[source.index('enum class GameplayCameraMode'):source.index('static bool g_gameplayCameraConfigLoaded')]
    code=structs+source[source.index('static bool saveGameplayCameraProfiles()'):source.index('static void updateGameplayCameraEditor(')]
    variants={'production':code,
        'frame_step':code.replace('(static_cast<float>(activeMs) / 16.0f)','1.0f'),
        'idle_accumulation':code.replace('nudgeClockKnown && elapsed <= 100 ? elapsed : 16','nudgeClockKnown ? elapsed : 16'),
        'lost_dirty':code.replace('p.dirty = !saved;','p.dirty = false;'),
        'false_success':code.replace('return allSaved;','return true;'),
        'wrong_ui':code.replace('const bool saved = saveGameplayCameraProfiles();','saveGameplayCameraProfiles(); const bool saved = true;')}
    assert all(v!=code for k,v in variants.items() if k!='production')
    run_variants(variants,PRELUDE,TESTS)
if __name__=='__main__':main()

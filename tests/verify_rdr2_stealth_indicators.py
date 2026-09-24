"""Execute production stealth classification, cache ownership, suppression and drawing."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants
PRELUDE=r'''
#include <algorithm>
#include <vector>
#include <cmath>
#include <cstdint>
#include <sstream>
#include <tuple>
#include <type_traits>
using Ped=int;using Player=int;using Hash=int;using DWORD=uint32_t;using BOOL=int;using Void=void;
constexpr int TRUE=1,FALSE=0,GT_INFO=1;
struct Vector3{float x=0,y=0,z=0;};
struct Actor{bool exists=true,dead=false,human=true,combat=false,focus=true,los=true,respond=false,aim=false,flee=false;int vision=1,relation=4,model=10;float suspicion=0,agitation=0;Vector3 pos;};
Actor actors[32];bool hidden=false,paused=false,cinematic=false,sceneExists=false,sceneRunning=false,satchel=false;int64_t scene=4;int snapshots=0,badReads=0,globalReads=0,sceneReads=0;bool nullGlobal=false;float cameraYaw=0;
std::vector<int> pool;struct Draw{float x,y;int red,alpha;};std::vector<Draw> draws;
int64_t* getGlobalPtr(int){++globalReads;return nullGlobal?nullptr:&scene;}
namespace ANIMSCENE{bool _DOES_ANIM_SCENE_EXIST(int){++sceneReads;return sceneExists;}bool _IS_ANIM_SCENE_STARTED(int,int){++sceneReads;return sceneRunning;}}
namespace HUD{bool IS_PAUSE_MENU_ACTIVE(){return paused;}bool IS_HUD_HIDDEN(){return hidden;}}
namespace CAM{bool IS_CINEMATIC_CAM_RENDERING(){return cinematic;}Vector3 GET_FINAL_RENDERED_CAM_ROT(int){return {0,0,cameraYaw};}Vector3 GET_GAMEPLAY_CAM_ROT(int){return {};}}
namespace ENTITY{bool DOES_ENTITY_EXIST(int p){return actors[p].exists;}bool HAS_ENTITY_CLEAR_LOS_TO_ENTITY(int p,int,int){return actors[p].los;}}
namespace PED{bool IS_PED_DEAD_OR_DYING(int p,int){return actors[p].dead;}bool IS_PED_HUMAN(int p){return actors[p].human;}bool IS_PED_IN_COMBAT(int p,int){return actors[p].combat;}bool IS_PED_FLEEING(int p){return actors[p].flee;}int GET_RELATIONSHIP_BETWEEN_PEDS(int p,int){return actors[p].relation;}}
namespace PLAYER{int PLAYER_ID(){return 0;}bool IS_PLAYER_TARGETTING_ENTITY(int,int p,int){return actors[p].aim;}bool IS_PLAYER_FREE_AIMING_AT_ENTITY(int,int p){return actors[p].aim;}}
Vector3 ENTITY_COORDS(int p){if(!actors[p].exists||actors[p].dead)++badReads;return actors[p].pos;}
Hash ENTITY_MODEL(int p){return actors[p].model;}
int sharedWorldPedSnapshot(int*out,int cap){++snapshots;int n=std::min(cap,(int)pool.size());for(int i=0;i<n;++i)out[i]=pool[i];return n;}
bool scriptRunning(const char*){return satchel;}bool developmentModeActive(){return false;}void gtLog(const char*,int,const std::string&){}
namespace GRAPHICS{void DRAW_SPRITE(const char*,const char*,float x,float y,float,float,float,int r,int,int,int a,int){draws.push_back({x,y,r,a});}}
template<class R,class...A> R invoke(uint64_t h,A...args){
 if constexpr(std::is_void_v<R>)return;
 else {auto t=std::make_tuple(args...);using First=std::tuple_element_t<0,decltype(t)>;
 if constexpr(std::is_integral_v<First>){int p=std::get<0>(t);
 if(h==0x06087579E7AA85A9)return (R)actors[p].focus;
 if(h==0x7F9B9791D4CB71F6)return (R)actors[p].vision;
 if(h==0x77525BBF433F2CD6)return (R)actors[p].respond;
 if constexpr(sizeof...(A)==3)if(h==0x42688E94E96FD9B4)return (R)(std::get<1>(t)==9?actors[p].suspicion:actors[p].agitation);
 }return (R)1;}}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
TESTS=r'''
void reset(){for(auto&a:actors)a=Actor{};g_stealthIndicators.clear();g_stealthIndicatorLastScan=0;draws.clear();pool.clear();hidden=paused=cinematic=sceneExists=sceneRunning=satchel=false;badReads=snapshots=globalReads=sceneReads=0;nullGlobal=false;cameraYaw=0;}
bool relevant(int p,StealthIndicatorLevel*level){bool focus=false;return stealthIndicatorRelevant(p,1,&focus,level);}
int main(){
 for(int mode=0;mode<4;++mode){reset();paused=mode==2;satchel=mode==3;
 updateStealthDetectionIndicators(mode==1?0:1,100,mode==0);
 CHECK(globalReads==0&&sceneReads==0&&snapshots==0&&draws.empty());}
 reset();nullGlobal=true;pool={2};updateStealthDetectionIndicators(1,100,false);CHECK(sceneReads==0&&draws.size()==1);
 reset();StealthIndicatorLevel level;actors[2].relation=0;CHECK(!relevant(2,&level));
 actors[2].relation=4;CHECK(relevant(2,&level)&&level==StealthIndicatorLevel::Focused);
 actors[2].vision=2;CHECK(!relevant(2,&level));actors[2].vision=1;actors[2].los=false;CHECK(!relevant(2,&level));
 actors[2].combat=true;CHECK(relevant(2,&level)&&level==StealthIndicatorLevel::Alert);
 actors[2].combat=false;actors[2].relation=0;actors[2].agitation=1;CHECK(!relevant(2,&level));
 actors[2].aim=actors[2].flee=true;CHECK(relevant(2,&level)&&level==StealthIndicatorLevel::Suspicious);
 actors[2].aim=false;actors[2].suspicion=.2;CHECK(relevant(2,&level));
 actors[2].dead=true;CHECK(!relevant(2,&level));actors[2].dead=false;actors[2].human=false;CHECK(!relevant(2,&level));
 for(int mode=0;mode<6;++mode){reset();pool={2};updateStealthDetectionIndicators(1,100,false);CHECK(draws.size()==1);
 hidden=mode==0;cinematic=mode==1;sceneExists=sceneRunning=mode==2;paused=mode==3;satchel=mode==4;
 draws.clear();updateStealthDetectionIndicators(1,101,mode==5);CHECK(draws.empty()&&g_stealthIndicators.empty()&&snapshots==1);
 hidden=cinematic=sceneExists=sceneRunning=paused=satchel=false;updateStealthDetectionIndicators(1,102,false);CHECK(draws.size()==1&&snapshots==2);}
 reset();sceneExists=true;pool={2};updateStealthDetectionIndicators(1,100,false);CHECK(draws.size()==1);
 for(int mode=0;mode<3;++mode){reset();pool={2};updateStealthDetectionIndicators(1,100,false);draws.clear();
 if(mode==0)actors[2].exists=false;if(mode==1)actors[2].dead=true;if(mode==2)actors[2].model=11;
 updateStealthDetectionIndicators(1,101,false);CHECK(draws.empty()&&g_stealthIndicators.empty()&&!badReads&&snapshots==1);}
 reset();for(int p=2;p<8;++p){actors[p].pos={0,(float)p,0};pool.push_back(p);}actors[7].combat=true;actors[6].suspicion=.5;
 updateStealthDetectionIndicators(1,100,false);CHECK(draws.size()==4&&draws[0].red==194&&draws[1].red==230);
 // The two nearest focused observers must fill the remaining two slots.
 CHECK(g_stealthIndicators.size()==6);
 actors[2].pos={2,0,0};actors[3].pos={-3,0,0};draws.clear();
 updateStealthDetectionIndicators(1,101,false);CHECK(draws.size()==4&&draws[2].x>.63f&&draws[3].x<.37f);
 pool.clear();draws.clear();updateStealthDetectionIndicators(1,450,false);CHECK(draws.size()==4&&draws[0].alpha==235);
 draws.clear();updateStealthDetectionIndicators(1,700,false);CHECK(draws.size()==4&&draws[0].alpha>0&&draws[0].alpha<235);
 draws.clear();updateStealthDetectionIndicators(1,951,false);CHECK(draws.empty());
 reset();pool={2};actors[2].pos={0,10,0};cameraYaw=90;updateStealthDetectionIndicators(1,100,false);CHECK(draws.size()==1&&draws[0].x>.63f);
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'));a=p.parse_args()
    source=(a.runtime_root/'GameplayTweaks/modules/stealth_indicators.cpp').read_text('utf-8')
    changes={
        'hud':'HUD::IS_HUD_HIDDEN()', 'cinematic':'CAM::IS_CINEMATIC_CAM_RENDERING()',
        'story':' || storyScene', 'identity':'ENTITY_MODEL(state.ped) != state.model',
        'priority':'(int)a.state.level > (int)b.state.level',
        'camera':'CAM::GET_FINAL_RENDERED_CAM_ROT(2)',
        'civilian':'(!hostile || !focused)',
        'nearest':'a.distanceSquared < b.distanceSquared',
        'cap':'(size_t)4',
    }
    replacements={'hud':'false','cinematic':'false','story':'','identity':'false','priority':'(int)a.state.level < (int)b.state.level','camera':'CAM::GET_GAMEPLAY_CAM_ROT(2)','civilian':'(!focused)','nearest':'a.distanceSquared > b.distanceSquared','cap':'(size_t)5'}
    variants={'production':source}
    for key,old in changes.items():
        assert old in source,old
        variants[key]=source.replace(old,replacements[key],1)
    start=source.index('\tconst auto scenePtr = getGlobalPtr(43800);')
    end=source.index('\tif (HUD::IS_HUD_HIDDEN()',start)
    scene_block=source[start:end]
    moved=source[:start]+source[end:]
    insertion=moved.index('\tif (unavailable || !playerPed',moved.index('static void updateStealthDetectionIndicators('))
    variants['scene_before_guard']=moved[:insertion]+scene_block+moved[insertion:]
    run_variants(variants,PRELUDE,TESTS)
if __name__=='__main__':main()

"""Execute the production opt-in reticle identity probe and pending-handle lifetime."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants

PRELUDE=r'''
#include <cmath>
#include <cstdint>
#include <sstream>
#include <string>
using Ped=int;using Entity=int;using DWORD=uint32_t;using BOOL=int;
constexpr int FALSE=0,GT_INFO=1,VK_F10=121;
struct Vector3{float x,y,z;};
bool g_compendiumGlintProbeEnabled=false,g_compendiumGlintProbeKeyWasDown=false;
unsigned g_compendiumGlintProbeCapture=0;
DWORD now=0;bool key=false,pending=true,targetExists=true,focused=true;int started=0,live=0,peak=0,logged=0;
std::string lastLog;
DWORD GetTickCount(){return now;}int GetAsyncKeyState(int){return key?0x8000:0;}
void gtLog(const char*,int,const std::string& s){lastLog=s;}
namespace EditorNumpadInput {bool editorWindowFocused(){return focused;}}
namespace ENTITY {bool DOES_ENTITY_EXIST(int e){return e!=7||targetExists;}bool IS_ENTITY_DEAD(int){return false;}}
Vector3 ENTITY_COORDS(int){return {};}
namespace CAM {Vector3 GET_FINAL_RENDERED_CAM_COORD(){return {}; }Vector3 GET_FINAL_RENDERED_CAM_ROT(int){return {};}}
int START_LOS_PROBE(Vector3,Vector3,int,int){++live;if(live>peak)peak=live;return ++started;}
int SHAPE_RESULT(int,BOOL*hit,Vector3*point,Vector3*,Entity*entity){if(pending)return 1;--live;*hit=1;*point={0,4,0};*entity=7;return 2;}
void logCompendiumEntity(int e,Vector3){if(e==7)++logged;}
void captureCompendiumGlintProbe(int){++g_compendiumGlintProbeCapture;}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
TESTS=r'''
void tick(unsigned t,bool down,bool blocked=false,int ped=1){now=t;key=down;updateCompendiumGlintProbe(ped,blocked);}
int main(){
 tick(1,true);CHECK(!started);g_compendiumGlintProbeEnabled=true;
 tick(2,false);tick(3,true);CHECK(started==1 && live==1);
 tick(4,true);CHECK(started==1);
 tick(5,false);tick(6,true);CHECK(started==1 && g_compendiumGlintProbeCapture==1);
 pending=false;tick(7,false);CHECK(logged==1 && !live);
 // A menu cancels ownership; a ready result is not logged as a fresh object.
 pending=true;tick(8,true);tick(9,false,true);pending=false;tick(10,false);CHECK(logged==1);
 // Expiration does not drop the pending handle, even after repeated presses.
 pending=true;tick(20,true);tick(21,false);tick(2000,true);CHECK(started==3 && live==1);
 tick(2001,false);tick(2002,true);CHECK(started==3 && live==1 && peak==1);
 pending=false;tick(2003,false);CHECK(logged==1 && live==0);
 // Holding the capture key while leaving a menu is not a fresh request.
 tick(2010,true,true);tick(2011,true);CHECK(started==3);
 tick(2012,false);pending=true;tick(2013,true);CHECK(started==4);
 targetExists=false;pending=false;tick(2014,false);CHECK(logged==1);
 targetExists=true;pending=true;tick(2020,true);tick(2021,false,false,2);
 pending=false;tick(2022,false,false,2);CHECK(logged==1);
 focused=false;tick(2030,true);CHECK(started==5);
 focused=true;tick(2031,true);CHECK(started==5);
 tick(2032,false);pending=true;tick(2033,true);CHECK(started==6);
 focused=false;tick(2034,false);pending=false;tick(2035,false);CHECK(logged==1);
 focused=true;

}
'''
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/compendium_glint_probe.cpp').read_text('utf-8')
    branch=source[source.index('static void updateCompendiumGlintProbe('):]
    for forbidden in ('worldGetAllObjects','worldGetAllPickups','SET_PICKUP','BLOCK_PICKUP','INVENTORY_REMOVE','UNLOCK_SET'):
        assert forbidden not in branch,forbidden
    variants={'production':branch,
      'duplicate-pending-probes':branch.replace('if (ray) {\n\t\t\tgtLog','if (false) {\n\t\t\tgtLog'),
      'expired-result-published':branch.replace('now - startedAt > 1500','false'),
      'menu-result-published':branch.replace('!allowed || playerPed != owner','false || playerPed != owner'),
      'off-app-capture':branch.replace('EditorNumpadInput::editorWindowFocused()','true'),
      'reused-player-result':branch.replace('playerPed != owner','false'),
      'deleted-target-queried':branch.replace('ENTITY::DOES_ENTITY_EXIST(entity)','true')}
    run_variants(variants,PRELUDE,TESTS)
    print('PASS: opt-in identity capture, one pending ray, cancellation/expiry and exact live target. No ownership inference or effect mutation.')

if __name__=='__main__':main()

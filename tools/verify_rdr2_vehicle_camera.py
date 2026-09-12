"""Execute the production vehicle camera owner with controlled native readbacks."""
from verify_rdr2_camera_switch import SOURCE, run_variants
from pathlib import Path
import argparse

PRELUDE=r"""
#include <cstdint>
#include <sstream>
#include <string>
using DWORD=uint32_t;using Ped=int;using Hash=int;using Any=int;
constexpr bool FALSE=false;constexpr int GT_INFO=0;
bool vehicle=true,aim=false,control=true,renderedFirst=false,release=false;
int disabled=0,releaseReads=0,firstForces=0,thirdForces=0,unsafeReads=0;
int g_gameplayCameraMountedZoomLevel=0;
namespace PED {bool IS_PED_IN_ANY_VEHICLE(Ped,bool){return vehicle;}}
namespace CAM {bool IS_AIM_CAM_ACTIVE(){return aim;}}
namespace PLAYER {int PLAYER_ID(){return 1;}bool IS_PLAYER_CONTROL_ON(int){return control;}}
namespace PAD {
void DISABLE_CONTROL_ACTION(int group,Hash,bool){disabled|=(group==0?1:2);}
bool IS_DISABLED_CONTROL_JUST_RELEASED(int,Hash){++releaseReads;if(disabled!=3)++unsafeReads;return release;}
}
Hash joaat(const char*){return 1;}
bool gameplayCameraAimHeld(){return aim;}
bool gameplayCameraFirstPerson(){return renderedFirst;}
void gameplayCameraForceThirdPersonLevel(int){++thirdForces;}
template<class T>T invoke(uint64_t){++firstForces;return 0;}
std::string logs;
void gtLog(const char*,int,const std::string& line){logs+=line;}
"""
TESTS=r"""
#define CHECK(x) do {if(!(x)) return __LINE__;}while(0)
void frame(){disabled=0;releaseReads=0;firstForces=thirdForces=0;}
int main(){
 frame();CHECK(gameplayCameraUpdateVehiclePolicy(1,true,100)==GameplayCameraVehiclePolicy::ThirdPerson);
 CHECK(disabled==3 && thirdForces==1 && firstForces==0 && unsafeReads==0);
 frame();release=true;CHECK(gameplayCameraUpdateVehiclePolicy(1,true,200)==GameplayCameraVehiclePolicy::FirstPerson);
 CHECK(firstForces==1 && thirdForces==0 && unsafeReads==0);
 frame();release=false;CHECK(gameplayCameraUpdateVehiclePolicy(1,true,300)==GameplayCameraVehiclePolicy::FirstPerson);
 CHECK(firstForces==1 && thirdForces==0);
 // A desired first-person state is not evidence of rendered first person.
 logs.clear();frame();gameplayCameraUpdateVehiclePolicy(1,true,4000);
 CHECK(logs.find("selected=first rendered=third")!=std::string::npos);
 frame();release=true;CHECK(gameplayCameraUpdateVehiclePolicy(1,true,4100)==GameplayCameraVehiclePolicy::ThirdPerson);
 CHECK(thirdForces==1 && firstForces==0);
 // Aim, loss of player control, exit and global ineligibility release ownership.
 for(int i=0;i<4;++i){
 frame();release=false;aim=i==0;control=i!=1;vehicle=i!=2;
 CHECK(gameplayCameraUpdateVehiclePolicy(1,i!=3,4200+i)==GameplayCameraVehiclePolicy::Inactive);
 CHECK(disabled==0 && releaseReads==0 && firstForces==0 && thirdForces==0);
 }
 frame();aim=false;control=vehicle=true;renderedFirst=true;
 CHECK(gameplayCameraUpdateVehiclePolicy(1,true,4300)==GameplayCameraVehiclePolicy::FirstPerson);
 CHECK(firstForces==1 && thirdForces==0);
}
"""

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--runtime-root",type=Path,default=SOURCE.parents[2])
    args=parser.parse_args()
    source=(args.runtime_root / "GameplayTweaks/modules/gameplay_camera.cpp").read_text("utf-8")
    start=source.index("enum class GameplayCameraVehiclePolicy")
    end=source.index("static void gameplayCameraAbortTransitionCapture",start)
    branch=source[start:end]
    variants={"production":branch,
      "missing-disable":branch.replace("PAD::DISABLE_CONTROL_ACTION(2, nextCamera, FALSE);", ""),
      "missing-first-force":branch.replace("invoke<Any>(0x90DA5BA5C2635416);", ""),
      "aim-owned":branch.replace("!CAM::IS_AIM_CAM_ACTIVE() && !gameplayCameraAimHeld() &&", ""),
      "request-as-rendered":branch.replace('<< " rendered=" << (gameplayCameraFirstPerson()', '<< " rendered=" << (firstPerson')}
    assert all(code!=branch for name,code in variants.items() if name!="production")
    run_variants(variants,PRELUDE,TESTS)
    print("Vehicle ownership verified. Actual wagon/cart/buggy camera rendering remains unverified.")
if __name__=="__main__":main()

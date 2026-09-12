"""Execute the production horse-recovery ownership and gait-command branch."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants

PRELUDE=r'''
#include <cmath>
#include <cstdint>
#include <sstream>
#include <string>
using Ped=int;using DWORD=uint32_t;constexpr int TRUE=1,GT_INFO=1;
int mount=2,writes=0,reads=0;float desired=3;bool exists=true,dead=false,ragdoll=false,swim=false,jump=false,fall=false,accept=true;
std::string logText;
void gtLog(const char*,int,const std::string& line){logText=line;}
namespace ENTITY {bool DOES_ENTITY_EXIST(int){return exists;}}
namespace PED {
int GET_MOUNT(int){return mount;}
bool IS_PED_DEAD_OR_DYING(int,int){return dead;}
bool IS_PED_RAGDOLL(int){return ragdoll;}
bool IS_PED_SWIMMING(int){return swim;}
bool IS_PED_JUMPING(int){return jump;}
bool IS_PED_FALLING(int){return fall;}
}
namespace TASK {
float GET_PED_DESIRED_MOVE_BLEND_RATIO(int){++reads;return desired;}
void SET_PED_DESIRED_MOVE_BLEND_RATIO(int horse,float value){if(horse!=mount)writes+=1000;++writes;if(accept)desired=value;}
}
float ENTITY_SPEED(int){return 6;}
float GET_PED_STAMINA(int){return 16;}
float horseMovementStaminaRate(int){return 0;}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
TESTS=r'''
int main(){
 updateHorseExhaustionRecovery(1,2,false,1);CHECK(!writes);CHECK(logText.find("idle")!=std::string::npos);
 updateHorseExhaustionRecovery(1,2,true,10);CHECK(writes==1 && desired==1);
 CHECK(logText.find("desiredAfter=1")!=std::string::npos);
 desired=3;updateHorseExhaustionRecovery(1,2,true,20);CHECK(writes==1);
 updateHorseExhaustionRecovery(1,2,true,110);CHECK(writes==2 && desired==1);
 desired=0;updateHorseExhaustionRecovery(1,2,true,210);CHECK(writes==2 && desired==0);
 desired=3;updateHorseExhaustionRecovery(1,2,false,211);CHECK(writes==2 && desired==3);
 swim=true;updateHorseExhaustionRecovery(1,2,true,212);CHECK(writes==2);
 swim=false;jump=true;updateHorseExhaustionRecovery(1,2,true,312);CHECK(writes==2);
 jump=false;fall=true;updateHorseExhaustionRecovery(1,2,true,412);CHECK(writes==2);
 fall=false;ragdoll=true;updateHorseExhaustionRecovery(1,2,true,512);CHECK(writes==2);
 ragdoll=false;dead=true;updateHorseExhaustionRecovery(1,2,true,612);CHECK(writes==2);
 dead=false;mount=3;updateHorseExhaustionRecovery(1,2,true,712);CHECK(writes==2);
 updateHorseExhaustionRecovery(1,3,true,713);CHECK(writes==3 && desired==1);
 desired=NAN;updateHorseExhaustionRecovery(1,3,true,813);CHECK(writes==3);
 // Failed setters remain visible as before/after=3, not reported as recovery.
 desired=3;accept=false;updateHorseExhaustionRecovery(1,3,true,1800);
 CHECK(logText.find("desiredAfter=3")!=std::string::npos);
 CHECK(logText.find("speed=6")!=std::string::npos && logText.find("stamina=16")!=std::string::npos);
}
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/horse_exhaustion_recovery.cpp').read_text('utf-8')
    for forbidden in ('SET_HORSE_CORE','SET_PED_STAMINA','SET_PED_MAX_MOVE_BLEND_RATIO','SET_CONTROL_NORMAL','CLEAR_PED_TASKS'):
        assert forbidden not in source,forbidden
    scripts=args.runtime_root/'_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel'
    assert 'TASK::SET_PED_DESIRED_MOVE_BLEND_RATIO(mount, 0f)' in (scripts/'act_hunting_2.ysc.c').read_text('utf-8')
    assert 'PED::SET_PED_MAX_MOVE_BLEND_RATIO(mount, 1f)' in (scripts/'act_cajav_homerob1.ysc.c').read_text('utf-8')
    variants={'production':source,
        'missing-gait-command':source.replace('TASK::SET_PED_DESIRED_MOVE_BLEND_RATIO(horse, 1.0f);',''),
        'healthy-horse-slowdown':source.replace('rider && horse && exhausted','rider && horse'),
        'wrong-mount-owned':source.replace('PED::GET_MOUNT(rider) == horse','true'),
        'swimming-slowdown':source.replace('!PED::IS_PED_SWIMMING(horse)','true'),
        'stationary-horse-forced-to-walk':source.replace('before > 1.0f','before >= 0.0f'),
        'per-frame-command-spam':source.replace('now + 100','now + 1')}
    run_variants(variants,PRELUDE,TESTS)
    print('PASS: exhaustion-only gait request, 10 Hz cadence, ownership and safety gates; native gait and recovery still need game acceptance.')

if __name__=='__main__':main()

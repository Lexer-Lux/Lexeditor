"""Execute production stow completion/recovery branches with controlled task state."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants
PRELUDE=r'''
#include <cstdint>
#include <string>
using DWORD=uint32_t;using LONG=int32_t;constexpr int TRUE=1,FALSE=0;
int ped=1,status=7,visible=0,restores=0,newInput=0;bool clip=false,input=false;
DWORD now=0,stowUntil=0,pressStart=0,enterAt=0,transitionRateLastSeenAt=0;
bool stowing=false,stowRecovery=false,holdDeferredByStow=false,ignoreUntilRelease=false,pressing=false,loggedHold=false,latched=false,scopeWasUp=false,g_binocularCoverKeyOwned=false;
bool transitionRateApplied=false,transitionRateSawClip=false;int previousWeapon=0,binoWeapon=0;
namespace TASK{int GET_SCRIPT_TASK_STATUS(int,int,int){return status;}}
namespace ENTITY{bool IS_ENTITY_PLAYING_ANIM(int,const char*,const char*,int){return clip;}}
void suppressBinocularActions(){}void suppressNativeBinocularPutAwayPrompt(){}bool maintainTransitionRate(){return clip;}
void restoreTransitionRate(const char*){++restores;}void binoLog(const char*){}void SET_PED_CURRENT_WEAPON_VISIBLE(int,int,int,int,int){++visible;}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
TESTS=r'''
void reset(){stowing=true;stowRecovery=false;stowUntil=1000;holdDeferredByStow=false;ignoreUntilRelease=pressing=false;status=7;clip=false;visible=restores=newInput=0;}
int main(){
 reset();tick(999,true);CHECK(stowing&&!visible);tick(1000,true);CHECK(!stowing&&visible==1&&pressing&&pressStart==1000);
 for(int s:{0,1}){reset();status=s;tick(1000,true);CHECK(stowing&&!visible);tick(3000,true);CHECK(stowing&&!visible);status=7;tick(3001,true);CHECK(!stowing&&visible==1&&pressing);}
 reset();clip=true;tick(1000,true);CHECK(stowing&&!visible);clip=false;tick(1001,true);CHECK(!stowing&&visible==1);
 // Timeout does not publish completion, show the weapon or replay queued input.
 reset();status=1;tick(6000,true);CHECK(stowRecovery&&!stowing&&!pressing&&ignoreUntilRelease&&!visible&&!newInput);
 tick(6001,true);tick(6002,false);tick(6003,true);CHECK(stowRecovery&&!newInput&&!visible);
 // Task can end while the authored exit clip remains active.
 status=7;clip=true;tick(6004,true);CHECK(stowRecovery&&!newInput);
 clip=false;tick(6005,true);CHECK(!stowRecovery&&ignoreUntilRelease&&!newInput);
 tick(6006,true);CHECK(!newInput);tick(6007,false);tick(6008,true);CHECK(newInput==1);
 // Minimum-window comparison works across the uint32 clock rollover.
 reset();stowUntil=20;tick(0xfffffff0u,true);CHECK(stowing&&!visible);tick(21,true);CHECK(!stowing&&visible==1);
}
'''
def block(s,start):
    begin=s.index(start);brace=s.index('{',begin);depth=1;i=brace+1
    while depth:
        if s[i]=='{':depth+=1
        elif s[i]=='}':depth-=1
        i+=1
    return s[begin:i]
def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'));a=p.parse_args()
    s=(a.runtime_root/'GameplayTweaks/modules/combat_inventory.cpp').read_text('utf-8')
    helper=block(s,'auto stowPresentationRunning = [&]() -> bool').replace('auto stowPresentationRunning = [&]() -> bool','static bool stowPresentationRunning()')
    recovery=block(s,'if (stowRecovery) {')
    latch=block(s,'if (ignoreUntilRelease) {')
    stow=block(s,'if (stowing) {')
    code=helper+'\nvoid tick(DWORD t,bool down){now=t;input=down;'+recovery+latch+stow+'if(input)++newInput;}\n'
    variants={'production':code,
      'timer_only':code.replace('const bool stowStillRunning = stowPresentationRunning();','const bool stowStillRunning = false;'),
      'no_recovery':code.replace('stowRecovery = true;','stowRecovery = false;'),
      'ignore_clip':code.replace('status == 0 || status == 1 || ENTITY::IS_ENTITY_PLAYING_ANIM(\n\t\t\tped, "mech_inventory@binoculars", "hold_2_exit", 1) != FALSE','status == 0 || status == 1'),
      'held_reentry':code.replace('if (stowRecovery) {\n\t\tg_binocularCoverKeyOwned = false;\n\t\tignoreUntilRelease = true;','if (stowRecovery) {\n\t\tg_binocularCoverKeyOwned = false;\n\t\tignoreUntilRelease = false;')}
    assert all(v!=code for k,v in variants.items() if k!='production')
    run_variants(variants,PRELUDE,TESTS)
if __name__=='__main__':main()

"""Execute RDR2's production climbing transitions with controlled native readbacks.

No game process, installed files, window, or game SDK is used by this verifier.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile

PRELUDE = r'''
#define assert(condition) do { if (!(condition)) return __LINE__; } while (0)
#include <cstdint>
#include <cmath>
#include <sstream>
#include <string>
using DWORD=uint32_t; using Ped=int;
constexpr bool TRUE=true;
struct Vector3 { float x=0,y=0,z=0; };
enum class ClimbState { Grounded, Climbing, ToppingOut, Airborne, Grabbing };
enum class ClimbMotion { Idle };
ClimbState g_climbState=ClimbState::ToppingOut;
DWORD g_climbStateAt=100, g_climbTopOutAt=0, g_climbNativeTopOutTraceAt=0;
DWORD g_climbTopOutRejectedAt=0,g_climbLastContactAt=0,g_climbLeapAt=0;
bool g_climbPhysicsOwned=true,g_climbNativeTopOutObserved=false;
bool g_climbNativeTopOutStarted=true,g_climbTopOutBlockedUntilRelease=false,g_climbReverseGrab=false;
int g_climbProtectedCore=0,g_climbCache=0;
ClimbMotion g_climbMotion=ClimbMotion::Idle;
const char *g_climbAnimClip=nullptr,*g_climbAnimDictInUse=nullptr;
Vector3 g_climbAnchor{},g_climbLeapFrom{};
bool nativeClimb=false,falling=false,inAir=false; int status=1;
int coords=0,velocity=0,clears=0,releases=0,attachments=0;
std::string reason;
namespace PED {
bool IS_PED_CLIMBING(Ped){return nativeClimb;} bool IS_PED_VAULTING(Ped){return false;}
bool IS_PED_FALLING(Ped){return falling;} void SET_PED_CAN_RAGDOLL(Ped,bool){}
}
namespace ENTITY {
float GET_ENTITY_HEIGHT_ABOVE_GROUND(Ped){return 10;}
bool IS_ENTITY_IN_AIR(Ped,int){return inAir;}
}
namespace TASK {
int GET_SCRIPT_TASK_STATUS(Ped,int,bool){return status;}
void CLEAR_PED_TASKS(Ped,bool,bool){++clears;}
}
int joaat(const char*){return 0;}
void SET_ENTITY_VELOCITY(Ped,Vector3){++velocity;}
void SET_COORDS_NO_OFFSET_ALIGNED(Ped,Vector3){++coords;}
void releaseClimbPhysics(Ped,bool){g_climbPhysicsOwned=false;++releases;}
void setClimbState(ClimbState state,const char *why){g_climbState=state;reason=why;}
void climbLog(const std::string&){}
float cvLen(Vector3 v){return std::sqrt(v.x*v.x+v.y*v.y+v.z*v.z);}
Vector3 cvSub(Vector3 a,Vector3 b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
Vector3 ENTITY_COORDS(Ped){return {3,0,0};}
float GET_STAMINA_BAR(int){return 100;}
int GET_CORE(Ped,int){return 100;}
bool IS_PED_FALLING(Ped){return falling;}
void attachClimbPhysics(Ped,int){++attachments;g_climbPhysicsOwned=true;}
void leaveClimbing(Ped,const char *why,bool){setClimbState(ClimbState::Grounded,why);}
void update(DWORD now,bool airborne,bool steepSurface=false){const Ped ped=1;const int player=1;
'''
TESTS = r'''
}
void reset(){
 g_climbState=ClimbState::ToppingOut;g_climbStateAt=100;g_climbTopOutAt=0;
 g_climbPhysicsOwned=true;g_climbNativeTopOutObserved=false;g_climbNativeTopOutStarted=true;
 g_climbTopOutBlockedUntilRelease=false;nativeClimb=false;falling=false;inAir=false;status=1;
 coords=velocity=clears=releases=attachments=0;reason.clear();
}
int main(){
 // Accepted task status alone never releases a supported lip.
 reset();update(300,false);assert(g_climbPhysicsOwned && releases==0 && coords==1);
 // Terminal rejection retains the lip instead of falling or teleporting to the roof.
 reset();status=8;update(400,false);assert(g_climbState==ClimbState::Climbing && g_climbPhysicsOwned);
 assert(g_climbTopOutBlockedUntilRelease && releases==0);
 // A real native mantle takes ownership once, with no coordinate writes after transfer.
 reset();nativeClimb=true;update(300,true);assert(releases==1 && coords==0);
 update(400,true);assert(releases==1 && coords==0);
 // Ending the animation while falling is not a successful landing, even with terminal status.
 nativeClimb=false;falling=inAir=true;status=8;update(500,true);
 assert(g_climbState==ClimbState::ToppingOut && coords==0);
 // Landing after the fall can finish; the runtime has actually observed the native traversal.
 falling=inAir=false;update(600,false);assert(g_climbState==ClimbState::Grounded);
 assert(reason=="native_top_out_complete");
 // A stalled traversal yields at its live position without killing fall velocity.
 reset();nativeClimb=true;update(300,true);nativeClimb=false;falling=inAir=true;
 const int beforeVelocity=velocity;update(5200,true);
 assert(g_climbState==ClimbState::Airborne && coords==0 && velocity==beforeVelocity);
 // A nearby wall must not capture the same failed mantle during the cooldown.
 update(5300,true,true);assert(attachments==0 && g_climbState==ClimbState::Airborne);
 update(7100,true,true);assert(attachments==1);
}
'''

def branch(source):
    start=source.index('\tif (g_climbState == ClimbState::Airborne) {')
    end=source.index('\tif (g_climbState == ClimbState::Dismounting) {',start)
    return source[start:end]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/movement.cpp').read_text('utf-8')
    production=branch(source)
    variants={'production':production,
      'fall-called-grounded':production.replace('!nativeTraversal && !airborne','!nativeTraversal'),
      'fall-velocity-cleared':production.replace('if (!airborne) SET_ENTITY_VELOCITY','SET_ENTITY_VELOCITY'),
      'cooldown-bypassed':production.replace('leapClear && !topOutCoolingDown &&','leapClear &&'),
      'timeout-called-grounded':production.replace('airborne ? ClimbState::Airborne : ClimbState::Grounded','ClimbState::Grounded')}
    compiler=shutil.which('g++') or shutil.which('clang++')
    vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    if not compiler and not vcvars.is_file():raise RuntimeError('A C++ compiler is required')
    with tempfile.TemporaryDirectory(prefix='lex-climb-test-') as temp:
      folder=Path(temp).resolve()
      assert folder.parent==Path(tempfile.gettempdir()).resolve()
      for name,code in variants.items():
        assert name=='production' or code!=production, f'Mutation did not apply: {name}'
        cpp=folder/'test.cpp';exe=folder/('test.exe' if os.name=='nt' else 'test')
        cpp.write_text(PRELUDE+code+TESTS,'utf-8')
        if compiler:command=[compiler,'-std=c++17',str(cpp),'-o',str(exe)]
        else:
          batch=folder/'compile.cmd'
          batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n','utf-8')
          command=['cmd','/d','/c',str(batch)]
        result=subprocess.run(command,cwd=folder,capture_output=True,text=True,errors='replace',timeout=60)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        result=subprocess.run([str(exe)],cwd=folder,capture_output=True,timeout=10)
        assert (result.returncode==0)==(name=='production'),(name,result.returncode,result.stderr)
        print(('PASS ' if name=='production' else 'REJECTED ')+name)
    print('Production climb transitions executed; four regressions rejected. In-game motion remains unverified.')
if __name__=='__main__':main()

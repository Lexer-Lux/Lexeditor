"""Execute production Recon disk geometry and async probe ownership without a game."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants

PRELUDE = r'''
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstddef>
template<size_t N,class...Args>int sprintf_s(char(&s)[N],const char*f,Args...args){return std::snprintf(s,N,f,args...);}
void reconLog(const char*){}
#include <algorithm>
using DWORD=uint32_t; using Entity=int; using Ped=int; using Hash=unsigned; using BOOL=int;
constexpr int TRUE=1,FALSE=0;
struct Vector3 {float x,y,z;};
float reconDistance(Vector3 a,Vector3 b){return std::sqrt((a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z));}
float g_reconAimRadius=.05f,g_reconMaxDistance=200;
Vector3 g_reconReticleHit={}; bool g_reconReticleHitValid=false; DWORD g_reconReticleHitAt=0;
const char* kReconMeterDict="rpg_meter";
bool pending=false,entityExists=true; int starts=0,outstanding=0,peak=0,draws=0;
Vector3 camera={}; float aspect=16.f/9;
Hash ENTITY_MODEL(int){return 55;}
namespace ENTITY {
bool DOES_ENTITY_EXIST(int){return entityExists;}
Vector3 GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(int,float x,float y,float z){return {x,y,z};}
Vector3 GET_OFFSET_FROM_ENTITY_GIVEN_WORLD_COORDS(int,float x,float y,float z){return {x,y,z};}
}
namespace CAM {Vector3 GET_FINAL_RENDERED_CAM_COORD(){return camera;}
Vector3 GET_FINAL_RENDERED_CAM_ROT(int){return {};}}
namespace GRAPHICS {
void GET_SCREEN_RESOLUTION(int*w,int*h){*w=1920;*h=1080;}
bool GET_SCREEN_COORD_FROM_WORLD_COORD(float x,float y,float z,float*sx,float*sy){
 if(y<=0)return false; *sx=.5f+x/(y*2);*sy=.5f-z/(y*2*aspect);return true;}
void DRAW_SPRITE(const char*,const char*,float,float,float,float,float,int,int,int,int,BOOL){++draws;}
}
template<class T> T invoke(uint64_t,const char*){return T(1);}
int SHAPE_RESULT(int,BOOL*hit,Vector3*point,Vector3*,Entity*entity){
 if(pending)return 1;--outstanding;*hit=TRUE;*point={0,20,0};*entity=7;return 2;}
int START_LOS_PROBE(Vector3,Vector3,int,int){++outstanding;peak=std::max(peak,outstanding);return ++starts;}
#define CHECK(x) do {if(!(x))return __LINE__;}while(0)
'''
TESTS = r'''
int main(){
 // Pixel circles on square, 16:9 and ultrawide screens; no distorted Y gate.
 for(float a : {1.f,16.f/9,32.f/9})
  CHECK(std::fabs(ReconArea::distance(.5f,.5f+.05f*a,a)-.05f)<.00001f);
 bool interior=false,edge=false; bool quadrants[4]={};
 for(unsigned i=0;i<ReconArea::Samples;++i){auto p=ReconArea::sample(i);
  float r=std::sqrt(p.x*p.x+p.y*p.y);CHECK(r<=1.00001f);
  interior|=r>.1f&&r<.7f;edge|=r>.95f;
  quadrants[(p.x>0?1:0)+(p.y>0?2:0)]=true;
 } CHECK(interior&&edge);for(bool q:quadrants)CHECK(q);
 // Inverse projection works with off-center origin, roll, FOV and aspect changes.
 for(float roll : {0.f,.6f,1.5f})for(float scale : {.03f,.2f}){
  ReconArea::Point o={.48f,.51f},r={o.x+scale*std::cos(roll),o.y+scale*std::sin(roll)},
   u={o.x-scale*.6f*std::sin(roll),o.y+scale*.6f*std::cos(roll)};
  for(unsigned i=0;i<ReconArea::Samples;++i){auto s=ReconArea::sample(i);
   ReconArea::Point target={.5f+s.x*.1f,.5f+s.y*.18f},p={};
   CHECK(ReconArea::unproject(o,r,u,target,p));
   CHECK(std::fabs(o.x+(r.x-o.x)*p.x+(u.x-o.x)*p.y-target.x)<.00001f);
   CHECK(std::fabs(o.y+(r.y-o.y)*p.x+(u.y-o.y)*p.y-target.y)<.00001f);
  }
 }
 ReconArea::Point out={};CHECK(!ReconArea::unproject({0,0},{0,0},{0,0},{1,1},out));
 CHECK(updateReconReticleProbe(1,true,20)==0);CHECK(starts==2);
 CHECK(updateReconReticleProbe(1,true,21)==7);CHECK(starts==2);
 // A completed ray must still be returned when the 75 ms scan runs later.
 pending=true;CHECK(updateReconReticleProbe(1,true,75)==7);
 CHECK(updateReconReticleProbe(1,true,150)==7);
 for(unsigned t=166;t<400;t+=16)updateReconReticleProbe(1,true,t);
 CHECK(peak<=int(ReconArea::Slots));CHECK(starts==10);
 CHECK(updateReconReticleProbe(1,true,500)==0);CHECK(!g_reconReticleHitValid);
 // Old handles remain bounded and polled, but cannot publish after exit/reentry.
 updateReconReticleProbe(1,false,501);CHECK(!g_reconReticleHitValid);
 pending=false;CHECK(updateReconReticleProbe(1,true,502)==0);
 CHECK(updateReconReticleProbe(1,true,518)==0);
 CHECK(updateReconReticleProbe(1,true,519)==7);
 entityExists=false;CHECK(updateReconReticleProbe(1,true,520)==0);
 CHECK(draws>0);
 entityExists=true;pending=false;updateReconReticleProbe(1,false,1000);
 const int startCount=starts;unsigned last=1000;
 for(unsigned t=1033;t<=2023;t+=33){
  const int before=starts;updateReconReticleProbe(1,true,t);
  CHECK(starts-before<=4);CHECK(peak<=int(ReconArea::Slots));
  CHECK(starts-startCount<=int((t-1000)*2/16+4));
  if(t>1700)for(const auto& h:g_reconAreaHits)
   CHECK(h.valid && t-h.at<=ReconArea::FreshMs);
  last=t;
 }
 // The independent selection cadence does not erase completed hits.
 CHECK(updateReconReticleProbe(1,true,last+1,false)==7);
 g_reconAimRadius=.1f;
 CHECK(updateReconReticleProbe(1,true,last+2)==0);
 CHECK(!g_reconReticleHitValid);
 updateReconReticleProbe(1,true,last+35);
 CHECK(updateReconReticleProbe(1,true,last+36)==7);
 camera.x=2;
 CHECK(updateReconReticleProbe(1,true,last+37)==0);
 CHECK(!g_reconReticleHitValid);
 updateReconReticleProbe(1,false,last+100);
 pending=true;updateReconReticleProbe(1,true,last+120);
 pending=false;CHECK(updateReconReticleProbe(0,true,last+700)==0);
 CHECK(!g_reconReticleHitValid);
 updateReconReticleProbe(1,true,last+720);
 CHECK(updateReconReticleProbe(1,true,last+721)==7);
 CHECK(updateReconReticleProbe(1,true,last+722,true,true)==0);
 CHECK(!g_reconReticleHitValid);
}
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/recon.cpp').read_text('utf-8')
    header=(args.runtime_root/'GameplayTweaks/modules/recon_area.h').read_text('utf-8')
    block=source[source.index('struct ReconAreaHit {'):source.index('// #96 PLANT SELECTION VIA')]
    code=header+'\n'+block
    variants={'production':code,
      'aspect-distortion':code.replace('(y - 0.5f) / aspect','(y - 0.5f)'),
      'center-only-rays':code.replace('index %= Samples;','index = 0;'),
      'expired-hit-accepted':code.replace('now - hit.at > ReconArea::FreshMs','false'),
      'slow-result-published':code.replace('now - probe.startedAt > ReconArea::FreshMs','false'),
      'frame-based-budget':code.replace('unsigned(now - budgetAt), 32u','unsigned(now - budgetAt), 16u'),
      'old-mode-published':code.replace('previousBinocularMode != binocularMode','false'),
      'old-session-published':code.replace('probe.generation != generation','false'),
      'lost-result-between-scans':code.replace('float best = 999.0f;','for(auto& h:g_reconAreaHits) h.valid=false; float best = 999.0f;')}
    run_variants(variants,PRELUDE,TESTS)
    start=source.index('\tauto considerPed =')
    end=source.index('\tEntity aimedEntity = 0;',start)
    candidate=source[start:end]
    candidate_prelude=PRELUDE+header+r'''
#include <vector>
#include <utility>
namespace PED {bool IS_PED_A_PLAYER(int){return false;}bool IS_PED_DEAD_OR_DYING(int,int){return false;}}
namespace ENTITY {bool HAS_ENTITY_CLEAR_LOS_TO_ENTITY(int,int,int){return false;}}
Vector3 ENTITY_COORDS(int){return {100,100,100};}
Vector3 reconAnchor(int){return {100,100,100};}
float reconProjectedExtent(int){return 0;}
bool isReconTagged(int){return false;}
float g_reconMinProjectedExtent=.001f,g_reconAreaAspect=16.f/9;
int main(){
 Ped playerPed=1,best=0;Vector3 playerPos={};float acquisitionMaxDistance=50;
 float bestScreen=999,nearestPedScreen=999;int pedRadiusRejected=0;
 std::vector<std::pair<Ped,float>> visiblePeds;
'''
    candidate_tests=r'''
 Vector3 body={0,20,0};
 considerPed(7,.02f,false,&body);
 CHECK(best==7 && visiblePeds.size()==1);
 considerPed(7,.02f,false,&body);CHECK(visiblePeds.size()==1);
 visiblePeds.clear();best=0;
 considerPed(7,.2f,false,&body);CHECK(!best && visiblePeds.empty());
 body.y=60;considerPed(7,.02f,false,&body);CHECK(!best);
 body.y=20;entityExists=false;considerPed(7,.02f,false,&body);CHECK(!best);
}
'''
    run_variants({'production':candidate,
      'animal-origin-range':candidate.replace('rayPoint ? *rayPoint : ENTITY_COORDS(candidate)','ENTITY_COORDS(candidate)'),
      'animal-origin-LOS':candidate.replace('!rayPoint && (reconProjectedExtent(candidate)','true && (reconProjectedExtent(candidate)')},
      candidate_prelude,candidate_tests)
    assert 'considerPed((Ped)hit.entity, screenDistance, false, &point)' in source
    assert 'rayPoint ? *rayPoint : ENTITY_COORDS(candidate)' in source
    assert '(!rayPoint && (reconProjectedExtent(candidate)' in source
    assert 'if (hit.entity != entity) continue;' in source
    assert 'ReconArea::distance(sx, sy, g_reconAreaAspect)' in source
    print('PASS: bounded area geometry, persistent results, entity/session ownership, actual-hit integration. Game rendering and performance remain unverified.')

if __name__=='__main__': main()

"""Execute the existing Recon suppression branch; do not infer rendered acceptance."""
import argparse
import json
from pathlib import Path
from verify_rdr2_camera_switch import run_variants

PRELUDE=r'''
#include <cstdint>
#include <string>
#include <vector>
using DWORD=uint32_t;constexpr int FALSE=0;
bool hud=false,cinematic=false,exists=false,running=false;
int runningCalls=0,lastScene=0;int64_t globalScene=23;
int64_t* getGlobalPtr(int index){return index==43800?&globalScene:nullptr;}
namespace ANIMSCENE {
bool _DOES_ANIM_SCENE_EXIST(int scene){lastScene=scene;return exists;}
bool _IS_ANIM_SCENE_STARTED(int scene,int){++runningCalls;lastScene=scene;return running;}
}
namespace HUD {bool IS_HUD_HIDDEN(){return hud;}}
namespace CAM {bool IS_CINEMATIC_CAM_RENDERING(){return cinematic;}}
namespace PLAYER {int PLAYER_ID(){return 1;}}
int observed=9,animalInfoTarget=9,playerPed=1,now=100;
struct Plant {int entity=0;}observedPlant{8};
float observedPlantProgressMs=800;
DWORD observedPlantProgressUpdatedAt=90;
bool observedPlantEligible=true,prompt=true,info=true;
std::vector<int> pedObservations={9};
std::vector<int> g_reconTargets={10,11},g_reconObjectTargets={12};
int acquisitions=0,draws=0,blipMutations=0;
std::string reason;
void updateReconAnimalInfoBoxBridge(int,int target,bool enabled,int){info=target||enabled;}
void updateReconPrompt(int,int target,float progress,bool enabled){prompt=target||progress||enabled;}
void heartbeat(const char* text){reason=text;}
void update(){
'''
TESTS=r'''
 ++acquisitions;++draws;++blipMutations;
}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
void seed(){observed=9;observedPlant.entity=8;observedPlantProgressMs=800;
 observedPlantProgressUpdatedAt=90;observedPlantEligible=true;pedObservations={9};
 animalInfoTarget=9;prompt=info=true;reason.clear();acquisitions=draws=blipMutations=0;runningCalls=0;}
int main(){
 for(int mode=0;mode<3;++mode){seed();hud=mode==0;cinematic=mode==1;exists=running=mode==2;
  update();CHECK(!acquisitions&&!draws&&!blipMutations);
  CHECK(!observed&&!observedPlant.entity&&!observedPlantProgressMs&&!observedPlantProgressUpdatedAt);
  CHECK(!observedPlantEligible&&pedObservations.empty()&&!animalInfoTarget&&!prompt&&!info);
  CHECK(g_reconTargets.size()==2 && g_reconObjectTargets.size()==1);
  CHECK(reason==(mode==0?"hud-hidden":mode==1?"cinematic":"cutscene"));
  if(mode==2)CHECK(runningCalls==1&&lastScene==23);
  hud=cinematic=exists=running=false;update();
  CHECK(acquisitions==1&&draws==1&&blipMutations==1);
  CHECK(g_reconTargets.size()==2&&g_reconObjectTargets.size()==1);
 }
 seed();exists=false;running=true;update();CHECK(acquisitions==1&&runningCalls==0);
 seed();exists=true;running=false;update();CHECK(acquisitions==1&&runningCalls==1);
}
'''
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args();root=args.runtime_root
    source=(root/'GameplayTweaks/modules/recon.cpp').read_text('utf-8')
    sdk=(root/'_downloads/RDR2_SDK/SDK/inc/natives.h').read_text('utf-8')
    db=json.loads((root/'_downloads/natives.json').read_text('utf-8'))['ANIMSCENE']
    assert db['0xCBFC7725DE6CE2E0']['name']=='IS_ANIM_SCENE_RUNNING'
    assert 'static BOOL _IS_ANIM_SCENE_STARTED(AnimScene animScene, BOOL p1) { return invoke<BOOL>(0xCBFC7725DE6CE2E0, animScene, p1); }' in sdk
    assert db['0x25557E324489393C']['name']=='DOES_ANIM_SCENE_EXIST'
    old=(root/'_downloads/RDR2-Decompiled-Scripts/script_rel/camp_beaverhollow.c').read_text('utf-8')
    current=(root/'_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/camp_beaverhollow.ysc.c').read_text('utf-8')
    assert 'ANIMSCENE::_IS_ANIM_SCENE_STARTED(Global_43800, false)' in old
    assert 'ANIMSCENE::DOES_ANIM_SCENE_EXIST(Global_43800) && ANIMSCENE::IS_ANIM_SCENE_RUNNING(Global_43800, false)' in current
    start=source.index('\tconst int activeAnimScene =')
    end=source.index('\tupdateReconCompendiumStudies(now);',start)
    branch=source[start:end]
    for later in ('reconEnsureBlipTextures(now);','drawReconMarker(', 'updateReconReticleProbe(playerPed,','selectReconPlant(aimedEntity,'):
        assert source.index(later,source.index('static void updateReconTagging'))>end,later
    variants={'production':branch,
      'cinematic-only-guard':branch.replace('hudHidden || cinematicCam || cutscenePlaying','cinematicCam'),
      'no-story-scene-guard':branch.replace('hudHidden || cinematicCam || cutscenePlaying','hudHidden || cinematicCam'),
      'progress-survives-cutscene':branch.replace('pedObservations.clear();',''),
      'plant-progress-survives-cutscene':branch.replace('observedPlantProgressMs = 0.0f;',''),
      'completed-tags-deleted':branch.replace('observed = 0;','observed = 0; g_reconTargets.clear();'),
      'early-return-lost':branch.replace('\t\treturn;','')}
    run_variants(variants,PRELUDE,TESTS)
    print('PASS: HUD/cinematic/running-scene suppression, pending-state reset, completed-tag preservation and resumption. SDK STARTED aliases current RUNNING hash. No rendered acceptance claimed.')

if __name__=='__main__':main()

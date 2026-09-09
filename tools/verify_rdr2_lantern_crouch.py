"""Execute player prop/light policy without native windows or game state."""
from pathlib import Path
import argparse
from verify_rdr2_camera_switch import run_variants
PRELUDE=r"""
#include <algorithm>
#include <cstdint>
using Ped=int;using DWORD=uint32_t;
struct Vector3 {float x,y,z;};
bool g_beltLanternMounted=false,g_beltLanternLit=false,g_beltLanternCrouched=false,g_beltLanternCalibrating=false;
int g_beltLanternProp=0,g_beltLanternPlayerLightRevision=0;
float g_beltLanternBrightness=3.2f;const float kBeltLanternCrouchBrightness=0.8f;
int spawns=0,removes=0,draws=0;float brightness=0;
void removeBeltLantern(const char*){++removes;g_beltLanternProp=0;}
void spawnBeltLantern(Ped,DWORD){++spawns;g_beltLanternProp=1;}
void updateBeltLanternCalibration(Ped,DWORD){}
void checkBeltLanternAttachment(Ped,DWORD){}
namespace ENTITY {bool DOES_ENTITY_EXIST(int id){return id!=0;}}
Vector3 ENTITY_COORDS(int){return {};}
void drawBeltLanternLightAt(Vector3,const char*,float value,bool,bool,int&){if(value>0){++draws;brightness=value;}}
void update(){Ped ped=1;DWORD now=100;
"""
TESTS=r"""
}
#define CHECK(x) do {if(!(x))return __LINE__;}while(0)
int main(){
 update();CHECK(spawns==1 && removes==0 && draws==0 && g_beltLanternProp==1);
 g_beltLanternCrouched=true;update();CHECK(draws==1 && brightness==0.8f && !g_beltLanternLit);
 g_beltLanternCrouched=false;draws=0;update();CHECK(draws==0 && !g_beltLanternLit && removes==0);
 g_beltLanternLit=true;update();CHECK(draws==1 && brightness==3.2f);
 g_beltLanternCrouched=true;update();CHECK(brightness==0.8f && g_beltLanternLit);
 g_beltLanternCrouched=false;update();CHECK(brightness==3.2f && g_beltLanternLit);
 g_beltLanternCrouched=true;g_beltLanternBrightness=0.2f;update();CHECK(brightness==0.2f);
 g_beltLanternBrightness=0;draws=0;update();CHECK(draws==0);
 g_beltLanternMounted=true;g_beltLanternBrightness=3.2f;update();CHECK(removes==1 && g_beltLanternProp==0 && draws==0);
}
"""
def main():
 p=argparse.ArgumentParser();p.add_argument("--runtime-root",type=Path,default=Path("C:/RDR2Mod"));a=p.parse_args()
 source=(a.runtime_root/"GameplayTweaks/modules/belt_lantern.cpp").read_text("utf-8")
 start=source.index("\tif (g_beltLanternMounted && g_beltLanternProp)")
 end=source.index("\tif (g_beltLanternLit && g_horseLanternOwned",start)
 code=source[start:end]
 variants={"production":code,
 "off-crouch-dark":code.replace("g_beltLanternCrouched || g_beltLanternLit","g_beltLanternLit"),
 "unlit-prop-missing":code.replace("!g_beltLanternMounted && !g_beltLanternProp)","!g_beltLanternMounted && !g_beltLanternProp && g_beltLanternLit)"),
 "not-dimmed":code.replace("(std::min)(g_beltLanternBrightness, kBeltLanternCrouchBrightness)","g_beltLanternBrightness")}
 run_variants(variants,PRELUDE,TESTS)
 print("Crouch override, saved-state restore and unlit prop policy pass. Rendered/radial acceptance remains.")
if __name__=="__main__":main()

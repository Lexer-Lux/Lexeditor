"""Execute production train discovery and cleanup without game or windows."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants
PRELUDE=r"""
#include <cmath>
#include <cstdint>
#include <sstream>
#include <string>
#include <map>
#include <vector>
using Vehicle=int;using Entity=int;using Hash=int;using DWORD=uint32_t;
constexpr int GT_INFO=0;bool g_trainTracking=true;int g_trainBlips[32]={};
std::vector<int> pool;std::map<int,int> engines;std::map<int,bool> exists,blips;
int nextBlip=10,created=0,removed=0,rotations=0;
namespace ENTITY {
bool DOES_ENTITY_EXIST(Entity e){return exists[e];}
Hash GET_ENTITY_MODEL(Entity e){return e;}
float GET_ENTITY_HEADING(Entity){return 45;}
}
namespace VEHICLE {
bool IS_THIS_MODEL_A_TRAIN(Hash e){return engines.count(e)!=0;}
int GET_PED_IN_VEHICLE_SEAT(Vehicle,int){return 0;}
}
template<class T>T invoke(uint64_t,Entity e){return engines[e];}
int worldGetAllVehicles(int* out,int cap){int count=0;for(int e:pool)if(count<cap)out[count++]=e;return count;}
int joaat(const char* name){return std::string(name)=="GhostTrainSteamer" ? -90 : std::string(name)=="steamerDummy" ? -91 : 1;}
namespace MAP {
bool DOES_BLIP_EXIST(int id){return blips[id];}
int _BLIP_ADD_FOR_ENTITY(int,Entity){++created;blips[++nextBlip]=true;return nextBlip;}
void SET_BLIP_ROTATION(int,int){++rotations;}
}
void REMOVE_MAP_BLIP(int* id){++removed;blips[*id]=false;*id=0;}
void ADD_BLIP_MODIFIER(int,int){}
DWORD GetTickCount(){return 1000;}
void gtLog(const char*,int,const std::string&){}
"""
TESTS=r"""
#define CHECK(x) do {if(!(x))return __LINE__;}while(0)
int main(){
 // A live engine without a driver and its two carriages make one marker.
 pool={1,2,3,9,-90,-91};for(int e:pool)exists[e]=true;
 engines[1]=1;engines[2]=1;engines[3]=1;engines[-90]=-90;engines[-91]=-91;
 updateTrainBlips();CHECK(created==1 && rotations==1);
 updateTrainBlips();CHECK(created==1 && removed==0);
 // A removed blip is recreated without adding a second train slot.
 blips[g_trainBlips[0]]=false;updateTrainBlips();CHECK(created==2);
 // Stream-out retires even if an entity handle remains reported as existing.
 pool={9};updateTrainBlips();CHECK(removed==1 && g_trainBlipEntities[0]==0);
 pool={1};updateTrainBlips();CHECK(created==3);
 // Entity deletion cannot leave an owned marker.
 exists[1]=false;updateTrainBlips();CHECK(removed==2);
 exists[1]=true;updateTrainBlips();CHECK(created==4);
 g_trainTracking=false;updateTrainBlips();CHECK(removed==3 && g_trainBlipEntities[0]==0);
}
"""
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--runtime-root",type=Path,default=Path("C:/RDR2Mod"));args=parser.parse_args()
 source=(args.runtime_root/"GameplayTweaks/modules/collectibles_map.cpp").read_text("utf-8")
 code=source[source.index("static bool isMapTrainEngine"):]
 primary=(args.runtime_root/"_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/long_update.ysc.c").read_text("utf-8")
 assert "trainCar = VEHICLE::_GET_TRAIN_CAR(*uParam1);" in primary
 assert "ENTITY::DOES_ENTITY_EXIST(trainCar)" in primary
 variants={"production":code,
  "driver-required":code.replace("return engine == vehicle", "return VEHICLE::GET_PED_IN_VEHICLE_SEAT(vehicle, -1) != 0 && engine == vehicle"),
  "carriage-duplicates":code.replace("engine == vehicle", "engine != 0"),
  "stream-out-leak":code.replace("!vehiclePoolContains(vehicles, vehicleCount, train) ||", ""),
  "disabled-leak":code.replace("const int vehicleCount =", "if (!g_trainTracking) return; const int vehicleCount =")}
 run_variants(variants,PRELUDE,TESTS)
 print("Discovery and cleanup pass. Real train resolution and distinct artwork remain unverified.")
if __name__=="__main__":main()

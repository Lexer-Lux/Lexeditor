"""Execute the production Player-page override; no game/window is started."""
from pathlib import Path
import argparse
from verify_rdr2_camera_switch import run_variants
PRELUDE=r"""
#include <cstdint>
#include <sstream>
#include <string>
#include <type_traits>
#include <map>
using DWORD=uint32_t;using Any=uint64_t;using Hash=uint64_t;using BOOL=bool;using Void=void;
constexpr bool FALSE=false;constexpr int GT_INFO=0,GT_WARN=1;
bool g_coreClockEnabled=true,active=false,valid=true;
int writes=0,reads=0;std::map<int,Any> cells;std::string logs;
Any* getGlobalPtr(int index){return &cells[index];}
Any DB_GET_PATH(const char*){++reads;return 42;}
bool DB_VALID(Any value){return valid && value!=0;}
Hash joaat(const char*){return 1;}
template<class T>T invoke(uint64_t hash,Any value){
 if constexpr(std::is_same_v<T,const char*>)return "";
 else return active;
}
int invalidWrites=0;
template<class T,class V>T invoke(uint64_t hash,Any id,V value){
 ++writes;
 if(id!=101 && id!=102 && id!=103 && id!=201 && id!=202 && id!=203 && id!=301 && id!=302 && id!=303 && id!=401 && id!=402 && id!=403)++invalidWrites;
}
void gtLog(const char*,int,const std::string& line){logs+=line;}
"""
TESTS=r"""
#define CHECK(x) do {if(!(x))return __LINE__;}while(0)
int main(){
 cells[1954819+5]=42;
 for(int panel=1;panel<=3;++panel){
 int base=1954819+5+2+1+panel*36;
 cells[base+12+1+2]=100+panel;cells[base+32+1+2]=200+panel;
 cells[base+12+1+1]=300+panel;cells[base+32+1+1]=400+panel;
 }
 updatePlayerCoreRates(100);CHECK(writes==0 && reads==0);
 active=true;g_coreClockEnabled=false;updatePlayerCoreRates(200);CHECK(writes==0);
 g_coreClockEnabled=true;cells[1954819+5]=99;updatePlayerCoreRates(300);CHECK(writes==0);
 cells[1954819+5]=42;updatePlayerCoreRates(400);CHECK(writes==12 && invalidWrites==0);
 CHECK(logs.find("blank=6/6")!=std::string::npos);
 updatePlayerCoreRates(450);CHECK(writes==24);
 valid=false;updatePlayerCoreRates(500);CHECK(writes==24);
 active=false;updatePlayerCoreRates(600);CHECK(writes==24);
}
"""
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--runtime-root",type=Path,default=Path("C:/RDR2Mod"));args=parser.parse_args()
 code=(args.runtime_root/"GameplayTweaks/modules/player_core_rates.cpp").read_text("utf-8")
 source=(args.runtime_root/"_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/short_update.ysc.c").read_text("utf-8")
 for token in ('"playerSkillsDatastore"', '"rpgLines"', 'TEXT_LABEL_APPEND_INT(&unk, j, 64);', 'TEXT_LABEL_APPEND_INT(&unk, i, 64);', 'Global_1954819.f_5.f_2[i /*36*/].f_12[j] =', 'Global_1954819.f_5.f_2[i /*36*/].f_32[j] =', 'return "PMPLAYER_CORE_DRAIN_RATE";', 'return "PMPLAYER_CORE_TIME";'):
  assert token in source,token

 for banned in ("SET_CORE", "SET_ATTRIBUTE", "SET_PLAYER", "DB_ADD", "*storeCell ="):
  assert banned not in code,banned
 variants={"production":code,
  "inactive-writes":code.replace('!invoke<BOOL>(0x25B7A0206BDFAC76, joaat("player_menu"))','false'),
  "wrong-store":code.replace(' || (Any)*storeCell != store',''),
  "count-cell-missing":code.replace('panelBase + 12 + 1 + row','panelBase + 12 + row'),
  "disabled-writes":code.replace('!g_coreClockEnabled ||','false ||')}
 run_variants(variants,PRELUDE,TESTS)
 print("Only the six drain time/rate bindings are written while active. Rendered acceptance remains required.")
if __name__=="__main__":main()

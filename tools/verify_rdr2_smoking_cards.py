"""Execute smoking-card trigger, chance boundaries and preservation."""
import argparse
from pathlib import Path
from verify_rdr2_camera_switch import run_variants
PRELUDE=r"""
#include <algorithm>
#include <cstdio>
#include <cstdint>
#include <vector>
#include <string>
#include <sstream>
#include <map>
using Hash=uint32_t;using DWORD=uint32_t;using Ped=int;
constexpr int GT_INFO=0,GT_WARN=1,GT_ERROR=2;
std::map<Hash,int> inventory;bool running=false,eventFired=false;Hash item=0;float chance=0;int adds=0;
Hash joaat(const char* s){Hash hash=0;while(*s)hash=hash*33+(unsigned char)*s++;return hash;}
int INVENTORY_ITEM_COUNT(Hash hash){return inventory[hash];}
bool INVENTORY_ADD(Hash hash,int count){inventory[hash]+=count;++adds;return true;}
DWORD GetTickCount(){return 100;}
float readF(const char*,const char*,float){return chance;}
void gtLog(const char*,int,const std::string&){}
bool ITEM_INTERACTION_RUNNING(Ped){return running;}
Hash ITEM_INTERACTION_ITEM(Ped){return item;}
namespace ENTITY {bool HAS_ANIM_EVENT_FIRED(Ped,Hash){return eventFired;}}
"""
TESTS=r"""
#define CHECK(x) do {if(!(x))return __LINE__;}while(0)
int main(){
 using namespace PremiumCigaretteCards;
 update(1,100);CHECK(s_cards.size()==144);
 // Acquisition and a loose-world card in the same poll never lose a card.
 inventory[joaat("CONSUMABLE_CIGARETTE_BOX")]=10;
 inventory[s_cards[0]]=1;update(1,200);CHECK(inventory[s_cards[0]]==1 && adds==0);
 // Discarding cigarettes is not a smoking event.
 inventory[joaat("CONSUMABLE_CIGARETTE_BOX")]=0;update(1,300);CHECK(adds==0);
 running=true;item=joaat("CONSUMABLE_CIGARETTE_BOX");eventFired=true;
 update(1,400);CHECK(adds==0 && std::string(s_lastOutcome)=="executed-miss");
 chance=100;eventFired=false;update(1,2200);eventFired=true;update(1,2300);CHECK(adds==1);
 update(1,2301);CHECK(adds==1); // Held event grants once.
 eventFired=false;item=joaat("CONSUMABLE_CIGARETTE_BOX_USED");update(1,2400);
 eventFired=true;update(1,2500);CHECK(adds==2);
 // Only one missing card: a winning smoke must choose that card.
 for(Hash h:s_cards)inventory[h]=1;inventory[s_cards[37]]=0;
 eventFired=false;update(1,2600);eventFired=true;update(1,2700);
 CHECK(inventory[s_cards[37]]==1 && adds==3);
 // Once all144 are owned, a duplicate is allowed.
 eventFired=false;update(1,2800);eventFired=true;update(1,2900);CHECK(adds==4);
 eventFired=false;item=joaat("CONSUMABLE_CIGAR");update(1,3000);
 eventFired=true;update(1,3100);CHECK(adds==4);
}
"""
def main():
 p=argparse.ArgumentParser();p.add_argument("--runtime-root",type=Path,default=Path("C:/RDR2Mod"));a=p.parse_args()
 code=(a.runtime_root/"GameplayTweaks/modules/premium_cigarette_cards.cpp").read_text("utf-8")
 assert "INVENTORY_REMOVE" not in code
 variants={"production":code,
 "repeat-event":code.replace("consumeEventFired && !s_consumeEventWasFired","consumeEventFired"),
 "ignore-zero":code.replace("roll < threshold","true"),
 "ignore-hundred":code.replace("roll < threshold","false"),
 "unowned-bypassed":code.replace("const bool duplicatesAllowed = unowned.empty();","const bool duplicatesAllowed = true;")}
 run_variants(variants,PRELUDE,TESTS)
 print("Smoking and preservation pass; vanilla acquisition-grant suppression remains unresolved.")
if __name__=="__main__":main()

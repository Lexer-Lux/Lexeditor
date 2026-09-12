"""Execute the shared overflow registry, transactions, poll and UI without a game."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile

HARNESS = r'''
#include <algorithm>
#include <cassert>
#include <climits>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <tuple>
#include <type_traits>
#include <vector>
#undef assert
#define assert(x) do {if(!(x)){std::fprintf(stderr,"check failed at %d\n",__LINE__);std::exit(93);}} while(0)
using Hash=unsigned;using DWORD=unsigned;using Void=void;
#define FALSE 0
#define TRUE 1
enum{GT_INFO,GT_WARN,GT_ERROR,VK_F7=100,VK_ESCAPE,VK_BACK,VK_RETURN,VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT};
std::string g_moduleDir;std::ostringstream logs;
void gtLog(const char*,int,const std::string&){}
std::ostream& GtLogStream(const char*,int){return logs;}
template<size_t N,class...A>int sprintf_s(char(&s)[N],const char*f,A...a){return std::snprintf(s,N,f,a...);}
Hash joaat(const char*s){if(std::string(s).find("COLLIDE")==0)return 77;unsigned h=0;while(*s){h+=std::tolower((unsigned char)*s++);h+=h<<10;h^=h>>6;}h+=h<<3;h^=h>>11;return h+(h<<15);}
std::map<Hash,int> counts,bases,caps;std::map<std::string,int> reserves;std::map<std::string,std::string> rawReserves;int writes=0;std::string pending;bool reservePersist=true;std::vector<int> queuedCounts;
std::map<int,int> keys;std::vector<Hash> capReads;bool persist=true;int removes=0,adds=0;bool reenter=false;void nested();
int GetAsyncKeyState(int k){int v=keys[k];keys[k]&=~1;return v;}
DWORD GetTickCount(){return 0;}
int INVENTORY_ITEM_COUNT(Hash h){if(!queuedCounts.empty()){int value=queuedCounts.front();queuedCounts.erase(queuedCounts.begin());return value;}return counts[h];}
void INVENTORY_REMOVE_WITH_REASON(Hash h,int q,Hash){++removes;counts[h]-=q;if(reenter)nested();}
void INVENTORY_ADD(Hash h,int q){++adds;counts[h]+=q;}
unsigned GetPrivateProfileIntA(const char*,const char*k,int,const char*){return reserves[k];}
DWORD GetPrivateProfileStringA(const char*section,const char*k,const char*def,char*out,DWORD size,const char*){std::string s=std::string(section)=="Transaction"?pending:rawReserves.count(k)?rawReserves[k]:reserves.count(k)?std::to_string(reserves[k]):def;s=s.substr(0,size-1);std::copy(s.begin(),s.end(),out);out[s.size()]=0;return (DWORD)s.size();}
int WritePrivateProfileStringA(const char*section,const char*k,const char*v,const char*){++writes;if(!persist)return 0;if(std::string(section)=="Transaction"){pending=v?v:"";return 1;}if(!reservePersist)return 0;reserves[k]=std::atoi(v);return 1;}
void CASING_FEED(const char*,const char*,Hash){}
bool scriptRunning(const char*){return true;}bool UIAPP_ACTIVE(Hash){return false;}
template<class T,class...A>T invoke(unsigned long long id,A...a){
 if constexpr(std::is_same_v<T,int>){auto t=std::make_tuple(a...);if(id==0xE80E50BEE276A54A){Hash h=std::get<0>(t);capReads.push_back(h);return bases[h];}return caps[std::get<1>(t)];}
 else if constexpr(std::is_same_v<T,const char*>)return "Localized item";
}
namespace HUD{template<class...A>void SET_TEXT_SCALE(A...){}template<class...A>void _SET_TEXT_COLOR(A...){}template<class...A>void SET_TEXT_CENTRE(A...){}template<class...A>void SET_TEXT_DROPSHADOW(A...){}template<class...A>void _DISPLAY_TEXT(A...){}bool IS_PAUSE_MENU_ACTIVE(){return false;}}
namespace MISC{template<class...A>const char* _CREATE_VAR_STRING(A...){return "text";}}
namespace PAD{bool IS_CONTROL_PRESSED(int,Hash){return false;}bool IS_DISABLED_CONTROL_PRESSED(int,Hash){return false;}bool IS_DISABLED_CONTROL_JUST_PRESSED(int,Hash){return false;}}
namespace ANIMSCENE{void _PAUSE_SCRIPT_THREADS(bool){}}
namespace GRAPHICS{template<class...A>void DRAW_RECT(A...){}}
#include "overflow_storage.cpp"
void nested(){assert(overflowWithdraw(g_overflowItems[1],99,1,1)==0);}
bool parse(const std::string&s){std::istringstream in(s);return overflowParseRegistry(in,g_overflowItems);}
void enable(){g_overflowEnabled=true;g_overflowNextPollAt=0;g_overflowPollCursor=0;g_overflowUiItem=0;counts.clear();bases.clear();caps.clear();capReads.clear();for(auto&i:g_overflowItems){bases[i.hash]=i.liftedBase;caps[i.hash]=i.liftedBase;counts[i.hash]=i.authoredBase;}}
int main(){
 assert(parse("# config\nCONSUMABLE_BAKED_BEANS_CAN,1,99\n"));
 auto bean=g_overflowItems[0].hash;enable();reserves["CONSUMABLE_BAKED_BEANS_CAN"]=7;
 g_moduleDir=".";auto writeCsv=[](const std::string&s){std::ofstream out(".\\overflow_storage_items.csv",std::ios::binary);out<<s;};
 writeCsv("CONSUMABLE_BAKED_BEANS_CAN,1,99\n");assert(overflowLoadPrototypeData());
 writeCsv(std::string(16385,'X'));assert(!overflowLoadPrototypeData()&&g_overflowItems[0].hash==bean);
 writeCsv("ITEM,1,99\nBAD\n");assert(!overflowLoadPrototypeData()&&g_overflowItems[0].hash==bean);
 std::istringstream failed("ITEM,1,99\n");failed.setstate(std::ios::badbit);assert(!overflowParseRegistry(failed,g_overflowItems));
 int saved=-1;assert(overflowReadReserve(g_overflowItems[0],saved)&&saved==7);assert(overflowWriteReserve(g_overflowItems[0],8));assert(reserves["CONSUMABLE_BAKED_BEANS_CAN"]==8);
 for(auto bad:{"", "-1", "nope", "2147483648", "99999999999999999999999999999999999999999999999999999999999999999999"}){
  rawReserves["BROKEN"]=bad;writeCsv("CONSUMABLE_BAKED_BEANS_CAN,1,99\nBROKEN,1,99\n");g_overflowLoaded=false;g_overflowEnabled=false;int beforeWrites=writes;
  loadOverflowStorage();assert(!g_overflowEnabled&&writes==beforeWrites&&rawReserves["BROKEN"]==bad);
 }
 rawReserves.clear();writeCsv("CONSUMABLE_BAKED_BEANS_CAN,1,99\nMISSING,1,99\n");g_overflowLoaded=false;loadOverflowStorage();assert(g_overflowEnabled&&g_overflowItems[1].reserve==0);
 rawReserves["CONSUMABLE_BAKED_BEANS_CAN"]="2147483647";assert(overflowReadReserve(g_overflowItems[0],saved)&&saved==INT_MAX);rawReserves.clear();
 assert(parse("CONSUMABLE_BAKED_BEANS_CAN,1,99\n"));
 // Every malformed tail leaves the previous complete registry unchanged.
 for(auto bad:{"", "ITEM,1,99\nBAD,1,1\n", "ITEM,1,99,\n", "ITEM,1,99\nITEM,1,99\n", "COLLIDE_A,1,99\nCOLLIDE_B,1,99\n", "bad-key,1,99\n", "ITEM,0,99\n", "ITEM,1,10000\n"}){assert(!parse(bad));assert(g_overflowItems.size()==1&&g_overflowItems[0].hash==bean);}
 std::string many;for(int i=0;i<64;++i)many+="ITEM_"+std::to_string(i)+",1,99\n";
 assert(parse(many));assert(!parse(many+"EXTRA,1,99\n")&&g_overflowItems.size()==64);
 enable();overflowPoll(0);assert(capReads.size()==4);overflowPoll(249);assert(capReads.size()==4);
 for(unsigned t=250;t<=3750;t+=250)overflowPoll(t);assert(capReads.size()==64);
 for(auto&i:g_overflowItems)assert(std::count(capReads.begin(),capReads.end(),i.hash)==1);
 // Only the registered item's own inventory and reserve change.
 assert(parse("CONSUMABLE_BAKED_BEANS_CAN,1,99\nTONIC,2,90\n"));enable();
 auto tonic=g_overflowItems[1].hash;counts[bean]=4;counts[tonic]=5;overflowPoll(0);
 assert(counts[bean]==1&&counts[tonic]==2&&g_overflowItems[0].reserve==3&&g_overflowItems[1].reserve==3);
 assert(reserves["CONSUMABLE_BAKED_BEANS_CAN"]==3&&reserves["TONIC"]==3);
 auto& a=g_overflowItems[0];auto& b=g_overflowItems[1];bases[bean]=1;int ec=0,ac=0;assert(!overflowCaps(a,ec,ac));assert(overflowCaps(b,ec,ac));assert(a.lastCatalogBaseReadback==1&&b.lastCatalogBaseReadback==90);
 // Recover a valid cap with no inventory transition: excess is still captured.
 counts[bean]=3;overflowPoll(250);bases[bean]=99;overflowPoll(500);assert(counts[bean]==1&&a.reserve==5);
 caps[bean]=INT_MIN;assert(!overflowCaps(a,ec,ac)&&ac==0);caps[bean]=99;
 reenter=true;counts[bean]=2;counts[tonic]=0;int oldAdds=adds;assert(overflowDeposit(a,99,1,2,1,false)==1);assert(adds==oldAdds&&counts[tonic]==0&&g_overflowEnabled);reenter=false;
 a.reserve=INT_MAX;counts[bean]=2;int oldRemoves=removes;assert(overflowDeposit(a,99,1,2,1,false)==0&&removes==oldRemoves);a.reserve=6;
 // Existing UI item selection and simultaneous Accept cannot target old item.
 g_overflowUiOpen=true;g_overflowUiInputArmed=true;g_overflowUiNextInputAt=0;
 keys[VK_RIGHT]=1;keys[VK_RETURN]=1;oldAdds=adds;overflowUiUpdate(1000);assert(g_overflowUiItem==1&&adds==oldAdds);
 keys[VK_RETURN]=1;overflowUiUpdate(1200);assert(counts[tonic]==1&&b.reserve==2&&counts[bean]==2);
 overflowSelectItem(1);assert(g_overflowUiItem==0);overflowSelectItem(-1);assert(g_overflowUiItem==1);
 // Transfer rechecks caps even if the UI cached a previous success.
 bases[tonic]=2;keys[VK_RETURN]=1;oldAdds=adds;overflowUiUpdate(1500);assert(adds==oldAdds);
 bases[tonic]=90;reservePersist=false;assert(overflowWithdraw(b,90,2,1)==0);assert(counts[tonic]==1&&!g_overflowEnabled&&!g_overflowTransactionActive&&pending.empty());reservePersist=true;
 // Invalid pre-counts cause no journal or inventory writes.
 g_overflowEnabled=true;int w=writes;oldAdds=adds;oldRemoves=removes;
 queuedCounts={-1};assert(overflowDeposit(a,99,1,2,1,false)==0);
 queuedCounts={-1};assert(overflowWithdraw(b,90,2,1)==0);assert(writes==w&&adds==oldAdds&&removes==oldRemoves);
 // Invalid post-remove/add never invents a delta; all later items lock out.
 counts[bean]=2;int priorReserve=a.reserve;queuedCounts={2,-1};assert(overflowDeposit(a,99,1,2,1,false)==0);
 assert(counts[bean]==1&&a.reserve==priorReserve&&!g_overflowEnabled&&!pending.empty());auto firstPending=pending;
 oldAdds=adds;assert(overflowWithdraw(b,90,2,1)==0&&adds==oldAdds&&pending==firstPending);
 writeCsv("CONSUMABLE_BAKED_BEANS_CAN,1,99\nTONIC,2,90\n");g_overflowLoaded=false;w=writes;loadOverflowStorage();assert(!g_overflowEnabled&&writes==w&&pending==firstPending);
 // Test-only recovery reset; production never automatically erases uncertainty.
 pending.clear();g_overflowEnabled=true;auto& restored=g_overflowItems[1];restored.reserve=2;counts[tonic]=0;queuedCounts={0,-1};
 assert(overflowWithdraw(restored,90,2,1)==0&&counts[tonic]==1&&restored.reserve==2&&!g_overflowEnabled&&!pending.empty());
 firstPending=pending;oldAdds=adds;assert(overflowWithdraw(restored,90,2,1)==0&&adds==oldAdds&&pending==firstPending);
 pending.clear();g_overflowEnabled=true;counts[tonic]=0;reservePersist=false;queuedCounts={0,1,-1};
 assert(overflowWithdraw(restored,90,2,1)==0&&counts[tonic]==1&&!pending.empty()&&!g_overflowEnabled);reservePersist=true;pending.clear();
 // One item retains the original cadence.
 assert(parse("CONSUMABLE_BAKED_BEANS_CAN,1,99\n"));enable();overflowPoll(0);overflowPoll(250);assert(capReads.size()==2);
}
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, default=Path('C:/RDR2Mod'))
    args = parser.parse_args()
    compiler = shutil.which('g++') or shutil.which('clang++')
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory(prefix='lex-overflow-registry-') as temp:
        folder = Path(temp)
        source = (args.runtime_root / 'GameplayTweaks/modules/overflow_storage.cpp').read_text(encoding='utf-8-sig')
        cpp, exe = folder / 'test.cpp', folder / 'test.exe'
        cpp.write_text(HARNESS, encoding='utf-8')
        if compiler:
            command = [compiler, '-std=c++17', str(cpp), '-o', str(exe)]
        else:
            batch = folder / 'compile.cmd'
            batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n')
            command = ['cmd', '/d', '/c', str(batch)]
        variants = {
            'production': source,
            'duplicate-hash': source.replace('if (existing.hash == item.hash) return false;', 'if (false) return false;'),
            'unbounded-poll': source.replace('(std::min)(kOverflowPollBatch, g_overflowItems.size())', 'g_overflowItems.size()'),
            'cross-item-reentry': source.replace('g_overflowEnabled && !g_overflowTransactionActive', 'g_overflowEnabled'),
            'reserve-overflow': source.replace('requested = (std::min)(requested, INT_MAX - item.reserve);', '// missing reserve bound'),
        }
        for name, variant in variants.items():
            if name != 'production' and variant == source:
                raise AssertionError(f'Mutation did not apply: {name}')
            (folder / 'overflow_storage.cpp').write_text(variant, encoding='utf-8')
            result = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            result = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=10)
            if (result.returncode == 0) != (name == 'production'):
                raise AssertionError(f'{name}: {result.stdout}{result.stderr}')
            print(('PASS ' if name == 'production' else 'REJECTED ') + name)
    print('PASS production overflow registry, bounded polling, per-item persistence/caps, transaction owner and UI selection')

if __name__ == '__main__':
    main()

#include "main.h"
#include "natives.h"
#include <windows.h>
#include <fstream>
#include <string>

static HMODULE owner;
static const char* items[]={"CONSUMABLE_MEDICINE","CONSUMABLE_POTENT_MEDICINE","CONSUMABLE_SPECIAL_MEDICINE_CRAFTED","CONSUMABLE_TONIC","CONSUMABLE_POTENT_TONIC","CONSUMABLE_SPECIAL_TONIC_CRAFTED","CONSUMABLE_SNAKE_OIL","CONSUMABLE_POTENT_SNAKE_OIL"};
static Hash hash(const char* s){unsigned h=0;for(;*s;++s){unsigned c=(unsigned char)*s;if(c>='A'&&c<='Z')c+=32;h+=c;h+=h<<10;h^=h>>6;}h+=h<<3;h^=h>>11;return h+(h<<15);}
struct Guid{Any data[4];};
static_assert(sizeof(Guid)==32,"Inventory GUID ABI");
static bool guid(Guid* parent,Hash item,Hash slot,Guid* out){return invoke<BOOL>(0x886DFD3E185C8A89,1,parent,item,slot,out)!=0;}
static bool valid(Guid* value){return invoke<BOOL>(0xB881CA836CC4B6D4,value)!=0;}
static int count(Hash item){Guid empty={},root={},entry={};if(!guid(&empty,hash("CHARACTER"),hash("SLOTID_NONE"),&root)||!valid(&root))return -1;if(!guid(&root,item,hash("SLOTID_SATCHEL"),&entry)||!valid(&entry))return 0;return invoke<int>(0xC97E0D2302382211,1,&entry,FALSE);}
static bool grant(Hash item){Guid empty={},root={},entry={};if(!guid(&empty,hash("CHARACTER"),hash("SLOTID_NONE"),&root)||!valid(&root))return false;guid(&root,item,hash("SLOTID_SATCHEL"),&entry);return invoke<BOOL>(0xCB5D11F9508A928D,1,&entry,&root,item,hash("SLOTID_SATCHEL"),1,hash("ADD_REASON_DEFAULT"))!=0;}

void ScriptMain(){
 char filename[MAX_PATH];GetModuleFileNameA(owner,filename,MAX_PATH);std::string path(filename);path=path.substr(0,path.find_last_of("\\/"));
 // One current log, one prior log. No per-session directories or unbounded append.
 MoveFileExA((path+"\\DurationProbe.csv").c_str(),(path+"\\DurationProbe.previous.csv").c_str(),MOVEFILE_REPLACE_EXISTING);
 std::ofstream log(path+"\\DurationProbe.csv",std::ios::trunc);
 log<<"event,case,item,elapsed_ms,count,health_core,stamina_core,deadeye_core,health_overpower,stamina_overpower,deadeye_overpower\n";log.flush();
 int selected=0;bool active=false,prior[3]={};DWORD started=0,last=0;unsigned rows=0;
 while(true){
  DWORD pid=0;GetWindowThreadProcessId(GetForegroundWindow(),&pid);bool focused=pid==GetCurrentProcessId();
  bool pressed[3];const int keys[]={VK_F8,VK_F9,VK_F10};for(int i=0;i<3;++i){bool down=focused&&(GetAsyncKeyState(keys[i])&0x8000);pressed[i]=down&&!prior[i];prior[i]=down;}
  Ped ped=invoke<Ped>(0x096275889B8E0EE0);bool ready=ped&&invoke<BOOL>(0xD42BD6EB2E0F1677,ped)&&!invoke<BOOL>(0x7D5B1F88E7504BBA,ped);
  if(rows<4096&&ready){
   if(pressed[0]&&!active){selected=(selected+1)%8;log<<"selected,"<<selected+1<<','<<items[selected]<<"\n";++rows;log.flush();}
   if(pressed[1]&&!active){int before=count(hash(items[selected]));bool accepted=before>=0&&before<2&&grant(hash(items[selected]));log<<"grant,"<<selected+1<<','<<items[selected]<<",0,"<<count(hash(items[selected]))<<",accepted="<<accepted<<"\n";++rows;log.flush();}
   if(pressed[2]){active=!active;started=GetTickCount();last=started-500;log<<(active?"start,":"stop,")<<selected+1<<','<<items[selected]<<"\n";++rows;log.flush();}
   DWORD now=GetTickCount();if(active&&now-started>600000){active=false;log<<"timeout,"<<selected+1<<"\n";++rows;}
   if(active&&rows<4096&&now-last>=500){last=now;log<<"sample,"<<selected+1<<','<<items[selected]<<','<<now-started<<','<<count(hash(items[selected]));for(int i=0;i<3;++i)log<<','<<invoke<int>(0x36731AC041289BB1,ped,i);for(int i=0;i<3;++i)log<<','<<invoke<float>(0x4C9F782180712742,ped,i);log<<"\n";log.flush();++rows;}
  }
  WAIT(0);
 }
}
BOOL APIENTRY DllMain(HMODULE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH){owner=module;scriptRegister(module,ScriptMain);}if(reason==DLL_PROCESS_DETACH)scriptUnregister(module);return TRUE;}

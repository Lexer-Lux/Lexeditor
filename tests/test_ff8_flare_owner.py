"""Compile the production Signal Flare request owner without a game process."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
VCVARS=Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")

class FlareOwnerTests(unittest.TestCase):
    @unittest.skipUnless(os.name=="nt" and VCVARS.exists(),"Windows C++ Build Tools required")
    def test_production_request_admission_gates_count_and_reset(self):
        source=ROOT/"games/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_flare_owner.cpp"
        code='#include "'+source.as_posix()+'"\n'+r'''
#include <cstdarg>
#include <cstdio>
#include <cstring>
bool ff8=true,enable_ff8_modern_controls=true;
Mode current{MODE_WORLDMAP};Mode *getmode_cached(){return &current;}
Save save{};unsigned buttons[2]{};Externals ff8_externals{&save,buttons};
bool field_available=true;extern "C" int __cdecl lexeditor_ff8_flare_field_input_available(){return field_available;}
bool square=false,exit_ready=false,exit_requested=false;
void *gameHwnd=(void*)1;void *focus=(void*)1;void *GetForegroundWindow(){return focus;}
unsigned fail_validate=0,patches=0;
int wrapper_calls=0;int ff8_toggle_battle_field(){++wrapper_calls;return lexeditor_ff8_flare_field_gate(true);}
unsigned uses=0;bool success=true;char notice[128]{};
int(__cdecl *menu_callback)()=nullptr;
bool lexeditor_ff8_modern_controls_take_square_press(){bool old=square;square=false;return old;}
void show_popup_msg(unsigned char,const char *format,...){va_list args;va_start(args,format);vsnprintf(notice,sizeof notice,format,args);va_end(args);}
extern "C" int __cdecl lexeditor_ff8_flare_use_world(unsigned id,unsigned short *encounter,unsigned char *remaining){
 ++uses;if(id!=199 || !success)return 0;*encounter=401;*remaining=7;return 1;}
extern "C" int __cdecl lexeditor_ff8_flare_use_field(unsigned id,unsigned short *encounter,unsigned char *remaining){return lexeditor_ff8_flare_use_world(id,encounter,remaining);}
extern "C" int __cdecl lexeditor_ff8_flare_menu_exit_request(){exit_requested=true;return 1;}
extern "C" int __cdecl lexeditor_ff8_flare_menu_exit_ready(){return exit_ready;}
extern "C" void __cdecl lexeditor_ff8_flare_menu_exit_reset(){exit_ready=false;exit_requested=false;}
extern "C" int __cdecl lexeditor_ff8_flare_menu_exit_install(){++patches;return 1;}
extern "C" int __cdecl lexeditor_ff8_flare_menu_request_bind(int(__cdecl*f)()){menu_callback=f;return 1;}
extern "C" int __cdecl lexeditor_ff8_flare_definition_install(){++patches;return 1;}
extern "C" int __cdecl lexeditor_ff8_flare_shop_install(){++patches;return 1;}
extern "C" int __cdecl lexeditor_ff8_flare_definition_validate(){return fail_validate!=3;}
extern "C" int __cdecl lexeditor_ff8_flare_shop_validate(){return fail_validate!=2;}
extern "C" int __cdecl lexeditor_ff8_flare_menu_exit_validate(){return fail_validate!=1;}
extern "C" int __cdecl lexeditor_ff8_flare_definition_ready(){return 1;}
extern "C" void __cdecl lexeditor_ff8_flare_transactions_enable(int){}
int main(){
 for(fail_validate=1;fail_validate<=3;++fail_validate)
  if(lexeditor_ff8_flare_owner_install() || patches || menu_callback)return 20;
 fail_validate=0;
 if(!lexeditor_ff8_flare_owner_install() || !menu_callback)return 1;
 save.items.items[197]={199,8};unsigned short encounter=0;
 lexeditor_ff8_flare_tick();current.driver_mode=MODE_MENU;lexeditor_ff8_flare_tick();
 if(!menu_callback() || menu_callback() || !exit_requested)return 2;
 current.driver_mode=MODE_WORLDMAP;
 if(lexeditor_ff8_flare_world_gate(&encounter,true)!=-1 || uses)return 3;
 exit_ready=true;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_world_gate(&encounter,true)!=1 || uses!=1 || encounter!=401 || strcmp(notice,"Signal Flare: 7 remaining"))return 4;
 if(lexeditor_ff8_flare_world_gate(&encounter,true)!=-1 || uses!=1)return 5;
 current.driver_mode=MODE_FIELD;lexeditor_ff8_flare_tick();current.driver_mode=MODE_MENU;lexeditor_ff8_flare_tick();
 if(!menu_callback())return 6;
 exit_ready=true;current.driver_mode=MODE_FIELD;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_field_gate(false)!=0 || uses!=1 || strcmp(notice,"Signal Flare cannot be used here."))return 7;
 current.driver_mode=MODE_WORLDMAP;lexeditor_ff8_flare_tick();buttons[1]=0;lexeditor_ff8_flare_tick();buttons[1]=0x80;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_world_gate(&encounter,true)!=1 || uses!=2)return 8;
 buttons[1]=0;lexeditor_ff8_flare_tick();buttons[1]=0x80;lexeditor_ff8_flare_tick();current.driver_mode=MODE_MENU;lexeditor_ff8_flare_tick();
 current.driver_mode=MODE_WORLDMAP;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_world_gate(&encounter,true)!=-1)return 9;
 current.driver_mode=MODE_MENU;lexeditor_ff8_flare_tick();save.items.items[0]={199,1};
 if(menu_callback())return 10;save.items.items[0]={0,0};
 if(!menu_callback())return 11;
 enable_ff8_modern_controls=false;lexeditor_ff8_flare_tick();
 if(!request.pending || !exit_requested)return 12;
 exit_ready=true;current.driver_mode=MODE_WORLDMAP;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_world_gate(&encounter,true)!=1 || uses!=3)return 21;
 enable_ff8_modern_controls=true;current.driver_mode=MODE_FIELD;buttons[1]=0;lexeditor_ff8_flare_tick();buttons[1]=0x80;
 lexeditor_ff8_flare_tick();if(lexeditor_ff8_flare_field_gate(true)!=1 || uses!=4)return 13;
 lexeditor_ff8_flare_tick();if(lexeditor_ff8_flare_field_gate(true)!=-1)return 14;
 buttons[1]=0;lexeditor_ff8_flare_tick();buttons[1]=0x80;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_field_gate(true)!=1 || uses!=5)return 15;
 current.driver_mode=MODE_MENU;lexeditor_ff8_flare_tick();current.driver_mode=MODE_FIELD;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_field_gate(true)!=-1)return 16;
 focus=nullptr;lexeditor_ff8_flare_tick();focus=gameHwnd;lexeditor_ff8_flare_tick();
 if(lexeditor_ff8_flare_field_gate(true)!=-1)return 17;
 buttons[1]=0;lexeditor_ff8_flare_tick();buttons[1]=0x80;lexeditor_ff8_flare_tick();
 lexeditor_ff8_flare_service_stationary_field();lexeditor_ff8_flare_service_stationary_field();
 if(wrapper_calls!=1 || uses!=6)return 22;
 field_available=false;buttons[1]=0;lexeditor_ff8_flare_tick();buttons[1]=0x80;lexeditor_ff8_flare_tick();
 lexeditor_ff8_flare_service_stationary_field();if(wrapper_calls!=1 || uses!=6)return 23;
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="lexeditor-flare-owner-") as temporary:
            folder=Path(temporary);(folder/"ff8").mkdir()
            for name,text in {
                "cfg.h":"extern bool enable_ff8_modern_controls;\n",
                "globals.h":"extern bool ff8;extern void *gameHwnd;void *GetForegroundWindow();\n#define FF8_US_VERSION true\n",
                "common.h":"#pragma once\nenum{MODE_WORLDMAP,MODE_FIELD,MODE_MENU};struct Mode{int driver_mode;};Mode *getmode_cached();\n#define TEXTCOLOR_LIGHT_BLUE 1\n",
                "ff8.h":"#pragma once\n#include <cstdint>\nstruct Slot{std::uint8_t item_id,item_quantity;};struct Save{struct{Slot items[198];}items;};struct Externals{Save *savemap;unsigned *engine_input_valid_buttons;};extern Externals ff8_externals;\n",
                "ff8/save_data.h":"#pragma once\n",
                "log.h":"void show_popup_msg(unsigned char,const char*,...);inline void ffnx_warning(const char*,...){}inline void ffnx_trace(const char*,...){}\n",
                "lexeditor_ff8_modern_controls.h":"bool lexeditor_ff8_modern_controls_take_square_press();\n",
            }.items():(folder/name).write_text(text)
            (folder/"check.cpp").write_text(code)
            (folder/"build.cmd").write_text(f'@echo off\ncall "{VCVARS}" >nul\ncl /nologo /EHsc /std:c++17 /I. check.cpp /Fe:check.exe\n')
            result=subprocess.run(["cmd","/c",str(folder/"build.cmd")],cwd=folder,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(folder/"check.exe")],capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

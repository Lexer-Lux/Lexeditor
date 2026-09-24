"""Run the unbound native trinket page with fake input/inventory/draw calls."""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

HARNESS = r'''
#include <cassert>
#include <map>
#include <string>
#include <vector>
using Void=void;
#define FALSE 0
template<class T,class... A>T invoke(unsigned long long,A...){return;}
enum class SettingsMenuTextAlign {Left,Center,Right};
std::vector<std::string> text;
void settingsMenuDrawSprite(const char*,const char*,float,float,float,float,int=255,int=255,int=255,int=255){}
void settingsMenuDrawText(const std::string& s,float,float,int,SettingsMenuTextAlign=SettingsMenuTextAlign::Left,bool=false,int=245,int=245,int=245,int=255){text.push_back(s);}
#include "trinket_view.cpp"
int main(){
 using namespace TrinketView;
 std::map<unsigned,int> inventory{{1,1},{2,0},{3,-1},{4,2}};
 std::vector<Record> catalog{{1,true,"Owned",{"Effect"}},{2,true,"Absent",{}},{3,true,"Unknown",{}},{4,false,"Talisman",{}},{1,true,"Duplicate",{}}};
 int reads=0;auto count=[&](unsigned id){++reads;return inventory[id];};
 Page page;assert(!page.begin(catalog,count,false)&&reads==0);
 assert(page.begin(catalog,count,true)&&page.rows.size()==1&&page.rows[0].record.item==1);
 assert(!page.begin(catalog,count,true));
 auto original=inventory;
 bool disabled=false;Input input;int samples=0;
 auto disable=[&](){disabled=true;};
 auto sample=[&](){assert(disabled);++samples;return input;};
 // The held opening press must not navigate or dismiss the new page.
 input={true,false,false,true};frameTrinketView(page,disable,sample);
 assert(!page.armed&&!page.closing);
 input={};frameTrinketView(page,disable,sample);assert(page.armed);
 input={true,false,false,true};assert(frameTrinketView(page,disable,sample)&&page.closing);
 assert(frameTrinketView(page,disable,sample)&&page.open);
 input={};assert(frameTrinketView(page,disable,sample)&&!page.open);
 int oldSamples=samples;assert(!frameTrinketView(page,disable,sample)&&samples==oldSamples);
 assert(inventory==original); // Read-only membership and lifecycle.
 // Many rows, wrap, page boundary, and selected detail all use the same index.
 catalog.clear();for(unsigned i=1;i<=20;++i)catalog.push_back({i,true,"Item "+std::to_string(i),{"Effect "+std::to_string(i)}});
 assert(page.begin(catalog,[](unsigned){return 1;},true));
 page.step({});page.step({true,true,false,false});assert(page.selected==19);
 text.clear();drawTrinketView(page);assert(text.size()==10);
 assert(text[1]=="Item 15"&&text[6]=="Item 20"&&text[7]=="Effect 20");
 page.step({true,false,true,false});assert(page.selected==0);
 page.step({true,true,true,false});assert(page.selected==0);
 page.step({true,false,false,true});page.step({});
 assert(page.begin(catalog,[](unsigned){return 0;},true));
 page.step({});page.step({true,false,true,false});assert(page.selected==0);
 text.clear();drawTrinketView(page);assert(text[1]=="No owned trinkets");
}
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, default=Path('C:/RDR2Mod'))
    args = parser.parse_args()
    modules = args.runtime_root / 'GameplayTweaks/modules'
    compiler = shutil.which('g++') or shutil.which('clang++')
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory(prefix='lex-trinket-view-') as temp:
        folder = Path(temp)
        for name in ('trinket_view.h', 'trinket_view.cpp'):
            shutil.copyfile(modules / name, folder / name)
        cpp, exe = folder / 'test.cpp', folder / 'test.exe'
        cpp.write_text(HARNESS, encoding='utf-8')
        if compiler:
            command = [compiler, '-std=c++17', str(cpp), '-o', str(exe)]
        else:
            batch = folder / 'compile.cmd'
            batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n')
            command = ['cmd', '/d', '/c', str(batch)]
        result = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        subprocess.run([str(exe)], cwd=folder, check=True, timeout=10)
    print('PASS native page adapter: ownership filter, duplicate/unknown exclusion, 20-row navigation, detail, empty, entry/back release and read-only state')

if __name__ == '__main__':
    main()

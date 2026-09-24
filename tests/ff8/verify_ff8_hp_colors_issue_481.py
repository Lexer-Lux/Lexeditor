"""Issue #481 deterministic smooth-HP source and interpolation checks."""
from __future__ import annotations
import argparse, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HEADER=ROOT/"plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_hp_colors.h"
SOURCE=ROOT/"plugins/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp"
PREPARE=ROOT/"tools/prepare_ff8_native_build.py"
SETTINGS=ROOT/"plugins/ff8/gameplay_settings.py"
EDITOR=ROOT/"plugins/ff8/boot.js"
def require(v,m):
    if not v: raise AssertionError(m)
def static_contract():
    source=SOURCE.read_text(encoding="utf-8");prepare=PREPARE.read_text(encoding="utf-8")
    settings=SETTINGS.read_text(encoding="utf-8");editor=EDITOR.read_text(encoding="utf-8")
    for token in ("lexeditor_ff8_hp_should_tint","g_better_hp_runtime_ready","FF8_US_VERSION","0x004B17D5","0x004B1100","0x004B127B","kCharacterWidget = 0x004C0780","kHpNumberRenderer = 0x004A3530","stack[3] != g_menu_hp.packed_position","computed[4], computed[5]","unreplace_function(g_hp_number_replace_id)","rereplace_function(g_hp_number_replace_id)","TEXTCOLOR_WHITE","TEXTCOLOR_YELLOW","v.r != 255 || v.g != 255 || v.b != 255","common_draw_paletted2D","lexeditor_ff8_hp_colors_requested"):
        require(token in source,f"runtime contract missing {token}")
    require("enable_ff8_better_hp_colors = false" in prepare,"candidate switch must default off")
    wanted="lexeditor_ff8_hp_colors_requested() ? lexeditor_ff8_hp_colors_draw_paletted2D : common_draw_paletted2D"
    require(wanted in prepare,"disabled driver must select original paletted draw")
    require("enable_ff8_better_hp_colors ? lexeditor" not in prepare,"ff8_opengl must not read cfg global directly")
    require("DEFAULT_BETTER_HP_COLORS = False" in settings,"Lexeditor default missing")
    require('"betterHpColors"' in settings and '"Better HP Colors"' in settings,"persistence missing")
    require('("enable_ff8_better_hp_colors", better_hp_colors)' in settings,"config writer missing")
    require('"aria-label":"Better HP Colors"' in editor and 'row("BETTER HP COLORS"' in editor,"UI missing")
def compile_contract(compiler):
    code=r"""#include <cassert>
#include "lexeditor_ff8_hp_colors.h"
void c(unsigned a,unsigned m,int r,int g,int b){auto x=lexeditor_ff8_hp_rgb(a,m);assert(x.r==r&&x.g==g&&x.b==b);}
int main(){c(100,100,255,255,255);c(75,100,255,255,128);c(50,100,255,255,0);c(375,1000,255,192,0);c(25,100,255,128,0);c(125,1000,255,64,0);c(0,100,255,0,0);c(120,100,255,255,255);c(0,0,255,255,255);assert(!lexeditor_ff8_hp_should_tint(100,100));assert(lexeditor_ff8_hp_should_tint(99,100));assert(lexeditor_ff8_hp_should_tint(50,100));assert(lexeditor_ff8_hp_should_tint(25,100));assert(lexeditor_ff8_hp_should_tint(1,100));assert(!lexeditor_ff8_hp_should_tint(0,100));assert(!lexeditor_ff8_hp_should_tint(0,0));}
"""
    with tempfile.TemporaryDirectory(prefix="ff8-hp-colors-") as d:
        p=Path(d);(p/"lexeditor_ff8_hp_colors.h").write_bytes(HEADER.read_bytes());(p/"check.cpp").write_text(code)
        if Path(compiler).name.casefold() in {"cl","cl.exe"}:cmd=[compiler,"/nologo","/EHsc","/std:c++17","check.cpp","/Fe:check.exe"];out=p/"check.exe"
        else:out=p/"check";cmd=[compiler,"-std=c++17","-Wall","-Wextra","check.cpp","-o",str(out)]
        r=subprocess.run(cmd,cwd=p,capture_output=True,text=True);require(r.returncode==0,"compile failed:\n"+r.stdout+r.stderr)
        r=subprocess.run([str(out)],cwd=p,capture_output=True,text=True);require(r.returncode==0,"execution failed:\n"+r.stdout+r.stderr)
def main():
    p=argparse.ArgumentParser();p.add_argument("--compile",action="store_true");p.add_argument("--compiler",default="cl");a=p.parse_args()
    static_contract()
    if a.compile:compile_contract(a.compiler)
    print("PASS: FF8 #481 interpolation, KO, fail-closed and vanilla-disable contracts");return 0
if __name__=="__main__":raise SystemExit(main())

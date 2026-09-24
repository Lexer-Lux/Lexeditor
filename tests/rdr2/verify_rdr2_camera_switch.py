"""Execute the production shoulder-target branch without a game or window."""
from pathlib import Path
import os
import argparse
import shutil
import subprocess
import tempfile

SOURCE = Path("C:/RDR2Mod/GameplayTweaks/modules/gameplay_camera.cpp")
PRELUDE = r"""
#include <cmath>
#include <cstdint>
using DWORD=uint32_t;
enum class GameplayCameraMode { Standing, Aim, CrouchedAim };
enum class GameplayCameraShoulderInput { None, Mapped };
struct Profile {float horizontal=2.95f;} profile;
GameplayCameraMode mode=GameplayCameraMode::Aim;
GameplayCameraShoulderInput input=GameplayCameraShoulderInput::None;
float lateral=-1; bool pending=false;
float gameplayCameraRenderedLateral(int){return lateral;}
GameplayCameraShoulderInput gameplayCameraShoulderInput(DWORD){return input;}
float update(DWORD now){int ped=1;
"""
TESTS = r"""
pending=nativeShoulderReadbackPending; return desiredHorizontal;
}
#define CHECK(x) do { if (!(x)) return __LINE__; } while(0)
int main(){
 CHECK(update(0)<0);
 input=GameplayCameraShoulderInput::Mapped;
 CHECK(update(100)>0);
 // Still on the old side during the blend: another press must reverse.
 CHECK(update(350)<0);
 CHECK(update(600)>0);
 // Each side keeps the configured magnitude.
 CHECK(std::fabs(update(850))==profile.horizontal);
 // Leaving aim invalidates pending readback; a new aim uses its actual side.
 input=GameplayCameraShoulderInput::None;mode=GameplayCameraMode::Standing;
 update(900);CHECK(!pending);mode=GameplayCameraMode::Aim;lateral=1;
 CHECK(update(950)>0);input=GameplayCameraShoulderInput::Mapped;
 CHECK(update(1000)<0);
}
"""

def run_variants(variants, prelude, tests):
    compiler=shutil.which("g++") or shutil.which("clang++")
    vcvars=Path("C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat")
    with tempfile.TemporaryDirectory(prefix="lex-camera-test-") as tmp:
        folder=Path(tmp)
        for name,code in variants.items():
            assert name=="production" or bool(code)
            cpp=folder/"test.cpp";exe=folder/("test.exe" if os.name=="nt" else "test")
            cpp.write_text(prelude+code+tests,"utf-8")
            if compiler:cmd=[compiler,"-std=c++17",str(cpp),"-o",str(exe)]
            else:
                batch=folder/"compile.cmd"
                batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n',"utf-8")
                cmd=["cmd","/d","/c",str(batch)]
            built=subprocess.run(cmd,cwd=folder,capture_output=True,text=True,timeout=60)
            assert built.returncode==0,built.stdout+built.stderr
            ran=subprocess.run([str(exe)],cwd=folder,capture_output=True,timeout=10)
            assert (ran.returncode==0)==(name=="production"),(name,ran.returncode)
            print(("PASS " if name=="production" else "REJECTED ")+name)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--runtime-root",type=Path,default=SOURCE.parents[2])
    args=parser.parse_args()
    source=(args.runtime_root / "GameplayTweaks/modules/gameplay_camera.cpp").read_text("utf-8")
    start=source.index("\tconst GameplayCameraShoulderInput shoulderInput =")
    end=source.index("\t// #175/#178", start)
    branch=source[start:end]
    variants={"production":branch,
        "lost-second-press":branch.replace("shoulderSwitchInFlight ? -shoulderBiasSign", "false ? -shoulderBiasSign")}
    # Remove only the exit reset, not the static initializer.
    variants["stale-aim-readback"]=branch.replace("\t\tnativeShoulderReadbackPending = false;", "")
    run_variants(variants, PRELUDE, TESTS)
    print("Target reversals verified. Rendered shoulder symmetry remains unverified.")

if __name__=="__main__":main()

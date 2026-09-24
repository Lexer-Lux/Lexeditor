"""Compile and exercise the production FF8 idle battle-camera policy helper."""
from pathlib import Path
import subprocess
import tempfile
import os

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'plugins/ff8/ffnx_modern_controls/battle_camera.h'

CASES = r'''
#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>
#include "battle_camera.h"
using namespace lexeditor_battle_camera;

static double radius(const Vec3s &p, const Vec3s &t) {
    const double x=p.x-t.x, y=p.y-t.y, z=p.z-t.z;
    return std::sqrt(x*x+y*y+z*z);
}
static double displacement(const Vec3s &a, const Vec3s &b) {
    const double x=a.x-b.x, y=a.y-b.y, z=a.z-b.z;
    return std::sqrt(x*x+y*y+z*z);
}
int main() {
    assert(safe_idle(0, 0, 0));
    assert(safe_idle(0, 0x2000, 0));
    assert(!safe_idle(1, 0, 0));
    assert(!safe_idle(0, 0x0001, 0));
    assert(!safe_idle(0, 0x8000, 0));
    assert(!safe_idle(0, 0, 1));
    assert(!safe_idle(0, 0, 0x1000));

    const Vec3s target{120,-80,40};
    // FF8's Y axis points down: a camera above the target has a lower Y.
    const Vec3s start{1120,-580,1540};
    Vec3s centered=start;
    for (int i=0;i<10000;++i) assert(!orbit(centered,target,128,128));
    assert(std::memcmp(&centered,&start,sizeof start)==0);
    Vec3s dead=start;
    assert(!orbit(dead,target,168,88));
    assert(std::memcmp(&dead,&start,sizeof start)==0);

    const double r0=radius(start,target);
    Vec3s partial=start, full=start, vertical=start;
    assert(orbit(partial,target,190,128));
    assert(orbit(full,target,255,128));
    assert(orbit(vertical,target,128,0));
    assert(displacement(partial,start) > 0.0);
    assert(displacement(partial,start) < displacement(full,start));
    assert(std::abs(radius(partial,target)-r0) < 1.5);
    assert(std::abs(radius(full,target)-r0) < 1.5);
    assert(std::abs(radius(vertical,target)-r0) < 1.5);
    assert(full.y == start.y);
    assert(vertical.y > start.y);   // stick up: view tilts up, camera drops

    Vec3s sweep=start;
    for (int i=0;i<240;++i) assert(orbit(sweep,target,255,128));
    assert(std::abs(radius(sweep,target)-r0) < 12.0);
    const Vec3s handed_back{-700,-900,2400};
    Vec3s adopted=handed_back;
    assert(orbit(adopted,target,255,128));
    assert(displacement(adopted,handed_back) < 100.0);
    assert(displacement(adopted,start) > 100.0);

    // Camera speed. The same stick push turns further at a higher setting and
    // less at a lower one, and a setting outside the usable range is brought
    // back into it rather than obeyed.
    Vec3s slow=start, normal=start, fast=start;
    assert(orbit(slow,target,255,128,0.035f,0.025f,0.4f));
    assert(orbit(normal,target,255,128));
    assert(orbit(fast,target,255,128,0.035f,0.025f,2.5f));
    assert(displacement(slow,start) < displacement(normal,start));
    assert(displacement(normal,start) < displacement(fast,start));
    Vec3s absurd=start, ceiling=start;
    assert(orbit(absurd,target,255,128,0.035f,0.025f,900.0f));
    assert(orbit(ceiling,target,255,128,0.035f,0.025f,MAX_SPEED_SCALE));
    assert(displacement(absurd,ceiling) < 1.5);
    Vec3s zero=start, floor_rate=start;
    assert(orbit(zero,target,255,128,0.035f,0.025f,0.0f));
    assert(orbit(floor_rate,target,255,128,0.035f,0.025f,DEFAULT_SPEED_SCALE));
    assert(displacement(zero,floor_rate) < 1.5);

    // The floor. Holding the stick up (the camera drops) can bring the camera level with what it
    // is looking at and no lower: below that it is inside the battlefield.
    Vec3s sinking=start;
    for (int i=0;i<600;++i) orbit(sinking,target,128,0);
    assert(sinking.y <= target.y + 2);
    Vec3s rising=start;
    for (int i=0;i<600;++i) orbit(rising,target,128,255);
    assert(rising.y < start.y - 1000);
    assert(pitch_of(rising,target) <= MAX_PITCH + .002f);
    // The floor a scene sets for itself. FF8 hands the camera back below level
    // here, so that pose is this battle's floor: the reader can sink to it and
    // no further, rather than being clamped up to level.
    Floor floor;
    Vec3s low{start.x,static_cast<std::int16_t>(target.y+300),start.z};
    assert(!orbit(low,target,128,128,0.035f,0.025f,1.0f,&floor));  // centred: learn
    assert(floor.known);
    assert(floor.pitch < 0.0f);
    const float learned=floor.pitch;
    Vec3s driven=low;
    for (int i=0;i<600;++i) orbit(driven,target,128,0,0.035f,0.025f,1.0f,&floor);
    assert(driven.y >= target.y + 1);   // not lifted to level
    assert(driven.y <= low.y + 2);      // and not driven below the scene's pose

    // A different battle starts from its own pose, not the last one's.
    Vec3s high{start.x,static_cast<std::int16_t>(target.y-400),start.z};
    assert(!orbit(high,target,128,128,0.035f,0.025f,1.0f,&floor));
    assert(floor.known && floor.pitch == 0.0f);
    assert(learned < floor.pitch);
    Vec3s again=high;
    for (int i=0;i<600;++i) orbit(again,target,128,0,0.035f,0.025f,1.0f,&floor);
    assert(again.y <= target.y + 2);

    std::cout << "Battle camera policy: idle gate, zero-drift center/deadzone, proportional X/Y orbit, radius preservation, speed scaling, per-scene ground floor and handed-back baseline passed\n";
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='ff8-battle-camera-') as folder:
        source=Path(folder)/'battle_camera_cases.cpp'
        binary=Path(folder)/'battle_camera_cases'
        source.write_text(CASES, encoding='utf-8')
        if os.name == 'nt':
            binary=binary.with_suffix('.exe')
            vcvars=Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat')
            script=Path(folder)/'build.cmd'
            script.write_text(f'@call "{vcvars}" >nul\n@cl /nologo /EHsc /std:c++20 /O2 /I"{HEADER.parent}" "{source}" /Fe:"{binary}"\n')
            subprocess.run(['cmd.exe','/c',str(script)],cwd=folder,check=True)
        else:
            subprocess.run([
                'g++','-std=c++20','-Wall','-Wextra','-O2',
                '-I',str(HEADER.parent),str(source),'-o',str(binary)
            ],check=True)
        subprocess.run([str(binary)],check=True,timeout=15)


if __name__ == '__main__':
    main()

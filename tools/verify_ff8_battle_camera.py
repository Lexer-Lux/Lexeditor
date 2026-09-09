"""Compile and exercise the production FF8 idle battle-camera policy helper."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'games/ff8/ffnx_modern_controls/battle_camera.h'

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
    const Vec3s start{1120,420,1540};
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
    assert(vertical.y > start.y);

    Vec3s sweep=start;
    for (int i=0;i<240;++i) assert(orbit(sweep,target,255,128));
    assert(std::abs(radius(sweep,target)-r0) < 12.0);
    const Vec3s handed_back{-700,900,2400};
    Vec3s adopted=handed_back;
    assert(orbit(adopted,target,255,128));
    assert(displacement(adopted,handed_back) < 100.0);
    assert(displacement(adopted,start) > 100.0);

    std::cout << "Battle camera policy: idle gate, zero-drift center/deadzone, proportional X/Y orbit, radius preservation and handed-back baseline passed\n";
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='ff8-battle-camera-') as folder:
        source=Path(folder)/'battle_camera_cases.cpp'
        binary=Path(folder)/'battle_camera_cases'
        source.write_text(CASES, encoding='utf-8')
        subprocess.run([
            'g++','-std=c++20','-Wall','-Wextra','-O2',
            '-I',str(HEADER.parent),str(source),'-o',str(binary)
        ],check=True)
        subprocess.run([str(binary)],check=True,timeout=15)


if __name__ == '__main__':
    main()

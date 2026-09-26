"""Compile and exercise the production FF8 Modern Controls vehicle policy."""
from pathlib import Path
import argparse
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'plugins/ff8/ffnx_modern_controls/vehicle_drive.h'

CASES = r'''
#include <cassert>
#include <iostream>
#include "vehicle_drive.h"
using namespace lexeditor_vehicle_drive;

int main() {
    assert(kL2 == 0x0001u && kR2 == 0x0002u);
    assert(kTriangle == 0x0010u && kSquare == 0x0080u);
    for (unsigned state : {0x20u,0x21u,0x28u,0x30u,0x32u,0x84u})
        assert(supported_state(state));
    for (unsigned state : {0u,9u,0x10u,0x16u,0x29u,0x31u,0x40u,0x42u,0x80u})
        assert(!supported_state(state));

    assert(axis(0.0f,0.0f) == 128);
    assert(axis(0.0f,1.0f) == 0);
    assert(axis(1.0f,0.0f) == 255);
    assert(axis(0.0f,0.5f) == 39);
    assert(axis(0.5f,0.0f) == 216);
    assert(axis(0.5f,0.5f) == 128);
    assert(axis(0.25f,0.75f) == 39);
    assert(axis(0.75f,0.25f) == 216);
    assert(axis(0.0f,0.0f,false,true) == 0);   // keyboard R2 = forward
    assert(axis(0.0f,0.0f,true,false) == 255); // keyboard L2 = reverse
    assert(axis(0.0f,0.0f,true,true) == 128);
    assert(axis(-2.0f,3.0f) == 0);
    assert(axis(3.0f,-2.0f) == 255);
    // XInput triggers also set digital aliases; partial pressure stays partial.
    assert(axis(0.0f,0.5f,false,true) == 39);
    assert(axis(0.5f,0.0f,true,false) == 216);
    // Tiny trigger noise is dead-zoned around center.
    assert(axis(0.00f,0.01f) == 128);
    assert(axis(0.01f,0.00f) == 128);
    for (int native_limit : {32,64,200}) {
        int previous = 0;
        for (int step = 2; step <= 100; ++step) {
            const float pull = step / 100.0f;
            const int cap = speed_limit(native_limit, pressure(0,pull));
            assert(cap >= previous && cap <= native_limit);
            assert(cap == speed_limit(native_limit, pressure(pull,0)));
            // Native dead zone is 45, then car acceleration divides by 48.
            assert(127-axis(0,pull) >= 49);
            assert(127-axis(pull,0) <= -49);
            previous = cap;
        }
        assert(previous == native_limit);
    }
    assert(speed_limit(64, pressure(0,0.5f,false,true)) == 32);
    assert(speed_limit(64, pressure(0,0.25f)) == 16);
    assert(speed_limit(200, pressure(0,0.5f)) == 100);
    assert(speed_limit(64, pressure(0,0,false,true)) == 64);
    assert(speed_limit(64, pressure(0.5f,0.5f)) == 0);
    std::cout << "Vehicle drive policy: FF8 pad masks, supported states, proportional LT/RT, L2/R2 keyboard fallback, cancellation and dead zone passed\n";
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='g++', choices=('g++','cl'))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ff8-vehicle-drive-') as folder:
        source = Path(folder) / 'cases.cpp'
        binary = Path(folder) / ('cases.exe' if args.compiler == 'cl' else 'cases')
        source.write_text(CASES, encoding='utf-8')
        command = [
            'g++','-std=c++20','-Wall','-Wextra','-O2',
            '-I',str(HEADER.parent),str(source),'-o',str(binary)
        ] if args.compiler == 'g++' else [
            'cl','/nologo','/std:c++20','/EHsc','/W4','/O2',
            '/I'+str(HEADER.parent),str(source),'/Fe:'+str(binary)
        ]
        subprocess.run(command, check=True, cwd=folder)
        subprocess.run([str(binary)], check=True, timeout=15)


if __name__ == '__main__':
    main()

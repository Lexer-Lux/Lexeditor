"""Compile and exercise the production FF8 Modern Controls vehicle policy."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'games/ff8/ffnx_modern_controls/vehicle_drive.h'

CASES = r'''
#include <cassert>
#include <iostream>
#include "vehicle_drive.h"
using namespace lexeditor_vehicle_drive;

int main() {
    for (unsigned state : {0x20u,0x21u,0x28u,0x30u,0x32u,0x84u})
        assert(supported_state(state));
    for (unsigned state : {0u,9u,0x10u,0x16u,0x29u,0x31u,0x40u,0x42u,0x80u})
        assert(!supported_state(state));

    assert(axis(0.0f,0.0f) == 128);
    assert(axis(0.0f,1.0f) == 255);
    assert(axis(1.0f,0.0f) == 0);
    assert(axis(0.0f,0.5f) == 192);
    assert(axis(0.5f,0.0f) == 64);
    assert(axis(0.5f,0.5f) == 128);
    assert(axis(0.25f,0.75f) == 192);
    assert(axis(0.75f,0.25f) == 64);
    assert(axis(0.0f,0.0f,false,true) == 255); // keyboard R2 = forward
    assert(axis(0.0f,0.0f,true,false) == 0);   // keyboard L2 = reverse
    assert(axis(0.0f,0.0f,true,true) == 128);
    assert(axis(-2.0f,3.0f) == 255);
    assert(axis(3.0f,-2.0f) == 0);
    // Tiny trigger noise is dead-zoned around center.
    assert(axis(0.00f,0.01f) == 128);
    assert(axis(0.01f,0.00f) == 128);
    std::cout << "Vehicle drive policy: supported states, proportional LT/RT, L2/R2 keyboard fallback, cancellation and dead zone passed\n";
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='ff8-vehicle-drive-') as folder:
        source = Path(folder) / 'cases.cpp'
        binary = Path(folder) / 'cases'
        source.write_text(CASES, encoding='utf-8')
        subprocess.run([
            'g++','-std=c++20','-Wall','-Wextra','-O2',
            '-I',str(HEADER.parent),str(source),'-o',str(binary)
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=15)


if __name__ == '__main__':
    main()

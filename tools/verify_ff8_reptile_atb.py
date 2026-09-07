"""Compile and exercise the production Reptile ATB speed-state helper."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'games/ff8/ffnx_gameplay_extensions/ffnx-src/reptile_atb_runtime.h'

CASES = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include "reptile_atb_runtime.h"
using namespace lexeditor_reptile_atb;

int main() {
    assert(enemy_index(0) == -1 && enemy_index(2) == -1);
    assert(enemy_index(3) == 0 && enemy_index(10) == 7 && enemy_index(11) == -1);
    assert(com_id(3, 0x10) == 0);
    assert(com_id(3, 0x14) == 4); // Geezard: scene entity 20 -> c0m004.
    assert(com_id(10, 0x43) == 0x33);
    assert(com_id(2, 0x14) == -1 && com_id(3, 0x0F) == -1);

    SpeedState state;
    for (double value : state.multiplier) assert(value == 1.0);
    assert(!state.apply(2, kFireElement));
    assert(state.scale_increment(2, 123) == 123);

    assert(state.apply(3, kIceElement));
    assert(std::abs(state.multiplier[0] - 0.92) < 1e-12);
    assert(state.scale_increment(3, 100) == 92);
    assert(state.apply(3, kFireElement));
    assert(std::abs(state.multiplier[0] - (0.92 * 1.08)) < 1e-12);

    state.reset();
    assert(state.apply(3, kFireElement | kIceElement));
    assert(std::abs(state.multiplier[0] - (0.92 * 1.08)) < 1e-12);

    state.reset();
    state.apply(3, kIceElement);
    std::uint64_t total = 0;
    for (int frame = 0; frame < 1000; ++frame) total += state.scale_increment(3, 1);
    assert(total == 920); // fractional carry preserves 0.92 instead of rounding to 1 or 0 per frame.

    state.reset();
    for (int i = 0; i < 10; ++i) state.apply(4, kIceElement);
    const double ice10 = std::pow(0.92, 10);
    assert(std::abs(state.multiplier[1] - ice10) < 1e-12);
    std::uint64_t slow_total = 0;
    for (int frame = 0; frame < 1000; ++frame) slow_total += state.scale_increment(4, 10);
    assert(std::llabs(static_cast<long long>(slow_total) - static_cast<long long>(std::floor(10000.0 * ice10))) <= 1);

    state.reset();
    for (int i = 0; i < 10; ++i) state.apply(5, kFireElement);
    const double fire10 = std::pow(1.08, 10);
    assert(std::abs(state.multiplier[2] - fire10) < 1e-12);
    assert(state.scale_increment(5, 1000) == static_cast<std::uint32_t>(std::floor(1000.0 * fire10)));

    state.reset();
    for (double value : state.multiplier) assert(value == 1.0);
    for (double value : state.remainder) assert(value == 0.0);
    std::cout << "Reptile ATB policy: scene identity, cumulative 0.92/1.08, fractional carry, party pass-through and reset passed\n";
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='ff8-reptile-atb-') as folder:
        source = Path(folder) / 'cases.cpp'
        binary = Path(folder) / 'cases'
        source.write_text(CASES, encoding='utf-8')
        subprocess.run([
            'g++', '-std=c++20', '-Wall', '-Wextra', '-O2',
            '-I', str(HEADER.parent), str(source), '-o', str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=15)


if __name__ == '__main__':
    main()

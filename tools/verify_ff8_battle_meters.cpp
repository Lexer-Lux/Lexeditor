#include "../games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_battle_meters.h"
#include <cassert>
#include <cmath>
#include <iostream>

using namespace lexeditor_ff8_meters;
static bool close(float a, float b) { return std::fabs(a - b) < 0.001f; }
int main()
{
    std::array<GuardianForce, 16> gfs{};
    assert(junctioned_gf_hp(0xffff, gfs, {}).maximum == 0);
    gfs[0] = {{500, 1000}, true};
    gfs[1] = {{1000, 2000}, true};
    gfs[15] = {{0, 9999}, true};
    assert(junctioned_gf_hp(0, gfs, {}).maximum == 0);
    auto hp = junctioned_gf_hp(1, gfs, {});
    assert(hp.current == 500 && hp.maximum == 1000);
    hp = junctioned_gf_hp(3, gfs, {});
    assert(hp.current == 1500 && hp.maximum == 3000);
    hp = junctioned_gf_hp(3, gfs, {{17, 2000}, 1});
    assert(hp.current == 517 && hp.maximum == 3000);
    // A summon not junctioned to this character must not appear in its bar.
    hp = junctioned_gf_hp(1, gfs, {{17, 2000}, 1});
    assert(hp.current == 500 && hp.maximum == 1000);
    hp = junctioned_gf_hp(0x8000, gfs, {});
    assert(hp.current == 0 && hp.maximum == 9999);
    // Invalid IDs cannot index memory; zero max and excess current are safe.
    hp = junctioned_gf_hp(1, gfs, {{99999, 0}, -7});
    assert(hp.current == 500 && hp.maximum == 1000);
    hp = junctioned_gf_hp(1, gfs, {{99999, 0}, 0});
    assert(hp.current == 0 && hp.maximum == 0);
    hp = junctioned_gf_hp(1, gfs, {{99999, 1000}, 0});
    assert(hp.current == 1000 && hp.maximum == 1000);
    for (auto &gf : gfs) gf = {{65535, 65535}, true};
    hp = junctioned_gf_hp(0xffff, gfs, {});
    assert(hp.current == 1048560 && hp.maximum == 1048560);
    for (float y : {20.0f, 35.0f, 50.0f}) {
        assert(close(hp_top(y, y + 16), y + 13));
        assert(close(hp_top(y, y + 12), y + 12));
        assert(close(gf_top(y), y));
        for (bool forward : {false, true}) {
            assert(!line(10, 110, y, {0, 0}, forward).visible);
            assert(!line(110, 10, y, {1, 1}, forward).visible);
            const auto empty = line(10, 110, y, {0, 9999}, forward);
            assert(empty.visible && close(empty.fill_left, empty.fill_right));
            const auto half = line(10, 110, y, {2500, 5000}, forward);
            const float width = 100 * 5000.0f / 9999;
            assert(close(half.right - half.left, width));
            assert(close(half.fill_right - half.fill_left, width / 2));
            assert(close(forward ? half.left : half.right, forward ? 10 : 110));
            assert(close(forward ? half.fill_left : half.fill_right, forward ? 10 : 110));
            const auto capped = line(10, 110, y, {99999, 12000}, forward);
            assert(close(capped.left, 10) && close(capped.right, 110));
            assert(close(capped.fill_left, 10) && close(capped.fill_right, 110));
        }
    }
    std::cout << "PASS: GF ownership/live override, HP bounds, bar orientation and row geometry\n";
}

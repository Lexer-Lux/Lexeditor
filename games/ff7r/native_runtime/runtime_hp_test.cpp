#include "RuntimeHP.hpp"

#include <cassert>

using namespace lexeditor::ff7r;

int main() {
    const PlayerStatsPrefix vanilla{1001, 1001, 40, 40};
    HPTrackState state;

    const auto half = makeHPWritePlan(state, vanilla, 0.5);
    assert(half.valid);
    assert(half.maxHP == 501);
    assert(half.hp == 501);
    assert(half.writeMaxHP);
    assert(half.writeHP);
    assert(half.vanillaMaxHP == 1001);
    commitHPWritePlan(state, half);

    const PlayerStatsPrefix alreadyApplied{501, 501, 40, 40};
    const auto stable = makeHPWritePlan(state, alreadyApplied, 0.5);
    assert(stable.valid);
    assert(stable.maxHP == 501);
    assert(stable.vanillaMaxHP == 1001);
    assert(!stable.writeMaxHP);
    assert(!stable.writeHP);

    // A native stat recalculation replaces our scaled MaxHP. The planner must
    // adopt it as the new composed vanilla value instead of scaling 1001 again.
    const PlayerStatsPrefix recalculated{501, 1200, 40, 40};
    const auto recalculatedPlan = makeHPWritePlan(state, recalculated, 0.5);
    assert(recalculatedPlan.valid);
    assert(recalculatedPlan.vanillaMaxHP == 1200);
    assert(recalculatedPlan.maxHP == 600);
    assert(recalculatedPlan.hp == 501);

    HPTrackState vanillaState;
    const auto oneToOne = makeHPWritePlan(vanillaState, vanilla, 1.0);
    assert(oneToOne.valid);
    assert(oneToOne.maxHP == vanilla.maxHP);
    assert(oneToOne.hp == vanilla.hp);
    assert(!oneToOne.writeMaxHP);
    assert(!oneToOne.writeHP);

    const PlayerStatsPrefix lowHP{1, 3, 0, 0};
    const auto tiny = makeHPWritePlan({}, lowHP, 0.1);
    assert(tiny.valid);
    assert(tiny.maxHP == 1);
    assert(tiny.hp == 1);

    assert(emptyPlayerStats({}));
    assert(!plausiblePlayerStats({}));
    assert(!makeHPWritePlan({}, {}, 0.5).valid);
    assert(!scaledMaxHP(100, 0.0).has_value());

    return 0;
}

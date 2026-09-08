#include "RuntimeMinimap.hpp"

#include <cassert>

using namespace lexeditor::ff7r;

int main() {
    constexpr std::uint32_t threshold = 350;

    // A short press preserves vanilla tap behavior and does not alter the
    // player's remembered minimap preference.
    MinimapToggleState tap;
    assert(observeMinimapVisibility(tap, true).kind == MinimapGestureKind::none);
    assert(minimapButtonDown(tap, 1000).kind == MinimapGestureKind::none);
    assert(minimapButtonTick(tap, 1200, threshold).kind == MinimapGestureKind::none);
    const auto tapUp = minimapButtonUp(tap, 1250, threshold);
    assert(tapUp.kind == MinimapGestureKind::openFullMap);
    assert(!tap.playerChoiceInitialized);
    assert(tap.chosenVisible);

    // Crossing the threshold toggles once while held. Release is consumed and
    // must not also produce an open-map action.
    MinimapToggleState hold;
    observeMinimapVisibility(hold, true);
    minimapButtonDown(hold, 2000);
    const auto holdAction = minimapButtonTick(hold, 2350, threshold);
    assert(holdAction.kind == MinimapGestureKind::applyMinimapVisibility);
    assert(!holdAction.minimapVisible);
    assert(hold.playerChoiceInitialized);
    assert(!hold.chosenVisible);
    assert(minimapButtonTick(hold, 2500, threshold).kind == MinimapGestureKind::none);
    assert(minimapButtonUp(hold, 2600, threshold).kind == MinimapGestureKind::none);

    // If the polling/input hook misses the exact threshold tick, a long release
    // is still a hold, never a tap.
    MinimapToggleState missedTick;
    observeMinimapVisibility(missedTick, false);
    minimapButtonDown(missedTick, 3000);
    const auto lateRelease = minimapButtonUp(missedTick, 3500, threshold);
    assert(lateRelease.kind == MinimapGestureKind::applyMinimapVisibility);
    assert(lateRelease.minimapVisible);

    // Once the player has chosen a state, automatic game changes are converted
    // into an enforcement action and cannot silently replace that preference.
    MinimapToggleState persistent;
    observeMinimapVisibility(persistent, true);
    minimapButtonDown(persistent, 4000);
    const auto chooseOff = minimapButtonTick(persistent, 4400, threshold);
    assert(chooseOff.kind == MinimapGestureKind::applyMinimapVisibility);
    assert(!chooseOff.minimapVisible);
    // Runtime applies the choice; observing that expected result is quiet.
    assert(observeMinimapVisibility(persistent, false).kind == MinimapGestureKind::none);
    // Combat/location auto-show must be driven back to the player's choice.
    const auto autoShow = observeMinimapVisibility(persistent, true);
    assert(autoShow.kind == MinimapGestureKind::applyMinimapVisibility);
    assert(!autoShow.minimapVisible);
    assert(!persistent.chosenVisible);

    // A second hold toggles relative to the persisted player choice, not the
    // latest automatic game state.
    minimapButtonUp(persistent, 4450, threshold);
    minimapButtonDown(persistent, 5000);
    const auto chooseOn = minimapButtonTick(persistent, 5400, threshold);
    assert(chooseOn.kind == MinimapGestureKind::applyMinimapVisibility);
    assert(chooseOn.minimapVisible);
    assert(persistent.chosenVisible);

    // Repeated key-down events do not reset the original press timestamp.
    MinimapToggleState repeat;
    minimapButtonDown(repeat, 6000);
    minimapButtonDown(repeat, 6200);
    const auto repeatHold = minimapButtonTick(repeat, 6350, threshold);
    assert(repeatHold.kind == MinimapGestureKind::applyMinimapVisibility);

    // Invalid thresholds and a regressing clock fail closed without opening the
    // full map or mutating the remembered preference.
    MinimapToggleState invalid;
    minimapButtonDown(invalid, 7000);
    assert(minimapButtonUp(invalid, 7100, 100).kind == MinimapGestureKind::none);
    assert(!invalid.buttonDown);

    MinimapToggleState regressing;
    minimapButtonDown(regressing, 8000);
    assert(minimapButtonTick(regressing, 7999, threshold).kind == MinimapGestureKind::none);
    assert(!regressing.buttonDown);
    assert(minimapButtonUp(regressing, 8100, threshold).kind == MinimapGestureKind::none);

    assert(validHoldThreshold(150));
    assert(validHoldThreshold(1500));
    assert(!validHoldThreshold(149));
    assert(!validHoldThreshold(1501));

    return 0;
}

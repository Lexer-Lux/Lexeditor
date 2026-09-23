#include "RuntimeContract.hpp"

#include <cassert>
#include <cmath>
#include <stdexcept>

using lexeditor::ff7r::MapButtonGesture;
using lexeditor::ff7r::MapGestureAction;
using lexeditor::ff7r::MinimapPreference;
using lexeditor::ff7r::effectiveCutsceneMultiplier;

int main() {
    {
        MapButtonGesture gesture(350);
        assert(gesture.onPress(1000) == MapGestureAction::None);
        assert(gesture.update(1200) == MapGestureAction::None);
        assert(gesture.onRelease(1300) == MapGestureAction::OpenFullMap);
    }
    {
        MapButtonGesture gesture(350);
        assert(gesture.onPress(2000) == MapGestureAction::None);
        assert(gesture.update(2349) == MapGestureAction::None);
        assert(gesture.update(2350) == MapGestureAction::ToggleMinimap);
        assert(gesture.update(2500) == MapGestureAction::None);
        // Releasing a fired hold must never also open the full map.
        assert(gesture.onRelease(2600) == MapGestureAction::None);
    }
    {
        MapButtonGesture gesture(350);
        gesture.onPress(5000);
        // Even if no update/poll happened at the threshold, a late release is
        // still a hold and is never misclassified as a tap.
        assert(gesture.onRelease(5350) == MapGestureAction::ToggleMinimap);
    }
    {
        MapButtonGesture gesture(350);
        assert(gesture.onRelease(1) == MapGestureAction::None);
        gesture.onPress(10);
        assert(gesture.onPress(20) == MapGestureAction::None);
        assert(gesture.onRelease(100) == MapGestureAction::OpenFullMap);
    }
    {
        MinimapPreference preference(true);
        assert(preference.visible());
        assert(!preference.toggle());
        assert(!preference.visible());
        assert(preference.toggle());
        preference.set(false);
        assert(!preference.visible());
    }
    {
        assert(std::abs(effectiveCutsceneMultiplier(1.25, false, 2.0) - 1.25) < 1e-9);
        assert(std::abs(effectiveCutsceneMultiplier(1.25, true, 1.5) - 1.875) < 1e-9);
        assert(std::abs(effectiveCutsceneMultiplier(1.5, true, 2.0) - 3.0) < 1e-9);
    }
    {
        bool threw = false;
        try {
            (void)effectiveCutsceneMultiplier(1.0, false, 2.0);
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        assert(threw);
    }
    {
        bool threw = false;
        try {
            MapButtonGesture invalid(149);
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        assert(threw);
    }
    return 0;
}

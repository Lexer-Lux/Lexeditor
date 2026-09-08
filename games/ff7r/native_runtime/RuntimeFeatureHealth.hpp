#pragma once

#include <cstdint>

namespace lexeditor::ff7r {

inline constexpr std::uint32_t kFeatureFailureThreshold = 3;

// Runtime workers poll mutable game state. A single failed read can be a benign
// race with a level/load transition, but a feature that stops applying must not
// remain reported active forever. This state debounces brief failures while
// still clearing a stale live flag promptly after repeated failures.
struct FeatureHealth {
    bool active = false;
    std::uint32_t consecutiveFailures = 0;

    // Returns true only when the externally visible active state changed.
    bool observe(bool successful) noexcept {
        const bool previous = active;
        if (successful) {
            consecutiveFailures = 0;
            active = true;
        } else {
            if (consecutiveFailures < kFeatureFailureThreshold) {
                ++consecutiveFailures;
            }
            if (consecutiveFailures >= kFeatureFailureThreshold) {
                active = false;
            }
        }
        return active != previous;
    }

    // Explicit lifecycle changes (for example a different AEndGameState) can
    // invalidate the previous application immediately rather than waiting for
    // the polling failure debounce.
    bool deactivate() noexcept {
        const bool previous = active;
        active = false;
        consecutiveFailures = 0;
        return previous;
    }
};

} // namespace lexeditor::ff7r

#pragma once

#include <cstdint>

namespace lexeditor::ff7r {

enum class MinimapGestureKind : std::uint8_t {
    none = 0,
    openFullMap,
    applyMinimapVisibility,
};

struct MinimapGestureAction {
    MinimapGestureKind kind = MinimapGestureKind::none;
    bool minimapVisible = false;
};

struct MinimapToggleState {
    bool buttonDown = false;
    bool holdTriggered = false;
    bool observedInitialized = false;
    bool observedVisible = true;
    bool playerChoiceInitialized = false;
    bool chosenVisible = true;
    std::uint64_t pressedAtMs = 0;
};

inline MinimapGestureAction noMinimapAction() noexcept {
    return {};
}

inline bool validHoldThreshold(std::uint32_t holdMilliseconds) noexcept {
    return holdMilliseconds >= 150 && holdMilliseconds <= 1500;
}

inline bool elapsedAtLeast(
    std::uint64_t nowMs,
    std::uint64_t startedAtMs,
    std::uint32_t thresholdMs,
    bool& clockValid) noexcept {
    if (nowMs < startedAtMs) {
        clockValid = false;
        return false;
    }
    clockValid = true;
    return nowMs - startedAtMs >= thresholdMs;
}

// Observe the game's current minimap state. Before the player makes a choice,
// that observation seeds the eventual toggle direction. After a player choice,
// automatic combat/location visibility changes never overwrite chosenVisible.
inline MinimapGestureAction observeMinimapVisibility(
    MinimapToggleState& state,
    bool visible) noexcept {
    state.observedInitialized = true;
    state.observedVisible = visible;
    if (!state.playerChoiceInitialized) {
        state.chosenVisible = visible;
        return noMinimapAction();
    }
    if (visible == state.chosenVisible) {
        return noMinimapAction();
    }
    return {
        MinimapGestureKind::applyMinimapVisibility,
        state.chosenVisible,
    };
}

inline MinimapGestureAction toggleChosenMinimap(MinimapToggleState& state) noexcept {
    const bool baseline = state.playerChoiceInitialized
        ? state.chosenVisible
        : (state.observedInitialized ? state.observedVisible : true);
    state.playerChoiceInitialized = true;
    state.chosenVisible = !baseline;
    return {
        MinimapGestureKind::applyMinimapVisibility,
        state.chosenVisible,
    };
}

// Key-repeat/button-repeat downs are deliberately ignored. A normal tap is not
// emitted on press because doing so would make it impossible to suppress the map
// opening after the same press later crosses the hold threshold.
inline MinimapGestureAction minimapButtonDown(
    MinimapToggleState& state,
    std::uint64_t nowMs) noexcept {
    if (state.buttonDown) {
        return noMinimapAction();
    }
    state.buttonDown = true;
    state.holdTriggered = false;
    state.pressedAtMs = nowMs;
    return noMinimapAction();
}

inline MinimapGestureAction minimapButtonTick(
    MinimapToggleState& state,
    std::uint64_t nowMs,
    std::uint32_t holdMilliseconds) noexcept {
    if (!state.buttonDown || state.holdTriggered || !validHoldThreshold(holdMilliseconds)) {
        return noMinimapAction();
    }
    bool clockValid = false;
    const bool held = elapsedAtLeast(nowMs, state.pressedAtMs, holdMilliseconds, clockValid);
    if (!clockValid) {
        // A regressing clock makes tap-vs-hold classification unsafe. Cancel the
        // gesture instead of accidentally opening the full map.
        state.buttonDown = false;
        state.holdTriggered = false;
        return noMinimapAction();
    }
    if (!held) {
        return noMinimapAction();
    }
    state.holdTriggered = true;
    return toggleChosenMinimap(state);
}

inline MinimapGestureAction minimapButtonUp(
    MinimapToggleState& state,
    std::uint64_t nowMs,
    std::uint32_t holdMilliseconds) noexcept {
    if (!state.buttonDown) {
        return noMinimapAction();
    }
    if (!validHoldThreshold(holdMilliseconds)) {
        state.buttonDown = false;
        state.holdTriggered = false;
        return noMinimapAction();
    }

    bool clockValid = false;
    const bool held = elapsedAtLeast(nowMs, state.pressedAtMs, holdMilliseconds, clockValid);
    if (!clockValid) {
        state.buttonDown = false;
        state.holdTriggered = false;
        return noMinimapAction();
    }

    const bool alreadyHeld = state.holdTriggered;
    state.buttonDown = false;
    state.holdTriggered = false;
    if (alreadyHeld) {
        // Hold already toggled while down: release must not also open the map.
        return noMinimapAction();
    }
    if (held) {
        // If the runtime missed the threshold tick, classify on release rather
        // than incorrectly converting a long press into a tap.
        return toggleChosenMinimap(state);
    }
    return {
        MinimapGestureKind::openFullMap,
        false,
    };
}

} // namespace lexeditor::ff7r

#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace lexeditor::ff7r {

enum class MapGestureAction {
    None,
    OpenFullMap,
    ToggleMinimap,
};

class MapButtonGesture {
public:
    explicit MapButtonGesture(std::uint32_t holdMilliseconds = 350)
        : holdMilliseconds_(validatedThreshold(holdMilliseconds)) {}

    void setHoldMilliseconds(std::uint32_t value) {
        holdMilliseconds_ = validatedThreshold(value);
    }

    [[nodiscard]] std::uint32_t holdMilliseconds() const noexcept {
        return holdMilliseconds_;
    }

    [[nodiscard]] bool pressed() const noexcept { return pressed_; }
    [[nodiscard]] bool holdFired() const noexcept { return holdFired_; }

    MapGestureAction onPress(std::uint64_t nowMilliseconds) noexcept {
        if (pressed_) {
            return MapGestureAction::None;
        }
        pressed_ = true;
        holdFired_ = false;
        pressedAt_ = nowMilliseconds;
        return MapGestureAction::None;
    }

    MapGestureAction update(std::uint64_t nowMilliseconds) noexcept {
        if (!pressed_ || holdFired_) {
            return MapGestureAction::None;
        }
        if (elapsed(nowMilliseconds) < holdMilliseconds_) {
            return MapGestureAction::None;
        }
        holdFired_ = true;
        return MapGestureAction::ToggleMinimap;
    }

    MapGestureAction onRelease(std::uint64_t nowMilliseconds) noexcept {
        if (!pressed_) {
            return MapGestureAction::None;
        }
        const bool qualifiesAsHold = holdFired_ || elapsed(nowMilliseconds) >= holdMilliseconds_;
        pressed_ = false;
        const bool alreadyFired = holdFired_;
        holdFired_ = false;
        if (qualifiesAsHold) {
            // If the polling/update path did not get a frame exactly at the hold
            // threshold, release still becomes a hold.  A hold can never fall
            // through and also emit OpenFullMap.
            return alreadyFired ? MapGestureAction::None : MapGestureAction::ToggleMinimap;
        }
        return MapGestureAction::OpenFullMap;
    }

private:
    static std::uint32_t validatedThreshold(std::uint32_t value) {
        if (value < 150 || value > 1500) {
            throw std::invalid_argument("map hold threshold must be between 150 and 1500 ms");
        }
        return value;
    }

    [[nodiscard]] std::uint64_t elapsed(std::uint64_t nowMilliseconds) const noexcept {
        return nowMilliseconds >= pressedAt_ ? nowMilliseconds - pressedAt_ : 0;
    }

    std::uint32_t holdMilliseconds_ = 350;
    std::uint64_t pressedAt_ = 0;
    bool pressed_ = false;
    bool holdFired_ = false;
};

class MinimapPreference {
public:
    explicit MinimapPreference(bool visible = true) : visible_(visible) {}

    [[nodiscard]] bool visible() const noexcept { return visible_; }

    bool toggle() noexcept {
        visible_ = !visible_;
        return visible_;
    }

    void set(bool visible) noexcept { visible_ = visible; }

private:
    bool visible_ = true;
};

inline double effectiveCutsceneMultiplier(double baseMultiplier,
                                          bool nativeFastForwardHeld,
                                          double nativeFastForwardMultiplier) {
    if (!std::isfinite(baseMultiplier) || baseMultiplier <= 1.0) {
        throw std::invalid_argument("base cutscene multiplier must be finite and greater than 1.0");
    }
    if (!std::isfinite(nativeFastForwardMultiplier) || nativeFastForwardMultiplier < 1.0) {
        throw std::invalid_argument("native fast-forward multiplier must be finite and at least 1.0");
    }
    return baseMultiplier * (nativeFastForwardHeld ? nativeFastForwardMultiplier : 1.0);
}

}  // namespace lexeditor::ff7r

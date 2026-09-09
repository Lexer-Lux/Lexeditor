#include "RuntimeCutscene.hpp"

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>

using namespace lexeditor::ff7r;

namespace {

void write_float(std::array<std::uint8_t, kGameSpeedDiscoveryBytes>& bytes,
                 std::size_t offset,
                 float value) {
    std::memcpy(bytes.data() + offset, &value, sizeof(value));
}

void write_game_speed_block(std::array<std::uint8_t, kGameSpeedDiscoveryBytes>& bytes,
                            std::size_t offset) {
    for (std::size_t index = 0; index < kGameSpeedChannelCount; ++index) {
        write_float(bytes, offset + index * sizeof(float), kVanillaGameSpeed);
    }
}

bool close_to(float actual, float expected, float tolerance = 0.00001F) {
    return std::fabs(actual - expected) <= tolerance;
}

} // namespace

int main() {
    std::array<std::uint8_t, kGameSpeedDiscoveryBytes> image{};
    constexpr std::size_t firstOffset = 0x120;
    write_game_speed_block(image, firstOffset);

    const auto oneMatch = findInitialGameSpeedBlocks(image);
    assert(oneMatch.size() == 1);
    assert(oneMatch[0].offset == firstOffset);

    constexpr std::size_t secondOffset = 0x2A0;
    write_game_speed_block(image, secondOffset);
    const auto ambiguous = findInitialGameSpeedBlocks(image);
    assert(ambiguous.size() == 2);
    assert(ambiguous[0].offset == firstOffset);
    assert(ambiguous[1].offset == secondOffset);

    std::array<std::uint8_t, kGameSpeedDiscoveryBytes> incomplete{};
    for (std::size_t index = 0; index + 1 < kGameSpeedChannelCount; ++index) {
        write_float(incomplete, firstOffset + index * sizeof(float), kVanillaGameSpeed);
    }
    assert(findInitialGameSpeedBlocks(incomplete).empty());

    CutsceneSpeedTrack state;
    const auto base = makeCutsceneSpeedWritePlan(state, 1.0F, 1.25);
    assert(base.valid);
    assert(base.write);
    assert(base.nativeSpeed == 1.0F);
    assert(close_to(base.logicalAppliedSpeed, 1.25F));
    assert(base.appliedSpeed > base.logicalAppliedSpeed);
    assert(close_to(base.appliedSpeed, 1.25F));
    commitCutsceneSpeedWritePlan(state, base);

    const auto stable = makeCutsceneSpeedWritePlan(state, base.appliedSpeed, 1.25);
    assert(stable.valid);
    assert(!stable.write);
    assert(stable.nativeSpeed == 1.0F);
    assert(close_to(stable.logicalAppliedSpeed, 1.25F));
    assert(stable.appliedSpeed == base.appliedSpeed);

    // A native fast-forward transition must compose with Lexeditor's base
    // multiplier rather than being replaced by it.
    const auto r2 = makeCutsceneSpeedWritePlan(state, 2.0F, 1.25);
    assert(r2.valid);
    assert(r2.write);
    assert(r2.nativeSpeed == 2.0F);
    assert(close_to(r2.logicalAppliedSpeed, 2.5F));
    assert(r2.appliedSpeed > r2.logicalAppliedSpeed);
    commitCutsceneSpeedWritePlan(state, r2);

    const auto r2Stable = makeCutsceneSpeedWritePlan(state, r2.appliedSpeed, 1.25);
    assert(r2Stable.valid);
    assert(!r2Stable.write);
    assert(r2Stable.nativeSpeed == 2.0F);

    const auto released = makeCutsceneSpeedWritePlan(state, 1.0F, 1.25);
    assert(released.valid);
    assert(released.write);
    assert(released.nativeSpeed == 1.0F);
    assert(close_to(released.logicalAppliedSpeed, 1.25F));

    // Regression: with a 1.5x user base, our ordinary-cutscene product is also
    // a plausible exact native R2 scalar. The one-ULP owned value must make a
    // later exact game write of 1.5 distinguishable and produce 2.25x rather
    // than being mistaken for our own unchanged write.
    CutsceneSpeedTrack collisionState;
    const auto collisionBase = makeCutsceneSpeedWritePlan(collisionState, 1.0F, 1.5);
    assert(collisionBase.valid);
    assert(close_to(collisionBase.logicalAppliedSpeed, 1.5F));
    assert(collisionBase.appliedSpeed != 1.5F);
    commitCutsceneSpeedWritePlan(collisionState, collisionBase);

    const auto collisionR2 = makeCutsceneSpeedWritePlan(collisionState, 1.5F, 1.5);
    assert(collisionR2.valid);
    assert(collisionR2.write);
    assert(collisionR2.nativeSpeed == 1.5F);
    assert(close_to(collisionR2.logicalAppliedSpeed, 2.25F));
    commitCutsceneSpeedWritePlan(collisionState, collisionR2);

    // Owned values are allowed above the native plausibility ceiling; otherwise
    // a valid high configured multiplier would work for one tick and then be
    // rejected as if it were a suspicious native game value.
    CutsceneSpeedTrack highState;
    const auto high = makeCutsceneSpeedWritePlan(highState, 4.0F, 8.0);
    assert(high.valid);
    assert(close_to(high.logicalAppliedSpeed, 32.0F));
    assert(high.appliedSpeed > 16.0F);
    commitCutsceneSpeedWritePlan(highState, high);
    const auto highStable = makeCutsceneSpeedWritePlan(highState, high.appliedSpeed, 8.0);
    assert(highStable.valid);
    assert(!highStable.write);
    assert(highStable.nativeSpeed == 4.0F);
    assert(close_to(highStable.logicalAppliedSpeed, 32.0F));

    // The inclusive 64x safety ceiling remains representable: ownership tagging
    // falls one ULP below the boundary rather than exceeding it.
    [[maybe_unused]] const float taggedMax = tagOwnedGameSpeed(kMaxPlausibleAppliedGameSpeed);
    assert(taggedMax > 0.0F);
    assert(taggedMax < kMaxPlausibleAppliedGameSpeed);

    assert(!makeCutsceneSpeedWritePlan({}, 0.0F, 1.25).valid);
    assert(!makeCutsceneSpeedWritePlan({}, -1.0F, 1.25).valid);
    assert(!makeCutsceneSpeedWritePlan({}, 1.0F, 1.0).valid);
    assert(!makeCutsceneSpeedWritePlan({}, 1.0F, 1000.0).valid);
    assert(!plausibleNativeGameSpeed(std::nanf("")));
    assert(!plausibleOwnedGameSpeed(std::nanf("")));

    return 0;
}

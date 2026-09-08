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
    assert(base.appliedSpeed == 1.25F);
    commitCutsceneSpeedWritePlan(state, base);

    const auto stable = makeCutsceneSpeedWritePlan(state, 1.25F, 1.25);
    assert(stable.valid);
    assert(!stable.write);
    assert(stable.nativeSpeed == 1.0F);
    assert(stable.appliedSpeed == 1.25F);

    // A native fast-forward transition must compose with Lexeditor's base
    // multiplier rather than being replaced by it.
    const auto r2 = makeCutsceneSpeedWritePlan(state, 2.0F, 1.25);
    assert(r2.valid);
    assert(r2.write);
    assert(r2.nativeSpeed == 2.0F);
    assert(r2.appliedSpeed == 2.5F);
    commitCutsceneSpeedWritePlan(state, r2);

    const auto r2Stable = makeCutsceneSpeedWritePlan(state, 2.5F, 1.25);
    assert(r2Stable.valid);
    assert(!r2Stable.write);
    assert(r2Stable.nativeSpeed == 2.0F);

    const auto released = makeCutsceneSpeedWritePlan(state, 1.0F, 1.25);
    assert(released.valid);
    assert(released.write);
    assert(released.nativeSpeed == 1.0F);
    assert(released.appliedSpeed == 1.25F);

    assert(!makeCutsceneSpeedWritePlan({}, 0.0F, 1.25).valid);
    assert(!makeCutsceneSpeedWritePlan({}, -1.0F, 1.25).valid);
    assert(!makeCutsceneSpeedWritePlan({}, 1.0F, 1.0).valid);
    assert(!makeCutsceneSpeedWritePlan({}, 1.0F, 1000.0).valid);
    assert(!plausibleNativeGameSpeed(std::nanf("")));

    return 0;
}

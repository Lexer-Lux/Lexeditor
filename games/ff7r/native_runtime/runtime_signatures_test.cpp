#include "RuntimeSignatures.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <vector>

using namespace lexeditor::ff7r;

int main() {
    std::vector<std::uint8_t> text(256, 0xCC);

    const std::size_t mapOffset = 19;
    for (std::size_t i = 0; i < kMapControlSignature.size(); ++i) {
        text[mapOffset + i] = kMapControlSignature[i];
    }
    const std::size_t inputOffset = 77;
    for (std::size_t i = 0; i < kRawInputRegistrationSignature.size(); ++i) {
        text[inputOffset + i] = kRawInputRegistrationSignature[i];
    }
    const std::size_t movementOffset = 143;
    for (std::size_t i = 0; i < kJoystickMovementSignature.size(); ++i) {
        text[movementOffset + i] = kJoystickMovementSignature[i];
    }

    const auto span = std::span<const std::uint8_t>(text.data(), text.size());
    const auto maps = findMapControl(span);
    const auto inputs = findRawInputRegistration(span);
    const auto movement = findJoystickMovement(span);
    assert(maps.size() == 1 && maps[0].offset == mapOffset);
    assert(inputs.size() == 1 && inputs[0].offset == inputOffset);
    assert(movement.size() == 1 && movement[0].offset == movementOffset);

    text[mapOffset + 3] ^= 0xFF;
    const auto damaged = std::span<const std::uint8_t>(text.data(), text.size());
    assert(findMapControl(damaged).empty());
    assert(findRawInputRegistration(damaged).size() == 1);
    assert(findJoystickMovement(damaged).size() == 1);

    std::vector<std::uint8_t> duplicates;
    duplicates.insert(duplicates.end(), kJoystickMovementSignature.begin(), kJoystickMovementSignature.end());
    duplicates.push_back(0x90);
    duplicates.insert(duplicates.end(), kJoystickMovementSignature.begin(), kJoystickMovementSignature.end());
    const auto duplicateSpan = std::span<const std::uint8_t>(duplicates.data(), duplicates.size());
    const auto duplicateMatches = findJoystickMovement(duplicateSpan);
    assert(duplicateMatches.size() == 2);
    assert(duplicateMatches[0].offset == 0);
    assert(duplicateMatches[1].offset == kJoystickMovementSignature.size() + 1);

    assert(findExactSignature(
        std::span<const std::uint8_t>(duplicates.data(), duplicates.size()),
        kJoystickMovementSignature,
        1).size() == 1);

    return 0;
}

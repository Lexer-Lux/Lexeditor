/* Lexeditor adapter for Crow's player protections. SPDX-License-Identifier: AGPL-3.0-only */
#pragma once
#include "GameData.h"
#include <cstddef>

/* Only the fields used by the imported guard; upstream PlayerInsStruct.h asserts
 * these offsets. Do not import the unrelated animation/rollback object model. */
struct PlayerProtectionChrCtrl { unsigned char data[0x104]; };
struct PlayerProtectionPlayerCtrl { PlayerProtectionChrCtrl chrCtrl; };
struct ChrIns {
    unsigned char prefix[0x68];
    PlayerProtectionPlayerCtrl *playerCtrl;
};
static_assert(offsetof(ChrIns, playerCtrl) == 0x68);
namespace Game { float *get_pc_position(); }
namespace PlayerProtection {
    void start();
    void validate();
    bool hosting_peers();
    bool is_invader(uint64_t id);
    void update_session(uint64_t lobby, uint64_t owner, uint64_t self,
                        const uint64_t *members, size_t count);
    void record_invader(const char *id);
}

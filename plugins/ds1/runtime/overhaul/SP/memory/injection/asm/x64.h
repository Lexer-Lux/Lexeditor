/* Minimal patch API used by the unmodified upstream anti-ban source.
 * SPDX-License-Identifier: AGPL-3.0-only */
#pragma once
#include <cstdint>
#include <cstddef>
namespace sp::mem {
bool patch_bytes(void *address, const void *bytes, size_t size);
namespace code::x64 {
void inject_jmp_14b(void *address, uint64_t *resume, size_t padding, void (*target)());
}
}

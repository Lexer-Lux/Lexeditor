/* Test-only System V to Windows x64 ABI bridge, not a game payload. */
#include <stdint.h>
typedef uintptr_t (__attribute__((ms_abi)) *win_fn)(void *, int);
uintptr_t invoke(void *address, void *actor, int delta) {
    return ((win_fn)address)(actor, delta);
}

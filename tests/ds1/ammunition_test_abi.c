/* Test-only Linux SysV <-> Windows-x64 adapter. No game code is executed. */
#include <stdint.h>
#define MS __attribute__((ms_abi))
typedef uint64_t (*sys_fn)(uint64_t,uint64_t,uint64_t,uint64_t);
typedef uint64_t (MS *win_fn)(uint64_t,uint64_t,uint64_t,uint64_t);
static sys_fn callbacks[16];
void set_callback(unsigned i, sys_fn fn) { if(i<16) callbacks[i]=fn; }
#define THUNK(n) uint64_t MS thunk##n(uint64_t a,uint64_t b,uint64_t c,uint64_t d) \
 { return callbacks[n](a,b,c,d); }
THUNK(0) THUNK(1) THUNK(2) THUNK(3) THUNK(4) THUNK(5) THUNK(6) THUNK(7)
THUNK(8) THUNK(9) THUNK(10) THUNK(11) THUNK(12) THUNK(13) THUNK(14) THUNK(15)
uint64_t invoke(void *fn,uint64_t a,uint64_t b,uint64_t c,uint64_t d) {
    return ((win_fn)fn)(a,b,c,d);
}

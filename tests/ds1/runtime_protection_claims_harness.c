#define LX_NO_DLLMAIN
#include "../../plugins/ds1/runtime/lexeditor_ds1_loader.c"
#include <assert.h>

int main(void)
{
    unsigned char patch[38] = "LXD1PAT";
    unsigned values[] = {1, 0x3000, 0x12345678, 1, KIND_HOOK, 0x1000, 1};
    memcpy(patch + 8, values, sizeof values);
    patch[36] = 1; patch[37] = 2;
    char message[256] = "";
    assert(lx_reserve_runtime_range(0x1000, 15));
    assert(!lx_check_claims(patch, sizeof patch, NULL, message, sizeof message, 0, "Example Mod"));
    assert(strstr(message, "Conflicts"));
    assert(strstr(message, "loader multiplayer protection") && strstr(message, "1000-1000"));
    unsigned adjacent = 0x100f;
    memcpy(patch + 28, &adjacent, 4);
    assert(lx_check_claims(patch, sizeof patch, NULL, message, sizeof message, 0, "Example Mod"));
    unsigned before = lx_claim_count;
    assert(lx_reserve_runtime_range(0x1005, 2));
    assert(lx_claim_count == before);
    assert(!lx_reserve_runtime_range(UINT_MAX, 2));
    assert(lx_check_claims(patch, sizeof patch, NULL, message, sizeof message, 1, "Example Mod"));
    assert(!lx_check_claims(patch, sizeof patch, NULL, message, sizeof message, 0, "Other Mod"));
    assert(strstr(message, "Example Mod") && strstr(message, "100F-100F"));
    puts("protection ranges passed");
    return 0;
}

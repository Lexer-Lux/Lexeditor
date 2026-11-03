/* Actual loader against synthetic RX code, with competing mod workers.
 * Report callbacks require another thread to run: logging while suspended
 * therefore fails deterministically instead of depending on a CRT deadlock. */
#define LX_NO_DLLMAIN
#include "../../plugins/ds1/runtime/lexeditor_ds1_loader.c"

#define MODS 12
static HANDLE request, acknowledged;
static SRWLOCK log_lock = SRWLOCK_INIT;
static volatile LONG log_failures;

static DWORD WINAPI logger_peer(LPVOID unused)
{
    (void)unused;
    for (;;) {
        WaitForSingleObject(request, INFINITE);
        SetEvent(acknowledged);
    }
}

static void checked_report(const char *text)
{
    (void)text;
    AcquireSRWLockExclusive(&log_lock);
    ResetEvent(acknowledged);
    SetEvent(request);
    if (WaitForSingleObject(acknowledged, 1000) != WAIT_OBJECT_0)
        InterlockedIncrement(&log_failures);
    ReleaseSRWLockExclusive(&log_lock);
}

static int ready(unsigned char *image)
{
    for (unsigned index = 0; index < MODS * 2; ++index)
        if (image[0x1000 + index * 16 + 1] != 42) return 0;
    return 1;
}

int main(void)
{
    unsigned char *image = VirtualAlloc(NULL, 0x3000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!image) return 2;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    dos->e_magic = IMAGE_DOS_SIGNATURE;
    dos->e_lfanew = 0x40;
    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(image + 0x40);
    nt->Signature = IMAGE_NT_SIGNATURE;
    nt->OptionalHeader.SizeOfImage = 0x3000;
    nt->FileHeader.TimeDateStamp = 123;
    unsigned char original[] = {0xB8,1,0,0,0,0xC3};
    for (unsigned index = 0; index < MODS * 2; ++index)
        memcpy(image + 0x1000 + index * 16, original, sizeof original);
    DWORD old;
    VirtualProtect(image + 0x1000, 0x1000, PAGE_EXECUTE_READ, &old);
    request = CreateEventW(NULL, FALSE, FALSE, NULL);
    acknowledged = CreateEventW(NULL, FALSE, FALSE, NULL);
    HANDLE peer = CreateThread(NULL, 0, logger_peer, NULL, 0, NULL);
    if (!request || !acknowledged || !peer) return 3;
    CloseHandle(peer);
    lx_report = checked_report;
    for (unsigned mod = 0; mod < MODS; ++mod) {
        unsigned char data[84] = {0};
        memcpy(data, MAGIC, 8);
        unsigned header[] = {1,0x3000,123,mod ? 3 : 2};
        memcpy(data + 8, header, sizeof header);
        for (unsigned hook = 0; hook < 2; ++hook) {
            unsigned offset = 24 + hook * 24;
            unsigned record[] = {KIND_HOOK,0x1000 + (mod*2+hook)*16,6};
            memcpy(data + offset, record, sizeof record);
            memcpy(data + offset + 12, original, 6);
            memcpy(data + offset + 18, original, 6);
            data[offset + 19] = 42;
        }
        unsigned delay[] = {KIND_DELAY,0,30};
        memcpy(data + 72, delay, sizeof delay);
        char message[256];
        if (!lx_apply(image, data, mod ? sizeof data : 72, message, sizeof message)) {
            puts(message);
            return 4;
        }
        MEMORY_BASIC_INFORMATION info;
        VirtualQuery(image + 0x1000, &info, sizeof info);
        if (info.Protect != PAGE_EXECUTE_READ) return 5;
    }
    DWORD deadline = GetTickCount() + 5000;
    while (!ready(image) && GetTickCount() < deadline) Sleep(10);
    if (!ready(image)) return 6;
    /* The first module is immediate; subsequent modules keep their hooks. */
    AcquireSRWLockExclusive(&hook_write_lock);
    VirtualProtect(image + 0x1000, 0x1000, PAGE_EXECUTE_READWRITE, &old);
    for (unsigned index = 2; index < MODS * 2; ++index)
        memcpy(image + 0x1000 + index * 16, original, sizeof original);
    VirtualProtect(image + 0x1000, 0x1000, old, &old);
    ReleaseSRWLockExclusive(&hook_write_lock);
    deadline = GetTickCount() + 5000;
    while (!ready(image) && GetTickCount() < deadline) Sleep(10);
    if (!ready(image)) return 7;
    /* Let repair logs finish their handshake too. */
    Sleep(100);
    MEMORY_BASIC_INFORMATION info;
    VirtualQuery(image + 0x1000, &info, sizeof info);
    if (info.Protect != PAGE_EXECUTE_READ || log_failures) return 8;
    puts("installed=24 repaired=22 protection=RX responsive=1");
    return 0;
}

/*
 * Runs the DS1 loader's lx_apply against a synthetic image in this process:
 * DOS and PE headers, and a function at 0x1000 that returns 1. The patch
 * file (argv[1], written by test_ds1_runtime_loader.py) redirects that
 * function into code placed past the image, which returns 42. No game code.
 *
 * Prints: applied=<0|1> message=<...> result=<function's return>
 *         unwind=<0|1>
 * With argv[3], the harness then puts the function's original bytes back, as
 * the game's own guard does, waits argv[3] ms and adds: repaired=<return>
 */
#define LX_NO_DLLMAIN
#include <stdlib.h>
#include "../../plugins/ds1/runtime/lexeditor_ds1_loader.c"

#define IMAGE_SIZE 0x3000u
#define TIMESTAMP 0x1234ABCDu

int main(int argc, char **argv)
{
    if (argc < 2)
        return 2;
    FILE *file = fopen(argv[1], "rb");
    if (!file)
        return 2;
    static unsigned char data[1 << 20];
    size_t size = fread(data, 1, sizeof data, file);
    fclose(file);

    /* 64 KB aligned, like any image; the 64 KB after it stay free. */
    unsigned char *image = (unsigned char *)VirtualAlloc(NULL, 0x20000, MEM_RESERVE, PAGE_NOACCESS);
    if (!image)
        return 3;
    VirtualFree(image, 0, MEM_RELEASE);
    image = (unsigned char *)VirtualAlloc(image, IMAGE_SIZE, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!image)
        return 3;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    dos->e_magic = IMAGE_DOS_SIGNATURE;
    dos->e_lfanew = 0x40;
    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(image + 0x40);
    nt->Signature = IMAGE_NT_SIGNATURE;
    nt->FileHeader.TimeDateStamp = TIMESTAMP;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR64_MAGIC;
    nt->OptionalHeader.SizeOfImage = IMAGE_SIZE;
    static const unsigned char returns_one[] = {0xB8, 0x01, 0x00, 0x00, 0x00, 0xC3};
    memcpy(image + 0x1000, returns_one, sizeof returns_one);
    DWORD old;
    VirtualProtect(image + 0x1000, 0x1000, PAGE_EXECUTE_READ, &old);

    char message[256] = "";
    int applied = lx_apply(image, data, size, message, sizeof message);
    /* A deferred patch writes its hooks from a thread: give it time. */
    if (argc > 2)
        Sleep((DWORD)atoi(argv[2]));
    int (*function)(void) = (int (*)(void))(image + 0x1000);
    int result = function();
    DWORD64 base = 0;
    int unwind = RtlLookupFunctionEntry((DWORD64)(ULONG_PTR)(image + 0x10000), &base, NULL) != NULL;
    printf("applied=%d message=%s result=%d\nunwind=%d\n", applied, message, result, unwind);
    if (argc > 3) {
        VirtualProtect(image + 0x1000, 0x1000, PAGE_EXECUTE_READWRITE, &old);
        memcpy(image + 0x1000, returns_one, sizeof returns_one);
        VirtualProtect(image + 0x1000, 0x1000, PAGE_EXECUTE_READ, &old);
        FlushInstructionCache(GetCurrentProcess(), image + 0x1000, sizeof returns_one);
        Sleep((DWORD)atoi(argv[3]));
        printf("repaired=%d\n", function());
    }
    return 0;
}

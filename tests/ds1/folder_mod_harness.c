/* The actual folder scanner/linker against synthetic executable memory.
 * No game, native windows, account, save, Steam or Documents writes. */
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
static unsigned char *test_image;
static wchar_t test_folder[MAX_PATH * 2];
static HMODULE test_module(const wchar_t *name) {(void)name; return (HMODULE)test_image;}
#define GetModuleHandleW test_module
#define LX_NO_DLLMAIN
#define LX_MOD_TEST
#define LX_ONLINE_BUILD
#include "../../plugins/ds1/runtime/lexeditor_ds1_loader.c"

static void folder_file(wchar_t *path, size_t size, const wchar_t *name)
{
    swprintf(path, size, L"%ls\\%ls", test_folder, name);
}
static void write_log(const char *text) {puts(text);}

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 3) return 2;
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, argv[1], -1, test_folder, MAX_PATH*2);
    test_image = (unsigned char *)VirtualAlloc(NULL, 0x2000000, MEM_RESERVE, PAGE_NOACCESS);
    if (!test_image) return 3;
    VirtualFree(test_image, 0, MEM_RELEASE);
    test_image = (unsigned char *)VirtualAlloc(test_image, 0x3000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!test_image) return 3;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)test_image;
    dos->e_magic = IMAGE_DOS_SIGNATURE; dos->e_lfanew = 0x40;
    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(test_image+0x40);
    nt->Signature = IMAGE_NT_SIGNATURE;
    nt->FileHeader.TimeDateStamp = 0x1234abcd;
    nt->OptionalHeader.SizeOfImage = 0x3000;
    const unsigned char original[] = {0xb8,1,0,0,0,0xc3};
    memcpy(test_image+0x1000, original, 6);
    memcpy(test_image+0x1100, original, 6);
    memcpy(test_image+0x1200, original, 6);
    test_image[0x1201]=3;
    DWORD old;
    VirtualProtect(test_image+0x1000, 0x1000, PAGE_EXECUTE_READ, &old);
    if(argc==3){lx_data_ready=lx_prepare_data();printf("prepared=%d\n",lx_data_ready);}
    lx_load_mod_folders();
    int (*first)(void) = (int (*)(void))(test_image+0x1000);
    int (*second)(void) = (int (*)(void))(test_image+0x1100);
    printf("results=%d,%d\n", first(), second());
    DWORD64 base;
    unsigned char *first_code=test_image+0x1005+(int32_t)read32(test_image+0x1001);
    unsigned char *second_code=test_image+0x1105+(int32_t)read32(test_image+0x1101);
    printf("unwind=%d,%d\n",RtlLookupFunctionEntry((DWORD64)(uintptr_t)first_code,&base,NULL)!=NULL,
           RtlLookupFunctionEntry((DWORD64)(uintptr_t)second_code,&base,NULL)!=NULL);
    return 0;
}

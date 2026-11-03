/* No game: validate the real proxy initialization against a generated DLL. */
#include <windows.h>
#include <stdio.h>
static wchar_t test_folder[MAX_PATH * 2];
static void folder_file(wchar_t *path, size_t capacity, const wchar_t *name)
{
    swprintf(path,capacity,L"%ls\\%ls",test_folder,name);
}
static void write_log(const char *message) { puts(message); }
#include "../../plugins/ds1/runtime/lexeditor_ds1_chain.c"

int wmain(int argc, wchar_t **argv)
{
    if (argc != 3) return 2;
    if (wcslen(argv[1]) >= MAX_PATH*2) return 2;
    wcscpy(test_folder,argv[1]);
    lx_chain_start();
    lx_chain_start();  /* process attachment happens once */
    if (!lx_system_create || !lx_input_create) return 3;
    if (!wcscmp(argv[2],L"chain")) {
        if (lx_input_create == lx_system_create) return 4;
        if (DirectInput8Create(NULL,0,NULL,NULL,NULL) != 42) return 4;
        if (DirectInput8Create(NULL,0,NULL,NULL,NULL) != 42) return 5;
        puts("chain=42");
    } else {
        if (lx_input_create != lx_system_create) return 6;
        puts("system=1");
    }
    return 0;
}

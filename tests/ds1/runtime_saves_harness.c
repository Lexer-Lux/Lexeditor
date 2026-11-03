/* Headless synthetic-save fixture; never loads the game or touches real saves. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "../../plugins/ds1/runtime/lexeditor_ds1_loader.h"

void lx_debug_log(const char *text) { fprintf(stderr, "%s\n", text); }

static int access_save(const wchar_t *mode, const wchar_t *path)
{
    HANDLE file = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ,
                              NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return 4;
    DWORD count;
    char before[64] = {0};
    if (!ReadFile(file, before, sizeof before - 1, &count, NULL)) return 5;
    printf("read=%s\n", before);
    if (wcscmp(mode, L"read") == 0 || wcscmp(mode, L"plain") == 0) { CloseHandle(file); return 0; }
    SetFilePointer(file, 0, NULL, FILE_BEGIN);
    if (!WriteFile(file, "modded-progress", 15, &count, NULL) || !SetEndOfFile(file)) return 6;
    CloseHandle(file);
    return 0;
}

static DWORD WINAPI small_stack_save(void *path) { return access_save(L"write", path); }

int wmain(int argc, wchar_t **argv)
{
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    if (argc != 3) return 2;
    if (wcscmp(argv[1], L"plain") && !lx_save_install((unsigned char *)GetModuleHandleW(NULL))) return 3;
    if (wcscmp(argv[1], L"thread-write") == 0) {
        HANDLE thread = CreateThread(NULL, 64 * 1024, small_stack_save, argv[2], STACK_SIZE_PARAM_IS_A_RESERVATION, NULL);
        if (!thread) return 8;
        WaitForSingleObject(thread, INFINITE);
        DWORD result;
        GetExitCodeThread(thread, &result);
        CloseHandle(thread);
        return (int)result;
    }
    return access_save(argv[1], argv[2]);
}

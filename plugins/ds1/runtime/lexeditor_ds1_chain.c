/* A player may preserve another dinput8 proxy as dinput8.chain.dll before
 * installing ours. Load it once, outside DllMain, before the game's entry
 * point; its input export forwards the game's calls when provided.
 * Native driver justification: loading another Windows DLL is file I/O. */
#include <windows.h>
#include <stdio.h>

typedef HRESULT(WINAPI *create_t)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);
__declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);

static INIT_ONCE lx_input_once = INIT_ONCE_STATIC_INIT;
static create_t lx_input_create, lx_system_create;
static volatile LONG lx_input_owner;

static BOOL CALLBACK lx_initialize_input(PINIT_ONCE once, PVOID parameter, PVOID *context)
{
    (void)once; (void)parameter; (void)context;
    InterlockedExchange(&lx_input_owner, (LONG)GetCurrentThreadId());
    wchar_t system_path[MAX_PATH], chain[MAX_PATH * 2];
    UINT length = GetSystemDirectoryW(system_path, MAX_PATH);
    if (length && length < MAX_PATH - 14) {
        wcscat(system_path, L"\\dinput8.dll");
        HMODULE system = LoadLibraryW(system_path);
        lx_system_create = system ? (create_t)GetProcAddress(system, "DirectInput8Create") : NULL;
    }
    lx_input_create = lx_system_create;
    folder_file(chain, MAX_PATH * 2, L"dinput8.chain.dll");
    DWORD attributes = GetFileAttributesW(chain);
    if (attributes != INVALID_FILE_ATTRIBUTES) {
        WIN32_FILE_ATTRIBUTE_DATA info;
        if ((attributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) ||
            !GetFileAttributesExW(chain, GetFileExInfoStandard, &info) ||
            info.nFileSizeHigh || !info.nFileSizeLow || info.nFileSizeLow > 32u * 1024u * 1024u) {
            write_log("dinput8.chain.dll is not a regular loader file within the 32 MiB limit; using system input");
        } else {
            /* Resolve the proxy's own dependencies relative to its full path.
             * Never search the working directory for the chained DLL itself. */
            DWORD old_mode = 0;
            BOOL changed_mode = SetThreadErrorMode(SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX, &old_mode);
            HMODULE chained = LoadLibraryExW(chain, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
            DWORD load_error = GetLastError();
            if (changed_mode) SetThreadErrorMode(old_mode, NULL);
            if (!chained) {
                char text[160];
                snprintf(text, sizeof text, "Could not load dinput8.chain.dll (Windows error %lu); using system input",
                         (unsigned long)load_error);
                write_log(text);
            } else {
                create_t create = (create_t)GetProcAddress(chained, "DirectInput8Create");
                if (create && create != DirectInput8Create) {
                    lx_input_create = create;
                    write_log("Loaded dinput8.chain.dll; forwarding its input calls");
                } else {
                    /* Some ASI loaders need only their process-attach entry.
                     * Keep the library alive, while system input handles calls. */
                    write_log("Loaded dinput8.chain.dll without an input export; using system input");
                }
            }
        }
    }
    InterlockedExchange(&lx_input_owner, 0);
    return TRUE;
}

static void lx_chain_start(void)
{
    InitOnceExecuteOnce(&lx_input_once, lx_initialize_input, NULL, NULL);
}

__declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE instance, DWORD version, REFIID iid, LPVOID *out, LPUNKNOWN outer)
{
    /* A proxy can call the game's input import during its own attach. Do
     * not recursively wait for the InitOnce currently loading that proxy. */
    if ((DWORD)InterlockedCompareExchange(&lx_input_owner, 0, 0) == GetCurrentThreadId())
        return lx_system_create ? lx_system_create(instance, version, iid, out, outer) : E_FAIL;
    lx_chain_start();
    return lx_input_create ? lx_input_create(instance, version, iid, out, outer) : E_FAIL;
}

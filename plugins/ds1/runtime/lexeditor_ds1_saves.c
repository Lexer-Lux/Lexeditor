/* Separate modded save, with one original and one latest pre-launch backup.
 * SPDX-License-Identifier: AGPL-3.0-only
 * Fixed .sl2 name matches Steam Auto-Cloud; backups deliberately do not.
 * Native file I/O is required; never writes or converts the vanilla save. */
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#include "lexeditor_ds1_loader.h"

#define SAVE_LIMIT (16u * 1024u * 1024u)
#define SAVE_PATH 32768
typedef HANDLE (WINAPI *create_file_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static create_file_t real_create_file;
static SRWLOCK save_lock = SRWLOCK_INIT;
static wchar_t prepared_path[SAVE_PATH];

static int regular(const wchar_t *path, int optional)
{
    DWORD attrs = GetFileAttributesW(path);
    if (attrs == INVALID_FILE_ATTRIBUTES)
        return optional && GetLastError() == ERROR_FILE_NOT_FOUND;
    if (attrs & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT))
        return 0;
    HANDLE file = real_create_file(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
                                   FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    BY_HANDLE_FILE_INFORMATION info;
    int ok = file != INVALID_HANDLE_VALUE && GetFileInformationByHandle(file, &info) &&
             !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
             info.nNumberOfLinks == 1 && info.nFileSizeHigh == 0 && info.nFileSizeLow <= SAVE_LIMIT;
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    return ok;
}

/* Copy through a fixed staging file then rename, never truncate a good backup
 * or a Cloud-restored save when a write fails. At most three backup files. */
static int snapshot(const wchar_t *source, const wchar_t *destination, const wchar_t *pending, int replace)
{
    if (!regular(source, 0) || !regular(destination, 1) || !regular(pending, 1))
        return 0;
    if (!CopyFileW(source, pending, FALSE))
        return 0;
    if (!MoveFileExW(pending, destination, MOVEFILE_WRITE_THROUGH | (replace ? MOVEFILE_REPLACE_EXISTING : 0))) {
        DWORD error = GetLastError();
        DeleteFileW(pending);
        /* A different launch may have created the modded save first. */
        return !replace && (error == ERROR_ALREADY_EXISTS || error == ERROR_FILE_EXISTS) && regular(destination, 0);
    }
    return 1;
}

/* Returns 0 on failure, 1 when unrelated, 2 when redirected. Exposed to the
 * native harness too, so tests exercise the actual save routing and I/O. */
int lx_save_path(const wchar_t *input, wchar_t *output, size_t capacity)
{
    if (!input || capacity > SAVE_PATH || wcslen(input) >= capacity)
        return 0;
    const wchar_t *name = wcsrchr(input, L'\\');
    const wchar_t *slash = wcsrchr(input, L'/');
    if (!name || (slash && slash > name)) name = slash;
    name = name ? name + 1 : input;
    if (_wcsicmp(name, L"DRAKS0005.sl2") != 0)
        return 1;
    size_t prefix = (size_t)(name - input);
    if (!prefix || prefix + 64 >= capacity)
        return 0; /* The game supplies a full account path, never a bare name. */
    wmemcpy(output, input, prefix);
    wcscpy(output + prefix, L"DRAKS0005.lexeditor.sl2");
    /* Game file-worker threads may have small stacks. Allocate only the path
     * lengths needed, never four Windows maximum-length buffers on a stack. */
    size_t path_chars = prefix + 64;
    wchar_t *storage = HeapAlloc(GetProcessHeap(), 0, path_chars * 3 * sizeof(wchar_t));
    if (!storage) return 0;
    wchar_t *original = storage, *latest = storage + path_chars, *pending = storage + path_chars * 2;
    wcscpy(original, output); wcscpy(original + prefix, L"DRAKS0005.lexeditor.original.bak");
    wcscpy(latest, output); wcscpy(latest + prefix, L"DRAKS0005.lexeditor.latest.bak");
    wcscpy(pending, output); wcscpy(pending + prefix, L"DRAKS0005.lexeditor.pending.bak");

    AcquireSRWLockExclusive(&save_lock);
    int ok = 1;
    if (_wcsicmp(prepared_path, output) != 0) {
        /* One Steam account per game process; no unbounded path cache. */
        if (prepared_path[0]) { ok = 0; goto done; }
        if (!regular(input, 1) || !regular(output, 1)) { ok = 0; goto done; }
        DWORD attrs = GetFileAttributesW(output);
        if (attrs == INVALID_FILE_ATTRIBUTES && GetFileAttributesW(input) != INVALID_FILE_ATTRIBUTES) {
            if (!snapshot(input, output, pending, 0)) { ok = 0; goto done; }
        }
        if (GetFileAttributesW(output) != INVALID_FILE_ATTRIBUTES) {
            if (!regular(original, 1) ||
                (GetFileAttributesW(original) == INVALID_FILE_ATTRIBUTES &&
                 !snapshot(output, original, pending, 0)) ||
                !snapshot(output, latest, pending, 1)) { ok = 0; goto done; }
        }
        wcscpy(prepared_path, output);
    }
    /* Recheck on every open: never follow an externally replaced save link. */
    if (!regular(output, 1)) ok = 0;
done:
    ReleaseSRWLockExclusive(&save_lock);
    HeapFree(GetProcessHeap(), 0, storage);
    return ok ? 2 : 0;
}

static HANDLE WINAPI save_create_file(LPCWSTR name, DWORD access, DWORD sharing,
                                      LPSECURITY_ATTRIBUTES security, DWORD disposition,
                                      DWORD flags, HANDLE template_file)
{
    size_t capacity = name ? wcslen(name) + 64 : 0;
    if (capacity > SAVE_PATH) capacity = SAVE_PATH;
    wchar_t *path = capacity ? HeapAlloc(GetProcessHeap(), 0, capacity * sizeof(wchar_t)) : NULL;
    int result = path ? lx_save_path(name, path, capacity) : 0;
    if (!result) {
        if (path) HeapFree(GetProcessHeap(), 0, path);
        lx_debug_log("Modded save could not be prepared; stopped before opening the vanilla save");
        TerminateProcess(GetCurrentProcess(), 0x4c58);
        SetLastError(ERROR_ACCESS_DENIED);
        return INVALID_HANDLE_VALUE;
    }
    HANDLE file = real_create_file(result == 2 ? path : name, access, sharing, security, disposition, flags, template_file);
    DWORD error = GetLastError();
    HeapFree(GetProcessHeap(), 0, path);
    SetLastError(error);
    return file;
}

int lx_save_install(unsigned char *image)
{
    /* Resolve the implementation, not an import thunk that we might redirect
     * when this module is compiled into the native test executable. */
    real_create_file = (create_file_t)GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "CreateFileW");
    if (!real_create_file) return 0;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    if (!image || dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(image + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC)
        return 0;
    DWORD rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return 0;
    int found = 0;
    for (IMAGE_IMPORT_DESCRIPTOR *entry = (IMAGE_IMPORT_DESCRIPTOR *)(image + rva); entry->Name; ++entry) {
        if (!entry->OriginalFirstThunk) continue;
        IMAGE_THUNK_DATA64 *names = (IMAGE_THUNK_DATA64 *)(image + entry->OriginalFirstThunk);
        IMAGE_THUNK_DATA64 *slots = (IMAGE_THUNK_DATA64 *)(image + entry->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL64(names->u1.Ordinal)) continue;
            IMAGE_IMPORT_BY_NAME *import = (IMAGE_IMPORT_BY_NAME *)(image + names->u1.AddressOfData);
            if (strcmp((const char *)import->Name, "CreateFileW") != 0) continue;
            DWORD old, ignored;
            if (!VirtualProtect(&slots->u1.Function, sizeof slots->u1.Function, PAGE_READWRITE, &old)) return 0;
            slots->u1.Function = (ULONGLONG)(uintptr_t)save_create_file;
            if (!VirtualProtect(&slots->u1.Function, sizeof slots->u1.Function, old, &ignored)) return 0;
            ++found;
        }
    }
    return found > 0;
}

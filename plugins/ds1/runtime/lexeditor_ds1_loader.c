/*
 * Lexeditor's Dark Souls Remastered loader, installed as dinput8.dll.
 *
 * The game imports DINPUT8.dll, so Windows loads this file from the game
 * folder before the game's own code runs. It reads lexeditor-ds1-patch.bin
 * (written by Lexeditor's Apply, see plugins/ds1/exe_patches.py) and makes
 * the tweaks' changes in memory. DarkSoulsRemastered.exe on disk is never
 * modified, so a crashed game that Windows keeps listed can no longer block
 * Apply or Restore, and removing two files restores the game.
 *
 * A native loader rather than a Hext patch: DS1 has no Hext host, and the
 * patches must be read from a file before the game starts (AGENTS.md: file
 * I/O). Every check happens before the first change: the image must be the
 * build the patch was made for, and every hook's original bytes must match.
 * If anything does not, nothing is changed and the game runs as it ships;
 * lexeditor-ds1-patch.log says why.
 *
 * DirectInput8Create, the one function the game imports from dinput8.dll,
 * is forwarded to the system's own dinput8.dll.
 */
#include <windows.h>
#include <string.h>
#include <stdio.h>
#include "lexeditor_ds1_loader.h"

#define MAGIC "LXD1PAT"
#define VERSION 1
#define KIND_HOOK 1
#define KIND_BLOCK 2
#define KIND_FUNCTIONS 3
#define KIND_WRITABLE 4
#define MAX_PATCH (16u * 1024u * 1024u)
#define MAX_RECORDS 4096u

typedef struct {
    unsigned kind, rva, length;
    const unsigned char *payload;
} record_t;

static unsigned read32(const unsigned char *at)
{
    return (unsigned)at[0] | ((unsigned)at[1] << 8) | ((unsigned)at[2] << 16) | ((unsigned)at[3] << 24);
}

static int fail(char *message, size_t capacity, const char *text)
{
    if (message && capacity) {
        strncpy(message, text, capacity - 1);
        message[capacity - 1] = 0;
    }
    return 0;
}

/* Is [address, address+size) committed and writable already? */
static int writable(unsigned char *address, size_t size)
{
    while (size) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(address, &info, sizeof info) || info.State != MEM_COMMIT)
            return 0;
        DWORD protect = info.Protect & 0xFF;
        if (protect != PAGE_READWRITE && protect != PAGE_EXECUTE_READWRITE && protect != PAGE_WRITECOPY &&
            protect != PAGE_EXECUTE_WRITECOPY)
            return 0;
        size_t span = (size_t)((unsigned char *)info.BaseAddress + info.RegionSize - address);
        if (span >= size)
            break;
        address += span;
        size -= span;
    }
    return 1;
}

static void restore_protections(unsigned char *image, const record_t *records, const DWORD *protections, unsigned upto)
{
    for (unsigned index = 0; index < upto; ++index) {
        DWORD ignored;
        if (records[index].kind == KIND_HOOK && protections[index])
            VirtualProtect(image + records[index].rva, records[index].length, protections[index], &ignored);
    }
}

static int apply_records(unsigned char *image, unsigned image_size, const unsigned char *data, size_t size,
                         unsigned count, record_t *records, DWORD *protections, char *message, size_t capacity);

int lx_apply(unsigned char *image, const unsigned char *data, size_t size, char *message, size_t capacity)
{
    if (size < 24 || memcmp(data, MAGIC, 8) != 0)
        return fail(message, capacity, "lexeditor-ds1-patch.bin is not a Lexeditor patch");
    if (read32(data + 8) != VERSION)
        return fail(message, capacity, "lexeditor-ds1-patch.bin is from another Lexeditor version");
    unsigned image_size = read32(data + 12), timestamp = read32(data + 16), count = read32(data + 20);
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(image + dos->e_lfanew);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->OptionalHeader.SizeOfImage != image_size || nt->FileHeader.TimeDateStamp != timestamp)
        return fail(message, capacity, "The running game is not the build these patches were made for");
    if (count > MAX_RECORDS)
        return fail(message, capacity, "lexeditor-ds1-patch.bin is damaged");

    record_t *records = (record_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (count ? count : 1) * sizeof *records);
    DWORD *protections = (DWORD *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (count ? count : 1) * sizeof *protections);
    int result = 0;
    if (!records || !protections) {
        fail(message, capacity, "Out of memory reading the patches");
        goto done;
    }
    result = apply_records(image, image_size, data, size, count, records, protections, message, capacity);
done:
    if (records)
        HeapFree(GetProcessHeap(), 0, records);
    if (protections)
        HeapFree(GetProcessHeap(), 0, protections);
    return result;
}

static int apply_records(unsigned char *image, unsigned image_size, const unsigned char *data, size_t size,
                         unsigned count, record_t *records, DWORD *protections, char *message, size_t capacity)
{
    size_t at = 24;
    for (unsigned index = 0; index < count; ++index) {
        if (at + 12 > size)
            return fail(message, capacity, "lexeditor-ds1-patch.bin is damaged");
        record_t *row = &records[index];
        row->kind = read32(data + at);
        row->rva = read32(data + at + 4);
        row->length = read32(data + at + 8);
        at += 12;
        unsigned long long payload = row->kind == KIND_HOOK ? 2ull * row->length
            : row->kind == KIND_BLOCK ? row->length
            : row->kind == KIND_FUNCTIONS ? 12ull * row->length
            : row->kind == KIND_WRITABLE ? 0 : ~0ull;
        if (payload == ~0ull || at + payload > size)
            return fail(message, capacity, "lexeditor-ds1-patch.bin is damaged");
        row->payload = data + at;
        at += (size_t)payload;
        unsigned long long end = (unsigned long long)row->rva + row->length;
        if ((row->kind == KIND_HOOK || row->kind == KIND_WRITABLE) && (row->length == 0 || end > image_size))
            return fail(message, capacity, "A patch lies outside the game's image");
        if (row->kind == KIND_BLOCK && (row->rva < image_size || row->rva % 0x1000 || row->length == 0))
            return fail(message, capacity, "Patch code must lie past the game's image");
    }
    if (at != size)
        return fail(message, capacity, "lexeditor-ds1-patch.bin is damaged");

    /* Every check before the first change. */
    for (unsigned index = 0; index < count; ++index) {
        record_t *row = &records[index];
        if (row->kind == KIND_HOOK && memcmp(image + row->rva, row->payload, row->length) != 0) {
            char text[160];
            snprintf(text, sizeof text, "The game's code at %08X is not what the patches expect; nothing was changed", row->rva);
            return fail(message, capacity, text);
        }
        if (row->kind == KIND_WRITABLE && !writable(image + row->rva, row->length))
            return fail(message, capacity, "Memory a patch needs is not writable; nothing was changed");
    }
    /* Every hook made writable before any is written: a refusal half way
     * would otherwise leave some hooks in and others out. */
    for (unsigned index = 0; index < count; ++index) {
        record_t *row = &records[index];
        if (row->kind != KIND_HOOK)
            continue;
        if (!VirtualProtect(image + row->rva, row->length, PAGE_EXECUTE_READWRITE, &protections[index])) {
            restore_protections(image, records, protections, index);
            return fail(message, capacity, "Windows refused to let a hook be written; nothing was changed");
        }
    }

    /* Code past the image, at the address its relocations were made for. */
    for (unsigned index = 0; index < count; ++index) {
        record_t *row = &records[index];
        if (row->kind != KIND_BLOCK)
            continue;
        unsigned char *want = image + row->rva;
        void *got = VirtualAlloc(want, row->length, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (got != want) {
            if (got)
                VirtualFree(got, 0, MEM_RELEASE);
            restore_protections(image, records, protections, count);
            return fail(message, capacity, "The address the patch code needs is in use; nothing was changed");
        }
        memcpy(want, row->payload, row->length);
        DWORD old;
        VirtualProtect(want, row->length, PAGE_EXECUTE_READ, &old);
        FlushInstructionCache(GetCurrentProcess(), want, row->length);
    }
    for (unsigned index = 0; index < count; ++index) {
        record_t *row = &records[index];
        if (row->kind != KIND_FUNCTIONS || !row->length)
            continue;
        /* The system keeps this table for the life of the process. */
        RUNTIME_FUNCTION *table = (RUNTIME_FUNCTION *)HeapAlloc(GetProcessHeap(), 0, (size_t)row->length * sizeof *table);
        if (!table) {
            /* The code pages stay allocated but unused: no hook points at them. */
            restore_protections(image, records, protections, count);
            return fail(message, capacity, "Out of memory registering patch functions; nothing was changed");
        }
        for (unsigned item = 0; item < row->length; ++item) {
            table[item].BeginAddress = read32(row->payload + item * 12);
            table[item].EndAddress = read32(row->payload + item * 12 + 4);
            table[item].UnwindData = read32(row->payload + item * 12 + 8);
        }
        if (!RtlAddFunctionTable(table, row->length, (DWORD64)(ULONG_PTR)image)) {
            restore_protections(image, records, protections, count);
            return fail(message, capacity, "Windows refused the patch functions' unwind table; nothing was changed");
        }
    }
    /* Nothing below can fail. */
    for (unsigned index = 0; index < count; ++index) {
        record_t *row = &records[index];
        if (row->kind != KIND_HOOK)
            continue;
        memcpy(image + row->rva, row->payload + row->length, row->length);
        FlushInstructionCache(GetCurrentProcess(), image + row->rva, row->length);
    }
    restore_protections(image, records, protections, count);
    snprintf(message, capacity, "Applied %u patch records", count);
    return 1;
}

#ifndef LX_NO_DLLMAIN
static void folder_file(wchar_t *path, size_t capacity, const wchar_t *name)
{
    DWORD length = GetModuleFileNameW(NULL, path, (DWORD)capacity);
    while (length && path[length - 1] != L'\\')
        --length;
    path[length] = 0;
    wcsncat(path, name, capacity - wcslen(path) - 1);
}

static void write_log(const char *text)
{
    wchar_t path[MAX_PATH * 2];
    folder_file(path, MAX_PATH * 2, L"lexeditor-ds1-patch.log");
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE)
        return;
    DWORD written;
    WriteFile(file, text, (DWORD)strlen(text), &written, NULL);
    CloseHandle(file);
}

static void apply_from_file(void)
{
    wchar_t path[MAX_PATH * 2];
    folder_file(path, MAX_PATH * 2, L"lexeditor-ds1-patch.bin");
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        write_log("No lexeditor-ds1-patch.bin: the game runs as it ships");
        return;
    }
    LARGE_INTEGER size;
    char message[256] = "";
    if (!GetFileSizeEx(file, &size) || size.QuadPart <= 0 || size.QuadPart > MAX_PATCH) {
        CloseHandle(file);
        write_log("lexeditor-ds1-patch.bin is empty or too large; nothing was changed");
        return;
    }
    unsigned char *data = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, (size_t)size.QuadPart);
    DWORD read = 0;
    int ok = data && ReadFile(file, data, (DWORD)size.QuadPart, &read, NULL) && read == (DWORD)size.QuadPart;
    CloseHandle(file);
    if (!ok)
        snprintf(message, sizeof message, "Could not read lexeditor-ds1-patch.bin; nothing was changed");
    else
        lx_apply((unsigned char *)GetModuleHandleW(NULL), data, read, message, sizeof message);
    if (data)
        HeapFree(GetProcessHeap(), 0, data);
    write_log(message);
}

typedef HRESULT(WINAPI *create_t)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);

__declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE instance, DWORD version, REFIID iid, LPVOID *out, LPUNKNOWN outer)
{
    static create_t create;
    if (!create) {
        wchar_t path[MAX_PATH];
        UINT length = GetSystemDirectoryW(path, MAX_PATH);
        if (!length || length > MAX_PATH - 14)
            return E_FAIL;
        wcscat(path, L"\\dinput8.dll");
        HMODULE system = LoadLibraryW(path);
        create = system ? (create_t)GetProcAddress(system, "DirectInput8Create") : NULL;
        if (!create)
            return E_FAIL;
    }
    return create(instance, version, iid, out, outer);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        apply_from_file();
    }
    return TRUE;
}
#endif

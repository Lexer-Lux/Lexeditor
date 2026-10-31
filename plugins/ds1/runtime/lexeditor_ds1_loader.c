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
 * Dark Souls Remastered checks parts of its own code: a hook written there
 * before the game starts makes it crash on purpose (always the same bad
 * call, into FMOD's read-only data). The check runs while the game starts
 * up, and a thread of ours that does anything then (even listing windows)
 * sets it off too. A DELAY record therefore has a thread of this DLL sleep
 * the record's milliseconds, then write the hooks with every other thread
 * of the game paused and none of them inside a hook site. A few seconds is
 * still during the game's opening logos, before a save can be loaded.
 *
 * DirectInput8Create, the one function the game imports from dinput8.dll,
 * is forwarded to dinput8.chain.dll when the player preserved another proxy
 * there, otherwise to the system's own dinput8.dll.
 *
 * A game whose code a mod changed must never reach FromSoftware's servers or
 * other players: their anti-cheat may ban the account. So whenever the patch
 * file holds any patch, every way the process opens a connection or looks up
 * a host fails as if there were no network, before anything else happens. An
 * empty patch file (a tweak that only changes the menu layout) leaves the
 * game online.
 */
#include <winsock2.h> /* before windows.h, which would bring in the old winsock.h */
#include <windows.h>
#include <tlhelp32.h>
#include <string.h>
#include <stdio.h>
#include "lexeditor_ds1_loader.h"

#define MAGIC "LXD1PAT"
#define VERSION 1
#define KIND_HOOK 1
#define KIND_BLOCK 2
#define KIND_FUNCTIONS 3
#define KIND_WRITABLE 4
#define KIND_DELAY 5
#define MAX_THREADS 2048
#define MAX_PATCH (16u * 1024u * 1024u)
#define MAX_RECORDS 4096u
/* Dark Souls Remastered silently puts back guarded code (its stamina update
 * among it) a minute or so after a hook is written. The loader checks every
 * hook this often and writes again any the game has restored. */
#define WATCH_MS 250

typedef struct {
    unsigned kind, rva, length;
    const unsigned char *payload;
} record_t;

/* Where the deferred hooks report; set by DllMain's part, NULL in tests. */
static void (*lx_report)(const char *text);
/* Every hook writer enters before suspending anyone. Otherwise two mod
 * workers can suspend one another, including a worker holding the log lock. */
static SRWLOCK hook_write_lock = SRWLOCK_INIT;

typedef struct {
    unsigned char *image;
    DWORD delay;
    unsigned count;
    unsigned *rva, *length;
    unsigned char **original, **replacement;
    DWORD *protection;
} deferred_t;

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

static int apply_records(unsigned char *image, unsigned image_size, const unsigned char *data, size_t size,
                         unsigned count, record_t *records, char *message, size_t capacity);

static void report(const char *text)
{
    if (lx_report)
        lx_report(text);
}

/* A copy of the hooks that outlives the patch file's buffer. */
static void free_hooks(deferred_t *later)
{
    if (!later) return;
    HANDLE heap = GetProcessHeap();
    for (unsigned index = 0; index < later->count; ++index)
        HeapFree(heap, 0, later->original[index]);
    if (later->rva) HeapFree(heap, 0, later->rva);
    if (later->length) HeapFree(heap, 0, later->length);
    if (later->original) HeapFree(heap, 0, later->original);
    if (later->replacement) HeapFree(heap, 0, later->replacement);
    if (later->protection) HeapFree(heap, 0, later->protection);
    HeapFree(heap, 0, later);
}

static deferred_t *defer_hooks(unsigned char *image, DWORD delay, const record_t *records, unsigned count, unsigned hooks)
{
    HANDLE heap = GetProcessHeap();
    deferred_t *later = (deferred_t *)HeapAlloc(heap, HEAP_ZERO_MEMORY, sizeof *later);
    if (!later)
        return NULL;
    later->image = image;
    later->delay = delay;
    later->rva = (unsigned *)HeapAlloc(heap, 0, hooks * sizeof(unsigned));
    later->length = (unsigned *)HeapAlloc(heap, 0, hooks * sizeof(unsigned));
    later->original = (unsigned char **)HeapAlloc(heap, 0, hooks * sizeof(unsigned char *));
    later->replacement = (unsigned char **)HeapAlloc(heap, 0, hooks * sizeof(unsigned char *));
    later->protection = (DWORD *)HeapAlloc(heap, 0, hooks * sizeof(DWORD));
    if (!later->rva || !later->length || !later->original || !later->replacement || !later->protection) {
        free_hooks(later);
        return NULL;
    }
    for (unsigned index = 0; index < count; ++index) {
        const record_t *row = &records[index];
        if (row->kind != KIND_HOOK)
            continue;
        unsigned char *copy = (unsigned char *)HeapAlloc(heap, 0, 2 * (size_t)row->length);
        if (!copy) {
            free_hooks(later);
            return NULL;
        }
        memcpy(copy, row->payload, 2 * (size_t)row->length);
        later->rva[later->count] = row->rva;
        later->length[later->count] = row->length;
        later->original[later->count] = copy;
        later->replacement[later->count] = copy + row->length;
        ++later->count;
    }
    return later;
}

static int inside_hook(const deferred_t *later, DWORD64 address)
{
    DWORD64 base = (DWORD64)(ULONG_PTR)later->image;
    for (unsigned index = 0; index < later->count; ++index)
        if (address >= base + later->rva[index] && address < base + later->rva[index] + later->length[index])
            return 1;
    return 0;
}

/* Pause every other thread; 0 when one of them is inside a hook site. All
 * memory is allocated before any thread is paused: a paused thread may hold
 * the heap's lock. */
static int pause_others(const deferred_t *later, HANDLE *paused, unsigned *count)
{
    *count = 0;
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        return 0;
    THREADENTRY32 entry;
    entry.dwSize = sizeof entry;
    DWORD self = GetCurrentThreadId(), process = GetCurrentProcessId();
    int safe = 1;
    unsigned opened = 0;
    /* Snapshot enumeration and handle acquisition can take locks: finish
     * both before suspending any process thread. */
    for (BOOL more = Thread32First(snapshot, &entry); more; more = Thread32Next(snapshot, &entry)) {
        if (entry.th32OwnerProcessID != process || entry.th32ThreadID == self)
            continue;
        HANDLE thread = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, entry.th32ThreadID);
        if (!thread || opened == MAX_THREADS) {
            if (thread) CloseHandle(thread);
            safe = 0;
            break;
        }
        paused[opened++] = thread;
    }
    CloseHandle(snapshot);
    if (!safe) {
        for (unsigned index = 0; index < opened; ++index) CloseHandle(paused[index]);
        return 0;
    }
    for (unsigned index = 0; index < opened; ++index) {
        HANDLE thread = paused[index];
        if (SuspendThread(thread) == (DWORD)-1) {
            /* Only the suspended prefix may be resumed. Close the rest
             * after the caller has resumed it. */
            for (unsigned rest = index; rest < opened; ++rest) CloseHandle(paused[rest]);
            return 0;
        }
        ++*count;
        CONTEXT context;
        context.ContextFlags = CONTEXT_CONTROL;
        if (!GetThreadContext(thread, &context) || inside_hook(later, context.Rip))
            safe = 0;
    }
    return safe;
}

static void resume_all(HANDLE *paused, unsigned count)
{
    for (unsigned index = 0; index < count; ++index)
        ResumeThread(paused[index]);
    for (unsigned index = 0; index < count; ++index) {
        CloseHandle(paused[index]);
    }
}

/* Write one hook again once the game has put its original bytes back.
 * 1 when written; 0 when its bytes are something else, or no safe moment came. */
static int rewrite_hook(deferred_t *later, HANDLE *paused, unsigned index)
{
    unsigned char *site = later->image + later->rva[index];
    for (int attempt = 0; attempt < 200; ++attempt) {
        unsigned count = 0;
        AcquireSRWLockExclusive(&hook_write_lock);
        if (!pause_others(later, paused, &count)) {
            resume_all(paused, count);
            ReleaseSRWLockExclusive(&hook_write_lock);
            Sleep(5);
            continue;
        }
        DWORD old, ignored;
        int written = 0;
        if (memcmp(site, later->original[index], later->length[index]) == 0 &&
            VirtualProtect(site, later->length[index], PAGE_EXECUTE_READWRITE, &old)) {
            memcpy(site, later->replacement[index], later->length[index]);
            VirtualProtect(site, later->length[index], old, &ignored);
            FlushInstructionCache(GetCurrentProcess(), site, later->length[index]);
            written = 1;
        }
        resume_all(paused, count);
        ReleaseSRWLockExclusive(&hook_write_lock);
        return written;
    }
    return 0;
}

/* For the game's lifetime: keep every hook in place. Only a site holding its
 * exact original bytes is written; anything else there is left alone. */
static void keep_hooks(deferred_t *later, HANDLE *paused)
{
    char text[200];
    unsigned repairs = 0;
    for (;;) {
        Sleep(WATCH_MS);
        for (unsigned index = 0; index < later->count; ++index) {
            if (memcmp(later->image + later->rva[index], later->original[index], later->length[index]) != 0)
                continue;
            if (!rewrite_hook(later, paused, index))
                continue;
            ++repairs;
            /* The log stays small: the first few, then every hundredth. */
            if (repairs <= 5 || repairs % 100 == 0) {
                snprintf(text, sizeof text, "The game put back its code at %08X; the hook was written again (%u so far)",
                         later->rva[index], repairs);
                report(text);
            }
        }
    }
}

/* No heap, logging or formatting inside the suspension window. The same
 * transaction handles immediate and delayed installation. */
static int write_hooks(deferred_t *later, HANDLE *paused, char *text, size_t capacity)
{
    for (int attempt = 0; attempt < 200; ++attempt) {
        unsigned count = 0;
        AcquireSRWLockExclusive(&hook_write_lock);
        if (!pause_others(later, paused, &count)) {
            resume_all(paused, count);
            ReleaseSRWLockExclusive(&hook_write_lock);
            Sleep(5);
            continue;
        }
        for (unsigned index = 0; index < later->count; ++index) {
            if (memcmp(later->image + later->rva[index], later->original[index], later->length[index]) != 0) {
                resume_all(paused, count);
                ReleaseSRWLockExclusive(&hook_write_lock);
                snprintf(text, capacity, "The game's code at %08X changed before the hooks were written; nothing was changed", later->rva[index]);
                return 0;
            }
        }
        DWORD *old = later->protection;
        unsigned index = 0;
        for (; index < later->count; ++index) {
            if (!VirtualProtect(later->image + later->rva[index], later->length[index], PAGE_EXECUTE_READWRITE, &old[index]))
                break;
        }
        if (index != later->count) {
            for (unsigned undo = index; undo-- > 0;) {
                DWORD ignored;
                VirtualProtect(later->image + later->rva[undo], later->length[undo], old[undo], &ignored);
            }
            resume_all(paused, count);
            ReleaseSRWLockExclusive(&hook_write_lock);
            return fail(text, capacity, "Windows refused to let the hooks be written; nothing was changed");
        }
        for (index = 0; index < later->count; ++index) {
            memcpy(later->image + later->rva[index], later->replacement[index], later->length[index]);
            FlushInstructionCache(GetCurrentProcess(), later->image + later->rva[index], later->length[index]);
        }
        /* Multiple sites may share a page. Write all of them before restoring
         * any protection, then undo in reverse order to retain the true RX. */
        for (index = later->count; index-- > 0;) {
            DWORD ignored;
            VirtualProtect(later->image + later->rva[index], later->length[index], old[index], &ignored);
        }
        resume_all(paused, count);
        ReleaseSRWLockExclusive(&hook_write_lock);
        snprintf(text, capacity, "Applied %u hooks", later->count);
        return 1;
    }
    return fail(text, capacity, "No moment was found with every thread outside the hooks; nothing was changed");
}

static DWORD WINAPI deferred_hooks(LPVOID argument)
{
    deferred_t *later = (deferred_t *)argument;
    HANDLE *paused = (HANDLE *)HeapAlloc(GetProcessHeap(), 0, MAX_THREADS * sizeof(HANDLE));
    char text[200];
    if (!paused) {
        report("Out of memory writing the deferred hooks; nothing was changed");
        free_hooks(later);
        return 0;
    }
    Sleep(later->delay);
    int written = write_hooks(later, paused, text, sizeof text);
    report(text);
    if (written) keep_hooks(later, paused);
    HeapFree(GetProcessHeap(), 0, paused);
    free_hooks(later);
    return 0;
}

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
    int result = 0;
    if (!records) {
        fail(message, capacity, "Out of memory reading the patches");
        goto done;
    }
    result = apply_records(image, image_size, data, size, count, records, message, capacity);
done:
    if (records)
        HeapFree(GetProcessHeap(), 0, records);
    return result;
}

static int apply_records(unsigned char *image, unsigned image_size, const unsigned char *data, size_t size,
                         unsigned count, record_t *records, char *message, size_t capacity)
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
            : row->kind == KIND_WRITABLE || row->kind == KIND_DELAY ? 0 : ~0ull;
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
    DWORD delay = 0;
    unsigned hooks = 0;
    for (unsigned index = 0; index < count; ++index) {
        if (records[index].kind == KIND_DELAY)
            delay = records[index].length;
        hooks += records[index].kind == KIND_HOOK;
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
            return fail(message, capacity, "Out of memory registering patch functions; nothing was changed");
        }
        for (unsigned item = 0; item < row->length; ++item) {
            table[item].BeginAddress = read32(row->payload + item * 12);
            table[item].EndAddress = read32(row->payload + item * 12 + 4);
            table[item].UnwindData = read32(row->payload + item * 12 + 8);
        }
        if (!RtlAddFunctionTable(table, row->length, (DWORD64)(ULONG_PTR)image)) {
            return fail(message, capacity, "Windows refused the patch functions' unwind table; nothing was changed");
        }
    }
    if (hooks) {
        deferred_t *later = defer_hooks(image, delay, records, count, hooks);
        if (!later)
            return fail(message, capacity, "Could not schedule the hooks; the patch code is placed but unused");
        if (delay) {
            HANDLE worker = CreateThread(NULL, 0, deferred_hooks, later, 0, NULL);
            if (!worker) {
                free_hooks(later);
                return fail(message, capacity, "Could not schedule the hooks; the patch code is placed but unused");
            }
            CloseHandle(worker);
            snprintf(message, capacity, "Placed the patch code; %u hooks follow after %lu ms", hooks, (unsigned long)delay);
            return 1;
        }
        HANDLE *paused = (HANDLE *)HeapAlloc(GetProcessHeap(), 0, MAX_THREADS * sizeof(HANDLE));
        int written = paused ? write_hooks(later, paused, message, capacity)
            : fail(message, capacity, "Out of memory writing the hooks; nothing was changed");
        if (paused) HeapFree(GetProcessHeap(), 0, paused);
        free_hooks(later);
        if (!written) return 0;
    }
    snprintf(message, capacity, "Applied %u patch records", count);
    return 1;
}

#include "lexeditor_ds1_mods.c"

#ifndef LX_NO_DLLMAIN
static void folder_file(wchar_t *path, size_t capacity, const wchar_t *name)
{
    DWORD length = GetModuleFileNameW(NULL, path, (DWORD)capacity);
    while (length && path[length - 1] != L'\\')
        --length;
    path[length] = 0;
    wcsncat(path, name, capacity - wcslen(path) - 1);
}

static DWORD started;

/* One line per event, each with the milliseconds since the DLL loaded. The
 * first line of a run starts the file afresh. */
static void write_log(const char *text)
{
    static int lines;
    static SRWLOCK lock = SRWLOCK_INIT;
    AcquireSRWLockExclusive(&lock);
    wchar_t path[MAX_PATH * 2];
    folder_file(path, MAX_PATH * 2, L"lexeditor-ds1-patch.log");
    HANDLE file = CreateFileW(path, lines ? FILE_APPEND_DATA : GENERIC_WRITE, FILE_SHARE_READ, NULL,
                              lines ? OPEN_ALWAYS : CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        ReleaseSRWLockExclusive(&lock);
        return;
    }
    LARGE_INTEGER size;
    if (GetFileSizeEx(file, &size) && size.QuadPart > 64000) {
        CloseHandle(file);
        file = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file == INVALID_HANDLE_VALUE) {ReleaseSRWLockExclusive(&lock); return;}
    }
    char line[768];
    int length = snprintf(line, sizeof line, "%s%6lu ms  %s", lines ? "\r\n" : "",
                          (unsigned long)(GetTickCount() - started), text);
    DWORD written;
    WriteFile(file, line, (DWORD)(length <= 0 ? 0 : length < sizeof line ? length : sizeof line - 1), &written, NULL);
    CloseHandle(file);
    ++lines;
    ReleaseSRWLockExclusive(&lock);
}

/* --- No network ---------------------------------------------------------- */

static int WSAAPI refuse_socket_call(void)
{
    SetLastError(WSAENETUNREACH); /* WSASetLastError is SetLastError */
    return SOCKET_ERROR;
}

static int WSAAPI refuse_lookup(void)
{
    SetLastError(WSAHOST_NOT_FOUND);
    return WSAHOST_NOT_FOUND;
}

static void *WSAAPI refuse_host(void)
{
    SetLastError(WSAHOST_NOT_FOUND);
    return NULL;
}

/* The start of `function` becomes a jump to `replacement`; the original is
 * never called again, so nothing of it needs keeping. */
static int redirect(HMODULE module, const char *name, void *replacement)
{
    unsigned char *function = (unsigned char *)GetProcAddress(module, name);
    if (!function)
        return 1; /* not in this Windows: nothing to block */
    unsigned char jump[12] = {0x48, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0xE0}; /* mov rax, imm64; jmp rax */
    memcpy(jump + 2, &replacement, sizeof replacement);
    DWORD protection;
    if (!VirtualProtect(function, sizeof jump, PAGE_EXECUTE_READWRITE, &protection))
        return 0;
    memcpy(function, jump, sizeof jump);
    VirtualProtect(function, sizeof jump, protection, &protection);
    FlushInstructionCache(GetCurrentProcess(), function, sizeof jump);
    return 1;
}

/* 1 once every way online fails; a second call changes nothing. */
int lx_block_network(void)
{
    static int blocked;
    if (blocked)
        return 1;
    static const char *const sockets[] = {"connect", "WSAConnect", "WSAConnectByNameA", "WSAConnectByNameW",
                                          "WSAConnectByList", "sendto", "WSASendTo", "WSASendMsg"};
    static const char *const lookups[] = {"getaddrinfo", "GetAddrInfoW", "GetAddrInfoExA", "GetAddrInfoExW",
                                          "WSALookupServiceBeginA", "WSALookupServiceBeginW"};
    static const char *const hosts[] = {"gethostbyname", "gethostbyaddr"};
    HMODULE ws2 = LoadLibraryW(L"ws2_32.dll");
    if (!ws2)
        return 0;
    int ok = 1;
    for (size_t i = 0; i < sizeof sockets / sizeof *sockets; ++i)
        ok &= redirect(ws2, sockets[i], (void *)refuse_socket_call);
    for (size_t i = 0; i < sizeof lookups / sizeof *lookups; ++i)
        ok &= redirect(ws2, lookups[i], (void *)refuse_lookup);
    for (size_t i = 0; i < sizeof hosts / sizeof *hosts; ++i)
        ok &= redirect(ws2, hosts[i], (void *)refuse_host);
    blocked = ok;
    return ok;
}

#endif

#if !defined(LX_NO_DLLMAIN) || defined(LX_MOD_TEST)
static void apply_from_file(void)
{
    /* This file is a derived description of the current enabled set. Never
     * reuse a prior run's support after preparation failed or was unavailable.
     * Independent native-only runtime.lxd modules still have their own path. */
    if (!lx_data_ready) {
        write_log("Shared patch skipped: mod preparation is unavailable or failed. Native-only folder mods can still load.");
        return;
    }
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
#ifndef LX_ONLINE_BUILD
    /* Offline before the first change, and even if the patch then fails:
     * Lexeditor told the reader the game would be offline. */
    if (!lx_block_network()) {
        CloseHandle(file);
        write_log("The network could not be blocked, so no patch was applied: the game runs as it ships");
        return;
    }
    write_log("Online play is off: mods change the game's code");
#endif
    unsigned char *data = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, (size_t)size.QuadPart);
    DWORD read = 0;
    int ok = data && ReadFile(file, data, (DWORD)size.QuadPart, &read, NULL) && read == (DWORD)size.QuadPart;
    CloseHandle(file);
    if (!ok)
        snprintf(message, sizeof message, "Could not read lexeditor-ds1-patch.bin; nothing was changed");
    else if (lx_apply((unsigned char *)GetModuleHandleW(NULL), data, read, message, sizeof message))
        lx_check_claims(data, read, NULL, message, sizeof message, 1);
    if (data)
        HeapFree(GetProcessHeap(), 0, data);
    write_log(message);
}
#endif

#ifndef LX_NO_DLLMAIN
#include "lexeditor_ds1_chain.c"

#ifdef LX_DEBUG_BUILD
/* The debug loader (lexeditor_ds1_debug.c) blocks the network, switches
 * Arxan off, and then applies the tweaks. */
void lx_debug_start(void);
void lx_debug_log(const char *text) { write_log(text); }
void lx_debug_apply(void) { lx_data_ready=lx_prepare_data(); lx_chain_start(); apply_from_file(); lx_load_mod_folders(); }
#endif

#ifndef LX_DEBUG_BUILD
static DWORD WINAPI start_mods(void *ignored)
{
    (void)ignored;
    /* Data preparation needs the pre-entry-point dearxan callback supplied
     * by the online/debug package. The basic proxy loads native-only mods. */
    lx_data_ready=0;
    lx_chain_start();
    apply_from_file();
    lx_load_mod_folders();
    return 0;
}
#endif

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        started = GetTickCount();
        lx_report = write_log;
#ifdef LX_DEBUG_BUILD
        lx_debug_start();
#else
        HANDLE worker=CreateThread(NULL,0,start_mods,NULL,0,NULL);
        if(worker)CloseHandle(worker);
#endif
    }
    return TRUE;
}
#endif

/* Online runtime for Lexeditor's DS1 loader.
 * SPDX-License-Identifier: AGPL-3.0-only
 * The save I/O and reporting hooks require a native runtime (not Hext).
 * No game executable on disk is modified. */
#include "overhaul/GameData.h"
#include "overhaul/AntiAntiCheat.h"
#include "overhaul/SP/memory/injection/asm/x64.h"
#include <bcrypt.h>
#include <cstdarg>

static void report(const char *format, va_list args)
{
    char message[256];
    vsnprintf(message, sizeof message, format, args);
    lx_debug_log(message);
}

void ConsoleWrite(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    report(format, args);
    va_end(args);
}

[[noreturn]] void FATALERROR(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    report(format, args);
    va_end(args);
    /* Never continue to official multiplayer with only part of protection. */
    TerminateProcess(GetCurrentProcess(), 0x4c58);
    abort();
}

bool sp::mem::patch_bytes(void *address, const void *bytes, size_t size)
{
    DWORD old, ignored;
    if (!VirtualProtect(address, size, PAGE_EXECUTE_READWRITE, &old))
        return false;
    memcpy(address, bytes, size);
    bool ok = VirtualProtect(address, size, old, &ignored) != 0;
    return FlushInstructionCache(GetCurrentProcess(), address, size) && ok;
}

void sp::mem::code::x64::inject_jmp_14b(void *address, uint64_t *resume, size_t padding, void (*target)())
{
    unsigned char jump[15] = {0xff, 0x25, 0, 0, 0, 0};
    if (padding > 1)
        FATALERROR("Unsupported upstream hook padding");
    memcpy(jump + 6, &target, sizeof target);
    jump[14] = 0x90;
    *resume = (uint64_t)address + 14 + padding;
    if (!sp::mem::patch_bytes(address, jump, 14 + padding))
        FATALERROR("Could not install multiplayer protection");
}

extern "C" void lx_online_preflight(void)
{
    /* Upstream uses absolute addresses, including one in its assembly. */
    if ((uintptr_t)GetModuleHandleW(NULL) != Game::ds1_base)
        FATALERROR("Unsupported image base; multiplayer protection was not started");
    wchar_t path[32768];
    DWORD length = GetModuleFileNameW(NULL, path, _countof(path));
    if (!length || length >= _countof(path))
        FATALERROR("Could not identify the game executable");
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    unsigned char digest[32], buffer[65536];
    static const unsigned char expected[32] = {
        0xa4,0x5a,0xaa,0x36,0xdd,0x2f,0x6c,0xc1,0x51,0x67,0x0a,0x63,0x9e,0xa5,0x54,0x70,
        0x43,0xcf,0x38,0xea,0x79,0xff,0x41,0x78,0xb9,0x63,0xc6,0xed,0x71,0xf9,0x8d,0x7b};
    bool ok = file != INVALID_HANDLE_VALUE &&
        BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0) >= 0 &&
        BCryptCreateHash(algorithm, &hash, NULL, 0, NULL, 0, 0) >= 0;
    while (ok) {
        DWORD read;
        if (!ReadFile(file, buffer, sizeof buffer, &read, NULL)) { ok = false; break; }
        if (!read) break;
        ok = BCryptHashData(hash, buffer, read, 0) >= 0;
    }
    if (ok) ok = BCryptFinishHash(hash, digest, sizeof digest, 0) >= 0 &&
                 memcmp(digest, expected, sizeof digest) == 0;
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    if (!ok)
        FATALERROR("Unsupported game build; multiplayer protection was not started");
}

extern "C" void lx_online_start(void)
{
    /* These four prologues are replayed by upstream's assembly. Refuse an
     * already hooked process (including a second anti-ban loader), rather
     * than silently stacking incompatible hooks. */
    static const unsigned char originals[][15] = {
        {0x48,0x8d,0x54,0x24,0x24,0x48,0x8b,0xcb,0xe8,0xbd,0xca,0xff,0xff,0x90},
        {0x48,0x8d,0xac,0x24,0xf0,0xfe,0xff,0xff,0x48,0x81,0xec,0x10,0x02,0,0},
        {0x48,0x8b,0x9c,0x24,0x68,0x02,0,0,0x48,0x81,0xc4,0x10,0x02,0,0},
        {0x49,0x8b,0xc0,0x49,0x83,0xc1,0x10,0x48,0xc1,0xe8,0x06,0x48,0x8d,0x14,0xc1}};
    static const uint64_t offsets[] = {0xbd6ae6, 0xbd4c7c, 0xbd8209, 0xbae8fe};
    for (size_t i = 0; i < _countof(offsets); ++i)
        if (memcmp((const void *)(Game::ds1_base + offsets[i]), originals[i], i ? 15 : 14))
            FATALERROR("Another patch changed a multiplayer protection hook; the game was stopped");
    AntiAntiCheat::start();
    if (!lx_save_install((unsigned char *)GetModuleHandleW(NULL)))
        FATALERROR("Save isolation could not be installed; the game was stopped");
    lx_debug_log("Multiplayer protection installed; modded saves use DRAKS0005.lexeditor.sl2");
}

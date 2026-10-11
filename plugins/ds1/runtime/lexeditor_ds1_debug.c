/*
 * Debug mode for Lexeditor's DS1 loader: the game runs with Arxan switched
 * off and without any network access, so a debugger can attach.
 *
 * Dark Souls Remastered is protected by Arxan: a debugger attached to it, a
 * breakpoint or a watchpoint makes the game close itself (Cheat Engine's own
 * debugger, its VEH debugger and a hand-written one all did, #742). dearxan
 * (https://github.com/tremwil/dearxan, MIT/Apache-2.0, by tremwil) neuters
 * every Arxan check when it runs before the game's entry point, which is
 * when Windows loads this DLL. Its callback runs once Arxan is off, and that
 * is where the tweaks are applied: the game's entry checks still look at its
 * code until then.
 *
 * A game with its protection off must never reach other players, so before
 * anything else every way the process opens a connection or looks up a host
 * fails as if there were no network. Built only into the debug loader
 * (build.py --debug); the everyday loader has none of this.
 */
#include <winsock2.h> /* before windows.h, which would bring in the old winsock.h */
#include <windows.h>
#include <stdio.h>
#include "lexeditor_ds1_loader.h"
#include "dearxan.h"

void lx_debug_log(const char *text);
void lx_debug_apply(void);

/* --- No network ---------------------------------------------------------- */

static int WSAAPI refuse_socket_call(void)
{
    WSASetLastError(WSAENETUNREACH);
    return SOCKET_ERROR;
}

static int WSAAPI refuse_lookup(void)
{
    WSASetLastError(WSAHOST_NOT_FOUND);
    return WSAHOST_NOT_FOUND;
}

static void *WSAAPI refuse_host(void)
{
    WSASetLastError(WSAHOST_NOT_FOUND);
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

static int block_network(void)
{
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
    return ok;
}

/* --- Arxan off ----------------------------------------------------------- */

static void arxan_off(const DearxanResult *result, void *opaque)
{
    (void)opaque;
    char line[256];
    if (result->status == DearxanSuccess)
        snprintf(line, sizeof line, "Debug mode: %s; a debugger can attach",
                 result->is_arxan_detected ? "Arxan is off" : "no Arxan found");
    else
        snprintf(line, sizeof line, "Debug mode: dearxan failed (%.*s); do not attach a debugger",
                 (int)(result->error_msg && result->error_msg_size < 160 ? result->error_msg_size : 0),
                 result->error_msg ? result->error_msg : "");
    lx_debug_log(line);
    lx_debug_apply();
}

void lx_debug_start(void)
{
    if (!block_network()) {
        /* Never run unprotected with a way online left open. */
        lx_debug_log("Debug mode: the network could not be blocked, so Arxan was left on and nothing was changed");
        lx_debug_apply();
        return;
    }
    lx_debug_log("Debug mode: the game has no network access");
    dearxan_neuter_arxan(arxan_off, NULL);
}

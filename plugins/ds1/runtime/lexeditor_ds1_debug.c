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
 * anything else the loader's lx_block_network makes every connection and
 * host lookup fail, even when no tweak is installed. Built only into the
 * debug loader (build.py --debug). The --online build instead verifies the
 * supported game, installs reporting protection and isolates saves before
 * applying tweaks; failed protection stops the process.
 */
#include <windows.h>
#include <stdio.h>
#include "lexeditor_ds1_loader.h"
#include "dearxan.h"

void lx_debug_log(const char *text);
void lx_debug_apply(void);

static void arxan_off(const DearxanResult *result, void *opaque)
{
    (void)opaque;
    char line[256];
    if (result->status == DearxanSuccess)
#ifdef LX_ONLINE_BUILD
        snprintf(line, sizeof line, "Mod loader: %s",
                 result->is_arxan_detected ? "Arxan is off" : "no Arxan found");
#else
        snprintf(line, sizeof line, "Debug mode: %s; a debugger can attach",
                 result->is_arxan_detected ? "Arxan is off" : "no Arxan found");
#endif
    else
        snprintf(line, sizeof line, "Debug mode: dearxan failed (%.*s); do not attach a debugger",
                 (int)(result->error_msg && result->error_msg_size < 160 ? result->error_msg_size : 0),
                 result->error_msg ? result->error_msg : "");
    lx_debug_log(line);
#ifdef LX_ONLINE_BUILD
    if (result->status != DearxanSuccess) {
        lx_debug_log("Multiplayer protection could not start; the game was stopped");
        TerminateProcess(GetCurrentProcess(), 0x4c58);
        return;
    }
    lx_online_start();
#endif
    lx_debug_apply();
}

void lx_debug_start(void)
{
#ifdef LX_ONLINE_BUILD
    lx_online_preflight();
#else
    if (!lx_block_network()) {
        /* Never run unprotected with a way online left open. */
        lx_debug_log("Debug mode: the network could not be blocked, so Arxan was left on and nothing was changed");
        return;
    }
    lx_debug_log("Debug mode: the game has no network access");
#endif
    dearxan_neuter_arxan(arxan_off, NULL);
}

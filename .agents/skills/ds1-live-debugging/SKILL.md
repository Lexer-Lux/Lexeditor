---
name: ds1-live-debugging
description: Debugging the running Dark Souls Remastered (who writes an address, where a value lives, breakpoints, Cheat Engine, x64dbg). Read before asking Lexer for any live game session or debugger step.
---

# Live debugging Dark Souls Remastered

## Debuggers work: use Debug mode

Lexeditor's DS1 **Debug mode** makes a debugger safe to use. Cheat Engine's
"Find out what writes / accesses", hardware breakpoints and x64dbg are all
allowed once it is on.

1. Ask Lexer to tick **Tweaks → INSTALLED GAME → DEBUG MODE**, then press
   **Apply** or **Play**. (Or check it yourself: `tweak_mods.status()` reports
   `debugMode` and `debugInstalled`.)
2. Start the game. Read `lexeditor-ds1-patch.log` in the game folder: it must
   say **"a debugger can attach"**. That line means Arxan, the game's
   anti-debug protection, was switched off by dearxan before the game's code
   ran. If it says anything else, do not attach; report what it says.
3. Attach and debug normally. The game has no network access in Debug mode
   (every connection and lookup fails), so it cannot go online.
4. When done, ask Lexer to untick Debug mode and Apply again for normal play.

## Without Debug mode, never attach

With the everyday loader, Arxan is active: an attached debugger, a breakpoint
or a watchpoint makes the game close itself. On 2026-10-10 (#742) Cheat
Engine's debugger, its VEH debugger and a hand-written debugger each killed
the game with zero hits, and each crash left zombie `DarkSoulsRemastered.exe`
entries that only a reboot clears. So: check the log line above first, every
time.

## Useful without any debugger

- **Read-only memory** (ReadProcessMemory, snapshot and diff) never crashes
  anything, Debug mode or not.
- **Pointer paths, not addresses.** The heap moves on load, rest and death.
  Player data is `GameDataMan` (exe `+0x1C8A530`) `+0x10`; attunement slots
  are at player data `+0xEDC8`: 12 slots of (spell id, casts remaining x3),
  so a full Soul Arrow reads 90.

## Asking Lexer for game time

He runs many sessions at once. Ask once, as one numbered list he can follow
without replying in between. Look up how others solved a problem (forums,
mod tools, me3, dearxan) before spending his launches.

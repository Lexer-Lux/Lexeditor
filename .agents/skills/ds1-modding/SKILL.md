---
name: ds1-modding
description: Dark Souls Remastered modding with live game inspection (who writes an address, where a value lives, breakpoints, Cheat Engine, x64dbg). Read before asking Lexer for any live game session or debugger step.
---

# Dark Souls modding

Mod work that needs the running game follows the debugging procedure below exactly.

## Debuggers work: use Debug mode

Lexeditor's DS1 **Debug mode** makes a debugger safe to use. Cheat Engine's
"Find out what writes / accesses", hardware breakpoints and x64dbg are all
allowed once it is on.

1. Ask Lexer to tick **Tweaks → INSTALLED GAME → DEBUG MODE**, then press
   **Save** or **Play**. (Or check it yourself: `tweak_mods.status()` reports
   `debugMode` and `debugInstalled`.)
2. Start the game. Read `lexeditor-ds1-patch.log` in the game folder: it must
   say **"a debugger can attach"**. That line means Arxan, the game's
   anti-debug protection, was switched off by dearxan before the game's code
   ran. If it says anything else, do not attach; report what it says.
3. Attach and debug normally (Cheat Engine's process list hides zombie entries from earlier crashes, so attach to the one game entry shown). The game has no network access in Debug mode
   (every connection and lookup fails), so it cannot go online.
4. When done, ask Lexer to untick Debug mode and Save again for normal play.

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

## One shared cheat table

All DS1 live debugging shares a single Cheat Engine table. Never tell Lexer
to type addresses, offsets, or pointer chains by hand, and never start a
second table: put every entry in the shared one, and when it changes tell him
to re-open it (select all rows, Delete, then File -> Open inside the already
attached CE - never double-click the file, which opens a new unattached CE).

- The shared table is `DS1-Shared.CT` on his Desktop, but his Desktop is
  redirected (currently `D:\Desktop`), so resolve the real folder first:
  `HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell
  Folders` `Desktop`, or `[Environment]::GetFolderPath('Desktop')`. Never
  assume `C:\Users\...`.
- Got a legacy per-muse table (like the old `Omnirolling.CT`)? Merge its
  unique entries into the shared file once, then stop using it.
- Re-read the file immediately before every write, keep IDs unique, and tag
  each description with your session (`[hum]`, `[omni]`...). Ship only entry
  shapes proven in-session: single-offset pointers and plain literals.
  Multi-box pointer chains have burned sessions before - verify any new shape
  against a known value before he trusts it.
- Refresh your own rows in place when the heap moves (death, rest, load). Freed heap still reads stale numbers instead of `??`, so name the stale rows. Batch your updates and ask for one re-open per batch. Never build an
  auto-reload: a table that reloads itself mid-debug would nuke his
  breakpoints and scans.

## Asking Lexer for game time

He runs many sessions at once. Ask once, as one numbered list he can follow
without replying in between. Look up how others solved a problem (forums,
mod tools, me3, dearxan) before spending his launches. Never quote Cheat
Engine entry IDs, addresses, or offsets at him: they mean nothing outside
your own window. Name the row ("your Soul Arrow casts row"), never its number.

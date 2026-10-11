---
name: ds1-live-debugging
description: Finding code or data in a running Dark Souls Remastered (who writes an address, where a value lives). Read before asking Lexer for any live game session, Cheat Engine step or debugger attach.
---

# Live debugging Dark Souls Remastered

## The rule: no debugger, no breakpoint, on a protected game

DSR is protected by Arxan (GuardIT): anti-debug checks, and code-integrity
checks spread through ordinary functions that crash the game when guarded
code changes. Measured on 2026-10-10 (#742, the mana session), every one of
these killed the game, with zero hits recorded:

- Cheat Engine "Find out what writes", default Windows debugger (twice).
- Cheat Engine with the VEH debugger.
- A minimal hand-written debugger with hardware watchpoints (attach alone,
  and arming across a load, both ended the game).

Do not try another breakpoint or attach on the protected game. Each attempt
costs Lexer a relaunch, and crashes leave zombie `DarkSoulsRemastered.exe`
entries that only a reboot clears (they can also hold the executable lock,
and once wedged his controller until reboot).

## What works

- **Read-only memory.** Snapshot-and-diff with ReadProcessMemory never
  crashed anything. Use it to find where a value lives.
- **Pointer paths, not addresses.** The heap moves on load, rest and death.
  Player data is `GameDataMan` (exe `+0x1C8A530`) `+0x10`; attunement slots
  are at player data `+0xEDC8`: 12 slots of (spell id, casts remaining x3),
  so a full Soul Arrow reads 90.
- **Static analysis** of the fingerprinted executable (sha-256
  `a45aaa36...71f98d7b`) to find candidate code, then prove it with an
  in-memory hook from Lexeditor's DS1 loader (`plugins/ds1/runtime/`), which
  re-writes its hooks when Arxan restores code.
- **A real debugger: DS1 Debug mode.** Tweaks tab → INSTALLED GAME → DEBUG
  MODE, then Apply or Play. The game then starts with the debug loader
  (`plugins/ds1/runtime/package/debug/dinput8.dll`): every network call
  fails, so it cannot go online, and dearxan
  (https://github.com/tremwil/dearxan) switches Arxan off before the game's
  code runs, so Cheat Engine or x64dbg can attach.
  `lexeditor-ds1-patch.log` in the game folder says "a debugger can attach"
  when it worked. Confirm that line before asking Lexer to set a watchpoint,
  and ask him to turn Debug mode off and Apply again afterwards.

## Asking Lexer for game time

He runs many sessions at once. Ask once, as one numbered list he can follow
without replying in between, and say what you will read and how long it
takes. Never ask him to set a watchpoint. Look up how others have solved a
problem (forums, mod tools, me3, dearxan) before spending his launches.

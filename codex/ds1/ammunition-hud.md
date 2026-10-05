# Remastered ammunition slots and native HUD

This is a static map for the executable with SHA-256
`a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`
(50,286,344 bytes). Addresses are module-relative RVAs, **not file offsets**.
It contains two `.text` sections; map addresses by their ranges, not their names.
This map is not proof of a working runtime modification.

## Independent slot and quantity reads

The native HUD getter at `0x678CD0` obtains player game data through:

```
singleton = *(moduleBase + 0x1C8A530)
playerGameData = *(singleton + 0x10)
equip = playerGameData + 0x280
assembly = equip + 0x80
```

Treat missing roots as unavailable player data, not zero ammunition.

`0x31B750` returns `int32(assembly + 0x24 + rawSlot * 4)` for raw slots
0 through 19, or -1 outside that range. The ammunition slots are:

| Binding | Primary | Secondary |
| --- | ---: | ---: |
| Arrows | 4 | 6 |
| Bolts | 5 | 7 |

The quantity routines `0x747860` and `0x747920` first translate logical or
special arguments into raw slots, then use the same inventory-index path:

```
index = int32(equip + 0x24 + rawSlot * 4)
count = int32(equip + 0x130)
split = int32(equip + 0x140)
table = pointer(equip + (0x150 if index < split else 0x158))
quantity = int32(table + index * 0x1C + 8)
```

The native routines reject negative indices and indices at or above count.
**Do not subtract `split` from the index for the second table.** Both branches
multiply the original index by 0x1C. Missing inventory (-1) and zero quantity
are different results. A conservative external reader must additionally reject
null/invalid pointers and incomplete reads rather than relying on game invariants.

The left/right selected-arrow indices live at `equip+0x94/+0x98`; selected
bolts at `equip+0x9C/+0xA0`. Independent primary/secondary reads do not need them.
This does not prove how to change ammunition safely at the instant a shot is
committed; that is a separate control/animation synchronization problem.

## A second HUD widget needs a second binding

`0x678CD0` determines an ammunition icon/count from a **hand** selector. Its
existing left/right paths do not mean primary/secondary. Weapon parameter
category byte `+0xE2` distinguishes bow (10) and crossbow (11); ammunition
icon IDs are read from parameter word `+0xBA`.

`0x678A00` updates count text and caches the current icon at widget `+0x22C`
and count at `+0x230`. Its children include `text_arrow_number00` and
`text_arrow_number01`. Reusing the same object's cache for two bindings can
suppress one update. A copied widget still needs independent slot selection,
cache state, correct visibility, ownership/teardown and placement.

The image names `Ins_F20-00_arrow_l`, `Ins_F20-00_arrow_r` and
`F20_01_arrow_change`. Native widget construction around `0x67A610` is a
continuation point; merely locating these names does not establish safe cloning.
The on-disk image references `menu:/menu.drb`; the actual layout was not available
for inspection in this investigation.

## On-disk code is not always the loaded code

The input site `0x396EAE` matches the public GyroAim interior hook. However,
on-disk bytes at `0x1A4140` and `0x1A41F0` differ from its live helper guards.
The probe does not unpack, change or execute those regions. Do not apply a
live-code signature as an on-disk Hext offset. Runtime helper verification,
shot selection/consumption and coexistence with input mods remain unproved.

## Diagnostic, not a tweak

`tools/ds1_ammunition_probe.py` checks the exact build and seven minimal
structural guards. Offline mode opens the executable read-only. An explicit
`--pid` on 64-bit Windows optionally samples all four slots with read/query
permissions only. It checks the process path, disk hash and live guards.
It does not discover/attach to other processes, elevate privileges, modify
memory, call game functions, change selection, render a HUD or fire anything.

Two equal samples are best-effort observations, not atomic snapshots and not
evidence that firing consumes the intended slot. Unknown builds, changed guards,
invalid memory and unstable samples fail closed. No compatibility or online
safety guarantee is implied.

## Sources and attribution

The slot/table/cache facts above were independently traced in the supplied
executable, kept private. No executable, disassembly, memory dump or game
archive is distributed.

The public reference used to locate native input and HUD helpers was
lud-berthe's **Dark Souls Remastered Gyro Aim**,
`src/Aiming.cpp` at `d451f3f6403fa4ee24b9fc0868280893fd2e17df`:
https://github.com/lud-berthe/Dark-Souls-Remastered-Gyro-aim-mod

The diagnostic's original ctypes transport uses Microsoft's documented
ReadProcessMemory, QueryFullProcessImageNameW, MODULEENTRY32W and
CreateToolhelp32Snapshot interfaces. No upstream implementation is copied:

- https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-readprocessmemory
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew
- https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-moduleentry32w
- https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot

Unsettled implementation work and source leads belong in `worklog/902.md`.

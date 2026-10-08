# Sources and implementation boundary

## User requirement

Issue: https://github.com/Lexer-Lux/Lexeditor/issues/856

User comment: https://github.com/Lexer-Lux/Lexeditor/issues/856#issuecomment-5960878772

The comment's Elden Ring reference is treated as approval of that design direction, not as another unanswered request for a combat policy. The native DS1 condition below is explicit; no Elden Ring grace-period value is invented.

## Private image analysis

The exact supported SHA-256 and size are in `script/native_patch.py`. The following addresses were inspected in that image. They are RVAs, not universal signatures. The original routines are not distributed.

| RVA | Observed role |
| --- | --- |
| 0x31FD7A | Sprint charge call; actor in RCX, delta -1 in EDX; return unused |
| 0x339680 | General stamina writer, retained unchanged |
| 0x1C77E50 | World character manager pointer |
| 0x392B80 | AI battle getter through controller +0x230 |
| 0x5C7370 | Perception getter through +0x30 |
| 0x61BA70 | Battle predicate compares perception +0xE0 with 3 |
| 0x391820 | Known always-false battle getter |
| 0x139DB00 | Known character-handle accessor vtable |
| 0x61A820 | Resolve cached character slot or registry handle |
| 0x3714B0 | Registry handle resolution with active pool/slot bounds |
| 0x33EC30 | Character slot stride calculation |

The active pool limit is read from world->registry(+0x10)->count(+0x18), plus two, with an upper bound of 29. Pools use 0x38-byte slots. The wrapper uses those native bounds instead of reading every allocated slot unconditionally. Target kind 1 and the known accessor layout are required before resolving a battle target. Other target kinds retain normal sprint costs.

Missing live-actor AI/perception state is deliberately conservative even where a native getter alone would return false. Known nonbattle controllers and dead actors are excluded. This cannot by itself prove every boss/event transition, concurrent object lifetime, or every mod's custom controller behavior.

## Public structural lead

DSR Gadget's published offsets were consulted as a lead for player/world structures; the supported image was inspected independently:
https://github.com/Nordgaren/DSR-Gadget-Local-Loader/blob/077102955ae43b86c99d49189d8c9f1179b0b2f0/DSR-Gadget/Util/DSROffsets.cs

No code from that project was imported. No cheat-engine trainer or global NoStaminaConsumption flag is used.

## Platform contracts

Microsoft PE format:
https://learn.microsoft.com/en-us/windows/win32/debug/pe-format

Microsoft x64 exception/unwind data:
https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64

Microsoft x64 prolog/epilog:
https://learn.microsoft.com/en-us/cpp/build/prolog-and-epilog

Microsoft RtlVirtualUnwind:
https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtlvirtualunwind

The wrapper's six register pushes and 56-byte stack allocation have one RUNTIME_FUNCTION record and matching UNWIND_INFO. The shared host relocates the code and rebuilds a single sorted exception table. The direct final jump goes outside the wrapper to the existing stamina writer. These format checks are not a substitute for Windows unwinder or game-startup execution.

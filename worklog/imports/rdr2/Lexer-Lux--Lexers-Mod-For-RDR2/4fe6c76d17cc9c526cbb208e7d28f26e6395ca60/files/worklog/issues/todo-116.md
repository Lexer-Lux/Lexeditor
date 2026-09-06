# Worklog: Todo 116

## #116 binoculars dead in the 07:5x build — animated draw, not the trigger 2026-08-05

Lexer reported "hold Q to use binos totally nonfunctional, gamepad too". The
trigger was never the problem. GameplayTweaks.binoculars.log, that session:
  HOLD cover=1 controlOn=1 kit=0xF6687C5A hasWpn=1 inv=1 heldMs=47
  enter binos kit=0xF6687C5A prev=0xA2719263 via held cover
  release; waiting for native binocular stow          <- 0.2-0.6 s later
  native stow complete; previous weapon restored
Eleven clean enter/exit cycles. Detection, kit resolution and ownership were all
fine every time.

CAUSE: the animated-equip rework (uncommitted, not mine) shipped
`InstantEquip=0 / DrawMs=900`, so forced aim and `g_binocularsActive` wait for
the draw to finish — 250 ms hold + 900 ms draw ≈ 1.15 s of holding before
anything is visible. Releasing earlier stows silently, showing nothing at all.
Every hold in the log was 0.2-0.6 s.

Restored `InstantEquip=1 / DrawMs=0 / StowMs=0` in both INIs. No rebuild: the INI
is re-read every 2 s and these are the documented escape hatches.

LEFT for whoever owns that rework: if the satchel draw is wanted, releasing
mid-draw must complete the raise (or the hold threshold must cover the draw)
instead of aborting into a stow.

NOTE ON PROCESS: the 07:5x build was compiled from the whole working tree while
another agent had this rework in progress, so I shipped their unfinished work
with my #113 fix. Build only what you can account for, or say plainly that the
build contains someone else's in-flight changes.



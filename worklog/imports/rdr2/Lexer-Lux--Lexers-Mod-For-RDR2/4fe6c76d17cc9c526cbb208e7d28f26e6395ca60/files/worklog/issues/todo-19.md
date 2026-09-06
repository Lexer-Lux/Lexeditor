# Worklog: Todo 19

## #19 — wagon stamina cores: the swap could never have fired

Lexer: "you can't put your horse into harnesses they all come with their own."
That is decisive. The gate I shipped only swapped the core display when the
player's owned mount was one of `GET_DRAFT_HORSE(wagon, 0..5)`. Since every
cart and wagon spawns with its own hitched team and the player's horse can
never join it, the test evaluated false on every tick and `_SHOW_HORSE_CORES`
was never called. "No horse cores in sight" was the only possible outcome.

Checked whether the swap could be made truthful instead of removing the gate:
`_SHOW_HORSE_CORES` takes a single bool, and grepping the whole decompiled
script set turns up no ped-targeted core-display native at all — every one of
Rockstar's ~50 calls is a show/hide pair bracketing a shop or satchel menu.
The display is hardwired to the player's own mount, so pointing it at a harness
horse is not possible. Forcing it on unconditionally would have shown an idle
horse's cores while the team did the work.

Replaced it with a mod-drawn ring, reusing the existing recon HUD primitives:
worst stamina core across the harness team, drawn only while the wagon is
moving above `MinimumSpeed`, amber down to 25% then red. The drain loop was
untouched — it was correct all along and merely invisible. New ini keys
`[WagonCores] ShowHorseCores/HudX/HudY/HudSize`; the toggle hides the ring
only, never the drain. Removed the now-dead `GET_LAST_MOUNT` helper.

Built clean and installed to the game folder. UNVERIFIED in game: ring
visibility, on-screen position, and that it visibly falls while driving.

**Correction to the above, same session.** Two things wrong. First, I invented a
HUD element nobody asked for — a ring reusing the recon tag primitives, which
look bad and which I placed over the minimap. Lexer never requested a custom
HUD. Reverted in full: ring, ini keys, globals and the rebuild are all backed
out and the clean .asi reinstalled. The drain loop stays, with a comment
recording why it is invisible. Second, I rewrote the TODO entry to a "needs a
test" status while leaving it sitting in Class_A — a status change means the
entry MOVES sections, and there was no move.

The mod Lexer half-remembered does exist: Hardcore Stamina by alfabravozapa
(Nexus 2925), "Added stamina core to horse-drawn vehicles". Its comment thread
confirms both that it shows wagon-horse cores and that it draws its own icons
with a configurable position. So custom drawing is the only route — my error was
the execution and the uninvited scope, not the diagnosis. #19 stays in Class_A
with the options written out for Lexer to choose.

---

**#85 — the casing hold leaked into vanilla's hold-E rest.**
Our loot prompt completes on SHORT_TIMED_EVENT, a shorter hold than vanilla's
rest. The key was therefore still down when the casing was granted, and the
rest prompt — which watches the same INPUT_LOOT family — kept counting and
fired right after the pickup. Nothing about the pickup itself was wrong; the
leftover press was.

Fix: from the frame a pickup starts, INPUT_LOOT/LOOT2/LOOT3 are disabled every
frame until the key is physically released. That is the same three-input
disable saloon_dining and theatre_ticket_taker perform when they own the loot
key. Suppression starts AT the pickup and not before, deliberately —
DISABLE_CONTROL_ACTION on INPUT_LOOT during our own hold could starve our own
prompt, and I have no way to test that from here.

I did not copy their accompanying `SET_PED_RESET_FLAG(ped, 203, true)`; I do
not know what flag 203 does, and guessing at a per-frame ped flag is how the
last few regressions started.

Built clean and installed. UNVERIFIED in game: that no rest starts when E is
held past a casing pickup, and that ordinary looting/skinning still works on
the next press.


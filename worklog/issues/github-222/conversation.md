# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356312766 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/222

Created: 2026-08-07T07:50:30Z; updated: 2026-09-05T07:01:21Z

Exact metadata: [source record](sources/issue-5356312766-8173e4b5c6c62cac0ebde6833f11a4ec7ab1e5497a127b7935a241c233ff8af2.json).

Split out of Lexer-Lux/Lexeditor#111, which fixed the missing casing ARTWORK but not this.

`GameplayTweaks.casings.log` records `PICKUP_LEX_CASING create failed - falling back to plain object` on every ejection. The casing then exists as an inert world object rather than a native pickup, so the acquisition card never fires.

This is why "no acquisition popups" persisted independently of the icon problem — two unrelated defects producing one symptom, which is why fixing the artwork alone did not resolve it.

Owner: `GameplayTweaks/modules/items_casings.cpp` (the pickup-creation path, not the icon path).

## What to establish first
- Why the pickup type fails to create: is `PICKUP_LEX_CASING` a registered pickup type in `MyOverhaul/pickups.meta` at all, and does its model/reward binding resolve?
- Compare against a vanilla pickup that does create successfully, and against `pickups.meta:3122`/`:3136`/`:3144-3145`, which document the model binding and the `KeepWeaponThatUsesThisAmmoEquipped` / separate weapon+ammo reward pattern.
- Do not assume the fallback is harmless: an inert object also means no acquisition log entry, which is the user-visible complaint.

## Acceptance
- [ ] Eject a casing and confirm a native pickup is created (no `create failed` line in the log).
- [ ] Confirm the acquisition card appears on pickup.
- [ ] Confirm the corrected lowercase icon renders on it (depends on Lexer-Lux/Lexeditor#111, already installed).

## issue 5356312766 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/222

Created: 2026-08-07T07:50:30Z; updated: 2026-09-06T12:56:02Z

Exact metadata: [source record](sources/issue-5356312766-8fd4864c572fd9d9c15b12da74710227713dab20a3e7ea1f81e9e93d7460e64c.json).

Casings should use Hold E, a ground-pickup animation and the casing’s acquisition card—not a grey Tab prompt for live ammunition.

**Status: The latest path correction is not confirmed installed.** Deliver it before another pickup test. Picking up brass must never grant live rounds; the separate longarm-held reach animation remains unfinished.

## comment 5550141834 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/222#issuecomment-5550141834

Created: 2026-08-19T12:49:41Z; updated: 2026-08-19T12:49:41Z

Exact metadata: [source record](sources/comment-5550141834-a8ea0816871b9e24d3af79a365b7044305edd57738cdf3ded03c5b7e33f7ff8f.json).

<img width="382" height="371" alt="Image" src="https://github.com/user-attachments/assets/2113c729-ad0e-4c52-b256-6858ef5ac9cc" />

Strange. Suddenly now it's asking me to use tab to pick it up instead of holding E like regular items you can pick up. Except it's greyed out so I can't pick them up anymore.

Again, the goal from the start was for you to take a look at the in-world items you can pick up by holding E that you can physically see John/Arthur pick up, and just use whatever that code/pathway is for the casing.

## comment 5550141844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/222#issuecomment-5550141844

Created: 2026-08-20T06:05:37Z; updated: 2026-08-20T06:05:37Z

Exact metadata: [source record](sources/comment-5550141844-3117693a173175c32d3753f27f0eafce7a0871fcf22c66a6552b2025ab8785fb.json).

You were right, and the screenshot explains itself once you know where the two bits of text come from.

**What was actually happening.** The pickup was being created fine — the log shows `pickup placed ... object pending` then `pickup object adopted after 0 ms`, and no `create failed` line anywhere. The problem is what kind of pickup the engine thought it was. The prompt said **".225 Round"**, which is the name of the *ammunition* (`AMMO_PISTOL = .225 Round` in strings.gxt2), not the casing (`LEX_CASING_PISTOL = .225 Casing`). So the game was reading the casing as an ammo pickup, and that is why it asked for TAB instead of a held E.

And it was greyed out because the pickup had nothing to give you. The casing pickups were declared as ammo rewards that award **zero rounds** — I checked every ammo reward in pickups.meta: 76 of them grant at least one round, and the only six that grant nothing are the six casing ones. A pickup with an empty reward gets its prompt disabled. The satchel item we hung on it was never what the game read.

**Why it can't be fixed by editing pickups.meta.** The game only has six kinds of pickup reward — ammo, weapon, health, money, robbed-satchel-item, special-ability — and none of them can hand you a named satchel item like a casing. There's also no native that sets a pickup's reward from script. Bumping the ammo amount above zero would un-grey it by giving you live bullets for picking up brass, which is the opposite of the point.

I also chased the real vanilla "hold E and watch him pick it up" path, since that's what you asked for. That's the herb/plant system, and the item it gives you is baked into the plant asset inside the game archives — every one of the 94 of them is a plant, mushroom or egg. We can't author a casing one. What *is* reachable from that system is the animation itself, and we already use it: `mech_pickup@system@rh / ground_near` is Rockstar's own pick-something-off-the-ground clip.

**What changed.** The engine-pickup route is gone. Casings now always use the held-loot-key prompt with Rockstar's pickup animation, then the item and its card — no TAB, no grey. The setting that switched between them now defaults to the working one, and if it's ever set back to `native` the mod says so in the log and collects on the loot key anyway instead of silently leaving you with a dead prompt. The prompt is also registered no matter what that setting says; previously, leaving it on `native` meant no loot prompt existed at all, which is the state you were stuck in.

**What to check when it's installed:**
1. Fire a shot, walk to the casing — the prompt should read "Pick Up .225 Casing" (or the matching caliber) on E, and should not be greyed.
2. Hold E — he reaches down, the casing goes, and the card shows the casing with its icon.
3. Check the satchel: the casing is there, and your ammo count did **not** go up.

One thing still open, and it belongs to Lexer-Lux/Lexeditor#182 rather than here: while you're holding a rifle the reach is still skipped on purpose, because that's what was dragging the longarm through the floor. I found `mech_pickup@system@lh`, the left-hand version of the same Rockstar pickup dictionary with the same clip in it, which is the obvious candidate for that case — but I'm not shipping it on a hunch after that regression. Say the word and it goes in as its own test.


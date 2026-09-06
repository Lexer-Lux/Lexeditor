# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356308631 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204

Created: 2026-08-06T05:59:38Z; updated: 2026-09-05T07:00:26Z

Exact metadata: [source record](sources/issue-5356308631-3f8ecf2d611f115f749931ba8be2060872faa70c1369201c0dab102c26e03cff.json).

Legacy TODO 43

At fences, including wagon and horse fences, the Honor price curve is mirrored: low Honor is cheap and high Honor is penalized. Regular shops remain unchanged.

## Test

- [ ] At low Honor, buy from a fence and confirm the price is discounted.
- [ ] At low Honor, buy from a general store and confirm the normal penalty remains.
- [ ] Repeat at high Honor and confirm fence pricing becomes penalized.
- [ ] Confirm regular-store pricing still follows the vanilla Honor curve.

## issue 5356308631 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204

Created: 2026-08-06T05:59:38Z; updated: 2026-09-06T12:55:42Z

Exact metadata: [source record](sources/issue-5356308631-500baf2e0d552fb495fb2186683592a94566613ded46ed8648380f4fa0e846a5.json).

Fences should reward low Honor with better prices and penalize high Honor, while normal stores retain their usual Honor curve.

**Status: Latest repair is not built or installed.** The previous low-Honor test still showed baseline prices. Deliver the independent shop-modifier correction before another purchase comparison.

## issue 5356308631 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204

Created: 2026-08-06T05:59:38Z; updated: 2026-09-06T12:55:42Z

Exact metadata: [source record](sources/issue-5356308631-b672c26189a789e34f29d8e8352a2d230833063e612620d86fe46b767c486601.json).

Fences should reward low Honor with better prices and penalize high Honor, while normal stores retain their usual Honor curve.

**Status: Latest repair is not built or installed.** The previous low-Honor test still showed baseline prices. Deliver the independent shop-modifier correction before another purchase comparison.

## comment 5550137245 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204#issuecomment-5550137245

Created: 2026-08-13T12:53:10Z; updated: 2026-08-13T12:53:10Z

Exact metadata: [source record](sources/comment-5550137245-2aabcd8ab56730961b0964eaceb42b8609e59f612d1ef53bdfddd4980bbc52ba.json).

Seemed to work fine with positive honor -- in the general store's catalog, the prices said "$Y \n was X" which is great. Seemed to be what they should be based on the values we put in though I didn't check. One problem though: I then set my honor to -240 and I just got the base prices. Huh?

## comment 5550137267 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204#issuecomment-5550137267

Created: 2026-08-14T01:36:08Z; updated: 2026-08-14T01:36:08Z

Exact metadata: [source record](sources/comment-5550137267-9250a391efd7b392d213cdc5e78f7ec3fae154d06f5c429116b96a7f53ee1478.json).

**Ruled two explanations out, and instrumented the two that survive.**

First, what your -240 result should have been. `honorRank(-240)` is `-240 / 40 = -6`, which selects `Rank-6Multiplier = 1.75` — a **penalty**, not base prices. The table is fully populated from -8 to +8, so there is no gap for an extreme value to fall into. Base prices are not what that path produces.

Two things that would have explained it, both eliminated:

- **The black-hood exemption.** At negative honor, wearing `KIT_MASK_BLACK_HOOD` forces exactly 1.0 — which *is* base prices and would look identical to this. But your selected mask is `KIT_MASK_PSYCHO` (`[CarriedMask] Item=KIT_MASK_PSYCHO`, and the log shows `usingMask=1 maskOnFace=0`), and the check tests that exact hash. Not it.
- **A missing table entry.** Ruled out above.

**The two that remain, which I cannot separate from here:**

1. **`honorValue()` may not be reading -240.** It reads the `HONOR_CURRENT` stat, and if honor set externally does not land in that stat, the read comes back 0 → rank 0 → multiplier exactly `1.00`. That is base prices, and it would look precisely like what you saw.
2. **No shop record carried the honor modifier key at that moment.** The write only touches entries already tagged with Rockstar's honor-modifier id; if none matched, nothing is written and Rockstar's own base price stands untouched.

**Why nobody could tell before:** this function logged nothing whatsoever — not the honor it read, not the rank, not the multiplier it chose, not whether it wrote anything. It is one of the few remaining places where a wrong result and a no-op were indistinguishable.

It now logs, on change or every 5 s while a shop menu is open:

```
[honor-price] shop price honor=… rank=… desired=… fence=… reversed=…
              hoodExempt=… matchedEntries=… writtenEntries=…
```

That is decisive either way. `matchedEntries=0` proves the second cause. A `honor=` that disagrees with the honor you set, or a `rank=0` when you expect -6, proves the first — and if `honor` reads 0 while you are at -240, the fix is the stat being read, not the pricing maths.

Next time: set honor negative, open a general store, then a fence, and leave each catalog open a few seconds.

Note your original test list still has the fence half unchecked — everything above is the general-store path. `reversed=1` is configured, so once the read is trusted the fence mirror can be judged from the same lines.


## comment 5550137285 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204#issuecomment-5550137285

Created: 2026-08-14T05:14:09Z; updated: 2026-08-14T05:14:09Z

Exact metadata: [source record](sources/comment-5550137285-a5775f096b14327e1242719b5f09c907e5f3686156760fbae6899d98e534bc1d.json).

**Found the first of the two candidate causes, from Rockstar's source rather than from another test.**

`HONOR_CURRENT` is not where honor lives. It is a **mirror**. Live honor is `Global_40.f_11095.f_35`:

- `abigail2_1.c:28124` is literally `return Global_40.f_11095.f_35;` — the getter.
- `:28529-28530` accumulate an honor change into it and clamp it.
- `:28616` then writes the `HONOR_CURRENT` **stat** from it, via `STAT_ID_SET_INT`.

It is referenced 11,088 times, so there is no ambiguity about which is canonical.

That mirror is only refreshed when Rockstar's own honor path runs. Honor set by any other route leaves the stat behind, and this module read only the stat — so a stale read of 0 gives rank 0, which selects multiplier 1.00, which is **base prices**. That is precisely your "-240 and I got base prices" result, and it is candidate cause 1 confirmed as a real mechanism rather than a hypothesis.

The pricing maths was never wrong: `honorRank(-240)` really is -6 and really does select `Rank-6Multiplier = 1.75`. It was being fed a value of 0.

Fixed: the global is the source now, with the stat retained as a fallback for the reverse case. Both are logged side by side, so you can read what happened instead of trusting me:

```
honor=… honorGlobal=… honorStat=…
```

- `honorGlobal=-240 honorStat=0` → this was the bug, and it is now fixed.
- Both `-240` → the stat was fine and the remaining cause is the second one (no shop record carrying the honor modifier key), which `matchedEntries=0` on the same line proves.
- Both `0` while you are visibly at -240 → my global address is wrong and I will say so.

Still `actionable`, because the fence half of your test list has never been exercised and I have no in-game confirmation of any of this.

When you get a chance: set honor negative, open a general store, leave the catalog up a few seconds, then do the same at a fence. One session gives every number needed to close this.


## comment 5550137298 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204#issuecomment-5550137298

Created: 2026-08-16T06:37:32Z; updated: 2026-08-16T06:37:32Z

Exact metadata: [source record](sources/comment-5550137298-90924dafe1429d1a11517d34855a033485d80560e86a725ca912602f7f68ebbe.json).

<img width="1893" height="1180" alt="Image" src="https://github.com/user-attachments/assets/3f0b8782-0cc7-43ce-98b5-1df4a0e1919a" />

-240 honor and all prices seem to be baseline.

## comment 5550137313 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/204#issuecomment-5550137313

Created: 2026-08-20T07:17:53Z; updated: 2026-08-20T07:17:53Z

Exact metadata: [source record](sources/comment-5550137313-87516e4d5a02b6dbb40f1e5cc4ef4e4b70d4b27846992f32ccd4d7271217d754.json).

The last repair still lost a race: Rockstar rewrites its own honor multiplier during every active shop tick. The source now leaves that entry under Rockstar control and adds a separate shop modifier whose product with Rockstar's value equals the configured honor price. This uses the current 1491.50 shop layout and reports the active shop, both multipliers, their combined readback, missing-entry failures, and disabled cleanup. The focused static and mutation checks pass. I did not build or install it, as requested, so this remains actionable.

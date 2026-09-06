# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356329339 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/283

Created: 2026-08-13T06:54:54Z; updated: 2026-09-05T07:04:43Z

Exact metadata: [source record](sources/issue-5356329339-2be39dc0ce674897965d0f65b437b310c15da1dc0770b5516bb5d5335f679aa0.json).

When you don' have enough stamina to roll, a roll input should not become a dive input. IT should do nothing.

## issue 5356329339 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/283

Created: 2026-08-13T06:54:54Z; updated: 2026-09-06T13:18:46Z

Exact metadata: [source record](sources/issue-5356329339-414e34844fc28695d990ba007560e4f5d9b25f52b5473217e7f0b9331dbab767.json).

**Status: Closed historical report; final behavior is not proved by its last note.** The last change corrected diagnostic input counting, not the dive itself. Keep the requirement—an unaffordable roll does nothing—in the active combined dodge work (#106).

## comment 5550162586 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/283#issuecomment-5550162586

Created: 2026-08-14T00:28:48Z; updated: 2026-08-14T00:28:48Z

Exact metadata: [source record](sources/comment-5550162586-b433bd786bc5fd510a74f7236aec8ba0becd803652dfd0376364d99237b2108b.json).

**The suppression you are asking for already exists — so before I rewrite it, one number has to become trustworthy.**

When you cannot afford the roll, the module already disables `INPUT_DIVE` every frame on control groups 0 and 2, which is Rockstar's own way of taking that move away (`beat_drunk_dueler.c:7950`, `mudtown3b.c:57928` and 18 more Story call sites). And the module's own roll is refused separately on the same condition, so it does not roll either. On paper a roll input while empty already does nothing.

Your last session shows the gate closing correctly — `gateClosed=1` whenever `affordable=0`, with hundreds of suppressed frames — but `refusals=0` throughout. That number is supposed to count "he actually pressed while empty and we refused it".

**It could not be trusted, and that is fixed here.** The refusal counter read the disabled-input buffer on group 0 only, while the suppression covers groups 0 **and** 2. A press arriving on group 2 was blocked correctly but never counted — so `refusals=0` was indistinguishable from "he never pressed while the gate was closed". Both groups are read now.

That matters because it decides which fix you need:

- **`refusals` climbs and you still dive** → the disable is being overridden or something re-enables the action, and the fix is ownership, not the gate.
- **`refusals` stays 0 while you are diving on empty** → the gate was open at that moment, meaning the affordability test disagreed with what you saw on the bar; the cost/threshold is then the target.

Two honest caveats. The gate only applies when the dodge roll feature is enabled and its stamina cost is above zero — with the feature off, vanilla's dive is untouched by design. And it deliberately never suppresses while mounted, in a vehicle or swimming, since diving there is a free vanilla move this feature does not replace.

Next time it happens, the `[roll]` heartbeat's `refusals` and `gateClosed` on the same line separate those two cases outright. Staying `actionable` — I have not proven the dive is stopped, only made the evidence capable of answering it.


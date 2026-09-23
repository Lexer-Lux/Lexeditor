# #477 — Faster Queen's Blood: skip the intro and turns with no valid move

## State (2026-09-23 impl/ff7r2-actionables pass)

- No agent-side implementation slice remains. The Data Map row
  `CardGameCommonParameter.uasset + CardGameAIParam.uasset (#477)` is
  `not-integrated` with no control, off-by-default has nothing to default
  yet, and the service exposes no card-game route. Rules are not inferred
  from field names.
- Public evidence already recorded in `plugins/ff7r2/server.py`:
  `EffectWaitTime`, `NeedCanPutCount`, player/enemy prediction fields,
  plus SDK seams (`UEndCardGameMenu._PassClass` with
  OnYes/OnNoButtonPressed, `AEndCardGame3DManager` turn visibility,
  `CardPlacementActor` state).
- Verification this pass: 66 passed across the four ff7r2 test files;
  managed service smoke passed; plugin descriptor valid. No source changes.

## Blocker (needs installed game, Lexer)

- The game's legal-move predicate (any card in hand legally placeable
  under placement cost and tile ownership).
- Automatic pass transition for a side with no valid move.
- Both-sides-no-moves match termination scored as it stands.
- Intro first-skippable-input hook for the automatic skip.

Stays `actionable`.

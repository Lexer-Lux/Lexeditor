# #472 — Make every restable bench the blue one, and require a cushion

## State (2026-09-23 impl/ff7r2-actionables pass)

- No agent-side implementation slice remains. The Data Map row
  `StateChange.uasset + StateTrigger.uasset + ActionGroup.uasset (#472)`
  is `not-integrated` with no control, and the service exposes no
  bench/cushion route.
- Public evidence already recorded in `plugins/ff7r2/server.py`: bench
  rest trigger/action rows, consumed-cushion resource, SDK seam
  `AEndFieldActionActorBenchBreak` with `BenchMeshComponent` and
  `ZabutonActorClass`, multiple bench models confirmed, and the vanilla
  distinction (ordinary blue benches free, Chocobo-stop benches consume a
  cushion) from gameplay documentation.
- Verification this pass: 66 passed across the four ff7r2 test files;
  managed service smoke passed; plugin descriptor valid. No source changes.

## Blocker (needs installed game, Lexer)

- Complete restable-placement to blue-mesh mapping.
- Inventory and state transition consuming a cushion for every valid rest,
  without changing unusable benches, vending machines, or the rest UI.

Stays `actionable`. No speculative bench/cushion control added.

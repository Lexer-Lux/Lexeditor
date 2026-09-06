# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356291792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/133

Created: 2026-08-06T02:12:04Z; updated: 2026-09-05T06:56:38Z

Exact metadata: [source record](sources/issue-5356291792-cdd2233508eff7ba0605df675351623674cc138be9f39c6395ca5a712fcef550.json).

ANIMAL TRACK GENERATION AND TRACK-LED HUNTING — find out whether tracks come
     only from live animals, from recently streamed ones, or are placed
     independently. If they can exist independently, design hunting around near
     zero incidental animal density and a lot more discoverable signs/tracks, so finding
     an animal usually starts with finding and following its tracks.


## issue 5356291792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/133

Created: 2026-08-06T02:12:04Z; updated: 2026-09-06T12:47:03Z

Exact metadata: [source record](sources/issue-5356291792-fc2be22e726ef73d710f797959fac09342448e5e858559c777ed330a6308dabe.json).

Explore low incidental animal density with hunting driven by signs and tracks.

**Status: Research incomplete.** Existing evidence does not prove that usable trails persist independently of a live animal. Prepare a controlled trail/streaming experiment before asking you to choose between native trails and custom hunting signs.

## issue 5356291792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/133

Created: 2026-08-06T02:12:04Z; updated: 2026-09-06T13:55:23Z

Exact metadata: [source record](sources/issue-5356291792-0740d997d997329f2cbe0af4b5ca339e95fcaa8b52905a0dd7aa04d493694a79.json).

Explore low incidental animal density with hunting driven by signs and tracks.

**Status: Research incomplete.** Existing evidence does not prove that usable trails persist independently of a live animal. Prepare a controlled trail/streaming experiment before asking you to choose between native trails and custom hunting signs.

## comment 5550118558 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/133#issuecomment-5550118558

Created: 2026-08-06T03:57:52Z; updated: 2026-08-06T03:57:52Z

Exact metadata: [source record](sources/comment-5550118558-967e9d517c1a3c060fc050b7748b0c021aa728c73d28ad89141123404c76e600.json).

Static research does not support free-standing ambient animal tracks. Story scripts manipulate tracking prompts/tutorials, while ordinary trails appear tied to a live or recently streamed ped; mission strings named TRACKS are not independent spoor. Near-zero animal density would probably remove the source of vanilla trails. The feature remains possible via a hidden/distant target animal whose trail is preserved until discovery, or custom signs leading to a later spawn. Before choosing, measure trail lifetime after a tagged animal streams out versus explicit deletion. Independent vanilla tracks remain unproven until that controlled probe.

## comment 5550118569 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/133#issuecomment-5550118569

Created: 2026-08-06T07:44:28Z; updated: 2026-08-06T07:44:28Z

Exact metadata: [source record](sources/comment-5550118569-2d2b45d9f435389c635fb889f2718bd0d429091235d5930abc10b7812e473bd7.json).

Static research is complete.

**What the evidence supports**
- I found no Story-script API that creates a free-standing ambient animal spoor/trail with no ped as its source. The generic `PED::REQUEST_PED_VISIBILITY_TRACKING` calls are line-of-sight tracking, not hunting spoor.
- The hunting scripts (`hunting1.c`, `act_hunting_2.c`) contain objective/dialogue strings such as `RH1_SEARCH_TRAIL` and challenge bookkeeping called `*_TRAIL`, but no independent track-placement call. Those names are UI/mission state, not evidence that vanilla spoor can exist by itself.
- `DATA_MAP.md`'s `effects/snowtracks.xml` is physical deep-surface deformation (snow, mud, sand, etc.). It can tune the appearance/persistence of footprints, but it does not provide an animal-track encounter generator or species trail.

**Design consequence**
Near-zero ambient animal density cannot safely rely on vanilla tracks: static evidence still points to tracks being an engine consequence of an extant/recently streamed animal. Viable designs are therefore:
1. keep a hidden/distant target ped alive and route the hunt toward it, allowing the engine to own its trail; or
2. create custom sign nodes/decals/props and spawn the target only near the end. This is more deterministic but is no longer vanilla spoor.

**Human/runtime check still required**
A controlled probe must tag one ambient animal, observe its trail, then compare (a) walking it beyond streaming range and returning, (b) explicit ped deletion, and (c) population suppression. Record whether the existing trail persists and for how long. That result chooses hidden-ped versus custom-sign architecture; static research cannot settle engine trail lifetime.

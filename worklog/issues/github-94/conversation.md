# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5349503760 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/94

Created: 2026-09-04T14:46:06Z; updated: 2026-09-05T06:13:33Z

Exact metadata: [source record](sources/issue-5349503760-e44cc737a4d7b00cdae660a6e03cd2276cf6524a1226c6982286c0a18d739fa8.json).

Add a Max Spell Tweak that sets the maximum stock for one spell. All draw, inventory, shared-Magic, and menu limits must use this value instead of a fixed 100. Junction scaling must reach its former maximum effect at the configured maximum stock, so lowering or raising the cap does not weaken or over-strengthen a full stack.

## issue 5349503760 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/94

Created: 2026-09-04T14:46:06Z; updated: 2026-09-06T12:46:13Z

Exact metadata: [source record](sources/issue-5349503760-a6c8abbb7245383913b3f99e2b7092a02c0e7610c6e284f77ffd4e6df73ff843.json).

A 1–255 cap and the above-127 stock repair are implemented. Full stacks should retain vanilla maximum junction strength at any chosen cap.

**Work remains:** Shared Magic is blocked with non-100 caps pending safe migration, and high-stock casting still needs a prepared game check. The original request includes that combination; the standalone cap is only a partial delivery.

## issue 5349503760 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/94

Created: 2026-09-04T14:46:06Z; updated: 2026-09-06T12:46:13Z

Exact metadata: [source record](sources/issue-5349503760-fc619157f62984517eca65f3a438af80a31814255f8fb467d8c19d7949100a00.json).

A 1–255 cap and the above-127 stock repair are implemented. Full stacks should retain vanilla maximum junction strength at any chosen cap.

**Work remains:** Shared Magic is blocked with non-100 caps pending safe migration, and high-stock casting still needs a prepared game check. The original request includes that combination; the standalone cap is only a partial delivery.

## comment 5543436797 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/94#issuecomment-5543436797

Created: 2026-09-04T16:24:08Z; updated: 2026-09-04T16:24:08Z

Exact metadata: [source record](sources/comment-5543436797-b77b5be92b6c07c674e4f0c4be96027bef5d3ad25cbcf6bcde574cbf26b4a514.json).

The Max Spell Tweak is implemented with a 1–255 cap and defaults off. The verified stock comparisons, Draw/menu clamps, and all junction scaling paths use the configured cap, so a full stack keeps the same junction strength as vanilla 100. The managed FFNx runtime also reads the cap. Shared Party Magic Inventory is deliberately blocked with a non-100 cap until that combination receives a safe migration path. Static, mutation, save, and composition checks pass. Please test drawing to the configured cap, menu display, and one full-stack junction in game.

## comment 5549900710 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/94#issuecomment-5549900710

Created: 2026-09-05T06:13:33Z; updated: 2026-09-05T06:13:33Z

Exact metadata: [source record](sources/comment-5549900710-a94580b179a9eb6a730f67468ccc575eeed3d248db6e844a5b27abcc772752bf.json).

Fixed five stock checks that treated amounts above 127 as negative. Those amounts could disappear from the Magic list or be cleared when casting. Tests now execute the patched instructions for stock from 0 to 255 and check visibility, selection, and exact stock after casting. Startup and loading a save were confirmed during the earlier short game test; the new fix still needs a battle check with a stack above 127.

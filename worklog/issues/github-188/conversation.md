# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356303792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/188

Created: 2026-08-06T04:06:21Z; updated: 2026-09-05T06:59:30Z

Exact metadata: [source record](sources/issue-5356303792-a822d56b5a4d392c57489a7160491c89d0c5238aba9509d91ff583ec6d4683c2.json).

## Goal

Split the monolithic `GameplayTweaks/script.cpp` into topic-owned source modules while continuing to ship exactly one `GameplayTweaks.asi`.

## Result

- `script.cpp` was reduced from 9,481 lines to 2,247 lines.
- Six topic modules now live under `GameplayTweaks/modules/`: collectible/map systems, world/economy, items/casings, combat/inventory, recon, and movement.
- The modules are included in dependency order into one translation unit. This preserves the existing file-local `static` state, object lifetimes, and frame-call order while allowing unrelated features to be edited in separate files.
- The concatenated extracted module bodies exactly matched the entire pre-refactor middle of `script.cpp`; no implementation bytes were lost or reordered.
- The normal project build succeeds with the same two pre-existing C4838 warnings and produces one ASI.
- Built ASI SHA-256: `69E55056160CB6D9C144097F7A502CBCDE56EC1E7A30B2E425BAAFD021C86085`.
- Installed to the closed game root and hash-verified.
- The prone/climb invariant checker now expands the module includes. Its remaining velocity invariant failure is pre-existing: the untouched pre-refactor backup and modular source fail identically.

## Test me

A normal startup smoke test is sufficient for the structural split. Confirm:

- [x] The ASI loads without a startup crash.
- [x] Collectible/map markers still appear.
- [x] Spent casings or empty-bottle handling still runs.
- [ ] Binocular/recon behavior still starts.
- [x] Stamina, prone, or climbing behavior is no worse/different solely because of the split.

No gameplay behavior was intentionally changed by this issue.

## issue 5356303792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/188

Created: 2026-08-06T04:06:21Z; updated: 2026-09-06T13:17:25Z

Exact metadata: [source record](sources/issue-5356303792-13e86df38401c7d01902b8d30eb99ed7d8cb20cea8094ab28af8752279d7b19a.json).

**Status: Closed after the structural refactor.** Topic modules replace the monolithic source while still producing one GameplayTweaks plugin. Startup and several subsystem smoke checks were recorded; no gameplay change was intended, and unrelated feature defects remain separate.

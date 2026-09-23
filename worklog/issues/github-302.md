# #302: Add interaction and card-opponent indicators

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/302)

## Requirements and decisions

- Show a distinct ordinary-interaction cue and an additional Triple Triad cue.
- The issue accepts a fixed-HUD position, so this branch does not guess field-model projection.
- The tweak is default-off and observational: it never presses a button, writes the native interaction request, or starts field script execution.

## Current implementation and evidence

PR #501 is integrated with local work and PRs #499/#500/#502.

The supported Steam English `FF8_EN.exe` was supplied privately and verified as
SHA-256 `064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`.
No executable bytes or binary dump are committed.

Executable-backed analysis establishes that field interaction selection:
- uses the player/entity table at `01D9CF88`, player index `01CD8FD0` and entity count `01D9D019`;
- filters disabled/non-talk entities, same-X/Y entities and targets outside the strict +/-256 Z range;
- uses native direction/distance helper `00477380`, native talk radii, and chooses the smallest facing error below `0x40`;
- writes Cross/Square interaction mode only after selection. This implementation mirrors the selection but never performs that write.

The field VM uses entity script base + 2 for Talk. Runtime instructions are dwords from
`01D9CF50`; the entry table is `01D9D0E4`; opcode `0x13A` dispatches to the verified
CARDGAME handler. The indicator therefore adds CARD only when the selected entity's direct
Talk-script range contains CARDGAME. Independent FF8UltimateEditor real-file tests identify
four `bghall_1` card players whose CARDGAME is directly in their `talk` scripts, which
supports this classification strategy without copying their proprietary fixtures.

A pure C++ policy harness passes locally for CARDGAME decoding, wraparound facing error,
strict Z bounds and strict talk-radius bounds. The branch also contains setting/config/UI
round-trip tests and a Windows FFNx build gate.

## Remaining acceptance boundary

- Build 35798579648 passed at f12a03d5. The downloaded DLL (`cf8aa19d233aa6cc69965ac8961759f5aadb7a1670926547e2ca07d052ad9621`) passed linked checks and compilation-input comparison before being added to the managed package. Native/UI workflow 35799144379 also passed. The user's game installation was not changed.
- Retail classifier check passed: all 37 Talk scripts from the installed `bghall_1.jsm` and matching `.sym` were passed through the compiled production classifier. Only `seito6`, `seito7`, `seito8` and `seito10` matched. Private script bytes remained in a temporary harness and were removed after the test.
- In a live game, verify ordinary targets show INTERACT, the four known Garden card players add
  CARD, out-of-range/facing-away/locked states show nothing, and Cross/Square behavior remains
  byte-for-byte native with the tweak disabled. Screenshots/logs are required for visual/runtime acceptance.

Keep the issue actionable until these delivery/runtime checks are recorded.

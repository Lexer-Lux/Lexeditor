# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286177998 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/30

Created: 2026-08-29T11:07:47Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5286177998-f8fb6aa86ad40318b0bbd628013708ddee9aa5cf40ed6496bde9080d9e736e78.json).

Lexeditor helper processes must run without opening visible command-prompt windows. This applies to startup game preparation, archive tools, validation tools, search helpers, and plugin build helpers whose output Lexeditor already captures. Errors must remain available through the owning UI or log instead of a transient console.

Acceptance:
- Launching Lexeditor and running its automatic scans opens no helper command-prompt windows.
- Captured stdout, stderr, exit codes, and timeout behavior remain intact.
- Commands that intentionally open a user-facing program are not hidden by this rule.

## issue 5286177998 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/30

Created: 2026-08-29T11:07:47Z; updated: 2026-09-06T13:06:43Z

Exact metadata: [source record](sources/issue-5286177998-fcca48b43ee339952459e76664fbd11ec1debcc6e42f92e33421795acc2443e0.json).

**Status: Implemented; needs a visible Windows check.** Background tools should stay hidden; deliberately opened applications should not.

- [ ] Fully restart Lexeditor, let game discovery finish, then open RDR1, RDR2 and Warband where installed. Confirm no command-prompt window flashes during preparation.
- [ ] Report which action produced a window, or confirm none appeared. Normal Explorer/game windows are not failures.

## comment 5462005658 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/30#issuecomment-5462005658

Created: 2026-08-29T11:11:29Z; updated: 2026-08-29T11:11:29Z

Exact metadata: [source record](sources/comment-5462005658-5aeba2abd938ab2fd7aa1d3ba2ae72fc4713f83b23b2462e0954412a9216803f.json).

Lexeditor now starts every owned background helper with the Windows no-console flag while preserving captured output and errors. This covers the RDR preparation tools, RDR2 search helper, and Warband validation/build helpers that were missing it. The source inventory confirms all 14 background launches use the silent path. Please confirm with one normal launch that no command-prompt windows flash.

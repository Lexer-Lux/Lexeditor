# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5318492637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/81

Created: 2026-09-02T01:05:20Z; updated: 2026-09-04T10:53:50Z

Exact metadata: [source record](sources/issue-5318492637-1a2799888158ae833cac2c1c8787b09957b158a7598734577e7efe9ba85c0859.json).

Helper installs are pinned. `ffnx_manager.PINNED_RELEASE` and `memoria_manager.PINNED_RELEASE` decide what Lexeditor installs. A new upstream release must not silently change the runtime.

Provide a Lexer Mode view for plugins that declare a managed helper.

For each managed helper, show:

- plugin and helper name
- the release pinned by Lexeditor
- the version currently installed in the detected game folder, when present
- the newest upstream release and its publication date
- whether the pin is behind
- a link to upstream release notes
- an inline error when the upstream lookup fails

Plugins without a managed helper do not appear.

The panel checks upstream when Lexer opens it. It intentionally ignores the normal automatic update-check interval. Keep the result for the current session unless Lexer selects Check Again. The panel is read-only and must never install or update anything.

Acceptance:

- Only managed-helper plugins appear, whether or not their games are installed.
- Pinned, installed, and newest versions remain distinct.
- The newest release includes its publication date and release-notes link.
- One failed lookup does not remove the other rows or break Home.
- Opening the panel performs its own check regardless of the shared update interval.
- Check Again forces a fresh lookup.
- No control installs or updates a helper.

## issue 5318492637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/81

Created: 2026-09-02T01:05:20Z; updated: 2026-09-06T12:38:28Z

Exact metadata: [source record](sources/issue-5318492637-09eaafb45a4cfc7dcab47e7d106e7c489716629f5f6195890668bd04afaa6689.json).

Add a read-only Lexer Mode overview for every plugin with a managed helper: pinned release, installed version and newest upstream release with date and release notes. Check on opening; Check Again refreshes. One failed lookup must not hide other rows, and nothing installs automatically.

**Status: Work remains.** This is not waiting for your testing.

## issue 5318492637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/81

Created: 2026-09-02T01:05:20Z; updated: 2026-09-06T12:38:28Z

Exact metadata: [source record](sources/issue-5318492637-9b0cb05c167231a5cbfbc77f37b27bfe0bb5ac433bc32cf8cc21f58f0eb13ce8.json).

Add a read-only Lexer Mode overview for every plugin with a managed helper: pinned release, installed version and newest upstream release with date and release notes. Check on opening; Check Again refreshes. One failed lookup must not hide other rows, and nothing installs automatically.

**Status: Work remains.** This is not waiting for your testing.

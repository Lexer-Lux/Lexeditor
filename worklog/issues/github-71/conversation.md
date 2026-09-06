# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5295106577 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/71

Created: 2026-08-31T00:09:20Z; updated: 2026-09-04T12:25:04Z

Exact metadata: [source record](sources/issue-5295106577-aed8196d34a53dc164ec137280fb37528c07b95545c22195617bb1d6442e0df8.json).

Stop RDR editor data from being extracted again when its prepared cache is still valid.

Cause found:

- The cache manifest, source archive hashes, extractor hash, file counts, and required cache files match.
- The validator then tries to parse packed and unpacked binary `.wgd` files as XML.
- That test must fail, so every plugin open treats the valid cache as stale and replaces all extracted directories.

Acceptance:

- Validate XML cache entries as XML.
- Validate packed WGD data by its real binary signature and basic size.
- Validate unpacked WGD data as a non-empty binary resource, not XML.
- The first preparation can extract missing data.
- A second preparation with unchanged sources performs no extraction and does not create another `.previous-*` directory.
- Changed source archives, extractor binaries, missing files, invalid XML, and invalid packed WGD signatures still invalidate the cache.


## issue 5295106577 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/71

Created: 2026-08-31T00:09:20Z; updated: 2026-09-06T13:16:59Z

Exact metadata: [source record](sources/issue-5295106577-ecee8a06091cdd1c054855dfc7e3d56fadc807ae0e88741bfb683c3db3d0437e.json).

**Status: Consolidated into #55, not cancelled.** The binary-versus-XML validation error was repaired so valid prepared data can be reused. The shared startup acceptance check belongs to #55; no duplicate test is requested here.

## comment 5472167087 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/71#issuecomment-5472167087

Created: 2026-08-31T00:16:14Z; updated: 2026-08-31T00:16:14Z

Exact metadata: [source record](sources/comment-5472167087-b81682582d80cac1fad0963dfe614daff8ef2de5d7479c177a19a2b972e34593.json).

Fixed the repeated RDR extraction. The cache validator was trying to parse binary WGD shop files as XML, so a valid cache always failed. It now uses format-appropriate checks. Two consecutive preparations reused the current installed cache with extraction disabled, and no new backup cache was created.

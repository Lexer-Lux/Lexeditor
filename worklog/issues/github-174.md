# #174: Casing acquisition notification

[Live issue](https://github.com/Lexer-Lux/Lexeditor/issues/174)

The requested card and icon depend on the corrected casing pickup path in #222. A source-only repair now prevents false success cards/sounds and world-prop deletion when inventory acquisition fails. Count increase confirms success. Each casing owns its transaction; cleanup prevents its credit passing to a replacement. Negative counts are rejected defensively, but the native has no documented failure sentinel. The executable harness passes and rejects four bad implementations. The existing 16 collection contracts pass.

See worklog/issues/github-222.md for exact files and remaining longarm animation boundary. No runtime installation was performed while the #151 experiment is active. Correct in-game acquisition card/icon acceptance remains unverified.

Combined development build passed: `8AE9385498F96437AFB504381F6B8E34491E3A740D8993C539D89C21B3D7BB2E`. Candidate delivery is held while #151 is active.

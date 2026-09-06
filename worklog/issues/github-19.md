# RDR1 issue #19

## 2026-09-06

Existing Items/Shops/Missions split retained. CI run [34035835307](https://github.com/Lexer-Lux/Lexeditor/actions/runs/34035835307) passed actual Chromium browser interactions and split-view checks. Six screenshots (three tabs at 1600x900 and 1280x720) were downloaded and visually inspected. All three master lists have complete last rows, 19 rows at 1600x900 or 14 at 1280x720, no master-list scroll, and no horizontal page overflow. Detail panes remain side-by-side; long details scroll independently at the smaller size.

Browser checks also pass multi-tab save preflight, decimal shop save/readback, fractional-loot rejection, discard restoring saved loot, missing optional evidence, and independent-tab recovery from corrupt loot JSON. No JavaScript page errors occurred. Existing split source-contract verifier passes.

Fixtures are synthetic and Chromium runs on Linux CI. This does not verify the user's installed WebView2 build, divider persistence/paging interactions beyond these assertions, or player acceptance. No issue closure or installed-game claim.

PR: #362. Branch: `fix/rdr1-editor-runtime-handoff`.



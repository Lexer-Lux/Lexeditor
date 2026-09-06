# Worklog: Github 15

## GitHub #15 wallet size cap — 2026-08-05

Added `[WalletCap] Enabled` and eleven hot-reloaded `RankNDollars` values. The
defaults reproduce Lexer's migrated amounts: $1/$2/$4/$7.50/$12.50/$20/$40/
$75/$150/$250/unlimited for Gambler ranks 0–10. Every 100 ms the existing cash
observer applies the Pig-mask fence multiplier first, then removes any balance
above the active cap and shows the active rank/cap in the item feed. A zero cap
means unlimited, which is the rank-10 default.

The ASI built successfully with the two pre-existing C4838 warnings and was
installed while the game was closed. Source and installed ASI SHA-256:
`DC66316AD1A53D76D364DFF1E1692D17F734A6D5B4CFAADEC1B2F4846DDCC49D`.
Source and installed INI SHA-256:
`13F0C46955B9DC9D7F9C0CF27BA7DAB7B04ECEA37865C6BCE6CD273D2BF2E4A5`.
Runtime cap enforcement and the rank transition remain unverified.


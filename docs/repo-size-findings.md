# Why the Lexeditor checkout is so large

Measured 2026-09-09 on this machine. Working tree 762 MB, `.git` 747 MB, so a
fresh clone plus checkout is roughly 1.5 GB.

| Area | Size |
| --- | --- |
| `games/rdr2` | 213 MB |
| `games/ff8` | 159 MB |
| `worklog/attachments` | 87 MB |
| `tools/rpf-cli` | 73 MB |
| `tools/magic-rdr` | 66 MB |
| `worklog/issues` | 62 MB |
| `games/warband` | 20 MB |

By file type the picture is simpler: 189 MB of PNG, 115 MB of `.bak`, 39 MB of
one `.P` binary, 10 MB of `.ytd`.

Three things account for most of it.

**Redundant FFNx backups, 115 MB, untracked.** `games/ff8/ffnx_issue_51/package/`
holds `AF3DN.P` at 38.8 MB plus three near-identical `.bak` copies of it
(`stackfail-84ba4689`, `manifest-broken`, `manifest-broken-5a67ba63`). Only the
live file is tracked in git; the backups exist solely in this working tree.
Deleting them reclaims 115 MB and loses nothing that git holds, but they belong
to the issue-51 investigation, so that is Lexer's call rather than mine.

**Icon source art, 189 MB of PNG.** Mostly RDR2 item-icon sources under
`games/rdr2/assets/item-icons`, several individual files at 1.7-1.9 MB. These
are tracked, so they are in the history permanently and deleting them now would
not shrink a clone. Worth deciding whether full-resolution sources belong in the
plugin repository or in a separate art repository going forward.

**Vendored tools, 139 MB.** `rpf-cli` and `magic-rdr` are third-party binaries
committed into `tools/`. They make the checkout self-contained at the cost of
being permanent history.

## What would actually shrink a clone

Nothing above except the untracked backups changes the 747 MB of history. Real
reduction needs a history rewrite (`git filter-repo`) moving the vendored tools
and icon sources out, which invalidates every existing clone. That is a decision
with consequences beyond disk space and is not something to do quietly.

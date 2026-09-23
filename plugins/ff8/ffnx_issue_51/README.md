# Shared Party Magic Inventory runtime

Shared Party Magic Inventory uses a pinned, GPL-source FFNx derivative. The
feature cannot use Hext alone because FF8 reads and writes each character's
Magic array through unrelated menu, battle, Draw, transfer, junction,
party-change, scenario, constructor, and save paths.

The package is built from FFNx commit
`c056db2783f376a340fcefa6a48cc33618998876`. Its manifest and Lexeditor's
hard-coded hashes must agree on the x86 driver, GPL license, complete source
patch, and build report. Lexeditor also checks the driver's PE shape and exact
runtime contract exports. A package manifest cannot approve its own files.

The runtime installs 28 guarded function hooks and four guarded call-site
patches only when all preconditions pass. Installation validates every source
instruction, prepares all writable pages before the first change, reads every
write back, flushes the instruction cache, restores page protection, and rolls
the complete set back if any step fails. A rollback or protection failure stops
the process because execution can no longer be proved safe.

The feature is off by default. The per-mod file is
`direct/lexeditor/gameplay.toml`, schema version 1. Missing, malformed,
wrong-type, unknown, or unreadable configuration disables the feature. The
disabled path installs zero issue-51 hooks.

On activation, the runtime losslessly merges all eight private inventories.
More than 32 distinct spells or more than 100 copies of a spell blocks the
activation, leaves every inventory unchanged, and shows a native FF8 warning.
After a successful activation, character zero is canonical and characters one
through seven are cleared. Save, scenario, and live-mirror operations use
explicit runtime phases so stock is not multiplied or lost.

`FFNx.shared-magic.log` is separate from the stock FFNx log. It records the
request state, installation counts, failures, hook hits, and an end-of-frame
heartbeat. A static build or log message does not prove player-visible
behavior. Final acceptance still requires an installed test and a launched
game: blocked migration, successful migration, menu/Draw/cast/junction/
transfer/party-change behavior, scenario behavior, save/reload, new game, and
the 28-function plus 4-call-site heartbeat must all be observed.

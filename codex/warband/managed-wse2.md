# Managed WSE2 contract

The initial pin is WSE2 v1.1.5.1 / Lexeditor package 1.1.5.1-lex1. The package is
bundled under `games/warband/runtime/`, not selected from latest-release metadata.
The deterministic build tool verifies the publisher ZIP and the repack digest.
Engine and Steam component bytes are unmodified; the updating launcher, servers
and PDBs are excluded. This is custom packaging, not a source-built engine fork.

Warband registers root-aware helper status/install hooks in `GamePlugin`. Home
passes its detected/selected installation root. Existing zero-argument helper
hooks remain supported for other plugins. A receipt is scoped to the resolved
game root; every managed file must also match the pin. Status is read-only.
Play performs fresh verification and serializes process creation with explicit
installation. Unmanaged or modified WSE2 binaries cannot pass launch preflight.

Installation stages/validates all package bytes before game writes, rejects
linked destinations, guards live Windows processes, takes a cross-process lock,
keeps per-transaction original-file backups and writes a durable pending journal.
Readback precedes the receipt commit. Normal failures roll back; crash recovery
is available only through explicit Install/Repair. External drift during recovery
is not overwritten. Stock game/Steam executables, saves, mods and WSE 3.x are
outside the write manifest. Existing shared WSE2 shaders/runtime files are backed
up. A separate user's WSE2 launcher remains untouched, but is not a Lexeditor
launch target.

The main-menu checker caches upstream responses, not installed state. WSE2's
latest/published/behind fields never select install bytes. Release-note navigation
is checked server-side and opens outside the privileged WebView.

Steam and achievement initialization strings occur in the pinned publisher
engine; the package carries the matching 32/64-bit Steam DLLs and AppID 48700.
This proves component retention, not actual Steam login/overlay/playtime/unlock
success. See `worklog/reference/warband-managed-wse2.md` for separate acceptance checks.

Upstream: https://github.com/Ruslan-700/WSE2-Releases/releases/tag/v1.1.5.1
Steam initialization requirements: https://partner.steamgames.com/doc/api/steam_api

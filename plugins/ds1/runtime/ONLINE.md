# Online loader and separate saves

Request: "I think you know what to make ... make it." The agreed behavior is
mod loading with multiplayer protection, a separate Cloud-compatible modded
save, bounded backups, and no cleaner or conversion back to vanilla.

- [x] Vendor the reporting protection, not the PvP gameplay changes.
- [x] Keep mod loading and merging, apply changes only in memory.
- [x] Redirect the game's specific `DRAKS0005.sl2` open to
  `DRAKS0005.lexeditor.sl2` in the same account folder.
- [x] Copy vanilla only when the modded save is absent. Never overwrite a
  modded save restored from Cloud; never convert it back to vanilla.
- [x] Keep fixed `.original.bak` and `.latest.bak` snapshots before play.
  Each save/snapshot is at most 16 MiB; staging uses one fixed `.pending.bak`.
  Backups do not match Steam's `*.sl2` rule.
- [x] Reject unsupported builds and conflicting reporting hooks before play.
- [ ] Observe in-game startup, save writes and reconnect with the candidate.
- [ ] Observe Steam upload and download of both save names on another machine.

## Source and license

Online runtime is AGPL-3.0-only. `overhaul/AntiAntiCheat.cpp`,
`AntiAntiCheat.h` and `AntiAntiCheatASM.asm` come from MetalCrow's
[Dark Souls 1 PvP Fixes and Overhaul](https://github.com/metal-crow/Dark-Souls-1-Overhaul),
commit `2a3d8cbe2acee663bef03c7be4f968dbb68f951f` (Beta36/Antiban A36).
The implementation credits MetalCrow and Ainsley Harriott. Corresponding source,
adapter and build instructions ship here; complete license is in `../credits.md`.
The sole edit to the copied implementation bounds the array-compaction loop,
which previously read one element beyond the supplied array.

The two adapter headers implement only the small patch/log API that this source
uses. No PvP changes, mode switching, UI, networking replacement or upstream save
manager are included. The online DLL also links dearxan 0.5.6, already used by
the debug loader. Its callback installs reporting and save hooks before applying
the reader's tweaks. The offline debug DLL remains available to developer tools.

Build (Visual Studio C++ Build Tools and unpacked dearxan release required):

    python plugins/ds1/runtime/build.py --online --dearxan FOLDER

Add `--check` to reproduce the shipped DLL without replacing it. The package
manifest records source and binary SHA-256, dearxan version and upstream revision.
The supported executable hash is the same as `exe_patches.VANILLA_SHA256`;
upstream assembly requires image base 0x140000000. Files on disk are never patched.

## Behavior and verification limits

The loader must be enabled for isolation and protection. Removing it makes the
game use its original filename; modded progress stays available for reinstalling.
Any other gameplay files still installed must also be restored before vanilla play.
Changing mod sets can leave references to removed content in the modded save.
Isolation starts with this installation. If the normal save was already changed
by earlier mods, it remains changed; this feature does not clean or certify it.

The native tests open synthetic saves through the real import-table hook. They
cover first copy, fresh characters, restart, bounded backups, uninstall behavior,
existing Cloud-restored contents, refusal on links/oversize/write failures and
unrelated files. A C++ fixture exercises the actual upstream report whitelist,
restoration of local flags and removal of the detection flag. This does not prove
that FromSoftware's private servers accept every custom character or item.

Steam's published DSR rules match `*.sl2` in its account save directories
([configuration](https://steamdb.info/app/570940/ufs/)); Auto-Cloud synchronizes
matching files around game sessions ([Steamworks](https://partner.steamgames.com/doc/features/cloud)).
Matching the rule is not evidence of an actual successful upload. Cloud must be
enabled and synchronized; normal Steam conflict handling still applies. The
loader uses a stable name across all mod sets so it cannot accumulate Cloud saves.

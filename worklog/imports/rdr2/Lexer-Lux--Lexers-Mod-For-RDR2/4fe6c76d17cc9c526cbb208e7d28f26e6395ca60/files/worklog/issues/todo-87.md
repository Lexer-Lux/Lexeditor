# Worklog: Todo 87

## #87 weapons stack — partial answer, 2026-08-04

Lexer asked whether he already extracted these by hand. `MyOverhaul/` contains
`weapons.ymt` (4,181,777 bytes) and `weaponcomponents.meta` (315,324 bytes) —
2 of the 11 layers. The 6 per-weapon pack_patch ymts and the remaining 3
weaponcomponents layers are absent. Enumerate the exact 9 missing filenames from
the archive index BEFORE requesting another OpenIV session.

## #87 weapon stack — complete, but one layer is a third-party file, 2026-08-04

All 11 stack files ARE present in MyOverhaul. The earlier "8 of 11" report was
mine and it was wrong: the check used `-Include 'weaponcomponents*.meta'`, which
cannot match `patch_weaponcomponents.meta`, `003_weaponcomponents.meta` or
`004_weaponcomponents.meta` because none of them START with that prefix.
Verified present: weapons.ymt, the six pack_patch per-weapon ymts,
weaponcomponents.meta, patch_weaponcomponents.meta, 003_ and 004_.

PROVENANCE (sha256 prefix):
  weaponcomponents.meta        8d1d2e84  == vanilla extract at
                               _downloads/extract/update_1_common/common/packs/base/data/ai/
  patch_weaponcomponents.meta  c7462f65  no vanilla copy on disk to compare
  003_weaponcomponents.meta    758a3e69  *** IDENTICAL to Realistic Weapon
                               Rebalance's 003_weaponcomponents.meta ***
  004_weaponcomponents.meta    af7e8ea1  differs from Rebalance's (b213410b)

So `003` is a third-party mod's file sitting in our mod. That violates the
project's never-ship-their-files rule AND means the stack baseline is not clean,
so any A/B measured against it is unsound. Replace it with a vanilla extract and
establish vanilla copies of `patch_` and `004` for comparison.

TOOLING NOTE: `_downloads/RPF8_TOOL/Rpf8Extract.exe` works.
  usage: Rpf8Extract <archive.rpf> <entry> [nested-entry ...] <output>
It successfully pulled the nested `0x800AFF13.rpf` (774,164,666 bytes) out of
`update_2.rpf`, contradicting the older note that it cannot read that archive.
Its "Distroy File:" line is a misspelled handle-close message, NOT damage —
update_2.rpf verified intact afterwards (152,046,254 bytes, mtime 2026-07-05).
Entries inside the nested archive are hashed, not plain paths, so plain-path
lookups fail; the remaining work is resolving the hashed entry name for the
weaponcomponents layers. OpenIV is installed at
%LOCALAPPDATA%\New Technology Studio\Apps\OpenIV\ if the hash route stalls.

## #87 clean baseline — CLI exhausted, needs OpenIV, 2026-08-04

The CLI route is dead for this file. `0x800AFF13.rpf` is encrypted, the extracted
blob has no RPF magic, and all four Rpf8Extract builds throw in `RPF8.Load`.
Hashed entry names are not plain JOAAT of the filename or of the full virtual
path (`003_weaponcomponents.meta` -> 0x4E9DA8BA, full path -> 0xFE71E071; neither
resolves). No vanilla copy of `patch_`/`003_`/`004_` exists anywhere on disk —
`_downloads/extract/` only ever covered base game plus update_1 common.
Settled tooling facts, including the "Distroy File" false alarm, are now in
CODEX.txt -> "Archive extraction tooling".

## #87 OpenIV blocked on the access prompt — 2026-08-04

`request_access` for OpenIV returned `user_denied` — Lexer is asleep, so the
approval dialog could not be answered. This is the permission gate working, not
a refusal to do the task. The CLI route is already proven dead (see the earlier
entry), so this genuinely needs an approved OpenIV session.

## #87 — final analysis before OpenIV, 2026-08-04

Checked whether Weapon Rebalance actually MODIFIED 003 or merely shipped a
vanilla passthrough (mods editing weapons must ship all 11 layers or they revert
Rockstar's patches, so most layers in any such mod are unmodified copies).
Its install.xml does replace all four component layers, so shipping 003 proves
nothing on its own.

Sizes tell a consistent story though:
  file                        ours     theirs    vanilla extract
  weaponcomponents.meta     315,324    307,324   315,324  (ours == vanilla)
  003_weaponcomponents.meta  12,895     12,895   (none on disk)
  004_weaponcomponents.meta  12,565      9,970   (none on disk)
Their base layer is 8 KB SMALLER than vanilla, i.e. they edit by trimming. Our
004 is 2.6 KB LARGER than theirs, consistent with ours being vanilla and theirs
being trimmed. Our 003 matches theirs byte for byte.
Most likely history: base, patch_ and 004 came from a real vanilla extraction;
003 was taken from Rebalance by mistake.

This cannot be settled without the vanilla 003. Blocked on OpenIV.

## #87 weapon stack — FINAL CORRECTION, no work remains — 2026-08-05

The repeated claim that `003_weaponcomponents.meta` was copied from Realistic
Weapon Rebalance was false. Git provenance settles it: commit `b1654849` added
`patch_weaponcomponents.meta`, `003_weaponcomponents.meta` and
`004_weaponcomponents.meta` together and explicitly records them as fresh
OpenIV exports from the game. The only transformation was mechanical naming of
hashed XML tags using already-known schemas; no reference-mod values were
copied. A later byte comparison found `003` identical to Weapon Rebalance and
incorrectly reversed the provenance. The correct inference is that Weapon
Rebalance shipped this vanilla layer unchanged.

All 11 weapon-stack files are present and mapped. The complete stack is still
required whenever the base weapon data is replaced, but obtaining or cleaning
the stack is finished. No further OpenIV extraction, approval, comparison, or
GitHub issue is needed for old item #87. The stale local Actionable entry was
removed.


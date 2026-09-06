# GitHub #99 — Bloodstain

## Requested behavior read before implementation

The live issue superseded the cash-bag bloodstain. A death had to move the
player's actual last-worn/recently-worn hat to the death location, bind the lost
cash to that hat, use the supplied bloodstained-hat map icon, and show this text
once and verbatim:

> Find your hat where near where you died and collect it to reclaim your money. If you die before then, it will be gone forever.

Picking up that hat had to restore the stored cash and immediately remove the
hat, map blip, and world marker. A second death had to permanently destroy the
previous unrecovered hat/cash before creating the new one.

## Engine evidence used

- Rockstar scripts use native `0x1F714E7A9DADFC42` to retrieve the player's
  last dropped hat. `winter1.c`, `long_update.c`, `feud1.c`, and
  `short_update.c` all use that object as the authoritative dropped hat.
- Rockstar scripts use `PED::KNOCK_OFF_PED_PROP` (`0x6FD7816A36615F48`) to
  materialize the currently worn hat as a physical object.
- `winter1.c` adds a blip directly to that hat object; `long_update.c` treats
  the same returned entity as the player's dropped hat. No guessed MetaPed
  component/model conversion was used.

## Source/data implementation

- Added `GameplayTweaks/modules/bloodstain_hat.cpp` as the issue-owned
  replacement for the legacy bloodstain block in `world_economy.cpp`.
- On each qualifying death it destroys any prior bloodstain first, queries the
  last dropped hat, asks the game to knock off the worn prop, then retains and
  relocates the returned physical hat. Its real model hash is persisted.
- If the engine takes a few frames to expose the hat, capture retries for three
  seconds. If no worn/recent hat can be captured, the just-removed cash is
  refunded instead of leaving an impossible bloodstain.
- Recovery is interaction-based, not proximity auto-award. It recognizes the
  engine consuming/attaching the dropped-hat object during native pickup and
  also supplies a nearby `Pick Up Hat` hold interaction for a model recreated
  after script restart. A successful interaction restores cash and clears all
  bloodstain state in the same update.
- Persistence is versioned as `hat-v2` and includes active state, cash,
  position, hat model, and the notification-shown bit. Legacy unversioned
  cash-bag records are not resurrected.
- The map marker uses `LEX_BLIP_HAT_BLOODSTAIN`; `MyOverhaul/blipdata.ymt`
  links that key to `lex_blip_hat_bloodstain` in `lex_blips`.
- The icon preparation pipeline validates the supplied 32x32 DDS and copies it
  byte-for-byte to the YTD input as `lex_blip_hat_bloodstain.dds`. The supplied
  PNG remains the preview/reference.
- Replaced the gold cash-bag world presentation with a subdued blood-red marker
  around the physical hat.

## Integration handoff

The integration agent must:

1. Remove the superseded block in `GameplayTweaks/modules/world_economy.cpp`
   from `struct BloodstainState` through the end of `updateBloodstain`.
2. Add `#include "modules/bloodstain_hat.cpp"` immediately after
   `#include "modules/world_economy.cpp"` in `GameplayTweaks/script.cpp`.
   Existing settings/load/death/update calls deliberately keep the same names
   and need no behavioral rewrite.
3. Run the icon preparation/YTD build so
   `lex_blip_hat_bloodstain.dds` is packaged into `lex_blips.ytd`, then perform
   the integration-owned full build, tests, install, and hash verification.
4. Classify issue 99 in the release manifest. Only after the built artifact and
   updated YTD/data are actually installed may the issue move from `actionable`
   to `test me`.

No shared dispatcher, legacy bloodstain block, release manifest, generated
knowledge index, GitHub issue state, build output, or installed file was changed
by this feature agent.

## Static verification and remaining runtime boundary

`python tools/reverse-engineering/verify_bloodstain_hat_issue_99.py` checks the
exact notification, authoritative hat natives, interaction-gated cash recovery,
one-bloodstain ordering, immediate cleanup, versioned model persistence, absence
of the cash-bag fallback in the replacement module, both supplied 32x32 assets,
the YTD input pipeline, and the blipdata linkage.

Static evidence cannot prove the game's dropped-hat interaction lifecycle,
MetaPed tint/variant survival, the rendered custom blip, cash mutation, or
cleanup across a real death/respawn. The five player-visible acceptance checks
in the live issue remain required after integration and installation.

## 2026-08-10 latest-comment triage

The latest comment reported campsite respawn selection: an activated campsite
existed, but the player remained at the ordinary respawn location. That path is
not implemented or called by `bloodstain_hat.cpp`. Campsite selection and the
"nearest activated campsite" messages are in the integration-owned campsite
death/respawn block in `GameplayTweaks/script.cpp`; the #99 module only records
the death position, captures/moves the dropped hat there, and manages hat/cash
recovery.

No #99 source or verifier was changed for that report because doing so could
not affect campsite selection and would misattribute an unrelated runtime
failure to Bloodstain. No campsite file, build/install artifact, or GitHub label
was changed in this issue-local pass.

## 2026-08-10 reported campsite-respawn failure repaired

Integration traced the report to the shared death/respawn block. After asking
Rockstar to stream the selected activated campsite, the code immediately called
the terrain probe once and treated a false result as permanent failure. A distant
campsite normally has no collision/navmesh on that first post-respawn frame, so
the configured 15-second retry window was bypassed and Arthur stayed at vanilla's
respawn point.

The immediate-abort condition was removed. The existing loop now keeps requesting
collision and retrying the safe offset until it succeeds or the full configured
window genuinely expires. The nearest-activated-site selection itself already
searched every activated campsite without a distance cap. This build still needs
the reported distant-campsite death/respawn test; the Bloodstain hat behavior also
retains its separate player-visible acceptance list.

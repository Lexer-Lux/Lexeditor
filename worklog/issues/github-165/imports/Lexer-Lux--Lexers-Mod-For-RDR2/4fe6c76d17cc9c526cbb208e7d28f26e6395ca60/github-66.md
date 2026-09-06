# GitHub #66 - Recoverable Uniques

## Failed locker-field attempt

- Preserved first-acquisition persistence, the 30-second missing grace period,
  live-world-pickup deferral, the mission exclusion, and the six requested
  Viking/Hewing/Double Bit/Hunter variants.
- The first attempted fix created the weapon inventory entry and cleared its
  full-item-data field 21, exactly matching `weapon_locker.c`'s stored state.
- The live test disproved the conclusion that this alone made a unique hatchet
  retrievable: no melee or throwable weapons appeared anywhere in the camp
  locker list.

## Root cause

`weapon_locker.c` `func_59` enumerates `ALL WEAPONS`, but rejects each entry
through `func_31` *before* it evaluates field 21 through `func_82`. `func_31`
accepts only `_0x705BE297EEBDB95D(weapon)` or `_IS_WEAPON_BOW(weapon)`. The six
hatchets fail that firearm/bow gate. Therefore the field-21 mutation really did
store the entry, but Rockstar's UI could never render or retrieve it. The prior
static verifier proved only the persistence bit and missed the earlier UI
filter; the user's empty locker list was the decisive runtime evidence.

The old ownership test also counted `INVENTORY_ITEM_COUNT > 0` as available.
That count includes the hidden field-21 entry, so the updater treated the
inaccessible staged weapon as owned and never offered another recovery path.

## Implemented correction

- A lost requested unique still waits until its matching live world pickup has
  disappeared for 30 seconds. It is then staged as a non-equipped field-21
  locker entry and persisted under `[PendingAtLocker]`; it is **not** returned
  to Arthur at that time.
- While Rockstar's `weapon_locker` script is active, a native menu prompt now
  exposes the first pending melee unique as `Recover <exact weapon name>` on
  `INPUT_GAME_MENU_EXTRA_OPTION`. Completing that hold performs Rockstar's
  inverse locker transition (`field 21 = 1`) on the exact inventory GUID. The
  weapon remains unequipped. Additional pending uniques are offered one at a
  time. Prompt ownership/input is a separate per-frame update so the existing
  one-second inventory/world scan cannot miss a menu input edge.
- The prompt is hidden and disabled everywhere outside the weapon locker and
  throughout missions. Recovery cannot happen in the field or from a timer.
- Existing hidden entries created by the failed build are migrated to pending
  at startup, so the Viking Hatchet from the reported test can be recovered
  without losing it again.
- Manual recovery still wins: a player/horse-owned entry or a live matching
  world pickup suppresses staging, and reacquiring a pending weapon clears its
  pending flag.
- Ancient Tomahawk #65 remains absent from this table and retains its separate,
  immediate-return implementation.

## Evidence and checks

- `_downloads/RDR2-Decompiled-Scripts/script_rel/weapon_locker.c` `func_59`
  builds the UI from `ALL WEAPONS`, but calls `func_31` before `func_82`.
- `func_31` admits firearms/bows only; this is why every hatchet was absent.
- `func_73` clears field 21 to store, while `func_74` sets it to 1 to withdraw.
- `python tools/reverse-engineering/verify_recoverable_uniques_issue_66.py`
  locks the missing filter evidence as well as pending persistence, locker-only
  prompting, inverse retrieval, mission exclusion, duplicate guards, the
  30-second grace, and separation from #65. All 12 checks passed.

## Acceptance boundary

Source/static checks cannot prove that the native extra-option prompt renders
over this frontend app or that setting field 21 back to 1 makes the melee weapon
available on this build. After build/install, open the camp weapon locker with
the already-hidden Viking Hatchet: the new `Recover Viking Hatchet` prompt must
appear, completing it must restore one unequipped Viking Hatchet, and reopening
the locker must not offer it again. Then repeat a full
throw/disappear/30-second cycle and confirm nothing returns before that explicit
locker action.

Integration must register `updateRecoverableUniqueLocker(ped, now,
dead || locked || postOfficeMailProtected, mission)` in the shared main loop;
the feature agent did not edit that integration-owned dispatcher.

The two shared pickup models (Hewing/Double Bit and Hunter/Hunter Rusted) keep
the existing conservative behavior: either matching live model defers both
siblings. This can delay recovery but cannot manufacture a duplicate.

## 2026-08-10 returned actionable: restore vanilla locker access first

Lexer's latest test could no longer access the weapon locker at all. The prior
implementation had two unsafe preconditions: it inserted melee weapons as
field-21 locker entries even though the vanilla app rejects melee before locker
classification, and it registered its extra prompt when the `weapon_locker`
script existed rather than after the `WEAPON_LOCKER` frontend had opened. No
runtime evidence proved either operation harmless to app launch.

The repair no longer mutates inventory when a loss matures. It persists only
the issue's `PendingAtLocker` record. Previously hidden field-21 melee entries
are treated as pending, restored through the inverse field transition, then
removed with a readback/log so they cannot poison later locker enumeration.
This preserves the already-lost Viking Hatchet as pending without returning it
to Arthur in the field.

The recovery prompt is now created/enabled only after
`UIAPPS::_IS_APP_ACTIVE_BY_HASH(WEAPON_LOCKER)` proves Rockstar's app opened;
mere script lifetime is no longer sufficient. Completing the prompt performs a
fresh duplicate guard across inventory and the live world, then gives exactly
one unequipped weapon and clears pending only after ownership reads back. Thus
the explicit action still occurs inside a successfully opened locker, but no
melee entry exists in the vanilla list before that action.

Runtime acceptance now starts with the regression boundary: an ordinary camp
locker must open normally with a pending Viking Hatchet. Only then should the
in-app recovery prompt appear and return one unequipped weapon. Reopening must
show no recovery prompt, and the full loss/30-second/pending cycle still needs a
separate test.

## fuckups.txt recurrence audit

- A hidden field-21 inventory entry is not a player-visible locker entry; the
  live locker list and retrieval result are the acceptance surface.
- Do not insert melee entries before the locker opens: Rockstar filters them
  before locker-state classification, and the previous insertion coincided
  with the whole locker becoming inaccessible.
- Do not claim the custom in-app recovery prompt rendered from registration or
  prompt-handle readback. First prove the ordinary `WEAPON_LOCKER` app opened,
  then Lexer must see and complete the named recovery action in that app.
- Never use a hash-only install comment as the answer. Explain that the standard
  list cannot admit melee without replacing/patching Rockstar's filter, and
  state exactly where the implemented recovery action should appear.

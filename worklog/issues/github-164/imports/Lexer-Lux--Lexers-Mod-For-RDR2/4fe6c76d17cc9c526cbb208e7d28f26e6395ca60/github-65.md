# GitHub #65 - Ancient Tomahawk returns on impact

## Requirement

Throw the Ancient Tomahawk and it returns to the inventory the instant it hits
the ground, a ped, or anything else. Not after a delay, not from a locker, not
at throw start. Separate from #66's generic recoverable-unique/locker path.

## Failure history and root cause

Three live builds failed. Lexer's reports, in order:

1. "i threw it into a tree and now it's no longer in my inventory and still in
   the tree."
2. "no change."
3. (dev build `9703EA02...`) "still just sits there after i throw it."

Diagnosis of the previous implementation:

- **Arming.** The first two builds armed only from `PED::IS_PED_SHOOTING`. The
  installed log contained nothing but the initialization line, proving the
  controller never reached `launch`: that native does not pulse for this
  throwable. The third build added an ownership-loss edge, which does arm, but
  it still did not return the weapon - so arming was never the only defect.
- **Impact detection (the real defect).** Both remaining signals are wrong for a
  thrown tomahawk:
  - `WEAPON::GET_PED_LAST_WEAPON_IMPACT_COORD` reports weapon-fire impacts. It
    produced no fresh coordinate for the throw in the live runtime.
  - `MISC::GET_COORDS_OF_PROJECTILE_TYPE_WITHIN_DISTANCE` (`0xD73C960A681052DF`)
    was justified in the old worklog by a claim that `rcm_bh_bandito_shack.c`
    queries it with the Ancient Tomahawk. **That claim is false.** Across
    `_downloads/RDR2-Decompiled-Scripts/script_rel/` every one of the 1087 call
    sites passes `WEAPON_THROWN_DYNAMITE` (1086) or `WEAPON_THROWN_MOLOTOV` (1).
    Zero pass a tomahawk hash. What `rcm_bh_bandito_shack.c:32346` actually uses
    for the tomahawk is the *coordinate-based* `IS_PROJECTILE_TYPE_WITHIN_-
    DISTANCE`. With that native never returning true, `sawProjectile` stayed
    false, so the `sawProjectile && !projectile` collision branch could never
    fire either. Every impact path was unreachable - hence "it just sits there".
- **The tree case is decisive.** The old code could only detect a projectile
  that *stopped existing*. A tomahawk embedded in a tree keeps existing as a
  world entity forever, so even a working projectile query would have missed it.

## Current implementation (entity-observed impact)

`GameplayTweaks/modules/ancient_tomahawk.cpp`, rewritten.

Evidence the tomahawk is directly observable as an entity:
`MyOverhaul/pickups.meta` binds `PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT` to model
`w_melee_tomahawk02` (and `..._TOMAHAWK`/`_HOMING`/`_IMPROVED` to `01`/`03`/`04`,
so the model uniquely identifies the ancient variant). The in-flight projectile
carries the same model in the object pool.

- `ancientTomahawkRefreshBaseline` (line ~124) snapshots every
  `w_melee_tomahawk02` object and pickup while the weapon is still owned, so the
  original site spawn and any other tomahawk can never be mistaken for the throw.
  The held weapon object is excluded via `IS_ENTITY_ATTACHED_TO_ENTITY`.
- Arming (line ~230) is the ownership-loss edge only. `IS_PED_SHOOTING` is gone.
- While armed, three independent impact signals are evaluated every tick
  (lines ~236-300):
  1. `ENTITY::HAS_ENTITY_COLLIDED_WITH_ANYTHING` on the tracked projectile
     object - the literal, instant collision flag;
  2. the tracked object having moved (>3 m/s) and then come to rest (<0.5 m/s) -
     this is what catches the tomahawk embedded in a tree or a ped;
  3. a `w_melee_tomahawk02` pickup appearing that was not in the baseline - the
     engine spawns `PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT` at the landing point.
  `GET_PED_LAST_WEAPON_IMPACT_COORD` survives only as a last-resort corroborator
  used when no entity was observed at all.
- `finishAncientTomahawkReturn` (line ~196) grants on the collision frame, then
  removes the world copy: the unbaselined pickup within 5 m, and, for the
  embedded case where no pickup exists, the tracked object itself.
- The module no longer reads `g_recoverUniqueWeapons`, so #65 is fully
  independent of #66. No new ini key was needed.
- A missed signal after 30 s logs `no-signal-abort` and grants nothing. There is
  still no timer/despawn/locker fallback anywhere in this file.

## Diagnostics

`GameplayTweaks.ancient-tomahawk.log` (module dir) now records:

- an init line with the resolved weapon and model hashes;
- an `idle` heartbeat every 15 s with ownership, current weapon and baseline
  sizes - a silent log now proves the module is not running at all;
- a `launch` line with the baseline sizes;
- a per-tick `scan` line while armed: `armedMs`, object count, attached count,
  tracked handle, speed, moved/collided/vanished flags, pickup count and fresh
  pickup handle;
- a `return` line naming which of the signals fired, the impact point, flight
  time, and whether `HAS_WEAPON` was true immediately after the grant.

If this build fails again, that single file identifies which stage broke without
another guess.

## Static verification

`python tools/reverse-engineering/verify_ancient_tomahawk_issue_65.py` - PASS.
Syntax-only compile (`cl /Zs` over `script.cpp`) is clean; the only warnings are
pre-existing `world_economy.cpp(85)` narrowing warnings. No build, link or
install was performed - integration-owned.

## Runtime acceptance boundary

Test all three: a ground throw, a throw into a tree/wall, and a throw into a ped
or animal. In every case the weapon should be back in the inventory on the
impact frame, no lootable duplicate should remain at the impact, and the
original world spawn (if in range) must be untouched. Also confirm another
unique weapon still follows #66's locker path rather than this one.

========================================================================
ATTEMPT 5 (2026-08-07) — the arming edge was the defect, not the impact
signal. Root cause identified from the installed runtime log.
========================================================================

## Evidence: the module ran and never armed

`<game root>\GameplayTweaks.ancient-tomahawk.log` after Lexer's "still not
working" test: 43 lines, timestamps 630308546..631626578 (~22 minutes of wall
clock). One init line, 42 `idle` heartbeats, and nothing else. No `launch`
line, therefore no `scan` line, therefore no `return` line.

Every heartbeat reads `owned=1`. Attempt 4 armed on an ownership-loss edge
(`previousOwned && !owned`), so that edge never fired once, and the entire
detection chain beneath it — all three impact signals, the grant, the pickup
removal — was unreachable. This is structurally the same failure as attempts
1-3 (fuckups.txt entry 2): a dead arming condition making every downstream
path unfalsifiable.

Secondary reading from the same log: `currentWeapon` is never 2133046983
(`WEAPON_THROWN_TOMAHAWK_ANCIENT`) at any 15 s sample — it cycles through
379542007 `WEAPON_REVOLVER_CATTLEMAN`, 2725352035 `WEAPON_UNARMED`,
3676417164 `WEAPON_MELEE_KNIFE`, 4134042714 `WEAPON_KIT_BINOCULARS`,
4111948705 `WEAPON_REPEATER_CARBINE`. The attempt-4 arming condition also
required `currentWeapon == weapon || previousWeapon == weapon`, so even had
ownership dropped, the equipped-weapon term was a second way to miss.

## Why ownership never drops: a throwable is ammo, not a weapon slot

Three independent sources, each opened and quoted:

1. `_downloads/RDR2-Decompiled-Scripts/script_rel/coachrobberies_gang3.c:30131`

       if (WEAPON::HAS_PED_GOT_WEAPON(Global_35, joaat("WEAPON_THROWN_DYNAMITE"), 0, false)
           && WEAPON::GET_AMMO_IN_PED_WEAPON(Global_35, joaat("WEAPON_THROWN_DYNAMITE")) > 0)

   Rockstar's own "does the player have a throwable to use" test. The ammo term
   is not redundant; if throwing cleared `HAS_PED_GOT_WEAPON`, it would be.

2. `coachrobberies_gang3.c:30222-30224`

       if (!WEAPON::HAS_PED_GOT_WEAPON(Global_35, joaat("WEAPON_THROWN_DYNAMITE"), 0, false)
           || WEAPON::GET_AMMO_IN_PED_WEAPON(Global_35, joaat("WEAPON_THROWN_DYNAMITE")) == 0)
       {
           if (!MISC::IS_PROJECTILE_TYPE_WITHIN_DISTANCE(
                   ENTITY::GET_ENTITY_COORDS(...), joaat("WEAPON_THROWN_DYNAMITE"), 10f, false))

   This is the shipped shape of exactly the query #65 needs: THROWN is
   `ammo == 0`, IN FLIGHT is a live projectile query, and LANDED is the
   projectile query going false. Not an object-pool handle, not an ownership
   edge.

3. `MyOverhaul/pickups.meta:3121-3145` —
   `PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT` carries `PickupFlags` including
   `KeepWeaponThatUsesThisAmmoEquipped` (:3136), and grants
   `REWARD_WEAPON_THROWN_TOMAHAWK_ANCIENT` and `REWARD_AMMO_TOMAHAWK_ANCIENT`
   as two separate rewards (:3144-3145). `REWARD_AMMO_TOMAHAWK_ANCIENT` has
   `AmmoRef AMMO_TOMAHAWK_ANCIENT` and `SatchelItem
   WEAPON_THROWN_TOMAHAWK_ANCIENT` (:4396-4400). Weapon presence and ammo
   count are two stores; only the second moves when you throw.

## The projectile native, and how it differs from the one in fuckups.txt

fuckups.txt entry 2 is about `GET_COORDS_OF_PROJECTILE_TYPE_WITHIN_DISTANCE`
(`0xD73C960A681052DF`), the ped-relative variant, which has zero tomahawk call
sites. That remains true and it is still not used here.

The coordinate-based `MISC::IS_PROJECTILE_TYPE_WITHIN_DISTANCE`
(`0xF51C9BAAD9ED64C4`, `_downloads/RDR2_SDK/SDK/inc/natives.h:3121`) is a
different native, and it *is* called with the Ancient Tomahawk in shipped code:

    rcm_bh_bandito_shack.c:32346
      MISC::IS_PROJECTILE_TYPE_WITHIN_DISTANCE(ENTITY::GET_ENTITY_COORDS(iParam0, true, false),
        joaat("WEAPON_THROWN_TOMAHAWK"), fParam1, true)
      || MISC::IS_PROJECTILE_TYPE_WITHIN_DISTANCE(ENTITY::GET_ENTITY_COORDS(iParam0, true, false),
        joaat("WEAPON_THROWN_TOMAHAWK_ANCIENT"), fParam1, true)

Signature is three separate floats, not a Vector3 (natives.h:3121).

## `baselineObjects=0` is not yet proof of anything

The attempt-4 idle line printed only the filtered count of *unattached*
`w_melee_tomahawk02` objects, so `0` could mean "pool scan broken", "model hash
wrong", or "no loose tomahawk nearby" — indistinguishable. The model hash
itself is correct: `MyOverhaul/pickups.meta:3122` binds the pickup to
`w_melee_tomahawk02` (joaat 2403651914, matching the init line), and 01/03/04
are the other variants. This build now also logs the raw pool count and the
attached count, so the next log separates those three cases.

## Changes (GameplayTweaks/modules/ancient_tomahawk.cpp, rewritten)

- **Arming is now ammo-driven.** `ammo-weapon-drop`
  (`GET_AMMO_IN_PED_WEAPON` > 0 -> 0) is primary; `ammo-type-drop`
  (`GET_PED_AMMO_BY_TYPE(AMMO_TOMAHAWK_ANCIENT)`), `ownership-lost` and
  `projectile-seen` are retained as fallbacks so no single wrong assumption can
  make the chain unreachable again. The `launch` line names which one fired
  (line ~370-386).
- **New impact signal `projectile-settled`** — `IS_PROJECTILE_TYPE_WITHIN_-
  DISTANCE` satisfied and then not, i.e. Rockstar's model. This is the one that
  covers a tomahawk embedded in a tree without needing the object pool to
  contain it at all (line ~453-457, fired at ~485).
- **The grant now restores ammo, not just the weapon** (line ~296-304).
  `GIVE_WEAPON` on a ped that already passes `HAS_PED_GOT_WEAPON` will not
  restore a thrown charge. Rockstar tops a throwable back up with
  `_ADD_AMMO_TO_PED(ped, weapon, n, 752097756)` on a ped that already owns it
  (`braithwaites2.c:36546-36548`). `752097756 == joaat("ADD_REASON_DEFAULT")`.
- Baseline is refreshed only while a charge is demonstrably held, so an already
  embedded tomahawk can no longer be absorbed into the baseline (line ~360-364).
- Object pool buffer 1024 -> 4096, and the raw returned count is logged.
- `scan` line rate-limited to 100 ms so one throw cannot flood the file.

## Diagnostics contract for the next log

- **Never armed** — only `idle` lines. Read `ammoWeapon` / `ammoType` /
  `owned` / `projNear` across the throw. Whichever moves is the real signal; if
  none of the four move, an ASI cannot observe the throw and this is the
  unfeasibility evidence.
- **Armed but no impact** — `launch`, then `scan` lines, then
  `no-signal-abort`. Each scan line prints `collided`, `speed`, `moved`,
  `vanished`, `projNear`, `sawProjectile`, `settled`, `freshPickup`
  independently.
- **Impact seen but grant failed** — a `return` line with `grantOk=0` plus
  `ownedBefore/After` and `ammoWeapon`/`ammoType` before->after.
- `rawObjects` / `attached` in the idle line settle whether the pool scan and
  the model hash work at all.

Log is still truncated once per launch and still carries the 15 s idle
heartbeat.

## Not done in this pass

No compile, link, install or ASI copy — static checks only, per scope. No
commits, pushes or label changes. Requires a build + install before the next
runtime test.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-09 staged startup-crash isolation

The guarded first-half progressive build survived every group through
recoverable uniques, then raised `ERROR:FFFFFFFF` after Ancient Tomahawk
activation while still held before Hunter Hatchet. The activation heartbeat
reported `owned=1`, `ammoWeapon=1`, `ammoType=1`, but
`currentWeapon=2725352035` (`WEAPON_UNARMED`).

Source inspection found that `held` meant "has any Ancient Tomahawk ammo," not
"is holding the Ancient Tomahawk." Consequently ordinary unarmed startup ran
the coordinate projectile query every frame and rebuilt the full object and
pickup-pool baselines every 500 ms. Even the first idle heartbeat performed an
extra object-pool scan. None of those operations was relevant until the player
actually equipped or threw this weapon.

The controller is now dormant while merely owned. Projectile observation runs
only while the Ancient Tomahawk is equipped, was equipped on the prior tick, or
a throw is armed. Baselines refresh once on equip or charge restoration rather
than periodically, and the idle heartbeat is read-only with no world-pool scan.
The impact, grant, duplicate-cleanup, and mission-independent #65 behavior are
otherwise unchanged.

The next full-build launch confirmed the new idle contract in its live log:
`monitoring=0 equipped=0 baselineObjects=0 baselinePickups=0` while the player
was unarmed. The game still aborted after later full-pipeline mutations, so the
startup crash had more than one surviving causal window; this result does not
re-attribute that later abort to #65.

## 2026-08-10 returned-world-copy correction

Lexer confirmed the impact-frame inventory return but also saw the thrown
tomahawk remain as a visible, marked, unlootable world duplicate. The source-only
correction removes a newly spawned pickup near the observed impact and deletes
the tracked unbaselined projectile object when it remains embedded. It never
deletes a pre-existing baseline object or the original world spawn. A successful
post-grant readback now also posts `Ancient Tomahawk returned` through the
vanilla-style acquisition feed. This correction is not accepted until the
combined build is installed and the ground, wall/tree, and ped impact cases are
tested.

## 2026-08-10 delayed world-copy/feed repair

Lexer's combined-build test showed that the preceding correction still left
the impact tomahawk and its map marker in the world, and posted no acquisition
feed, even though the inventory charge returned. The defect was the single
same-frame cleanup/readback in `finishAncientTomahawkReturn`: RDR2 can convert
the projectile into its loose object/pickup after that call, and the successful
inventory readback used to gate the feed could also lag the grant by a tick.

The impact-frame grant remains immediate. After it, the module now keeps a
bounded 2.5-second cleanup observer that repeatedly removes any unbaselined
Ancient Tomahawk pickup within 5 m of the recorded impact and deletes any
unbaselined loose `w_melee_tomahawk02` object there. It also retains the exact
tracked object/pickup handles across the engine's conversion boundary. Held
weapon props are excluded by attachment and all pre-existing baseline handles,
including the original world spawn, remain protected. Each removal receives an
existence readback and the log reports removed/deleted/remaining counts.

The acquisition feed is now posted once on a later tick after both weapon
ownership and positive ammo-in-weapon are observable. It is no longer
suppressed by a stale same-frame grant readback. This remains unaccepted until
an integrated build proves that ground, ped and wall/tree impacts leave no
world copy or map marker and show exactly one return feed.

## 2026-08-10 recurrence audit: owned charge but no hash-level equip

- Read `fuckups.txt` before editing the detector again.
- The retained session after Lexer's latest comment ran 16,078 updater ticks with `owned=1`, `ammoWeapon=1`, `ammoType=1`, `everArmed=0`, and no Ancient Tomahawk current-weapon hash. The only heartbeat weapon hashes were unarmed and binoculars. Therefore no impact/cleanup path executed in that session.
- Do not broaden the expensive projectile or object-pool scans back to every owned frame. Resolve the missing equip/throw observation through Rockstar's current weapon-entity handle and the exact Ancient Tomahawk model, and retain the existing dormant-while-unarmed contract.
- The current weapon-entity is used only to open the bounded exact-projectile observation window when its model is `w_melee_tomahawk02`. `IS_PED_SHOOTING` remains forbidden because prior evidence proved it does not pulse for this throwable. The existing exact projectile edge, not ordinary gunfire, arms the return.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## 2026-08-10 exact held-entity detector and installed build

- The retained runtime log proved the return controller ticked 16,078 times but never armed: inventory reported the Ancient Tomahawk owned with one charge, while the current-weapon hash exposed only unarmed and binocular states. No launch, impact, return, cleanup or feed path ran.
- The detector now reads `GET_CURRENT_PED_WEAPON_ENTITY_INDEX` and recognizes only an actually held entity whose model is `w_melee_tomahawk02`, the Ancient Tomahawk model bound by the shipped weapon and pickup data. That exact entity signal opens the existing bounded projectile observation window and is retained for one transition frame.
- `IS_PED_SHOOTING` remains forbidden and absent because the prior throwable probe disproved it. Merely owning the charge still does not activate global object or pickup scans.
- The combined development ASI `A614960C71F38EA257D773955F61797DA0B16CEF53F119FC4C4BC8EDA525B428` was installed with RDR2 closed; source and game-root hashes matched. GitHub #65 moved from `actionable` to `test me` only after that installed-hash verification.
- Runtime acceptance remains: initial pickup/equip, then ground, wall/tree and ped throws must each return one inventory charge, leave no duplicate object or map marker, and post exactly one acquisition feed. The expanded log distinguishes held entity/model, projectile edge, grant, delayed cleanup and feed stages.

## 2026-08-11 returned world-copy root cause

Lexer confirmed the inventory return fires on impact, but the thrown item and
its map icon remain. Before code, `fuckups.txt`, the live issue, this worklog,
and the current cleanup source were read again. No new impact native or guessed
coordinate was introduced.

The defect was in the already-running cleanup, not the return signal. When
`projectile-settled` fired without a tracked object handle, the code stored the
player's position as the impact position. Cleanup then ignored every new
Ancient Tomahawk pickup/object more than five metres from that position. A
tomahawk thrown into a wall or tree farther away was therefore intentionally
excluded even though its inventory charge had already returned.

A second late-conversion race could preserve the same duplicate. During the
2.5-second cleanup observer, restoration of the held charge could trigger a new
baseline snapshot. If Rockstar materialized the loose object/pickup around that
transition, the snapshot classified the returned copy as pre-existing and the
cleanup would never delete it.

The repaired ownership boundary is the per-throw baseline itself. The baseline
was captured while the charge was still held, so every later unbaselined loose
`w_melee_tomahawk02` object or pickup belongs to this throw; attached held props
remain excluded by the pool scan. Cleanup now removes those unbaselined copies
without a fabricated distance gate. Baseline refresh is disabled for the
entire cleanup window, so a delayed projectile-to-pickup conversion cannot be
absorbed. Original pre-placed world copies remain protected by their baseline
handles.

Static checks passed:

```
python tools/reverse-engineering/verify_ancient_tomahawk_issue_65.py
PASS: #65 Ancient Tomahawk uses entity-observed impact return and is separated from generic recovery

python -m py_compile tools/reverse-engineering/verify_ancient_tomahawk_issue_65.py
PASS

git diff --check -- GameplayTweaks/modules/ancient_tomahawk.cpp tools/reverse-engineering/verify_ancient_tomahawk_issue_65.py worklog/issues/github-65.md
PASS
```

No dispatcher change is required; #65 is already included. Integration must
build/install the combined artifact. Runtime acceptance remains ground,
wall/tree, and ped impacts: immediate inventory return, no loose item, no map
icon, and exactly one acquisition feed. Static checks cannot establish those
player-visible results.

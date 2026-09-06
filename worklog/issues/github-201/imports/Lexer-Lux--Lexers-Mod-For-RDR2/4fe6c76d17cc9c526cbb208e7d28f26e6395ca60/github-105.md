# GitHub #105 - Remove child invincibility in free roam

## 2026-08-10 safe mechanism conclusion

- No safe Story-native or entity-local mechanism was resolved. Story's
  `short_update.c` identifies each ready-to-render child with `_IS_PED_CHILD`,
  then applies invincibility, rejects entity damage, and enables every proof.
- The public entity-local experiment changed the damage/proof readbacks, but
  the engine still rejected the child as a crosshair target. A real attack then
  aborted through `ERROR:FFFFFFFF`; those readable fields are not the final
  child-hit acceptance layer.
- Kill Children v1.1 proves the requested player-visible result is possible,
  so this is not an absolute engine-feasibility conclusion. Its only resolved
  mechanism is two process-wide engine-predicate detours, however. The #114
  runtime regression proved those predicates also own normal clerks, shops,
  stations, and paperboys. Those interactions exist in ordinary free roam, so
  toggling the detours off only for missions cannot scope them safely.
- No authoritative per-call child entity was resolved at either predicate
  boundary. Treating an unknown argument as a ped and conditionally forwarding
  would be another ABI guess with process-wide blast radius, not an entity-local
  repair.
- Removed the dormant hook installer from
  `GameplayTweaks/modules/child_vulnerability.cpp`. The existing integration
  entry points now install zero hooks, perform zero entity writes, and emit a
  bounded 30-second heartbeat plus mission/blocked gate changes. Rockstar's
  protection therefore remains intact in missions and blocked contexts.
- This source state does not implement #105 and has no in-game acceptance claim.
  It was intentionally made incapable of silently reinstalling the #114 shop
  regression if the old INI setting is enabled.

### Issue recommendation

Recommendation: remove `actionable`, add `needs a human`; do not use `test me`
or call the request unfeasible. Further work needs an explicit architecture
decision or new primary evidence for a truly entity-local child-hit predicate.
The unsafe reference hooks must not be resurrected as the default or combined
GameplayTweaks implementation.

## Evidence

- Live acceptance requires ambient Saint Denis street children to take damage
  in ordinary free roam while Jack and other children in missions retain their
  scripted protection.
- Native `0x137772000DAF42C5` is named `_IS_PED_CHILD` in the native database; it
  is a direct engine classification rather than a model-name approximation.
- `GET_MISSION_FLAG` (`0xB15CD1CF58771DE1`) is the existing project-wide
  mission gate. The module returns before enumerating or mutating children when
  that flag, an integration-owned blocked state, a missing player ped, or death
  is present.
- Rockstar scripts commonly pair `SET_ENTITY_INVINCIBLE(ped, false)` with
  `SET_ENTITY_PROOFS(ped, 0, false)`. The entity API additionally exposes
  `SET_ENTITY_CAN_BE_DAMAGED` and `_GET_ENTITY_CAN_BE_DAMAGED`; all three
  protections matter here.

## Implemented

- Added `GameplayTweaks/modules/child_vulnerability.cpp` with a bounded nearby
  ped scan every 100 ms.
- Only live peds positively identified by `_IS_PED_CHILD` are changed.
- In free roam it enables `CAN_BE_DAMAGED`, clears invincibility, and clears
  the entity proof bitset. It does no work in missions or blocked states.
- The first application to each streamed handle writes its model and
  `_GET_ENTITY_CAN_BE_DAMAGED` readback to
  `GameplayTweaks.child-vulnerability.log`.
- Added `tools/reverse-engineering/verify_child_vulnerability_issue_105.py`.

## Integration handoff

Include the module, call `initializeChildVulnerability()` once after the module
path is known, and call
`updateChildVulnerability(ped, now, mission, blocked)` once per frame. Remove
the old inline `lastChildTick` block in `script.cpp` and its timer variable;
otherwise the module and legacy code would duplicate the same scan. The feature
agent did not edit the integration-owned dispatcher, build, or install.

## Validation

- `python tools/reverse-engineering/verify_child_vulnerability_issue_105.py`
  passed.
- `git diff --check` passed for all issue-owned files.

## Runtime acceptance still required

- In free roam, damage an ambient Saint Denis street child and confirm health
  loss/death rather than animation-only reactions. Confirm the log says
  `damageable_after=1` for that model.
- Start or replay a mission involving Jack or another child and confirm the
  child remains protected and the module adds no new log entry while the
  mission is active.

## Crosshair follow-up

The installed pass cleared damageability, invincibility, and proofs, but a
separate ped targeting flag still disabled the player's crosshair. Free-roam
scanning now also calls `SET_PED_CAN_BE_TARGETTED(child, true)`. Mission and
blocked-state gates remain first.

## Returned test: no child was ever reached

- Lexer tested the installed pass against Saint Denis street children and
  reported both that the crosshair still disabled and that nothing changed.
- The installed runtime log at
  `GameplayTweaks.child-vulnerability.log` contained only its header after that
  test. It had no `ped=...` record at all. Therefore the prior nearby-ped scan
  and `_IS_PED_CHILD`-only filter never reached a target; the earlier targeting
  follow-up could not affect the tested children.
- Replaced the failed 32-entry nearby-ped query with the project's established
  160-entry streamed-ped enumeration, bounded to 100 metres of the player.
- Retained `_IS_PED_CHILD` as the primary classifier and added explicit
  fallbacks for the three ambient street-child archetypes present in shipped
  data: `A_M_Y_NBXSTREETKIDS_01`, `A_M_Y_NBXSTREETKIDS_SLUMS_01`, and
  `A_M_Y_SDSTREETKIDS_SLUMS_02`. These names are present in
  `_downloads/RDR2-Unhashed-Strings/MemberNames.txt` and the corresponding
  ambient entries are present in the shipped loot-table data.
- Added the player-specific targeting gate
  `SET_PED_CAN_BE_TARGETTED_BY_PLAYER(child, PLAYER_ID(), true)` alongside the
  general ped gate. The native and its hash `0x66B57B72E0836A76` are declared
  in the local RDR2 SDK. The module reapplies both every scan because game
  scripts may restore protection state.
- Mission/blocked-state handling is still the first gate, before enumeration or
  any mutator, so mission children remain untouched by this module.
- Runtime logging now records whether classification came from the native or
  ambient-model fallback, plus both requested targeting layers. Those targeting
  values are requests, not readbacks; the SDK exposes no matching getters.

## Root cause of the repeated failures (decompiled-script pass)

Grepped `_downloads/RDR2-Decompiled-Scripts/script_rel/` for the whole child
protection path. Findings:

- `short_update.c` `func_150` (lines 5186-5196) is the **only** place in the
  shipped Story Mode scripts that protects children. For each ped tracked in
  `Global_1945917.f_8`, once `IS_PED_READY_TO_RENDER` (`0xA0BC8FAED8CFEB3C`)
  and `_IS_PED_CHILD` are both true it calls
  `SET_ENTITY_INVINCIBLE(true)`, `SET_ENTITY_CAN_BE_DAMAGED(false)` and
  `SET_ENTITY_PROOFS(255, false)`, then clears the slot.
- Peds enter that list in `func_168` (line ~5735) from a ped-created event,
  and only when `IS_ENTITY_A_MISSION_ENTITY` is false; `CS_JACKMARSTON` and
  `CS_JACKMARSTON_TEEN` are explicitly skipped.
- That protection pass runs **after** the ped becomes ready to render. Any
  one-shot write from this module can therefore be silently overwritten later
  and never restored. The previous implementation memoised each ped in
  `g_childVulnerabilityLogged` and never wrote to it again — so even a
  successful write could be undone by Rockstar's own pass.
- No shipped script calls `SET_PED_CAN_BE_TARGETTED` or
  `SET_PED_CAN_BE_TARGETTED_BY_PLAYER` for a child at all
  (`SET_PED_CAN_BE_TARGETTED` appears 1705 times in `script_rel`, always for
  mission/anim-scene peds; `SET_PED_CAN_BE_TARGETTED_BY_PLAYER` appears once).
  The reticle rejection for children is therefore **not script-applied**.
- The SDK exposes no native that changes a ped's child classification.
  `_IS_PED_CHILD` (`0x137772000DAF42C5`) is a read-only engine query.

Additional defects in the previous implementation, independent of the above:

- **The reported ped was never a candidate.** The Annesburg/Saint Denis
  paperboy is `S_M_Y_NEWSPAPERBOY_01` (model string present throughout
  `script_rel`; `main.c:3263` suppresses it by name). It was not in the
  three-model fallback list, so if `_IS_PED_CHILD` did not classify him the
  module skipped him entirely. `A_M_Y_NBXSTREETKIDS_02`,
  `U_M_Y_SHACKSTARVINGKID_01` and `G_M_M_UNILANGSTONBOYS_01` were also absent.
- **The staging almost certainly never completed.** The module required the
  same ped to remain the single nearest child for 5000 ms and then applied one
  native per 250 ms scan — about 6.3 s of standing still next to one child with
  no other child becoming nearer. In ordinary play the candidate resets and
  nothing is ever written. This matches the empty runtime log.
- Only the single nearest child was ever touched, never the others streamed in.

## Current pass

Rewrote `GameplayTweaks/modules/child_vulnerability.cpp`:

- All five mutators now live in one `childVulnerabilityApply` helper
  (lines 50-56) and are re-applied **every 250 ms scan**, so Rockstar's
  ready-to-render pass cannot leave a child permanently protected.
- Removed the 5 s candidate-stability staging and the one-shot
  `g_childVulnerabilityLogged` memo entirely.
- Applies to every classified child within 100 m, bounded to 8 per scan so one
  frame never rewrites the whole streamed set.
- Model fallback expanded to the seven ambient archetypes above
  (lines 33-41), including `S_M_Y_NEWSPAPERBOY_01`.
- Added `IS_ENTITY_A_MISSION_ENTITY(child)` as a second safety gate, mirroring
  Rockstar's own exclusion, so scripted children stay protected even if the
  mission flag is briefly clear.
- Diagnostic: for the nearest child, at most once per 2 s, one `before` line
  and one `after` line record model, distance, engine-vs-model classification,
  `_GET_ENTITY_CAN_BE_DAMAGED`, `_GET_ENTITY_PROOFS`,
  `IS_PLAYER_TARGETTING_ENTITY`, and `GET_PED_CONFIG_FLAG` for the twelve
  indices the shipped scripts most often set adjacent to a
  `SET_PED_CAN_BE_TARGETTED` call. Those twelve are logged, never written.

## Native-surface limit on the crosshair

The targeting rejection is engine-side. Proof: no shipped script applies any
targeting restriction to a child ped, yet the restriction is present in-game;
and the only script-visible levers, `SET_PED_CAN_BE_TARGETTED` and
`SET_PED_CAN_BE_TARGETTED_BY_PLAYER`, did not lift it. This establishes only
that the native-only implementation cannot work. It does not establish that the
feature is unfeasible: an engine hook can replace the internal predicate that
the public native surface does not expose.

## Static validation after returned test

- `python tools/reverse-engineering/verify_child_vulnerability_issue_105.py`
  checks streamed enumeration, all three data-backed models, both targeting
  calls, the damage layers, and ordering behind the mission gate.
- This source pass was not built, installed, or represented as in-game proof by
  the feature agent.

## 2026-08-09 repeated-mutation startup crash repair

Two consecutive startup-crash sessions loaded beside the same Saint Denis child
model `0x0FC40064` at 25.7 m. The first session still contained the 4 Hz pause-map
focus poll; the next build removed that poll and its log remained at
`focusWrites=0`, but Rockstar produced the same no-dump `ERROR:FFFFFFFF` again.

In the second run, child-vulnerability was the final logged mutation. Its
readback already said `damageable=1 proofs=0`, yet the module applied all five
damage/targeting setters again. Source inspection showed this was not merely the
2-second diagnostic: every 250 ms scan rewrote every streamed child, and the
diagnostic added another application. The same ped was therefore mutated dozens
of times during the few seconds between startup release and the abort.

Blind reapplication was removed. A `(ped, model)` registry applies targetability
once per live ped. Later scans first read damageability and proofs; they perform
another write only if those readable values prove Rockstar restored protection.
The mission, mission-entity, classification, distance and eight-per-frame safety
gates remain. Every actual mutation logs a before/after readback and whether it
was the first application or a returned-protection repair.

`verify_child_vulnerability_issue_105.py` now rejects a periodic diagnostic
reapplication timer and requires the first-application/readback gate. It and the
startup, #14 and #94 verifiers pass. Development ASI
`0064A7C4F446693A72F7472C0B17154B0A631C58678D999F50097A65AFC8FAB4`
built successfully and was installed after RDR2 exited. Source/game-root ASI
and project/game-root manifest hashes match. The feature remains
runtime-unconfirmed.

### Causal attribution retracted

The `0064...` correction did not stop the startup abort. On the next run the
module performed one legitimate first application to a newly protected child
(`damageable=0 proofs=255` before, `damageable=1 proofs=0` after), with no blind
repeat before the error. The game still aborted roughly three seconds after the
whole update pipeline started. Therefore the previous final-log ordering did not
prove #105 caused the asynchronous failure. The state-driven repair remains a
valid removal of redundant native writes, but #105 is no longer being identified
as the crash source without the hard pipeline bisect.

## 2026-08-09 action-triggered native failure and removal

The hard pipeline bisect later removed the unrelated owned-gear scanner and
produced a normal build that ran for more than five minutes. In that stable
session Lexer aimed a thrown weapon at the Saint Denis newspaper boy. The log
shows model `0x111A98CA` (`S_M_Y_NEWSPAPERBOY_01`) had been changed from
`damageable=0 proofs=255` to `damageable=1 proofs=0`; when the attempted attack
completed, Rockstar displayed `ERROR:FFFFFFFF` and stopped the ScriptHook
fiber. This is the exact player-facing acceptance path #105 exists to enable,
not an idle-startup correlation.

The public native surface could not satisfy the requested feature safely. The
two targetability writes never made Rockstar accept an ordinary weapon
crosshair, while forcing the damage/proof state allowed the attempted hit to
enter an engine-owned child path that aborted. The per-ped native implementation
was therefore removed from the live translation unit. This failure applied to
that implementation, not to engine-level detours.

## 2026-08-09 established-mod correction and engine-hook port

Lexer supplied the existing Nexus `Kill Children` mod as direct counter-evidence
to the `unfeasible` verdict. Version 1.1 was downloaded only for static analysis:

- Archive SHA-256:
  `C49CD3A80A8E860ECA8BBEE2925F03EE33EAAC89192DC49D09A92BA49DF48CB0`
- `kill_children.asi` SHA-256:
  `E74B39A47A60EBE2C0FC99AD030FF26382FAF70F79D0822E7951590F6E69A531`
- Windows Defender reported no threats. The unsigned reference binary was
  never installed or executed.

Static disassembly showed two MinHook detours and no ScriptHook/native imports.
The first resolves an internal flag-query function through
`BA 18 E6 A7 BA 48 8B CF E8 ?? ?? ?? ?? 84 C0 75 17`, forwards every query
except hash `0xE4401C70`, and returns false for that one flag. The second resolves
an internal child blood-effects predicate through
`E8 ?? ?? ?? ?? 84 C0 75 78 48 3B 5F 08` and returns false. This is why the
established mod lifts both the engine-owned attack rejection and the separate
blood suppression without rewriting live ped entity state.

Read-only scanning of the current loaded `RDR2.exe` found each signature exactly
once, at RVAs `0x6C9CDF` and `0x9C45C0`; their relative calls resolved to RVAs
`0xB49AD0` and `0x1426370`. The on-disk executable did not expose these decrypted
code signatures, so runtime scanning is required.

`child_vulnerability.cpp` was replaced with a port of those two predicate
detours. It verifies unique matches inside the loaded `.text` section, uses
vendored MinHook 1.3.4, performs no ped enumeration or native mutation, and
gates both detours with an atomic free-roam flag. During missions, fades,
loading, disabled player control, and custom menus, both detours forward to the
original engine functions. `verify_child_vulnerability_issue_105.py` requires
the two signatures, mission/blocked gating, MinHook build inputs, and rejects
all six prior per-ped mutation/enumeration paths.

The combined ASI built successfully with SHA-256
`9D66086D0FE44AF89EBA2FBFFFEAE760BB676C49D75940FC32E437B3EFAB9C53`.
RDR2 was still running, so this build was not installed and #105 correctly
remained `actionable`.

## 2026-08-10 process-wide hook rollback

The reference ASI detours were ported as process-wide predicates. In the live
build they still did not make the paperboy targetable, while the same interval
lost ordinary clerk prompts, shop minimap icons, and shop-script ownership. The
port therefore failed its requested behavior and had an engine-wide regression
surface.

`[ChildVulnerability] Enabled=0` now defaults off and prevents either MinHook
detour from being installed. This is a safety rollback, not completion of #105;
the issue remains actionable until the mechanism can be scoped to the actual
child ped under evaluation without affecting ordinary world interactions.

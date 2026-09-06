# GitHub #64 - Remove world-collectible masks

## Proven scope

The active Bandit strand assigns masks at ranks 1-3 and 5-9. Its eight exact
reward records are:

1. `KIT_MASK_METAL`
2. `CLOTHING_ITEM_MASK_PIG_001`
3. `KIT_MASK_BLACK_HOOD`
4. `KIT_MASK_BROWN_SACK`
5. `CLOTHING_ITEM_SKULLMASK_MR1_002_1`
6. `KIT_MASK_PSYCHO`
7. `CLOTHING_ITEM_SKULLMASK_MR1_000_1`
8. `CLOTHING_ITEM_SKULLMASK_MR1_001_1`

Only four of those eight are fixed discoverable-world pickups in Rockstar's
Story scripts. `discoverable_generic_corpse.c` and
`discoverable_generic_carriable.c` both prove the same scenario-to-item map:

| Scenario brain | Internal discoverable | Granted item | Authored position |
|---|---:|---|---|
| `WB_DISCO_PIG_MASK` | `-763376358` | `CLOTHING_ITEM_MASK_PIG_001` | `2545.93, 800.34, 77.013` |
| `WB_DISCO_PAGAN_RITUAL` | `-739986731` | `CLOTHING_ITEM_SKULLMASK_MR1_001_1` | `-2904.945, -254.221, 187.3` |
| `WB_DISCO_CAT_MASK` | `1801731633` | `CLOTHING_ITEM_SKULLMASK_MR1_002_1` | `2286.46, -727.94, 42.98` |
| `WB_DISCO_RAM_MASK` | `1490223565` | `CLOTHING_ITEM_SKULLMASK_MR1_000_1` | `-5151.3, -2118.4, 13.0` |

The four `KIT_MASK_*` rewards do not appear in either discoverable grant map.
`KIT_MASK_GREY_CLOTH` is not a Bandit reward and must remain untouched.

## Implemented source boundary

`common/data/ai/scenarios/discoverables.meta` binds each of the four scenario
brains to the generic discoverable script, but the scenario point owns more
than the inventory grant. In particular `WB_DISCO_PAGAN_RITUAL` owns the corpse,
attack volume, journal/map discovery, and ritual presentation as well as the
Pagan Skull Mask. Deleting or disabling that scenario point would remove the
site rather than only the mask. Marking the discoverable complete would also
falsely mutate save progress. Polling inventory and removing a newly granted
mask would leave a takeable world object and would not satisfy this issue.

The decompiled scripts prove the narrower interaction-entity hook. They create
the mask as a separate carriable entity with `PED::_0x9641A9A20310F6B8`, then
grant the clothing item only after `PED::_GET_CARRIER_AS_PED(mask) == Global_35`
through `func_73(func_72(...))`. Their exact spawned model hashes are:

| Mask | Spawned model hash |
|---|---:|
| Pig | `1057717101` |
| Pagan Skull | `-1822543706` |
| Cat Skull | `-342606109` |
| Ram Skull | `-987312756` |

`GameplayTweaks/modules/world_collectible_masks.cpp` enumerates world objects
only while the player is within 150 m of one of the four sites and deletes an
entity only when both its exact model and a 2 m authored-position boundary
match. This removes the carriable acquisition entity before it can have a
player carrier. It never mutates inventory, discoverable completion, scenario
points, map assets, corpses, journals, or any other mask. Existing-save
ownership therefore remains untouched.

This issue-local module is intentionally unregistered pending integration.
The integration agent must include it and call
`tickWorldCollectibleMaskRemoval(player, now)` from the shared dispatcher.

Focused static verification:

```text
python tools/reverse-engineering/verify_world_collectible_masks_issue_64.py
PASS: #64 suppresses only four exact carriable models at their authored positions
```

## Acceptance once the missing mechanism exists

- The Pig, Pagan Skull, Cat Skull, and Ram Skull masks have no take prompt and
  cannot be acquired at their fixed locations before their Bandit rank reward.
- The four locations and the Pagan Ritual journal/discovery still function.
- Completing Bandit ranks 2, 6, 8, and 9 grants the corresponding mask.
- Saves that already own any of the four masks retain them.
- The four `KIT_MASK_*` Bandit rewards and every non-reward mask, including the
  Grey Cloth Mask, are not removed by this issue.

## 2026-08-10 returned actionable: deletion raced Story-script respawn

Lexer correctly rejected the prior `test me` transition because no runtime
evidence showed that any acquisition entity had actually stayed removed. The
implementation also contradicted the decompiled lifecycle it cited:
`discoverable_generic_corpse.c` creates the carriable inside
`if (!DOES_ENTITY_EXIST(handle))`. Deleting our copy of that entity made the
Story script recreate a fresh takeable mask on its next tick. A 100 ms deletion
poll therefore created a recurring pickup window rather than a persistent
suppression.

The issue-local module now retains the exact model-and-position-matched entity
so the owning Story script continues to see a valid handle, but makes that mask
invisible, non-colliding, frozen and relocates it 50 m below its authored point.
It never takes mission ownership or deletes the handle. A postcondition checks
both invisibility and displacement before marking that source suppressed. The
module remembers each exact entity, resumes scanning if streaming destroys it,
uses the full 4096-entry object pool, and scans at 25 ms only while the player is
near an unsuppressed target. A 15-second heartbeat distinguishes module-not-run,
never-near, scanning-with-no-match, and successful suppression.

This remains runtime-unaccepted. Each of the four sites must log `ok=1`, lack a
take prompt, and still preserve its surrounding discoverable/corpse/journal
behavior; challenge rewards and already-owned saves remain separate acceptance
checks.

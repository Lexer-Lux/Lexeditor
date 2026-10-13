# Repair, shops and the bonfire repair option

Measured by read-only inspection of the Steam Remastered install (executable
SHA-256 `a45aaa36…71f98d7b`, parameter archive from its preserved original).
Static facts below are measured bytes; in-game behavior marked UNVERIFIED has
not been seen running yet.

## ShopLineupParam

`ShopLineupParam.param` holds 392 rows of 32 bytes. Layout from the game's own
`paramdef/paramdef.paramdefbnd.dcx` (`ShopLineupParam.paramdef`):

| Offset | Type | Field |
| --- | --- | --- |
| 0 | s32 | equipId |
| 4 | s32 | value (price) |
| 8 | s32 | mtrlId |
| 12 | s32 | eventFlag (which merchant) |
| 16 | s32 | qwcId |
| 20 | s16 | sellQuantity |
| 22 | u8 | shopType |
| 23 | u8 | equipType (3 = goods) |
| 24 | u8[8] | pad |

Setting a row's equipId to -1 unlists it. The Repairbox (goods 2602) is sold
by exactly four rows: 1106 (3000 souls, flag 11017040) and 1404, 6217, 6304
(2000 souls, flag 11017170). Goods 2603 exists
(`[Unused] Magic Equipment Menu Unlock`) but is sold nowhere and granted
nowhere, so no inventory holds it. Item lot 4054 grants the Repairbox as
treasure; it is not a shop row.

## Durability and repair prices

- `fixPrice` on a weapon or armor row is the base repair price; 0 repairs free.
- `durability` / `durabilityMax` cap at 999.
- SpEffect `corrosionIgnore`, when ON, disables durability damage to the
  effect owner's weapons and armor.
- SpEffect `insideDurability` applies durability loss to the owner's used
  equipment when the effect is applied; negative values restore. Vanilla
  users: effect 1330 (the Repair sorcery, -150), effect 3100 (Repair Powder,
  -100), and the corrosion attacks (positive).
- SpEffect `maxDurability` shifts how many hits each durability loss takes.

Resident equipment effects (a weapon's `residentSpEffectId`, an armor piece's
`residentSpEffectId`) apply to the owner while equipped, so one effect with
`corrosionIgnore` on any equipped item protects everything equipped.

Free resident slots in vanilla: every weapon row leaves `residentSpEffectId1`
and `residentSpEffectId2` at 0/-1 (52 rows use slot 0). Armor uses all three
slots somewhere: `residentSpEffectId` on 67 rows (effects 6200, 6201, 6210,
6211, 6220, 6221, 6230, 6231, referenced by armor only), `residentSpEffectId2`
on 272, `residentSpEffectId3` on 11 (Armor Rework's slot).

## The bonfire Repair Equipment option

The bonfire menu reuses the boxes' goods IDs as its own option IDs. RVAs:

- `0x632CBD` and `0x632D09`: the menu updater's `mov edx, 0xa2a` (goods 2602,
  Repairbox) ahead of the ownership call. The matching Weapon Smithbox checks
  (`mov edx, 0xa28`) sit at `0x632ABE` and `0x632B0A`.
- `0x634D70`: the selection handler's `cmp ebx, 0xa2a`, taken to `0x634E24`,
  which opens the repair menu through `0x637F70` (mirroring the 2600 path
  through `0x637DE0`).

Asking about goods 2603 instead of 2602 in all three places makes the
ownership checks fail (nobody holds 2603) and the selection dispatch fall
through to nothing. UNVERIFIED: that the row is hidden in-game rather than
shown disabled, and that selecting a leftover row is a silent no-op.

## Composing with Armor Rework

Repair Rework edits fields only and adds no rows, so it merges field by field
with any mod that also only edits fields (its armor `residentSpEffectId` and
weapon `residentSpEffectId1` do not overlap Armor Rework's slot 3). Armor
Rework adds SpEffect rows, which forces whole-member fallback: with both
enabled the loader reports one `Effects (whole table)` conflict and the later
mod's SpEffect table wins whole, dropping the other's effect changes. Shop,
weapon and armor members still merge cleanly.

# Inventory and radial architecture

This is the settled #42 trace. It supersedes the failed assumptions that catalog
category, inventory GUID location, or inventory enable/disable alone chooses a
radial slot.

### The radial has a data-defined item-to-slot layer

Rockstar registers two base resources in `content.xml`:

- `quickSelectItems` as `WHEEL_INFO_FILE`;
- `quickSelectSlots` as `WHEEL_SLOT_FILE`.

`quickselectitems.ymt` contains an item hash, slot ID, and sort order. In the
Story group:

- `KIT_BANDANA` -> `CLOTHING_ITEMS`;
- the ten Story mask records -> `HORSE_LARGE_MASKS`.

The Cowhand Fix independently proves that an owned item with no
`quickselectitems` entry does not appear in its horse quick-select slot. Weapon
mods likewise change wheel grouping/order by editing these mappings.

### `short_update` supplies eligible inventory items

`short_update.c:65119-65325` builds inventory filters and enumerates two distinct
clothing categories:

- `81053684`: ordinary bandana;
- `-525676072`: large mask.

`func_2134` accepts every ordinary-bandana-category item, but only
`KIT_MASK_GREY_CLOTH` through its generic large-mask eligibility branch.
`func_2135` then calls:

- `_INVENTORY_ENABLE_ITEM(inventoryId, item)`;
- `_INVENTORY_DISABLE_ITEM(inventoryId, item, reason)`.

These natives change item availability and take an inventory ID. They do not
add/remove a HUD collection member. The earlier use of
`HUD::_0x0501D52D24EA8934(1)` as that first argument was invalid.

Both layers matter: catalog category determines which inventory query sees an
item; `quickselectitems.ymt` determines which radial slot can display it.

### Installed #42 seam

`MyOverhaul/quickselectitems.ymt` removes the real bandana and ten Story masks
from quick-select assignment, so no real item remains in `HORSE_LARGE_MASKS`.
Ten custom carrier records map to `CLOTHING_ITEMS`: one bandana fallback and
nine supported masks.

The ASI:

1. persists a supported mask observed in the active wardrobe/metaped component;
2. keeps exactly one custom carrier item in inventory;
3. uses that carrier's real mask icon/name in the ordinary item-wheel slot;
4. redirects carrier use to Rockstar's real mask or bandana interaction state;
5. swaps to the bandana carrier during missions.

No real mask is hidden, disabled, removed from ownership, or made unavailable
to the wardrobe.

The first 2026-07-30 runtime pass proved that both replacement data files
loaded, but its carrier grant failed. CLOTHING records cannot be granted through
the generic `SLOTID_SATCHEL` path. Decompiled `func_152` instead resolves the
`WARDROBE` inventory container and the clothing item's container-specific slot
before `_0xCB5D11F9508A928D`. The first C++ port also truncated every generated
inventory GUID by declaring Rockstar's `struct<4>` as four 32-bit integers.
ScriptHook defines `Any` as `uint64_t`; the correct GUID is therefore four
64-bit slots (32 bytes). The corrected build fixes that ABI, mirrors the
decompiled path, and logs the stage of any further rejection. The 2026-08-03
pass then proved the carrier existed and changed with wardrobe selection, but
the item-wheel segment remained blank even after the carrier was explicitly
enabled. `short_update` also maintains the actual carried-clothing list at
`Global_1946804.f_2657`: at most 18 item hashes, per-category counts (the
ordinary bandana category is limited to one), and auxiliary slot metadata.
Its vanilla `func_1650`/`func_2906` path unhides the wardrobe GUID, inserts the
item into that list, increments the category count, and raises refresh flags 8
and 16. The installed follow-up reproduces those operations for the runtime
carrier. Enable/disable remains only one prerequisite, not radial registration.

### Acceptance

A full restart must prove: the selected mask alone appears in the ordinary item
wheel; the horse mask selector has zero entries; changing the wardrobe mask
updates the carrier; selecting it uses full-mask put-on/take-off behavior; and
mission bandana behavior still works.


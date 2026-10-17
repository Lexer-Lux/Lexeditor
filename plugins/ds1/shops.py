"""Which shop rows each merchant sells.

Every merchant's stock carries a [Merchant] prefix in the Smithbox row
names, with three exceptions pinned here:

- 'Griggs of Vinheim - Logan in DA' is served by Big Hat Logan: the rows
  duplicate Griggs' own stock at identical prices, which one talk menu
  could never list twice, and Logan is the only spell merchant standing
  in the Duke's Archives.
- Row 1134 has no Smithbox name; it sits inside the Undead Merchant's
  range and sells his Dried Finger, so it joins the male merchant (npc
  251001, who drops the Uchigatana he wields).
- Laurentius of the Great Swamp has no NpcParam row and no placement in
  the game's data, so his five rows list under the NPCs tab's Unowned
  shops subtab; no merchant page can claim them.

Attribution reads the static Smithbox names, never the live display
names, so a mod renaming a shop line cannot move it to another merchant.
"""

from __future__ import annotations

import re

#: Shop-name prefix to the NpcParam rows of the character who serves it.
MERCHANT_PREFIXES = {
    'Andre': (264000,),
    'Crestfallen Merchant': (6250,),
    'Darkstalker Kaathe': (533001,),
    'Domhnall of Zena': (6260,),
    'Dusk of Oolacile': (6050, 6700),
    'Eingyi': (321001,),
    'Elizabeth': (414000,),
    'Giant Blacksmith': (286001,),
    'Griggs of Vinheim': (6040, 6041, 6130),
    'Griggs of Vinheim - Initial': (6040, 6041, 6130),
    'Griggs of Vinheim - Logan in DA': (6030, 6031, 6032),
    'Hawkeye Gough': (411000,),
    'Ingward': (6180,),
    'Laurentius': (),
    'Marvellous Chester': (409000, 409010),
    'Oswald of Carim': (6370,),
    'Patches': (6320, 6321),
    'Petrus of Thorolund': (6080,),
    'Quelana of Izalith': (6170,),
    'Rhea of Thorolund': (6070,),
    'Rickert of Vinheim': (6220,),
    'Shiva of the East': (6310, 6311),
    'Undead Merchant - Female': (251000,),
    'Undead Merchant - Male': (251001,),
    'Vamos': (292000, 292002),
}

#: Shop row IDs with no usable prefix, to their merchants.
SHOP_ROW_MERCHANTS = {
    1134: (251001,),
}

def _invert() -> dict[int, tuple[str, ...]]:
    inverted: dict[int, list[str]] = {}
    for prefix, ids in MERCHANT_PREFIXES.items():
        for npc in ids:
            inverted.setdefault(npc, []).append(prefix)
    return {npc: tuple(prefixes) for npc, prefixes in inverted.items()}


#: NpcParam row to the shop prefixes it serves.
NPC_MERCHANTS = _invert()


def owners(document, row_id) -> tuple:
    """The NpcParam rows serving one shop line, or () for an unowned line."""
    names = document.schemas['ShopLineupParam']['names']
    match = re.match(r'\[(.*?)\]', names.get(row_id, '') or '')
    owned = set(MERCHANT_PREFIXES.get(match.group(1), ())) if match else set()
    owned |= set(SHOP_ROW_MERCHANTS.get(row_id, ()))
    return tuple(sorted(owned))


def has_owner(document, row_id) -> bool:
    """Whether any merchant page can claim one shop line."""
    return bool(owners(document, row_id))


def is_merchant(npc_id) -> bool:
    """Whether an NpcParam row belongs to a merchant with a shop."""
    return npc_id in NPC_MERCHANTS or any(
        npc_id in ids for ids in SHOP_ROW_MERCHANTS.values())


def stock(document, npc_id) -> list[dict]:
    """The shop lines one NPC serves, in shop order.

    Each line carries its ShopLineupParam id, the bare item name, and the
    editable price (value) and stock (sellQuantity).
    """
    try:
        npc = int(npc_id)
    except (TypeError, ValueError):
        return []
    if not is_merchant(npc):
        return []
    names = document.schemas['ShopLineupParam']['names']
    rows = []
    for row in document.params['ShopLineupParam'].rows:
        if npc not in owners(document, row.row_id):
            continue
        schema_name = names.get(row.row_id, '') or ''
        display = document.display_name('ShopLineupParam', row.row_id, row) or schema_name
        bare = re.sub(r'^\[.*?\]\s*', '', display or '')
        rows.append({
            'id': row.row_id,
            'name': bare or display or f'Row {row.row_id}',
            'value': document.value('ShopLineupParam', row.row_id, 'value'),
            'sellQuantity': document.value('ShopLineupParam', row.row_id, 'sellQuantity'),
        })
    rows.sort(key=lambda entry: entry['id'])
    return rows

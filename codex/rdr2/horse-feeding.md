# Horse feeding and bonding

## Story 1491.50 script path

The retained player_horse.ysc.c separates feed eligibility, item nutrition and bond awards. Annotated positions are source evidence, not verified offsets in installed bytecode.

- func_724 at 0x14B42 accepts 45 food/herb IDs. func_789 at 0x167DB selects from 11 ordinary feeds, then 26 herbs.
- func_433 at 0xD4ED dispatches food to func_739 at 0x152FC while the item hash remains available.
- func_739 applies item effects through func_790 and measures combined health/stamina core change. Eight herbs in func_959 receive no feeding bond event. Common bulrush, English mace, peppermint and sugar cubes use event 16. Other foods use event 13 if core recovery is at least 50 or attribute 13 base rank is below 30; event 14 at recovery of at least 25; event 15 at nonnegative recovery. The attribute check is func_357 mode2 through func_652 to GET_ATTRIBUTE_BASE_RANK; this does not establish the attribute's human-readable meaning.
- func_758 at 0x15C56 supplies base values: event13=15, event14=5, event15=1, event16=5. These are not guaranteed final awards.
- func_454 at 0xDA87 checks horse identity, rank, per-event accumulated limits and a motivation gate. It applies the shared bonus at Global_40.f_11095.f_68, calls func_760 and updates event accounting.
- func_760 at 0x15DC3 adds to the saved bonding accumulator and calls func_677 at 0x13749, which writes attribute7 bonding points.

The constant20 in func_962 is not the food bond amount. Its callers update separate f_407 state through func_895. The food award path does not call func_962. Earlier attribution of this constant to feeding bond is incorrect.

## Editing boundary

Catalog fields cannot extend the scripted allowlist or preferred selection. A per-item amount path must keep the item hash through func_739 and substitute the magnitude for its single award while preserving native gates and accounting. An after-consumption watcher adds a second award and does not implement this path.

The resolver tools/research_rdr2_horse_feed_dispatch.py checks the chain and emits IDs and source positions. It does not patch bytecode. No item-aware player_horse dispatcher hook is validated. Source annotations are not installable patch addresses.

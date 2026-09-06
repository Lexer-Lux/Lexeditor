# Worklog: Github 80

## GitHub #80 cigarette-card map coordinates — 2026-08-05

The 144 cigarette-card rows were still using coordinates projected from public
website-map pins. Comparing those rows to direct game-space card placements
showed a 41.83 m median horizontal error and a 1,274.70 m maximum; 127 cards
were more than 10 m off, 64 were more than 100 m off, and the largest failures
were concentrated in the far west and south.

Replaced all 144 card X/Y pairs with set-and-card-keyed world coordinates from
the Apache-2.0 Z-eus dataset, completed and cross-checked against bcc-nazar's
144-model placement list at commit
`f28c5a6d81d79288dd911aa5317a3b45fe82d244`. The resulting CSV has 144 unique
card identities and 143 unique positions: World Champions cards 2 and 11
intentionally share the shack windowsill, which independent location guides
also identify for both cards. No non-card row, requirement, collected-state
key, category, icon, or runtime behavior changed.

This was data-only, so the current ASI did not need rebuilding. RDR2 was
running; corrected watcher PID 406808 will copy and verify the latest
`collectibles.csv` after exit. Runtime acceptance is checking several
uncollected cards across distant regions and confirming each marker lands on
the physical pickup.

## Gang-hideout completion layer — 2026-08-06

Restored the six Story locations counted by `GANG_HIDEOUT_COMPLETED`: Six Point
Cabin, Shady Belle, Beaver Hollow, Hanging Dog Ranch, Thieves Landing, and Fort
Mercer. This excludes the larger RDO hideout set and former gang camps that are
not part of Story's six-hideout 100% requirement.

Coordinates reproduce the checked-in RDOMap game-to-map transform against its
game-derived named locations. Thieves Landing uses its named encounter search
area and Fort Mercer its named physical-item point because neither has a Story
hideout discoverable-text row. The two New Austin locations require `FIN1`;
the four normally accessible sites remain immediately visible as guide areas.

The dataset has 584 rows across 11 categories and preserves every prior
category count. `gang_hideout` is integrated into the category toggle, icon,
label, and proximity-retirement paths. Reaching a hideout does not retire it,
because entering the area is not proof Rockstar incremented the completion
counter.

## Point-of-interest repair — 2026-08-06

The previous 57 POI rows were only verified against a polynomial calibration
of website-map pins. That proved internal reproducibility, not correct in-game
inspect positions. It also left POIs on the generic proximity-clearing path, so
walking near a marker could permanently erase it before the INSPECT animation
and journal sketch completed.

Replaced 21 calibrated positions with literal Story Mode coordinates from
`discoverable_generic_location.c` (`func_76`, `func_100`, and `func_164`). The
largest concrete repairs were Jesuit Missionary (196.57 m) and Sperm Whale
Bones (152.89 m). The remaining POI rows have not been represented as exact:
they retain their calibrated positions until a literal placement is recovered.

POIs no longer use proximity retirement. Fifty journal POIs now read the same
Story save flags used by Rockstar's discoverable scripts:
`Global_40.f_8863[func_99(discoverable)] & 4`. The four trail trees and six
Aztec writings use their individual `f_152`/`f_154` bits instead of hiding a
whole group at once. Coal Mine Writing is a cheat inscription rather than a
journal discoverable, so it has no false completion signal and remains visible.

Static acceptance is
`python tools/reverse-engineering/verify_gang_hideouts_issue_80.py`. Runtime
acceptance still requires installing the integrated ASI/data and confirming:
(1) an uninspected POI remains after entering/leaving its radius, (2) its blip
disappears only after the journal sketch completes, (3) an already-discovered
POI is absent after loading a save, and (4) Jesuit Missionary and Sperm Whale
Bones land at their actual inspect sites.

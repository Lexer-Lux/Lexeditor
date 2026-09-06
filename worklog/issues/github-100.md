# #100: Finish record-based mod combining

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/100)

## Requirements and decisions

Independent edits from enabled mods must coexist. When two mods edit the same proven record field, the later/higher-priority mod wins that field without discarding unrelated edits from the lower-priority mod.

## Current implementation and evidence

`games/ff8/runtime_layout.py` composes fixed-data files through the semantic merger in `games/ff8/fixed_data_merge.py` when an extracted baseline is available. The existing load-order verifier covers managed order, Hext order and conflict presentation.

Issue #100 now also has `tools/prepare_ff8_mod_combining_fixture.py`, which generates two ordinary folder mods from the user's own extracted `menu/price.bin`; no game data is committed. The fixture makes independent Hi-Potion/Phoenix Down edits and a deliberate Potion collision. `tools/verify_ff8_mod_combining_issue_100.py` composes both load orders from a synthetic baseline and verifies that independent fields coexist, only the Potion collision changes with priority, untouched bytes remain baseline-identical, and the conflict manifest names the correct winner/claimants.

GitHub Actions run 34062240051 passed both the pre-existing mod-order verifier and the new semantic fixture verifier on the branch.

## Player acceptance remaining

Generate/install the fixture with `python tools/prepare_ff8_mod_combining_fixture.py --install`, enable both issue-100 mods in FF8 Load Order and save the order.

With **Issue #100 — High Priority** later/higher than **Low Priority**, the fixture expects Potion = 4560 gil, Hi-Potion = 5670 gil and Phoenix Down = 8910 gil. Reverse only their priority and save again: Potion must become 1230 gil while Hi-Potion remains 5670 and Phoenix Down remains 8910. Check the values in a shop that sells those items, then disable/remove the fixture mods.

Automated composition is verified; actual installed-game/shop acceptance is not claimed yet.

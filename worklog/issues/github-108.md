# #108: Independent camera profiles and vehicle framing

[Live request and comments](https://github.com/Lexer-Lux/Lexeditor/issues/108)

## Scope and boundaries

Standing, crouched, prone, horseback, vehicle, aim, crouched aim, armed and crouched armed profiles exist. Developer mode gates editing, not application of saved profiles. Camera calibration uses the shared developer mode and keypad owner; there is no separate calibration toggle. Held adjustments must be responsive.

Continuous vertical positioning and effective vehicle LOW/NORMAL remain unresolved in the proven gameplay-camera path. Do not present a fake Y control or guess vehicle camera states. The two-mode vehicle handoff is tracked in #220. Shoulder placement remains #267. The current #269 request needs its specified clean automatic transition capture; #270 needs its isolated camera/lantern bob comparisons. Earlier source checks do not replace those results.

## 2026-09-08 source repair

`C:/RDR2Mod/GameplayTweaks/modules/gameplay_camera.cpp`:

- Calibration uses elapsed time, preserving 0.05 units per 16 ms instead of slowing with frame rate. Ctrl retains one-tenth speed. A gap over 100 ms is treated as one initial 16 ms step, so returning from an inactive editor does not apply accumulated idle time. Existing keypad and editing gates remain.
- Save checks every field write for each profile. A failed write keeps that profile dirty, which protects its live values from the periodic INI reload. Other profiles can save successfully. All field writes are attempted, even after one fails. The HUD and log report incomplete saves; retry can clear the dirty state after success.
- This is failure detection and live-edit protection, not an atomic multi-field INI transaction. A failed save may have written some fields; retry is required before restart if the full profile must persist.

## Checks

`tools/verify_rdr2_camera_authoring.py --runtime-root C:/RDR2Mod` compiles and executes the actual profile table, save and calibration functions. Production passes and five mutations are rejected. The harness checks equal one-second adjustment at 30/60/144 FPS, fine adjustment, inactive-time protection, failure of every one of the 27 profile-field writes, per-profile dirty state, all writes attempted, retry and truthful HUD/log feedback. Temporary compiler files are removed.

Existing runtime verifiers pass: `verify_gameplay_camera_issue_8.py` (50 contracts), `verify_camera_rigs_issue_177.py` (nine contracts and nine rejected mutations), and `verify_editor_keypad_input_issue_8.py` (two rejected regressions). The #177 extractor anchor now accepts the save function's boolean result; its observer checks are unchanged.

## Next work

Parent owns build and delivery. No game files were changed; #151 currently owns the game installation. Keep this issue actionable: vehicle height, shoulder placement and reported transitions still have unfinished scope. After delivery, check saved presets with developer mode off, responsive held controls, failed-save feedback if reproduced, and the prepared issue-specific camera captures. Source/harness results do not prove rendered framing or actual disk success on the player's game path.

Root reviewed and built the authoring repair. ASI SHA-256 `EE30ECF24A9494BE45424591408875264FE0FEBD9BFD6957BD158A7F1295AD20`, with matching release manifest, is held in `out/rdr2-after-duration`. The camera authoring verifier is in the shared runtime audit. Nothing was installed while #151 remains active. Per-profile writes are failure-aware, not an atomic whole-file transaction; partial disk writes can remain after an error, while live dirty state is retained for retry.

## Continuous vehicle-height evidence boundary

A bounded read-only review found no decrypted engine dump, native-handler export or handler registration map in the existing `_downloads`, `_analysis` or output inventory. The SDK native caller forwards hashes; it does not expose the camera handler body. The central engine limits also document that known engine anchors exist in loaded `.text` but not in the encrypted on-disk executable. No new dump, launch or dependency was used.

The available native database gives `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` (`0x066167C63111D8CF`) five arguments: speed, horizontal ownership, horizontal offset, distance ownership, distance. No vertical argument exists in that proved contract. `SET_IN_VEHICLE_CAM_STATE_THIS_UPDATE` takes a vehicle and an unresolved integer state, not a height. Its opened Story calls use states 0/1/3 without establishing a height mapping.

The separate vertical native `SET_GAMEPLAY_HINT_CAMERA_RELATIVE_VERTICAL_OFFSET` (`0x29E74F819150CC32`) is a hint-camera parameter. Current `winter4.ysc.c` lines 37210–37212 set an entity hint, FOV and this vertical offset together. That proves a targeted hint path, not continuous free-follow vehicle height with normal look/aim ownership. It was not substituted.

The existing 2.2 MB `_analysis/cameras_ymt.xml` is a mostly unresolved hashed camera metadata export. The horse-camera builder identifies one horse block and four unrelated centering/damping edits; it supplies no proved vehicle-height field or live profile setter. Editing guessed metadata hashes would not complete continuous per-profile calibration.

Remaining technical work is to obtain and inspect the actual follow-vehicle handler/metadata layout through an independently supported source path, then prove a height parameter and its ownership contract. This is a limit of the evidence available in this pass, not universal impossibility or a new user question. Full height scope remains actionable. No height code was changed.

# #254: Implement the requested area-based Recon targeting

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/254)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #162 worklog](github-254/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-162.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 area probe candidate

Live #254 and its full comments were read. Original human design specifies a radius measured as a percentage of screen width, a visible circle during aiming/binocular use, rays through the interior, and animal/herb study. #357's safe scenario path remains intact. Scope stays actionable until candidate delivery and remaining work are accounted for.

Recurrence audit: reviewed `C:/RDR2Mod/fuckups.txt` and existing Recon crash, plant, tolerance and Study-mode verifiers. Prior failure classes are unsafe native buffers, static checks that require a defect, per-frame native/draw overload, and claiming visual success from a build. Primary evidence: current SDK `GET_FINAL_RENDERED_CAM_COORD/ROT`, `GET_SCREEN_COORD_FROM_WORLD_COORD`, entity world/local offset calls; existing `START_LOS_PROBE`/`SHAPE_RESULT` wrappers and already used `rpg_meter_99` artwork. Sanctioned path: bounded async ray handles and one-result typed scenario queries. Execution proof: executable C++ geometry, probe lifecycle and actual ped-candidate tests. Player-visible boundary: no game or rendered acceptance yet.

`recon.cpp` plus `recon_area.h` now sweep 49 disk samples, including center and interior. Successive sweeps rotate sampling angles. Three projected points on a camera-facing plane calibrate the inverse projection for the final rendered camera, including roll and FOV. Centimeter calibration offsets remain near screen center under high zoom. Pixel-distance gates divide normalized Y by the current width/height ratio. The circle uses the existing meter texture in one draw; exact rendered artwork bounds still need inspection.

The fixed pool owns at most eight pending probes. Time-earned credit permits two starts per 16 ms with a capped four-start burst, so 30 FPS does not double the sweep time. No accumulated catch-up burst and no abandoned pending handles. Results older than 450 ms, including late probe completions, are discarded. Aim-session, radius and cumulative camera-position changes invalidate old generations. Fresh collision points remain available across the separate 75 ms scan cadence. Entity model/existence checks and local hit offsets follow moving targets. Result projection runs at selection cadence, not every frame. A bounded diagnostic reports active state, starts/results/hits, pending handles, oldest pending age and fresh cache count.

Ped selection uses real body-hit distance and visibility rather than rejecting that hit using an unrelated origin, anchor, size or origin-to-player LOS. Native aim priority and Rockstar animal Study-mode bypass remain. All fresh ray objects can supply plant candidates. The existing safe typed fallback rotates one query center across fresh hit locations per 250 ms sweep; its native call budget is unchanged. This fallback can take longer to find a non-colliding plant than a directly hit plant visual.

`tools/verify_rdr2_recon_area.py --runtime-root C:/RDR2Mod` executes production geometry, async ownership and the actual ped-candidate lambda. It covers square/16:9/ultrawide geometry, camera roll, FOV scaling, disk interior, 30 FPS sweep freshness, pending limits, non-scan frames, stale results, old sessions, radius/camera changes, slow completions and body-hit acceptance. Production passes; nine intentional regressions are rejected. Existing crash, plant, tolerance and animal Study-mode checks pass. Root owns full build/install. No game launch, config change or save mutation.

Remaining: integrate/build/install this candidate; inspect exact circle size and outline at multiple aspect ratios and binocular zoom; measure frame time and probe results during sustained aiming; confirm center/interior/edge acquisition on large animals, small birds and herbs, study readback, occlusion, camera movement and wheel transitions. The historical separate gun/binocular radius request is not implemented by this change and remains open. Do not close the full issue from these tests.

## Area candidate delivered, 2026-09-08

Development build and two production C++ harnesses passed; nine regressions rejected. Installed ASI and matching release manifest with RDR2 closed, SHA-256 `23C876015C16227B098C326285B64B148889F5B1B4966E3921A7200B08415C54`. Prior ASI retained as a small rollback copy. No settings, catalog or save changes. Full circle visibility, ray alignment, animal/herb studying and game performance remain unverified. Separate gun/binocular radius controls are still being implemented; full issue remains actionable.

## Independent radius controls, 2026-09-08

The explicit original request for separate gun/binocular values was recovered before this change. Coding scope for that request is now implemented: existing `ScreenCenterTolerancePercent` is labeled Binocular Tagging Radius; new `WeaponScreenCenterTolerancePercent` is Gun Tagging Radius. Both use 0.1-35 percent of screen width. Guns include rifle scopes; scope distance policy remains independent. Runtime caches both values on the existing two-second cadence and selects the active radius before rays, circle drawing and acquisition. Aim-mode changes invalidate old probe generations even when the two radii are equal.

Old INIs inherit their previous common radius for the absent gun field. Both Lexeditor and the native settings menu show that inherited value without writing during reads. Saving the new control creates its key. Saving the binocular control first also preserves the old inherited gun value before changing the binocular value, so a legacy profile does not silently change both. Existing unrelated INI values are preserved. Fresh source INI adds the new key at 5, matching its existing radius. Shared schema and generated native menu expose both bounded controls with width-percent help; the menu count ledger now records 363 visible / 376 total.

Source files: runtime `recon.cpp`, `settings_menu.cpp`, `settings_menu_schema.generated.h`, source INI; Lexeditor `games/rdr2/server.py` settings functions and `settings_schema.json`. Updated tolerance and menu parity verifiers. `tools/verify_rdr2_recon_radii.py` executes actual runtime loading/selection, native menu compatibility and native save branches, plus actual extracted Python settings functions against a temporary INI. Legacy reads make no writes; gun-first and binocular-first saves, independent values, bounds, unknown-key rejection and failed native writes pass. Four intentional regressions fail. Area harness also passes and now rejects ten regressions, including cross-mode stale results. Menu parity, tolerance and crash checks pass.

Root owns build and later delivery. Runtime installation is on hold while the separate #151 DurationProbe experiment owns the game files; this agent made no game-directory or experiment-bundle changes. Remaining #254 work is candidate build/delivery after that experiment and actual rendered geometry, hit/study behavior and sustained performance acceptance. Separate radius controls are no longer outstanding coding scope.

Root verified the development build and executable radius checks. Built ASI SHA-256: `5FF544CFB543099812D9FB0ED3F81F8EE57B081AFA9AAECCFE2A20A9D46A63D8`. This build is not installed while #151 is active. The main runtime audit now includes the radius regression harness.

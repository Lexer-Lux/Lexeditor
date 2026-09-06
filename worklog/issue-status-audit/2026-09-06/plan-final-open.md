# Remaining reviewed open issues

@@ 244|actionable|Deliver reliable campsite respawn and truthful warnings
Respawn at the nearest valid activated campsite, safely beside the fire. With none available, preserve normal respawn and show one clear notification.

**Latest repair is not built/installed.** The real notification path replaces the rejected custom panel, but delivery and the actual campsite selection/placement still need verification.

@@ 245|actionable|Deliver restored custom icons and visible corpse markers
All existing custom map icons must keep working; new artwork must not replace the rest of the texture collection.

**Latest repair is uninstalled:** the returned corpse-X visibility regression has a new asset candidate. Deliver it and verify the real minimap result before requesting another test; an archive hash does not prove visible markers.

@@ 251|actionable|Restore climbing entry and stop animation on release
Releasing movement while climbing should stop the movement cycle cleanly and hold position; resuming must not be interrupted by a stale stop.

**Blocked by unfinished code, not you:** the latest report says walls cannot be grabbed at all. Restore entry (#193) and deliver the unbuilt stop/rebind repair before asking you to test release behavior.

@@ 252|actionable|Fix top-out on angled surfaces without falls or teleporting
At an angled roof or ledge, Arthur must either mantle onto a valid landing or remain attached—not fall, stall indefinitely and snap back later.

**Incomplete:** bounding the old freeze did not fix the fall/snap behavior. The current wall-grab failure (#193/#251) also prevents a meaningful test. Repair those paths first.

@@ 253|actionable|Implement proper sideways climbing rather than a substituted pose
Sideways traversal now moves the character, but the installed version holds a static grip pose after the vertical and ledge-walking substitutes were rejected.

**The requested animation is not delivered.** Investigate correct blending or authored/retargeted animations and restore wall grabbing first. Do not force a choice between accepting a rejected substitute and declaring the entire feature impossible.

@@ 254|actionable|Fix target acquisition across the visible animal, not its anchor
The tolerance control now uses a real percentage, but that does not implement your later request for area/raycast-based acquisition over an animal's visible extent.

**Work remains:** investigate the requested sampling and performance tradeoffs, preserve direct aimed-target selection, and resolve binocular crash #357 before a binocular test.

@@ 258|actionable|Remove the slide-and-snap before mantling
Reaching the top of a climb should produce a continuous mantle, not a downward slide followed by a teleport.

**Not ready for another test:** older probe repairs were installed, but the newer wall-grab failure prevents reaching this path. Restore climbing entry and verify the top-out transition before requesting acceptance.

@@ 259|actionable|Validate reverse-mantling into a ledge grab
Walking or sneaking off a climbable ledge should reverse-mantle into a stable climbing position; running/sprinting should keep their intended behavior.

**Earlier candidate exists, but acceptance is blocked by the newer climbing-entry regression.** Repair that shared path and prepare a known valid ledge before asking you to repeat the test.

@@ 260|unfeasible|The available scale setter does not resize the attached lantern
Runtime comparison showed unchanged attached geometry despite different stored scale values. The no-op scale control was removed; the physical rig remains normal size.

Real resizing needs validated pre-scaled model assets or another rendering path. A changing getter is not evidence that the lantern visibly scales.

@@ 261|actionable|Deliver the climbing surface and transition repair
Sliding must not lead to repeated falls, snap-backs, underground movement or empty-space climbing.

**Latest repair is source-only.** It tightens contact support and landing checks, but still needs build, delivery and a working wall-grab path. Do not label static guard tests as accepted movement.

@@ 267|actionable|Make shoulder switching reach both sides evenly
Repeated X presses while aiming should move smoothly between comparably offset shoulders, not far-left and centered.

**Latest player test still failed.** The signed-magnitude attempt is not accepted; repair the actual settled framing rather than treating any sign change as success.

@@ 269|actionable|Deliver the camera-transition recorder before requesting a capture
Drawing a weapon and changing stance should not add an unrelated camera shift or mismatched transition curves.

**Diagnostic preparation remains:** the latest automatic recorder now preserves the pre-change frame, but is not built/installed. Deliver it before asking for a capture; Numpad 9 is obsolete and must not be used for this test.

@@ 270|waiting|Compare crouched camera bob with the lantern and camera tweak off
The crouched bob is measured, but its cause remains unconfirmed. Lantern contact is a newer hypothesis; neither it nor the camera module should be blamed without comparison.

- [ ] Record a brief crouched, stationary view at the same location with your usual settings.
- [ ] Disable the belt lantern, fully restart and repeat. Then disable the Camera tweak, restart and repeat again.
- [ ] Report which change removes or reduces the bob, with the three clips and GameplayTweaks.log. Restore your settings afterward.

@@ 272|actionable|Deliver clearer inactive campsites
Inactive campsites should be easy to locate, with black smoke; active sites use white smoke, and removed sites must leave no plume.

**Latest repair is not built/installed.** Deliver the improved smoke update and verify the site lifecycle before asking you to revisit camps.

@@ 274|actionable|Resolve missing audit markers and prepare the next location pass
The manual audit reached Artists, Writers & Poets as far as the save allowed; the next intended entry is Famous Gunslingers Card 1.

**Preparation remains:** resolve the missing Amazing Inventions Card 7 marker and the unlocated Artists, Writers & Poets Card 4, then confirm the required save and jump/relocation tools are ready. Do not ask you to continue blind from an incomplete checkpoint.

@@ 276|waiting|Choose how Hair Tonic should affect configurable beard growth
The mechanism for setting each growth stage's duration and removing the late-stage tonic requirement is identified. No implementation is delivered.

- [ ] Choose whether tonic remains an optional 2×/4×/8× accelerator or whether the configured duration should be exact and ignore tonic.
- [ ] Specify the desired base game-hours per stage, or different durations by stage.

@@ 277|actionable|Verify delivery of the cutscene tag-suppression repair
Recon tags must disappear during story cutscenes and return afterward without losing completed tags.

**Delivery/validation remains:** the latest source replaces the incorrect cinematic-camera-only gate with the actual HUD/scene checks, but does not establish a delivered visual fix. Verify that before asking you to replay a cutscene.

@@ 286|actionable|Finish usable Online content in Story Mode
Make the requested Online items genuinely obtainable and usable, preserving the existing Story edits. Catalog presence alone is not completion.

**Latest changes await installation:** the Irish Whiskey/Old Tom Gin wheel mappings and catalog preservation repairs need delivery. Remaining categories and upgrades still need their own obtain/use checks; do not mark the entire import done after two bottles.

@@ 290|actionable|Make lantern brightness and range controls work
The brightness and range controls should visibly change the lantern's illumination.

**Still broken:** your latest test found no difference, including light remaining at brightness 0. Investigate the effective light path and repair it before requesting the same comparison again.

@@ 291|actionable|Finish the saddle lantern's obtainable, working test setup
The installed candidate removes the rider's belt lantern and attaches an owned lantern to the saddle horse.

**Test preparation remains:** identify the exact purchase/equip route and verify it with the unresolved lantern-light controls (#290). Then provide the horse-switch, mount/dismount and radial-toggle checks. “Buy and equip it” without that route is insufficient.

@@ 292|actionable|Make native animal Study focus drive Recon tagging
When the game enters a valid animal Study interaction, use that target directly instead of rejecting it through unrelated screen-center or range limits.

**Still failing in your latest test.** Repair the native-focus integration before another acceptance request; relabeling the same build as Waiting does not resolve it.

@@ 293|actionable|Deliver bounded 3D tag scaling and metre-based head gaps
Keep selectable 2D/3D tags with a world-space head gap. In 3D, the symbol, rings and text should scale together between the configured near/far bounds; 2D remains fixed-size.

**Latest scaling repair is not built/installed.** Deliver and validate it before asking you to compare distances.

@@ 294|untested|Check the approved hat-and-shoulders Recon icon
You selected the broad-brim hat/person icon. It is implemented; there is no outstanding icon-design question.

- [ ] Restart RDR2. Tag a neutral person without binoculars while #357 remains open; confirm the chosen person glyph appears, not the old plain circle.
- [ ] Change distance and available tag size/fade settings. Confirm the hat and shoulders stay centered inside the health ring; send a screenshot of any mismatch.

@@ 295|unfeasible|Reliable belt-lantern clearance is not established for the current rig
The physically jointed lantern can intersect animated legs or clothing. No validated collision/cloth/asset solution currently provides reliable clearance for that rig.

Preserve the working attachment rather than replacing it with an unproved correction. A new collision or custom-asset path would reopen this technical boundary; attachment orientation is separate in #348.

@@ 296|actionable|Deliver facing indicators for tagged enemies
Tagged enemy minimap blips should show facing/FOV like animal blips, without revealing untagged enemies or adding duplicate overlays.

**Source-only:** the generic-enemy cone change is not built/installed. Preserve the native law/bounty cones and verify delivery before requesting comparison tests.

@@ 297|actionable|Finish law and bounty-hunter Recon icons and states
Law and bounty-hunter tags should use their proper role artwork and requested state colors, leaving unrelated targets unchanged.

**Incomplete:** the latest role-art change is unbuilt, and overhead conditional coloring is still unresolved. Map-blip coloring does not complete the separate overhead-tag requirement.

@@ 298|untested|Check aimed crows get animal information
The installed repair stops the screen-center heuristic discarding an engine-confirmed aimed crow and gives that explicit target priority.

- [ ] Fully restart RDR2. Aim a weapon at a crow near a corpse without firing; confirm the lower-right information/Study interaction belongs to the crow. Do not use binoculars while #357 is unresolved.
- [ ] If it fails, take one F10 capture with the already-prepared compendium probe and attach its output plus GameplayTweaks.log. Report whether the crow or another target was selected.

@@ 299|actionable|Improve formula readability without changing the game style
The rejected opaque math overlay has been removed, and Blank now has graph examples. The readability redesign itself is unfinished.

Keep the game font, shadow, transparent background, curve-following placement and matching extrema. Prepare and render an improved layout before asking for your visual approval; a priority deferral is not Waiting.

@@ 300|actionable|Build illustrated cards and editable NPC decks
Rework Cards into Cards and Players subtabs: real artwork with four editable ranks and element icons, plus editable NPC decks, using the requested CCGroup layout reference.

**Not implemented.** Existing fixed-slot editing is #91; expanding the card-type limit is separate. The design already specifies what to build, so this is not waiting for another approval.

@@ 301|untested|Check Fast Start removes the remaining startup screens
The later repair targets the remaining startup flashes after opening-movie skipping worked. It still needs a player-visible check.

- [ ] Restart Lexeditor, enable Fast Start, save and cold-launch FF8. Confirm it reaches the main menu without a Squaresoft/Square Enix splash, FFNx splash or opening movie; report anything that remains.
- [ ] Disable Fast Start and relaunch. Confirm normal startup returns.

@@ 302|actionable|Add interaction and card-game prompts
Show distinct prompts for ordinary interactions and card-playing NPCs. Prefer positioning near the character; the requested fixed-HUD fallback is acceptable where necessary.

**Not delivered.** Implement the runtime detection and toggle, then prepare a representative interaction/card-opponent test. Being lower priority does not make this Waiting.

@@ 303|waiting|Choose the first smooth-rendering milestone
Separating rendering from game timing is a larger change than raising an FPS limit. The research proposes starting with battles while keeping original battle timing.

- [ ] Choose the first target: 60 FPS battles, display-refresh-rate battles, or full-game arbitrary-refresh rendering.
- [ ] Confirm original simulation timing must remain unchanged, including ATB, status durations and input windows. Implementation begins after the milestone is selected.

@@ 304|actionable|Verify Vibration Consolidation is delivered before requesting testing
Start should open normal pause behavior without the extra one-item Vibration screen; vibration remains available in Config.

**Readiness needs verification:** the issue contains a requested test but no delivery record. Confirm the actual setting/runtime candidate and its field/battle coverage before sending it for acceptance.

@@ 306|actionable|Prepare a delivered Better Targeting check
Remove red Target labels from unselected actors and make selected pointers fully opaque, preserving valid targets and controls.

**Readiness needs verification:** confirm the implemented candidate and prepare single/all-enemy and ally examples. A list of desired checks alone does not establish that the change is installed.

@@ 308|actionable|Finish menu repairs and battle-item ordering
The latest body reports an installed repair for the backward GF-ability-page crash and battle-item ordering. Other requested menu work remains unfinished.

**Keep the broader issue actionable:** complete the remaining menu behavior and preserve the distinction between the fixed crash, fixed ordering and unfinished features. Use a test save for any crash-repair check; do not call partial progress complete.

@@ 309|actionable|Verify and prepare the True ATB Wait test
When any living party member can act, other ATB gauges should pause without freezing animations; they resume only after no party member is ready.

**Test preparation remains:** confirm a delivered candidate and provide a setup that makes both ally and enemy timing observable. Do not ask you to inspect an invisible enemy gauge.

@@ 310|actionable|Finish Shared Magic compatibility and delivery checks
The runtime is packaged around one party spell pool with lossless migration and a warning when private stocks cannot fit.

**Acceptance is incomplete:** verify the managed installation route and resolve the excluded combinations with non-100 stock caps (#94) and Party Switch (#313). Menus, Draw, casting, junctions and save/reload must all use the same pool without loss or duplication.

@@ 312|actionable|Finish fixed character/GF commands and learned-ability gating
Use Attack, Magic, the character's command and the single junctioned GF's command. GF commands must require their learned abilities and disappear when that GF is removed.

**Partly repaired:** the latest body reports a Treatment learning-gate repair, but custom command behavior remains unfinished (#314), including undefined Angelo behavior. Do not call the whole command rework ready because one gate was patched.

@@ 314|actionable|Finish GF Magic pages and custom battle commands
Keep the specified Switch, Shoot, Summon and per-enemy Draw behavior. Magic must use the GF spellbook; Shoot must consume ammo and the configured fraction of ATB.

**Incomplete:** later Draw/Shoot repairs are reported installed, but GF pages and other custom behavior remain unfinished. Do not make you retest unimplemented parts or treat an unanswered spellbook mapping as the only remaining work (#93).

@@ 315|untested|Check free Scan targeting and the Item shortcut
The later repair restores explicit Scan targeting and cancellation. Scan must consume neither stock nor the acting character's turn; RB opens Item.

- [ ] Restart Lexeditor, enable Universal Item and Enhanced Scan, save and enter a battle with two enemies. On your turn press Square/controller X, choose a target and cancel once; the same character must remain ready.
- [ ] Repeat and confirm the other target. Check its Scan information appears, stock is unchanged and you keep the turn. Press RB and cancel Item. Report the first failed step and any soft lock.

@@ 316|actionable|Prepare a controlled flying-evasion comparison
Flying enemies gain the configured evasion bonus against melee; ranged attacks and Float ignore only that added bonus. The current patch also routes nominal always-hit melee through accuracy.

**Validation remains:** confirm the loaded patch and prepare fixed attacker/target values for the comparison. Random hit/miss observations without a controlled setup cannot prove the rule or its exceptions.

@@ 317|untested|Check Single GF and automatic inventory sorting
These per-mod tweaks use the normal Save control. Single GF clears existing multi-GF junctions on entry and prevents adding a second GF; inventory sorting runs on menu open.

- [ ] On a disposable save, junction several GFs to one character, enable Single GF and relaunch. Confirm those junctions clear on field/world entry, one GF can be added, and a second cannot; removal/transfer must still work.
- [ ] Enable Auto-sort, rearrange Items and reopen the menu; confirm sorting preserves quantities. Disable both tweaks and relaunch; confirm normal multi-GF behavior and retained manual item order. Report the failing step.

@@ 318|waiting|Choose replacement GF acquisition rewards
Acquire the Draw-only Guardian Forces through another route without losing progression or granting duplicates.

- [ ] Specify each replacement acquisition event or reward, or confirm that defeating the original carrier should grant its GF automatically.
- [ ] State how missed GFs should be handled on existing saves. No alternative acquisition design has yet been selected.

@@ 319|actionable|Identify and restore the requested altered content
Establish the exact regional/version differences before offering optional restoration patches.

**Research remains:** prepare the evidence and candidate list without assuming every change is censorship. There is no restoration package or useful approval list ready yet.

@@ 320|actionable|Implement the Journal using the agreed specification
This overlaps the detailed Journal request in #87. Use that specification for objectives, side quests and durable state rather than inventing a second quest menu.

**Implementation remains.** Coordinate the two issues so an unfinished menu is not marked complete in one and actionable in the other.

@@ 321|waiting|Resolve the map-menu scope alongside the existing design issue
This is the same broad map-menu request being designed in #90, not an independently specified second menu.

- [ ] Answer the map contents and interaction choices in #90; those decisions apply here too.
- [ ] Confirm whether this issue adds any behavior beyond that menu, or can be treated as a duplicate.

@@ 322|waiting|Specify the Mug defect
“Fix Mug” does not identify the observed failure or intended change, and there is no recorded reproduction to investigate.

- [ ] Describe what Mug currently does wrong, including the enemy or situation where you saw it.
- [ ] State what should happen instead, particularly how stealing, damage and failed steals should interact.

@@ 323|waiting|Define the Reptile tag's gameplay meaning
Add a Reptile enemy tag only once its intended use is clear; a new flag alone would change nothing in game.

- [ ] Specify which enemies should receive the tag.
- [ ] Describe which attacks, abilities or other rules should behave differently against reptiles.

@@ 324|actionable|Expand Scan with useful, accurate enemy information
Show the requested weaknesses, Devour results and other actionable details for the selected enemy.

**Implementation remains:** derive messages from effective enemy data and verify target-specific output. Do not call the feature ready merely because a Scan shortcut exists.

@@ 325|actionable|Prepare a reliable Better Card target test
The implementation filters impossible Card targets and disables the command when none remain, sharing its eligibility handling with Draw Once.

**Acceptance setup remains:** confirm delivery and provide named mixed-target and no-valid-target encounters. Do not ask you to discover which enemies are cardable just to validate the feature.

@@ 326|actionable|Prepare a measurable damage-limit test
The current implementation raises the ordinary 9,999 clamp to the engine's 60,000 path; it does not remove every possible limit.

**Test preparation remains:** supply a delivered candidate and known attacks/healing that exceed 9,999, with expected values. An unprepared “deal more damage” request is not ready for acceptance.

@@ 327|actionable|Build the approved Flare and vehicle-control changes
Use a Flare to trigger a local random encounter and show the remaining count through the fuel-style notification.

**Design already supplied:** gate the Square shortcut on Modern Controls; move forward/reverse driving to triggers and keyboard equivalents, with analog trigger speed where feasible. Implement and verify these interactions rather than asking you to approve the same design again.

@@ 329|actionable|Research vertical analog world-map camera movement
Horizontal analog rotation is confirmed working in #305. Determine whether safe vertical movement is supported without altering normal movement or zoom.

**Research remains.** Report the actual axis/state limits, then implement supported behavior with proportional speed and a dead zone. This is not waiting for the completed horizontal repair.

@@ 330|actionable|Research and extend analog camera controls to battle
Establish which battle camera axes/states can be controlled, then add proportional analog movement without breaking command navigation or targeting.

**Research/implementation remains.** A prior priority deferral does not make this a question waiting on you.

@@ 331|actionable|Validate the RDR1 workspace through its current structured editors
Game detection and the editable project workspace exist. This is no longer an unstarted plugin.

**Acceptance needs updating:** the old raw-file test predates the structured Items/Shops/Missions views. Prepare a current save/readback and deployment check without directing you to obsolete UI or claiming every tab is integrated (#337).

@@ 332|untested|Check the installed RDR1 runtime and development toggle
RedHook and the development plugin are installed. Confirm the normal launch and toggle without entering the known-crashing weapon radial (#333).

- [ ] Start RDR1 Story Mode through Lexeditor, press tilde twice and confirm development mode changes once per press.
- [ ] Close the game normally and report any startup/exit failure. Attach the loader/plugin logs so the runtime heartbeat can be checked.

@@ 333|actionable|Fix the weapon-radial crash before further testing
Opening the radial reproducibly crashes and can leave the process hanging. Slow motion and vertical centering are not accepted as working.

**Needs repair; testing remains deferred at your request.** Preserve the captured evidence and investigate the fault before another game run. This status is Actionable because the missing work is ours, not yours.

@@ 334|actionable|Keep the horse map marker visible and update its artwork
Preserve the owned horse's marker through ordinary distance/state changes and use validated RDR-compatible versions of the requested map artwork.

**Not delivered.** Resolve the marker lifecycle and assets, then provide a game test; copied RDR2 hashes alone are not implementation.

@@ 335|actionable|Use the shop mouse wheel for quantity
Scrolling should change the current buy/sell quantity within bounds, not move the selected item. Keyboard and controller behavior stay unchanged.

**Implementation remains.** Verify the actual shop input path and selection behavior before requesting acceptance.

@@ 336|actionable|Prepare complete controls for the installed development camera
The installed development build can enter the custom camera with tilde development mode enabled and F4.

**Test instructions are incomplete:** verify and document the movement/rotation bindings, then provide an enter, move, exit and cleanup check. Do not make you discover the controls by trial and error.

@@ 337|actionable|Finish the RDR1 structured editor surfaces
Complete the Items, Shops, Loot, Missions and Settings workflows using real project data and typed controls, with honest Data Map coverage and shared GitHub access.

**Partly implemented:** individual pages exist, but the complete scope and runtime deployment are not accepted. Remove misleading placeholders and preserve installed archives rather than treating tab names as coverage.

@@ 338|actionable|Start eligible carriage resting automatically
When the game's carriage Rest action becomes valid, begin it without an extra button press. Busy/ineligible states and normal carriage controls must remain intact.

**Not delivered.** Implement the real state transition rather than repeated synthetic input, then prepare a working carriage example.

@@ 339|untested|Check startup logos are skipped
RedHook is now installed and its startup-logo skipping setting is enabled; the original movie files were left unchanged.

- [ ] Fully close RDR1 and start it again through Lexeditor. Confirm the startup logo movies are skipped and the normal menu/loading sequence completes.
- [ ] Report any logo that remains or any launch failure. Do not enter the crashing weapon radial while #333 is unresolved.

@@ 340|untested|Check the repaired money and ammo HUD
The installed repair corrects the cash source and keeps HUD text out of loading screens.

- [ ] Restart RDR1 and load Story Mode. Confirm no stray numbers appear during loading, then check the money line includes $ and matches your balance.
- [ ] Fire/reload the equipped weapon without opening the crashing radial. Confirm ammunition updates steadily beneath money; report flicker, wrong values or alignment.

@@ 341|actionable|Prepare a deployed shop-price test
The Shops editor reads real stock, edits supported quantities/prices and saves isolated overrides without changing the installed archive.

**Runtime acceptance remains:** provide a specific shop/item edit, deployment route and expected in-game value. Editor readback alone does not establish that the game consumes the override.

@@ 342|actionable|Restore deliberate shoulder swapping in cover
The shoulder-swap control should alternate sides while John stays in cover, without relying solely on his movement direction.

**Implementation remains.** Verify the native cover/input/camera paths and preserve normal aiming and exit behavior before asking for a test.

@@ 343|actionable|Implement a reversible first-person toggle
V should toggle between a usable first-person view and the previous third-person camera, recovering safely after transitions.

**Research/implementation remains:** inspect the supplied reference mod and RDR camera data, then validate aim, riding, cover, cutscenes, death and loading. No candidate is ready for acceptance.

@@ 344|actionable|Prepare a repeatable mission-reward test
The Missions editor and runtime override file are connected, but the requested cash/fame/Honor results are not yet confirmed in game.

**Test preparation remains:** provide a named mission, suitable save, exact reward edit and deployment steps. Verify each reward occurs exactly once; do not make you replay unspecified content to discover what should change.

@@ 345|actionable|Finish the actual cutscene and campsite key remaps
Use E for cutscene skipping and T for campsite Travel to, with matching prompts and no changes to unrelated confirm controls.

**Still incomplete:** Travel to remains Return, and changing its prompt alone cannot fix the action. Implement a safe script-level remap rather than a global or synthetic confirm input.

@@ 350|waiting|Confirm where the remaining startup warning appears
Lexeditor already launches FF8 directly, so the warning's current source needs confirmation rather than another assumed launcher fix.

- [ ] Start FF8 with Lexeditor's Play button. Report whether the epilepsy warning appears; if it does, attach its text or a screenshot and say whether it appears before or inside the game window.

@@ 354|actionable|Add a no-magic-consumption tweak
When enabled, casting a spell should not reduce its stock. Disabling the tweak restores normal consumption.

**Not implemented.** Cover the relevant casting paths and compatibility with shared stock and GF spellbooks; then provide a before/after stock check.

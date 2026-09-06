# Reviewed RDR2 issue rewrites — continued

@@ 171|actionable|Prepare a readable drowning transition
At zero swimming stamina, death must become inevitable immediately, but a brief struggle/submerge should explain the outcome. No rescue window or warning overlay.

**Research done; prototype not delivered.** Test the corrected engine-owned drowning approach without forcing movement or camera effects, then provide the actual candidate and steps. Earlier zero-second and paired-animation proposals were rejected.

@@ 172|actionable|Verify safe placement beside respawn campfires
Campsite respawn must place Arthur on safe ground beside the fire, never on its origin or inside its props.

**Delivery remains unconfirmed:** the repair record ends at queued installation. Verify the installed build and coordinate with the unresolved campsite/respawn work before asking you to die and test it again.

@@ 174|actionable|Restore casing acquisition popups
Picking up a casing should show its name and artwork in the acquisition feed.

**Still unresolved:** fixing the icon alone did not repair the pickup path. The newer collection repair in #222 must be delivered and checked first; do not send this back for an unchanged icon-only retest.

@@ 176|actionable|Finish exhaustion without consuming cores
Empty outer bars must not fall back to cores. Empty Dead Eye stays unavailable until refilled, without disabling Eagle Eye; an exhausted horse should slow down and recover without requiring Ctrl.

**Partly repaired:** the Eagle Eye regression has an installed fix, but the reported horse exhaustion/recovery behavior remains unresolved. Keep the whole request open as development work.

@@ 177|actionable|Prepare a synchronized core-animation test
Core state is integer-valued and extracted core artwork has staged fills. That alone does not establish which update/presentation step causes the visible choppiness.

**Test preparation remains:** provide synchronized value logging and video instructions before asking for a capture. Do not add a replacement overlay or change restoration timing under this research-only request.

@@ 178|actionable|Finish collectible and location marker acceptance
The installed marker pass covers cards, bones, carvings, dreamcatchers, graves, exotics, legendary fish, shacks, treasure clues and points of interest. Each must appear, disappear and sit in the correct place without spoilers.

**Work remains:** resolve broken artwork (#245) and prepare the saves/authoring route for the position audit (#274). Preserve quest gates, grouped map entries and the deliberate exclusion of actual treasure caches.

@@ 179|actionable|Deliver animated holstering without a dead Tab key
Tapping Tab should put the weapon away with its authored animation, including during a draw, while preserving the wheel and other shared-key actions.

**Repair not confirmed installed:** the latest change fixes the module suppressing an input it could not read. Finish delivery and verify the key before asking you to repeat the failed test.

@@ 180|actionable|Resolve and deliver the cigarette-card glint change
The current body requests casing-style glints on real uncollected cards, but older comments also record a request to remove the feature because native cards already flash.

**Work remains:** reconcile the latest recorded decision before shipping anything. The newest glint code is unbuilt; do not present it as ready or silently reinstall a rejected feature.

@@ 181|actionable|Investigate why binocular animation speed does nothing
The transition-speed setting has no visible effect in your latest test. Earlier claims of working 10× speed were incorrect because the value was clamped.

**Needs investigation:** prove which animation path can actually be controlled and make the displayed bounds/units accurate. Failed attempts do not establish universal impossibility. The entry crash in #357 takes precedence over another binocular test.

@@ 182|waiting|Capture compendium state for the broader glint feature
Your scope is all relevant compendium entries, not only animals. The installed read-only probe collects identity/discovery evidence; it does not yet add the final glints.

- [ ] In the development build, set CompendiumGlintProbe Enabled to 1 and restart. Without using binoculars, press F10 while focused on a studied animal, an unstudied animal, a known horse breed and an unknown breed.
- [ ] Capture a herb before/after picking another instance, then owned/discovered and undiscovered weapon/equipment examples where available. Note which example each capture represents.
- [ ] Attach GameplayTweaks.compendium-probe.log and turn the probe off. Report any category that produced no record rather than repeating captures indefinitely.

@@ 184|actionable|Validate the reusable canteen with the repaired crafting menu
The installed prototype crafts a five-drink canteen from one Empty Bottle at a campfire. Drinking should spend one charge and restore the configured Stamina Core amount; refills and remaining water must persist correctly.

**Acceptance is not complete:** first deliver the outstanding crafting/menu repairs (#122) and a reliable pump-refill path (#185). Then supply a combined obtain, drink, refill and save/reload check.

@@ 185|actionable|Finish water-pump interactions and readable map artwork
Pumps should offer Hold E to drink and Hold R to refill the canteen, with aligned pumping animation and correct restoration.

**Work remains:** replace the rejected full-height pump icon with a readable head/handle design, and verify the scenario/placement evidence using the current extraction tools. The old blanket request for manual extraction is not a prepared human test.

@@ 186|waiting|Choose discovery behavior for new map icons
Custom markers should not reveal distant locations from the start. The proposed approach records discovery when you approach, while preserving quest gates.

- [ ] Choose whether existing saves should start with custom markers undiscovered or retain previously known locations where that history can be established.
- [ ] Specify which marker categories should always be visible and which should require nearby discovery.

@@ 187|actionable|Deliver stable horse water markers and feeding behavior
The owned horse should safely eat/drink when eligible, with correct restoration and clean interruption. Preserve the requested leading-state rules for water markers.

**Repair not delivered:** the latest fix for flashing/disappearing water icons is source-only. Build and verify that change and the actual horse interactions before asking for another leading test.

@@ 190|actionable|Hide untagged enemies when tagged-only minimap mode is enabled
Tagged Only On Minimap should hide untagged hostile humans and animals; switching it off restores ordinary visibility while keeping Recon tags.

**Still broken:** the latest report has untagged wolves appearing as native red dots. Trace and repair that path before requesting another unchanged test.

@@ 191|waiting|Compare the missing gold Stamina bar with a normal tonic
The engine supports a fortified Stamina bar. The current evidence does not establish whether Rampage's command or an interaction with the overhaul causes the missing gold display.

- [ ] On a disposable save, use Rampage's attribute-overpower command and capture the bars.
- [ ] Reload, use a tonic whose description fortifies Stamina, and capture the result. Report whether Stamina turns gold in each case and name the tonic. Do not edit attribute memory or build a diagnostic yourself.

@@ 192|actionable|Deliver Recon progress decay and distance fading
Recon must reliably identify/tag eligible targets. Completed tags use the configured distance fade; incomplete Study/tag progress should decay gradually at the selected rate instead of vanishing.

**Latest repair is unbuilt.** Finish delivery and prepare the actual settings/target comparison. Completed tags must not decay like incomplete study progress.

@@ 193|actionable|Restore reliable wall grabs before testing climbing
Free Climbing must grab valid surfaces, move correctly and mantle without sliding, clipping, teleporting or launching Arthur.

**Not test-ready:** the last contact-fit repair was built but not installed, and the later report says jumping at walls no longer grabs at all (#251). Restore the entry path before requesting dependent climbing tests.

@@ 194|actionable|Deliver a live count beneath each radial ammo icon
Every ammo icon needs its own correct reserve count, with zero quantities dimmed and no duplicated native X/Y display.

**Package not installed:** the latest repair finally targets the resolved native UI files, but delivery and live replacement verification remain. Do not ask you to recheck the same overlapping count display yet.

@@ 195|actionable|Implement the recoverable bloodstained hat
On death, leave the last-worn hat carrying the lost money, with the approved hat icon and notification. Recovery returns the money and removes the markers; a second death permanently replaces the old recoverable loss.

**The hat-based replacement is not confirmed delivered.** Preserve the exact approved notification in the retained specification and coordinate campsite respawn separately with #244. The older cash-bag behavior does not complete this request.

@@ 196|actionable|Prepare the shared ammo-cap test after radial counts are fixed
Each configured ammo family should have one combined limit across its variants; 0 keeps vanilla per-variant limits.

**Dependency/test preparation remains:** finish per-icon radial counts (#194), then provide the mixed-ammo capacity check and expected inventory totals. The obsolete cross-repository dependency must not send you to an unrelated issue.

@@ 201|actionable|Find a safe, local free-roam vulnerability implementation
The requested free-roam behavior must not affect mission protections or unrelated shop, station and newspaper interactions.

**Disabled, not test-ready:** the previous global hooks broke those interactions and were removed. A later logging repair did not restore the feature. Investigate an entity-local path; an engineering decision is not a human blocker.

@@ 202|actionable|Prepare a measurable Viking Comb Honor comparison
Carrying the comb should double eligible small positive social Honor gains, while leaving mission rewards, losses and larger gains unchanged.

**Test preparation remains:** establish the delivered candidate and provide a repeatable comparison with visible/measurable Honor values. “Confirm it doubles” without that setup is not a useful test request.

@@ 203|actionable|Prepare a controlled Viking Hatchet cash-loot test
Eligible victims killed with the Viking Hatchet should yield four times their actual cash loot, without changing item loot or authored payouts.

**Test preparation remains:** supply a controlled payout comparison and confirm the installed implementation. Random victims with unknown baseline cash cannot prove a 4× reward.

@@ 204|actionable|Deliver the fence Honor-pricing repair
Fence prices should use the requested inverted Honor relationship while normal shops retain their usual rules.

**Repair not delivered:** the latest source change avoids fighting the game's price multiplier, but was not built or installed. Finish delivery before requesting another shop-price comparison.

@@ 205|waiting|Choose interchangeable feather ingredients or one generic item
The latest proposal keeps species-specific feathers but lets recipes accept any member of a Feather category, instead of converting every ordinary feather into Flight Feathers.

- [ ] Confirm which design to use: category-based ingredients or the earlier single Flight Feather item.
- [ ] Confirm exotic mission plumes remain separate and whether any ordinary feather recipes need exceptions.

@@ 206|actionable|Prepare complete bait buy, sell and crafting checks
Bread, cheese, corn, cricket tins and worm cans need valid shop stock, prices, resale, crafting, carry caps and finite consumption.

**Test preparation remains:** specify each actual recipe/station, expected output and cap, and confirm the candidate is installed. Do not make you discover the expected behavior from a generic seven-part checklist.

@@ 207|untested|Compare Improved Sights with Stock Sights
The loaded component data defines a narrower aiming view, not improved bullet spread. Both vanilla and the current catalog show the same five-point displayed accuracy increase.

- [ ] At a gunsmith, compare Cattleman Revolver → Customize → Components → Sights, changing only Stock versus Improved Sights. Confirm the comparison bar changes as described.
- [ ] Take aiming screenshots from the same position with each sight. Improved should show a slightly narrower view. Report a missing difference; the Navy Revolver is not a valid test for this package.

@@ 208|waiting|Choose how to handle the unsupported gray-wallet display
The sale/Auto-Bank repair is installed, but conditional greying of the native wallet display has no supported path. Replacing the HUD would be a separate design change.

- [ ] Decide whether to keep the native wallet without greying or pursue a replacement display.
- [ ] On a disposable save at the wallet cap, compare a money gain with Auto-Bank on and off. Report wallet/bank changes and any missing cap notice; money must not be lost or oscillate.

@@ 210|actionable|Deliver newspaper markers that reflect actual availability
Show a newspaper marker only when that seller can offer a purchasable newspaper, retaining the native map-index category.

**Latest repair is not built/installed:** it changes the visibility of the real newspaper markers rather than creating misclassified replacements. Verify delivery before requesting another map/shop check.

@@ 212|unfeasible|Map zoom-step strength is not exposed by the proven path
The tested method only queues more equal-sized zoom inputs, producing lag rather than a stronger zoom step. No script-reachable step-strength control was found.

A faster responsive map zoom needs a different validated UI/input path. This limitation does not affect the completed map-centering feature (#114).

@@ 214|untested|Check safe collectible relocation and undo
The installed F2 repair acts on release: tap relocates the nearest eligible marker; holding for 800 ms undoes the last move. Development tools must remain inert when development mode is off.

- [ ] Enable tilde development mode. At a known nearby collectible, tap/release F2, then hold/release it for at least 800 ms. Confirm clear move/undo messages and the original position returns.
- [ ] Try with no eligible marker in range, then with development mode off. Confirm clear refusal in the first case and no relocation in the second. Report any wrong marker or failed undo.

@@ 216|untested|Check horse-location persistence across restarts
The installed feature records the owned horse's position and restores it on the next startup, without moving the player or duplicating the horse.

- [ ] Let the installed build run once, leave your horse outside whistling range and exit cleanly. Restart and load the save; confirm the same horse remains where you left it.
- [ ] Repeat with a hitched horse, then retrieve it normally. Report unexpected relocation, duplicates or broken stable/recall behavior.

@@ 220|actionable|Finish the two-view camera toggle in vehicles
You confirmed the two camera modes work on foot and horseback. Wagons, carts and buggies were still stuck in third person.

**Delivery needs verification:** the latest vehicle-toggle change claims one first/third-person state but does not identify a delivered, checked candidate. Confirm that before asking you to press V again; do not redo the accepted foot/horse work.

@@ 222|actionable|Deliver usable casing pickup prompts and rewards
Casings should have the correct casing name, a held-loot prompt, pickup animation and acquisition card, without granting live ammunition.

**Repair not confirmed installed:** the broken native-ammo-pickup route was replaced in source. Verify delivery and the longarm interaction before another test. A created object alone is not a functioning pickup.

@@ 223|unfeasible|L3 cannot switch wheel pages through injected controls
Holding L3 can open the weapon wheel, but the wheel ignores the tested injected page-switch input. That implementation was dropped.

Opening directly to Items needs a different validated wheel-navigation mechanism. Do not reinstall the failed input-injection version.

@@ 224|closed:not_planned|Keep cigarette-card markers grouped
**Dropped by your design choice.** Individual card names would split the map index into 144 entries. Keep the shared Cigarette Card category instead.

This is not an unimplemented request or proof that individual names are technically impossible.

@@ 225|actionable|Research a skills interface without assuming the pause menu can expand
The proposed skills system is not implemented. The native pause menu's fixed structure blocks that particular insertion approach, not every possible skills system.

**Research remains:** establish an appropriate interface and progression implementation before claiming the feature is unfeasible or asking you to test it.

@@ 226|actionable|Verify options for removing weight and mounted drain modifiers
Remove the unwanted perfect-weight/mounted contribution to core drain while preserving the intended overhaul rates.

**Research remains:** the old one-line “engine-hardcoded” note does not establish the precise boundary or rule out a safe alternative. Identify the actual control path and limitations before classifying it Unfeasible.

@@ 227|actionable|Investigate Dead Eye regeneration without kill-based gains
Regenerate Dead Eye according to the core instead of rewarding kills.

**Research remains:** the old claim that kill-based gain cannot be removed has no supporting boundary in the issue. Verify the source of gains and available controls; do not declare the whole feature impossible from an unsupported summary.

@@ 228|actionable|Research configurable bounty limits
Allow the intended maximum bounty changes without destabilizing law behavior or saved values.

**Research remains:** not having found a field or hook is not proof of impossibility. Establish the active limit and supported ways to change it, then report the actual boundary.

@@ 229|unfeasible|Plant density cannot be reduced by disabling picking
The tested scenario-point workaround leaves visible plants that cannot be picked, so it does not reduce plant density and was rejected.

A real reduction requires a validated placement/spawn path that removes the corresponding visible plants. That path has not been established; the broken workaround stays disabled.

@@ 230|closed:not_planned|Do not restore the rejected pulsing core effect
**Dropped.** The available effect controls produced pulses rather than the requested steady ramp, and a generic replacement vignette was explicitly rejected.

Keep this implementation removed. A future presentation-only approach would need separate evidence and approval.

@@ 231|actionable|Research a custom challenge menu for additional strands
The native menu has nine fixed strand links, so adding more strands through data alone does not supply a usable menu.

**A replacement-menu approach remains unimplemented.** Research that path and its progress/save behavior rather than calling all additional strands impossible. The old link to the mask-removal issue is unrelated.

@@ 232|actionable|Implement parallel challenge progress without duplicate strands
Allow the requested per-strand sequential/parallel rules while keeping one visible strand and correct progress.

**Work remains:** the reference workaround duplicates strands and breaks some goals; that disproves the workaround, not the entire feature. A correct runtime companion still needs implementation and validation.

@@ 234|waiting|Clarify the separate movement-rework request
This issue has no description. Human movement is already specified in #236, so the separate scope here is unknown.

- [ ] State what additional movement behavior this issue should cover, or confirm it is a duplicate of #236.

@@ 235|actionable|Restore the correct binocular mask
At scale 1 and opacity 1, the binocular mask should match the native shape and quality—not a pixelated single circle.

**Comparison/repair remains:** the last screenshot was not accepted as matching vanilla. Prepare a reliable reference and resolve the new entry crash (#357) before asking you to repeat a binocular test.

@@ 236|actionable|Deliver walk/sprint controls without forced movement
Holding Sprint should sprint; releasing it returns to walking. Remove crouch-running and inappropriate sprint restrictions while preserving normal locomotion.

**Latest repair is source-only.** Build, deliver and check it before retesting restricted locations. Absolute speed control remains a separate unresolved technical limitation, not a silently completed part of this feature.

@@ 238|actionable|Grey out items that cannot afford their core cost
An item that would take any affected core below zero must be visibly unavailable and unusable; an exact-zero result is allowed.

**Partly working:** you confirmed activation is blocked, but the radial entry is not greyed out. Implement the missing availability display rather than asking you to test the same invisible refusal again.

@@ 239|actionable|Deliver the pocket-watch font choices
Owning a pocket watch should show the game time in the requested top-right presentation. Keep its placement independent from temperature.

**Delivery remains:** the latest font selector is integrated in settings but not built/installed. Package it before asking you to compare the five font options visually.

@@ 240|untested|Check the thermometer and independent temperature position
The installed thermometer uses its own X/Y percent settings, independent of pocket-watch placement.

- [ ] Fully restart RDR2 with a thermometer bought from a general store. Compare the displayed temperature with the normal location/info popup.
- [ ] Change Thermometer Position X/Y in settings. Confirm the temperature moves within about one second without moving the clock, and survives restart. Report a mismatch or overlap.

# Reviewed RDR2 issue rewrites

@@ 101|actionable|Finish campsite activation and protect authored camps
Authored camps must be usable but not removable through normal play; disable free-roam camp creation while preserving mission requirements.

**Work remains:** the latest activation and map-name repairs are source-only, not built or installed. Deliver and verify those changes before asking you to repeat the camp test.

@@ 102|actionable|Finish fixed-HP rings for Recon tags
Recon tags should resemble native cores. Each overlapping ring represents a configured fixed amount of HP, not a percentage of the target's maximum; keep the selected color progression and horse-core exception.

**Not delivered:** the latest ring repair is built but its installation is unconfirmed. Finish delivery and prepare a target with known HP before requesting a visual test.

@@ 103|actionable|Replace the wagon stamina white square with a working HUD
Driving a wagon should use its horses' stamina and show a native-looking horse stamina display in the correct position.

**Still unresolved:** your tests reported a white square. Later build notes do not establish a repair for that rendering failure. Fix and check the actual display before another test request.

@@ 104|actionable|Restore animated binocular quick access
Holding Cover should raise and stow binoculars using the normal satchel animations, not make them appear instantly. A short tap must still work as Cover.

**Work remains:** earlier shortcut repairs exist, but the new binocular-entry crash in #357 blocks a safe acceptance test. Investigate that first; do not repeat the old test unchanged.

@@ 105|actionable|Finish manual belt-lantern control
The lantern stays on the belt when unlit; the radial controls its light. Crouching uses the requested dim state and standing restores the prior state. Preserve mission lanterns.

**Incomplete:** the latest control repair is not built/installed, and refusing selection while crouched does not yet grey out the radial entry. Orientation defects are #348; leg clipping is #295.

@@ 106|actionable|Finish combat dodge rolls and stamina rules
Space/Jump in the appropriate combat state should roll instead of dive, including fistfights. Each roll costs stamina; insufficient stamina does nothing, regeneration pauses during the roll, and first-person rolling stays disabled.

**Work remains:** the latest input change still needs validation and confirmed delivery. Do not ask you to test the obsolete Cover-key version.

@@ 107|actionable|Turn unique gun features into interchangeable components
Unique guns should unlock their distinctive parts for compatible ordinary guns, allowing them to be mixed at a gunsmith.

**Research only so far.** Prepare the proposed component prototype and check saves, ownership and dual-wield behavior. No playable candidate or design preview is ready for you.

@@ 108|actionable|Finish camera profiles and clear unsupported controls
Keep independent standing, crouched, prone, riding, vehicle and aiming profiles, with working shoulder changes and no aiming flashes or crouch bobbing.

**Incomplete:** profiles exist, but related defects remain in #267, #269 and #270. Continuous height adjustment is not established, and vehicle LOW framing is ignored by the current path. Do not present those controls as functional or call the whole editor accepted.

@@ 110|actionable|Finish minimap zoom help
You confirmed the minimap zoom works. The remaining request is help explaining that zooming out can hide crowded icons.

**Delivery remains:** the help was changed, but the in-game menu update was not built and installed. Do not reopen the accepted zoom behavior or ask you to retest it unnecessarily.

@@ 111|actionable|Improve the restored casing, bottle and ammo icons
The missing icons now appear, but you rejected their artwork as poor quality.

**Work remains:** prepare improved artwork previews for the affected casings, hulls, bottles and .225 AP round. This becomes a design-review request only once the previews are actually available.

@@ 113|actionable|Finish the remaining stealth audit conditions
Movement/noise research is already recorded; the remaining audit covers cover, lantern visibility and weather. Do not repeat completed trials.

**Test preparation remains:** confirm the short follow-up probe is installed and resolve its manual-lantern dependency (#105). Then provide its ready-gated capture steps and output location. An unconfirmed queued probe is not a task waiting on you.

@@ 116|actionable|Deliver visible muzzle-origin bullet tracers
Tracers should be visible day and night, originate at the weapon rather than the camera, and not duplicate the native trail.

**Not repaired in the delivered build:** your last test still had no visible tracers. The subsequent visibility repair is source-only. Build, install and check it before requesting another test.

@@ 118|untested|Check in-game settings and core-drain values
The latest installed repair fixes the in-game core-hour controls incorrectly changing saved values such as 24 hours to 0.01.

- [ ] Fully restart RDR2, press F8 and open Cores → CoreClock. Confirm the player and horse durations match your saved settings.
- [ ] Change one duration, save and reopen the menu; confirm only that value changed. Report any mismatched value or setting whose restart requirement is unclear.

@@ 119|actionable|Build detection indicators from verified stealth state
Add readable directional detection indicators without pretending RDR2 supplies one universal awareness percentage.

**Work remains:** reconcile the indicator implementation with the unfinished stealth audit (#113), then validate actual observer detection. An earlier claim that the dependency was complete is not sufficient evidence for testing this feature.

@@ 120|untested|Check the single development-mode toggle
The installed development build now uses the shared tilde toggle for development overlays instead of separate conflicting switches.

- [ ] Fully restart the development build. Press tilde twice; confirm the development/stamina-mode overlays hide and return together, once per press.
- [ ] Open the settings menu and confirm the removed ShowMode switch is absent. Report any tool that remains active while development mode is off.

@@ 121|actionable|Implement persistent progress without normal save reloading
Meaningful progress and consequences should save continuously, with no normal-player reload loop and a development-only recovery escape hatch.

**Not implemented.** Research safe handling of death, missions, crashes and save migration, then build and validate it. This large task is agent work, not a reason to file it as Waiting.

@@ 122|actionable|Finish the custom crafting menu and exit handling
Support the requested custom and breakdown recipes, including multiple outputs, without rewriting vanilla recipe data.

**Partly implemented:** the latest pause, exit and alt-tab repair is not built or installed. Finish delivery and verify safe return to gameplay before asking you to repeat the menu test.

@@ 123|actionable|Show remaining gold overfill accurately
Fortified cores and outer bars need separate gold-fill displays showing their remaining extra amount, not an all-or-nothing gold state.

**Incomplete:** the current approach mixes core/bar state and does not implement the requested core-shaped fill. Repair the value mapping and artwork; another generic ring or square is not a finished substitute.

@@ 124|untested|Check paying serious bounties instead of surrendering
The installed repair uses the game's High-severity crime classification and avoids the crash-prone crime query. Payoff should show the amount or shortfall and end pursuit only after valid payment.

- [ ] On a disposable free-roam save, incur a serious bounty and approach lawmen with enough cash. Use the displayed payoff action; confirm the exact amount is charged and bounty/pursuit clear without a crash.
- [ ] Repeat without enough cash. Confirm the shortfall is shown, payment is unavailable and no money is taken. Report the crime, displayed amount and failed step.

@@ 125|actionable|Prove that disabling core XP blocks real gains
Core XP gain should be disabled by default without corrupting ranks or maximum bars.

**Validation remains:** an unchanged XP total during ordinary play does not prove a successful block. Prepare a controlled earning test below the cap and verify both enabled and disabled behavior. Do not restore the unsafe rank-clamping attempt.

@@ 126|actionable|Expand overflow storage beyond the first-item prototype
Excess items should enter persistent storage with clear pickup feedback and a usable camp storage interface.

**Prototype only:** the installed camp interface currently covers Baked Beans. General item coverage, capacity behavior and persistence still need work. Do not describe one working item as the complete storage system.

@@ 128|actionable|Finish integrated ammo pickup controls
Keep the no-auto-pickup change inside the overhaul, not as a separate mod, and expose the relevant supported loot/prompt controls in Lexeditor.

**Partly done:** the data change is already merged into the overhaul. The editor controls and a prepared in-game check remain; another approval to integrate it is unnecessary.

@@ 129|actionable|Validate the animal density multiplier
Expose one meaningful animal-density multiplier; a value of 1 restores normal density.

**Validation remains:** the existing population counts came from different conditions and do not prove the multiplier works as claimed. Prepare a controlled comparison that accounts for existing animals and streaming before asking you to test it.

@@ 130|actionable|Build tonic refilling on shared overflow storage
Health, Stamina and Dead Eye tonics need upgradeable carried capacities. Camp visits and death should refill from storage, highest tier first, with a shortage notice.

**Not delivered:** the premature separate storage implementation was removed. Finish the shared storage dependency (#126), then implement this without a second competing inventory system.

@@ 131|actionable|Restore correct per-drink alcohol strengths
Expose each drink's real strength as an editable value, including the requested strong Moonshine behavior.

**Reported broken:** the latest report says all drink values became 1. Restore accurate baseline values and verify the effective in-game strengths before requesting another test.

@@ 132|untested|Check independent casing glints and their settings
The installed build adds glint timing variation and editable size, opacity, brightness, duration and fades.

- [ ] Fully restart RDR2 and reload a revolver. Confirm the ejected casings do not all flash in lockstep.
- [ ] Change one glint setting at a time, applying its stated reload/restart requirement. Confirm the named property visibly changes; report the setting and before/after result.

@@ 133|actionable|Research hunting by tracks instead of frequent animal sightings
Determine whether useful animal tracks can exist independently of visible live animals before designing very sparse, track-led hunting.

**Research remains:** prepare a controlled track/streaming probe and report viable approaches. Do not ask you to perform unsupported spawn/delete experiments or choose a solution before the evidence exists.

@@ 134|actionable|Expose meaningful per-item horse feeding and bonding
Let supported items define whether they can be fed to horses and how much bonding they grant, rather than offering a misleading catalog tag.

**Work remains:** feeding eligibility and bonding are script-owned. Investigate a configurable, event-aware data/hook path that preserves item consumption and avoids duplicate rewards. Shared bonding tiers are not independent per-item values.

@@ 135|actionable|Fix missing and stale train markers
Real passenger trains, cargo trains and streetcars should have the correct moving marker and direction arrow; stale markers must disappear when their train is gone.

**Still broken:** missing-marker reports remain unresolved. Validate live train detection and cleanup before treating the latest icon-class changes as a finished repair.

@@ 136|actionable|Investigate a usable trinket inventory view
Provide a trinket-only view without breaking the normal satchel.

**Research only:** the native satchel has fixed category handling. Prepare a working insertion or separate-page prototype before asking you to choose its presentation. No new tab is ready to test.

@@ 137|actionable|Grant cigarette cards when smoking, not buying packs
Smoking a premium cigarette should roll the configured card chance (default 20%), favoring unowned cards. Buying, collecting or discarding a pack must not grant a card; loose world cards remain unchanged.

**Not delivered:** the smoking-event change is integrated but its installation is unconfirmed. Verify delivery and the buy/collect/discard/smoke paths before requesting a test.

@@ 138|actionable|Prepare replacement map-icon previews
Show the proposed collectible/location icons, revise them from your feedback, then install the approved artwork.

**Previews still need preparing.** This is not waiting for your approval until there is actually something to review. Existing icon rendering failures remain #245.

@@ 139|actionable|Restore the pause menu while removing unwanted entries
Remove Online and Social Club without removing the rest of the pause menu.

**Repair not delivered:** your last report showed an empty menu. The corrected menu-data replacement is not installed. Deliver and check that repair before requesting another restart/test.

@@ 140|waiting|Choose what physical shop displays should show
A shop's catalog and its physical shelf props are separate. A representative display is practical; a visible prop for every stock item is not established.

- [ ] Choose the first shop to redesign and the items or categories that most need physical displays.
- [ ] Confirm whether a representative selection is acceptable, or whether showing every stocked item is essential to your design.

@@ 141|actionable|Prepare a workable way to add gunsmiths
Add gunsmiths to towns that lack them, with usable interiors, merchants and stock.

**Preparation remains:** provide a concrete authoring workflow or prototype covering the interior and shop behavior. You already asked how to do this; another vague request for you to design an interior is not an answer.

@@ 144|actionable|Prepare a valid casing-ejection comparison
Match custom casing positions and momentum to vanilla before removing the reference visuals.

**Test setup is incomplete:** the current restore does not cover the full layered weapon data, so it is not a reliable vanilla control. Fix that comparison first, then supply repeatable weapon/reload checks.

@@ 145|actionable|Finish missing editor icon extraction and decoding
Many previously missing icons have already been extracted. Remaining unresolved references and unsupported texture decoding still leave gaps.

**Agent work remains:** finish those paths and audit actual rendered failures. The old request for you to manually export whole dictionaries is stale.

@@ 146|untested|Check disabled horse-camera recentering
The corrected installed camera package loads, and the basic riding orbit was confirmed. Transitions and the toggle still need acceptance.

- [ ] Fully restart RDR2 with horse recentering disabled. Ride, rotate the camera sideways and release input; confirm it stays there.
- [ ] Aim, look behind, change camera view, then dismount/remount. Confirm controls recover normally. Re-enable recentering and restart; confirm normal behavior returns. Report the failing transition.

@@ 148|untested|Check compact shop filters and acceptance reporting
The rejected full-catalog layout was rolled back. Shops again uses compact categories, subcategories and search, with the effective acceptance report.

- [ ] Restart Lexeditor and open RDR2 Shops → Weapons → Revolvers. Search for a weapon and confirm category/filter changes keep the view compact and select the right records.
- [ ] Inspect a merchant's acceptance report and a test-mod Accept/Reject override. Save and reopen; confirm the chosen rule is retained and unknown behavior is not described as proven. Report the merchant/item and mismatch.

@@ 149|actionable|Finish configurable wanted duration and search areas
Let crimes create longer-lasting search pressure with configurable area and timing, preserving distinct areas where supported.

**Research/implementation remains:** the installed diagnostic crash repair is not the wanted-system rework. Establish the safe timing/area controls and prepare a usable prototype before requesting gameplay acceptance.

@@ 150|closed:completed|Explain enemy combat profiles, accuracy and health
**Research complete.** Enemy behavior is split across combat profiles, situational accuracy, tactics and shared health archetypes; there is no single authoritative per-model stat table.

The editor should expose those layers separately. This did not rebalance combat or establish model assignments. The ineffective assignment UI repair is tracked in #18.

@@ 151|actionable|Prepare the effect-duration experiment
Find what duration category changes by comparing controlled effects with deliberately different behavior, time and category values.

**The test has not been prepared.** Build and deliver the comparison records, specify how to obtain/use them, and provide exact measurements to report. Research needing a game session does not by itself make this Waiting.

@@ 152|waiting|Choose how weapon-stat previews should be presented
Real weapon/ammo/component fields are editable. The radial stat bars are derived summaries; their exact normalization has not been established, so a preview cannot honestly claim exact game values.

- [ ] Choose whether to include an explicitly approximate derived-bar preview or show only the authoritative mechanical fields.
- [ ] Identify any particular displayed stat that must match the game exactly before such a preview would be useful.

@@ 153|actionable|Finish collectible bottles and their pickup feedback
Empty bottles from consumed drinks should be collectible and produce the correct inventory feedback without duplication.

**Delivery remains:** the latest cleanup of the bottle/pickup presentation has not been built and installed. Verify the final-swig, stow and collection paths before asking for another test.

@@ 154|actionable|Explain and finish the bounty-hunter editor
Expose useful spawn, group, equipment, support and escalation controls so bounty hunters can be deliberately tuned.

**Work remains:** your latest report asks what each tier actually means. Add accurate, tier-specific explanations and verify which controls affect each behavior. Merely listing editable values does not answer that question.

@@ 155|actionable|Explain knockouts and the controls that actually affect them
Clarify how ordinary punches, knockouts, recovery and lethal follow-up attacks differ, then identify the exact editable controls needed for the requested nonlethal fistfights.

**Explanation/research remains:** the existing flag descriptions did not answer your question. Provide concrete controls and consequences instead of asking you to test unexplained settings.

@@ 156|actionable|Allow card sales only after the set is mailed
Cards must remain unsellable until their twelve-card set has been completed and mailed. Only later duplicates from that set may be sold; submitted cards must not reappear.

**No implementation is established.** Build and validate the per-set rule before requesting a test.

@@ 157|actionable|Explain and expose items missing from the satchel
Determine why ammo and other owned items do not appear in the satchel, then expose supported visibility rules without inventing a catalog toggle.

**Research remains:** different inventory contexts and native category handling need to be traced. There is no prepared change waiting on your acceptance.

@@ 158|unfeasible|Independent binocular zoom stages are not supported by the proven path
The available data changes the native range's base FOV, not each zoom stage independently. The attempted replacement camera failed in game and was removed.

Separate adjustable stages need a different validated camera/input path. Native binocular behavior is retained; overlay repair is #235 and the new entry crash is #357.

@@ 159|actionable|Build a compatible collection of standalone bug fixes
The candidate fixes cover unrelated clothing, carrying, messages, map artwork and completed-quest behavior.

**Audit done; implementation remains.** Select source-compatible fixes, preserve permissions and verify each independently. Researching the candidates is not a delivered bug-fix collection.

@@ 160|waiting|Choose truthful Player-page core-drain information
The native Player page calculates its own drain summaries, which do not describe the overhaul's activity-dependent rates. A display override is possible; changing unrelated game state is not a valid fix.

- [ ] Choose a replacement summary showing current activity and time-to-empty, or hide the misleading native drain rows.
- [ ] Specify any additional drain information the replacement must show.

@@ 161|actionable|Add real per-action Honor amounts
The editor currently offers event toggles and shared magnitude tiers, not an independent editable amount beside every action.

**Incomplete:** the event must be intercepted before its identity is lost. Investigate and implement that path; choosing the technical architecture is agent work, not a reason to wait on you. Do not present the shared tier table as completion.

@@ 162|waiting|Supply the custom casing pickup sound
A per-item sound category can route casings to a custom sound, but the audio still needs a compatible registered game-bank event.

- [ ] Attach the sound sample you want for picking up brass casings.
- [ ] State its source and any permission or credit requirements. After that, audio integration and both pickup-mode tests are agent work.

@@ 163|actionable|Remove world masks reassigned to challenge rewards
Masks reassigned to Bandit rewards must no longer be collectible from their old world locations. Preserve existing ownership and unrelated masks.

**Still broken:** your latest test found the Cat Mask still present. Verify a real removal before requesting the same test again.

@@ 164|untested|Check Ancient Tomahawk returns on every impact
The installed repair addresses the stale tracking state that allowed only the first throw to return. Return feedback also needs checking.

- [ ] Fully restart RDR2 and equip the Ancient Tomahawk. Throw it at the ground three times consecutively; each impact should immediately return it, not just the first.
- [ ] Repeat against a wall and a target. Confirm there is one usable copy and note whether the acquisition popup appears. Report which throw fails and attach that session's GameplayTweaks log.

@@ 165|untested|Check lost unique weapons can be recovered at the locker
The installed candidate keeps lost uniques pending and offers a named recovery action inside the ordinary weapon locker, rather than putting them back in your hands automatically.

- [ ] Fully restart RDR2 with the already-lost Viking Hatchet pending. Open the normal camp weapon locker; confirm it opens and shows Recover Viking Hatchet.
- [ ] Use the recovery action once, then reopen the locker. Confirm one unequipped copy is returned and the action disappears. Report a missing action, duplicate or failure to open the locker.

@@ 166|actionable|Deliver the Hunter's Hatchet animal-kill rework
The Hunter's Hatchet should instantly kill ordinary animals without reducing their original pelt quality. Preserve mission/legendary behavior and avoid duplicate loot.

**Delivery is unconfirmed:** the only build record says installation was queued. Confirm the actual installed candidate and prepare the quality comparison before requesting a test.

@@ 167|actionable|Develop usable prone weapon animations
Prone weapon selection, aiming and firing failed in the last test. Existing poses did not track the reticle or preserve a stable prone body.

**Work remains:** investigate retargeting or generating compatible upper-body animations and the required export pipeline, including longarms, reloads and binoculars. You explicitly asked us to pursue that; animation work is not automatically a task to hand back to you.

@@ 168|actionable|Rebuild owned-gear sparkle suppression safely
Owned weapons and collectible hats should stop advertising themselves as new pickups.

**Not working:** the weapon implementation was removed after repeated crash isolation. The hat path is also unfinished. Restore a safe implementation and prepare any necessary identification probe before asking you for a capture.

@@ 169|untested|Check restored thrown-weapon and arrow behavior
The installed weapon data restores missing vanilla projectile flags while keeping the overhaul's intended edits.

- [ ] Fully restart RDR2. Fire ordinary and special arrows; confirm normal impact and recovery behavior.
- [ ] Throw a knife, tomahawk and hatchet, then retrieve them. Report any missing impact, sticking or pickup behavior and the exact weapon/ammo type. Unique locker recovery is checked separately in #165.

@@ 170|waiting|Choose the remaining road-travel benefit
The stamina benefit can remain. The tested foot-speed method is limited to a 15% increase, which you rejected as too small; a stronger horse-only path remains unverified.

- [ ] Choose stamina savings only, or keep research into an additional horse-only speed benefit.
- [ ] Confirm whether a large speed boost for both Arthur and the horse is essential; no supported way to deliver that combined speed requirement has been established.

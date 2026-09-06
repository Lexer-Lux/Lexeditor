# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356304474 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190

Created: 2026-08-06T04:36:15Z; updated: 2026-09-05T06:59:38Z

Exact metadata: [source record](sources/issue-5356304474-3a334c331cf97c9458339db53230b528ccb047b950d475430b9a4f11fba8d433.json).

Go to places like Fort Wallace and attack. Everyone starts up red despite not being recon tagged.
However, I would like this to be a .ini toggle setting under Misc. Tagged Only On Minimap. When off, tagged things still show up on the minimap, but untagged things that would show up in vanilla are still allowed to as well.

## issue 5356304474 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190

Created: 2026-08-06T04:36:15Z; updated: 2026-09-06T12:55:21Z

Exact metadata: [source record](sources/issue-5356304474-b5196eddb0a126ab8b9299e8a07e046d0b9a41d37473b03f3173194bbbebeed9.json).

When Tagged Only On Minimap is enabled, untagged enemies and animals must stay hidden. Turning it off allows normal vanilla markers alongside tags.

**Status: Still broken.** The latest report found hostile wolves appearing as ordinary red dots immediately after howling. Investigate that concrete case; no newer successful repair is recorded.

## issue 5356304474 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190

Created: 2026-08-06T04:36:15Z; updated: 2026-09-06T13:57:48Z

Exact metadata: [source record](sources/issue-5356304474-89f035bd1a1eaff621dce7c330ce80c24a327590306da72c33d9a37a94c7b997.json).

When Tagged Only On Minimap is enabled, untagged enemies and animals must stay hidden. Turning it off allows normal vanilla markers alongside tags.

**Status: Still broken.** The latest report found hostile wolves appearing as ordinary red dots immediately after howling. Investigate that concrete case; no newer successful repair is recorded.

## comment 5550133062 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133062

Created: 2026-08-06T05:20:20Z; updated: 2026-08-06T05:20:20Z

Exact metadata: [source record](sources/comment-5550133062-33417a2e90057a29c59073fdfe9c078377b4121160fd1056631162cf22c472be.json).

Built and installed with `[Misc] TaggedOnlyOnMinimap=1` in GameplayTweaks ASI `7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`. At Fort Wallace, verify untagged defenders stay off the minimap, tagged enemies remain visible, and setting the toggle to `0` restores vanilla hostile dots.

## comment 5550133082 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133082

Created: 2026-08-06T07:48:34Z; updated: 2026-08-06T07:48:34Z

Exact metadata: [source record](sources/comment-5550133082-1facd014afeb0f086870b3e4591f82cb4492c44b476ba46ee6c2d76ae31814b4.json).

how bizarre. it seems as if their dots are still showing up, then they fade out when...i'm not looking at them? WTF? then they reappear when i look again???????? how does this even happen on accident???????????????

## comment 5550133095 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133095

Created: 2026-08-06T08:59:03Z; updated: 2026-08-06T08:59:03Z

Exact metadata: [source record](sources/comment-5550133095-4cdee3438974aaff1ebdce09e1e21e467a87428b4faf831376dc567227ec2f9d.json).

Marked-only minimap suppression and its `[Misc] TaggedOnlyOnMinimap` toggle are integrated and installed in `C92A04F…CCA3`. Moved to `test me` for Fort Wallace/tagged-enemy verification.

## comment 5550133112 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133112

Created: 2026-08-06T09:18:57Z; updated: 2026-08-06T09:18:57Z

Exact metadata: [source record](sources/comment-5550133112-73f8d7ded1b4b52e1bde94ea30253a1e88a6147bb771dfc5c8d738c9fca91ac2.json).

Correction: your report that hostile dots disappear and reappear based on camera direction was not addressed by the later deployment comment. This is back in actionable until that specific visibility bug is fixed.

## comment 5550133132 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133132

Created: 2026-08-06T12:01:37Z; updated: 2026-08-06T12:01:37Z

Exact metadata: [source record](sources/comment-5550133132-ff9b36a15f033aad14e5f12153335b2af53faf91d2bea8feaeeef195fc96d2fe.json).

still not fixed.

## comment 5550133145 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133145

Created: 2026-08-06T14:42:23Z; updated: 2026-08-06T14:42:23Z

Exact metadata: [source record](sources/comment-5550133145-2f137530294560216bd6f04b17fca2004cbb3cfd61cf50273a568a3c1a5f31cd.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. With marked-only minimap enabled, confirm unmarked hostile dots stay hidden across frustum changes and tagged targets remain visible.

## comment 5550133151 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133151

Created: 2026-08-06T19:25:23Z; updated: 2026-08-06T19:25:23Z

Exact metadata: [source record](sources/comment-5550133151-78016cfb753c3aef3fc34b828c8ff5e6e05f789d22d80d6f7079ab4944c22257.json).

got in a little skirmish. seemed to be working fine. went to fort wallace and fought. a bunch of red dots showed up. then disappeared? And when I aim at them they get tagged and their minimap icons come back.
So it seems like we're close!

## comment 5550133163 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133163

Created: 2026-08-09T06:35:32Z; updated: 2026-08-09T06:35:32Z

Exact metadata: [source record](sources/comment-5550133163-c657101df25b2fda2d949c8bfa2885b1d6ad097f5a42979123ec69567baddfda.json).

Crash-fix candidate installed in development build `77EB108E5106BA4E5E9993F2139828195BD3A57DB70347DD346C9AB6715D148D`.

The hostile sweep had been rate-limited, but `SET_POLICE_RADAR_BLIPS(FALSE)` was still outside that throttle and ran every frame. It now shares the 250 ms cadence. Rockstar's shipped calls are transition/event calls (`mob2.c:18609`, restore at `73159`), not a permanent per-frame write.

The unfinished hot-reload isolation is also complete: `PartMinimap`, `PartMarkers`, `PartBlips`, and `PartPlants` each gate and clean up their own layer, and recon heartbeats/pre-tag diagnostics record all four values plus a post-blip readback.

This remains `actionable`: first confirm a normal ped tag no longer freezes, then run the existing Fort Wallace marked-only checks. No label changed.

## comment 5550133174 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133174

Created: 2026-08-09T07:15:57Z; updated: 2026-08-09T07:15:57Z

Exact metadata: [source record](sources/comment-5550133174-0f9429635a03f8541cdc3d0817717e284d3312ad563ae81bb79c4b563f0184a3.json).

The installed 77EB... candidate still left unsafe recon work after a tag existed: per-frame SET_BLIP_ROTATION, per-frame polling of five texture dictionaries, and all recon creation/removal/scanning during the weapon-wheel/horse-weapon commit window. The remaining FFFFFFFF captures occurred in or immediately after exactly that transition.

The current source now pauses recon for the complete wheel transaction plus the existing 2-second horse-weapon commit guard. Texture polling and saddle-horse membership run at 1 Hz; existing blip mutation runs at 4 Hz and only after a heading change of at least five degrees. A new crash regression verifier passes, and development ASI BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5 builds.

I have not installed it over the isolated candidate yet. Lexer-Lux/Lexeditor#190 remains actionable; no label was changed.

## comment 5550133191 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133191

Created: 2026-08-09T07:19:07Z; updated: 2026-08-09T07:19:07Z

Exact metadata: [source record](sources/comment-5550133191-34fdba30594f99344e9509a01acb1836fca4ed4c8ceaa6a63e493f6b3afa8c6c.json).

The completed recon crash guard is now installed and hash-verified in development ASI BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5. Test a normal tag, then weapon-wheel/horse-rifle/binocular transitions; after that, test Fort Wallace marked-only visibility and toggle restoration. Moved from actionable to test me and read back OPEN with only test me.

## comment 5550133210 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133210

Created: 2026-08-09T07:41:54Z; updated: 2026-08-09T07:41:54Z

Exact metadata: [source record](sources/comment-5550133210-cc416ff35cb787f18b75c4639f105877cbe1efd12385434a944bc345c34bd531.json).

The installed crash-fix candidate failed its normal-tag acceptance check.

The unified trace ends at the exact completed dwell:
- mark begin ped=3330 kind=3
- recon blip created and read back
- marked ped=3330 kind=3 studied=1
- no later GameplayTweaks tick

kind=3 is ReconDisposition::Animal, so the selected target was the rider's horse, not the human. The tag path then called COMPENDIUM_HORSE_OBSERVED after creating the recon tag, duplicating Rockstar's own study transaction in short_update.c:8911-8945. Lexer-Lux/Lexeditor#190 is back to actionable while that duplicate compendium mutation is removed; no other issue labels are changing.

## comment 5550133230 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133230

Created: 2026-08-09T07:48:22Z; updated: 2026-08-09T07:48:22Z

Exact metadata: [source record](sources/comment-5550133230-940664b4a512fc797443b3bab87c663dac891ac419f1aa72575bd753f07d9895.json).

Installed mounted-target crash correction in development ASI D086398ABE350E919FA593A0096C14454A674FDA7856DFCA75C0CAABB292C0AF; source, game-root ASI and release manifest hashes match.

The failed trace selected the horse (kind=3 = Animal), not the rider, and ended immediately after recon independently forced COMPENDIUM_HORSE_OBSERVED. Recon now creates only its session tag and logs compendium=untouched; Rockstar's validated short_update path remains the sole owner of observed/studied compendium progress.

The crash guard now rejects both compendium mutators in recon. Re-test the exact reproduction: hold aim on a mounted target until the recon dwell fills and confirm the tag appears without ERROR:FFFFFFFF. Lexer-Lux/Lexeditor#190 is moved back to test me only because this corrected build is installed.

## comment 5550133248 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133248

Created: 2026-08-09T07:55:03Z; updated: 2026-08-09T07:55:03Z

Exact metadata: [source record](sources/comment-5550133248-21e6bd3ca255540faf2fa680db64da9f355fc1aba6155bb908a4202208260e28.json).

Correction from Lexer: recon Study is supposed to be one combined action. Holding R on the selected binocular target must fill Study, create the recon tag, and record the compendium observation when the entity has a valid compendium entry. Ordinary humans without an entry remain tag-only. The installed build removed the compendium half and the prompt was filling without reading R, so Lexer-Lux/Lexeditor#190 is actionable again while both are corrected through Rockstar's validated discovery path.

## comment 5550133267 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133267

Created: 2026-08-09T08:05:31Z; updated: 2026-08-09T08:05:31Z

Exact metadata: [source record](sources/comment-5550133267-2bf8cb7c0161abde3da52c647cbf8b165d984bc0fa470f949b6ac8051a397c46.json).

Corrected combined Study build installed: B05E3C1DBDA9C58EC7E6A22C8C9FA6DF77D814F4D3B53A1436E94E8BF6096D02 (source/game/manifest verified). The R prompt now advances only while R is held and resets on release. Completion creates the recon tag; valid nonhuman compendium targets are queued through Rockstar's discoverable name/type and player gate, written outside the blip transaction, and read back. Humans without entries remain tag-only. Test: hold R on a previously unstudied ordinary animal and horse, confirm tag + compendium observation, then repeat the mounted-person/fire-bottle reproduction without ERROR:FFFFFFFF. This is installed but not runtime-confirmed.

## comment 5550133280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133280

Created: 2026-08-09T08:07:59Z; updated: 2026-08-09T08:07:59Z

Exact metadata: [source record](sources/comment-5550133280-38c29ca7a2fd6578c5ec1f459d6879e1eb38ee3f4297cc52181c46131e67b2d6.json).

Lexer correction: the Study ring is progress toward the automatic recon tag, not a second input. Requiring R was wrong because binocular use may already involve Q/RB and weapon-aim tagging has no shared tag key. The indicator must show no key and fill automatically while the target continues satisfying the tagging requirements. Lexer-Lux/Lexeditor#190 is actionable again until that correction is rebuilt and installed.

## comment 5550133300 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133300

Created: 2026-08-09T08:11:46Z; updated: 2026-08-09T08:11:46Z

Exact metadata: [source record](sources/comment-5550133300-07d87a0a9d671e19047500a2c488e100ab7cc23c61184430d97b90b7b37b694f.json).

Automatic/keyless correction installed: 9111F78D3EEED32D0E6BB37B288174829DE3DC082B635D9F4302802922606A26 (source/game/manifest verified). There is no Study key now. The world-space Studying ring fills automatically while the selected target continues meeting the reticle, range, projected-size and LOS requirements in either binocular or weapon-aim mode. Losing the target resets acquisition. Tag completion and the validated/deferred eligible-compendium observation remain combined. Installed but not runtime-confirmed.

## comment 5550133314 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133314

Created: 2026-08-09T08:33:57Z; updated: 2026-08-09T08:33:57Z

Exact metadata: [source record](sources/comment-5550133314-88ffa94fc4085632bc3f08c4984aca2a0648b2e4b7691d29b4e3b9eb06c06a08.json).

Runtime crash confirmed again. The new minidump resolves the 0xC0000409 stack-cookie failure to selectReconPlantScenarioPoint(): the bulk scenario-point native overwrote its caller stack. The visible human tag was not the failing compendium path; humans are skipped correctly, and the horse seen behind the target was the player's own horse. Moving this back to actionable while the unsafe plant scanner is replaced and the repaired ASI is rebuilt/installed.

## comment 5550133325 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133325

Created: 2026-08-09T08:42:11Z; updated: 2026-08-09T08:42:11Z

Exact metadata: [source record](sources/comment-5550133325-1fe9e47607b07293e48d8fac60082408f46c0b8d768f65aea404c73cc5fd862e.json).

Crash repair installed. The dump-confirmed cause was the plant selector's bulk scenario-point out-buffer corrupting its stack, not the visible human tag or compendium skip. That native and caller-owned array are gone; plant selection now uses the reticle ray hit plus bounded one-result WB_ type queries. Installed/source/manifest SHA-256: BEB2B8D83DC829772957F3187C1D1C49A3B49BC0E126807D7E03DDAC75D9F446. Please restart RDR2 and retry the aim/throw tagging flow, binocular/weapon tagging, and continued aiming with no ped selected long enough to exercise plant scanning.

## comment 5550133342 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133342

Created: 2026-08-09T08:44:14Z; updated: 2026-08-09T08:44:14Z

Exact metadata: [source record](sources/comment-5550133342-7304cc603fadafbdb1478ec1a91f279f77ddb26bb538b8df983e49780e079d43.json).

Timing correction from Lexer: the old crash presented at the exact moment the human's full tag completed. The trace supports that—the final records are human mark begin, blip creation, human compendium skip, and completed mark. The minidump independently places the stack-cookie failure inside selectReconPlantScenarioPoint. A following selector call could fail before its post-call diagnostic, but that ordering is inference, not proof that tag completion was unrelated. The installed BEB2 build has not run yet (no log/dump newer than 02:19; it was installed at 02:41), so its acceptance test must explicitly include fully tagging a human.

## comment 5550133358 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133358

Created: 2026-08-09T09:09:37Z; updated: 2026-08-09T09:09:37Z

Exact metadata: [source record](sources/comment-5550133358-855e15b21dd70354af66e9eddea16e086a2cbf492fd898b592cc3cca0c339b91.json).

went to fort wallace and threw some molotovs. they all lit up red dots on the minimap one by one. then they all vanished. it seems like you're just looping through all map dots every fixed interval and hiding the ones for non-tagged people even though that's obviously an awful idea? if you have no way of actually preventing it to begin with then you would need to at least run this check before the end of each frame, no? otherwise it would be very obvious to the player when the dot suddenly appears then blinks out of existence shortly later

## comment 5550133370 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133370

Created: 2026-08-09T09:42:37Z; updated: 2026-08-09T09:42:37Z

Exact metadata: [source record](sources/comment-5550133370-88ebf00c3188c5bc96e5dcd2dc66259941670d56dbd47ba6b7ac45faac4fb8ef.json).

The latest Saint Denis FFFFFFFF run produced no new dump/Event 1000; the watchdog instead showed ScriptHook scheduling stop at WAIT while the independent map hook continued. Added world-transition containment: a >250 m jump discards the pre-teleport shared ped snapshot and quarantines full-world ped scans plus recon/stealth acquisition for five seconds while the destination streams. This is targeted containment, not a claimed faulting-instruction diagnosis. Installed/source/manifest SHA-256: F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28. Re-test ordinary tagging, then the same Saint Denis teleport and continued play.

## comment 5550133384 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133384

Created: 2026-08-09T11:20:47Z; updated: 2026-08-09T11:20:47Z

Exact metadata: [source record](sources/comment-5550133384-e5e4762aad29e9bf6379be4c38bf7834156768f5025b5db42a42a394bb1654cd.json).

The startup test failed on F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28. That retracts the earlier wording that called the crash fixed: a startup crash never exercised the post-teleport quarantine, which was containment rather than a proven fault fix.

The preserved run had no new minidump, Windows crash event, or vectored C++ exception; the watchdog ended at WAIT. The unified log did prove that multiple gameplay-mutating systems ran during initial loading while player control was unavailable. I repaired that lifecycle boundary: no gameplay systems or live save-state reads/writes now run until the player ped has existed, remained alive/unfaded, and been controllable for five continuous seconds. Clock/cash/bounty/honor baselines, recoverable uniques, toxicity, and the shop dump are seeded only after that gate releases.

Installed development ASI: 1F20B3DDE8DD78B5CF4065D11BA9DBFE04C91F168F9AF77F16EA6B56975153BA. Source/game-root ASI hashes and project/game-root manifests match. Static startup-quarantine and Lexer-Lux/Lexeditor#190 verifiers pass. This remains test me because the asynchronous Rockstar abort still requires runtime confirmation; stability is not being claimed from the build alone.

## comment 5550133399 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133399

Created: 2026-08-09T11:29:46Z; updated: 2026-08-09T11:29:46Z

Exact metadata: [source record](sources/comment-5550133399-0e84cc99fa35e7eeeb06b4ae5ef18828d462a570556a77026add412e1a8b8e2f.json).

The 1F20... startup test failed. The startup gate behaved as logged: it held gameplay mutations for 14 seconds and the error occurred about two seconds after release. No vectored exception, Windows crash event, or minidump was produced; the watchdog ended with the script yielded at WAIT.

The fresh log exposed the Lexer-Lux/Lexeditor#114 pause-map focus native still being written four times per second while MAP was closed, reaching eight writes immediately before the abort. That is the same native and same no-dump WAIT-stage startup failure previously caused by its per-frame loop; the earlier mitigation only reduced it from about 100 Hz to 4 Hz. I did not disable or blame the child-vulnerability feature merely because it also appeared near the end of the log.

The periodic focus mutation is now removed. It writes once only on a direct-map or pause-menu opening input edge, matching Rockstar document scripts focus-before-launch sequence.

Installed development ASI: 144FDA14CFF5426F1406FB8909E89A0399C50F7C6A952F7F722E2A3ADAD24E19. Source/game-root ASI and project/game-root manifest hashes match. Startup, Lexer-Lux/Lexeditor#114, and Lexer-Lux/Lexeditor#190 verifiers pass. Lexer-Lux/Lexeditor#190 remains test me; runtime stability is not claimed yet.

## comment 5550133414 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133414

Created: 2026-08-09T11:41:01Z; updated: 2026-08-09T11:41:01Z

Exact metadata: [source record](sources/comment-5550133414-e60cb46e31a41d78585449084abab83b1ad93c504ac70e92eb5304a865672225.json).

The 144F... build also failed. This run disproves the pause-map focus path as the remaining trigger: focusWrites stayed 0 for the entire session. The gate released correctly, the script ran for about six seconds, and Rockstar again aborted asynchronously while the script was yielded at WAIT, with no exception/event/dump.

The final recorded mutation was Lexer-Lux/Lexeditor#201 child vulnerability on the same nearby Saint Denis child. Its readback already said damageable=1 proofs=0, but the module issued the five damage/targeting setters again. Source inspection found it was actually doing that to every child every 250 ms; the periodic diagnostic added another write.

That blind loop is removed without disabling the feature. Targetability is now applied once per ped. Damage/proof writes repeat only when their readback proves Rockstar restored protection.

Installed ASI: 0064A7C4F446693A72F7472C0B17154B0A631C58678D999F50097A65AFC8FAB4. Source/game-root and manifest hashes match. Lexer-Lux/Lexeditor#190 remains test me; stability is not claimed yet.

## comment 5550133433 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133433

Created: 2026-08-09T12:03:50Z; updated: 2026-08-09T12:03:50Z

Exact metadata: [source record](sources/comment-5550133433-7445544c39c848e769b842f50cf8f739421876dc586f8ef9d44e5b420b7abd15.json).

The 0064... build also failed. I retract the last-record attribution: this run had zero map-focus writes, Lexer-Lux/Lexeditor#201 performed only one legitimate first application to a protected child, and the same asynchronous abort followed. The normal log cannot name the trigger because the script is already at WAIT when Rockstar aborts; whichever subsystem logged last is not necessarily causal.

I have installed a hard update-pipeline bisect instead of another guessed fix. Diagnostic ASI F2890DEAA091C02D3B77540B8B7BC6291CFB893C8A98DE75B231384EEB63D5A6 defines GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_QUARTER and contains the bisect early-quarter WAIT marker. It runs only menus, vendor/mail/campfire policy, wanted trace, wagon stamina, horse persistence and autonomous horse needs, then yields before map, inventory, binoculars, recon, stealth, radial, projectile, prone, child, minimap, density, and the rest.

Source/game-root ASI and project/game-root manifest hashes match. On one launch, another crash proves the cause is in the enabled early quarter; surviving proves it is in the disabled remainder. This build is only for crash isolation, not normal feature acceptance.

## comment 5550133447 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133447

Created: 2026-08-09T12:09:24Z; updated: 2026-08-09T12:09:24Z

Exact metadata: [source record](sources/comment-5550133447-10959db6decea3c3ea492639ac51783d767fc51cb60412d3a621f67d688087f3.json).

Rockstar is catching this failure internally and leaving RDR2.exe alive with the ERROR:FFFFFFFF dialog. That means Windows receives no unhandled exception, so WER and the plugin vectored handler have nothing to dump.

I added and armed an external live-dump watcher: tools/runtime/Capture-RDR2-ErrorDump.ps1. It detects the ERROR:FFFFFFFF top-level window, then calls Dbghelp MiniDumpWriteDump directly against the still-running RDR2 PID with full memory, handles, indirect memory, unloaded modules, process/thread data, and thread information. Its P/Invoke/window detector validates under Windows PowerShell and it is running hidden at a 100 ms poll interval.

On the next error, leave the dialog open briefly. The dump will be written under C:\RDR2Mod\crash-dumps. This runs alongside the installed F289... early-quarter hard-bisect build.

## comment 5550133457 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133457

Created: 2026-08-09T12:17:36Z; updated: 2026-08-09T12:17:36Z

Exact metadata: [source record](sources/comment-5550133457-d42a4c3bbbc3b21ba42942a6e4704aaec5fed4dbfa5e4ad4a626c5718977882a.json).

Early-quarter bisect result: stable. The live watchdog confirms stage=bisect early-quarter WAIT with continuing script ticks, and the dump watcher saw no error. That clears menus, newspaper/mail/campfire policy, wanted trace, wagon stamina, horse persistence, and autonomous horse needs; the crash is in the disabled remainder.

The next wider diagnostic is built: 06351B5E14B3AC1365D57E10FD6BAC8A32CCB68E31FCB81A6AB017A8201149CE with GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_MID_A and the bisect early-mid-a WAIT marker. It adds map input-edge handling, core XP, tonics, honor shop pricing, casings, bottles, carried-mask sync, partial bounty, and merchant overrides, then stops before dodge/binocular/recon/stealth/radial/projectile/prone/child/minimap and later systems. Installer is waiting for RDR2 to exit; full-dump watcher remains armed.

## comment 5550133469 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133469

Created: 2026-08-09T12:21:49Z; updated: 2026-08-09T12:21:49Z

Exact metadata: [source record](sources/comment-5550133469-2151bc26a68c33d056d286aa015aced380e166a56cfe47a7735934f2aa097657.json).

Early-mid-a bisect result: stable. Installed hash and the fresh session confirm the wider build, and the watchdog shows stage=bisect early-mid-a WAIT with advancing ticks. That clears pause-map input-edge handling, core XP, tonics, honor pricing, casings, bottles, carried-mask sync, partial bounty, and merchant overrides.

Next diagnostic built: 552508C2C9407B2D82D9234B03E46C71714FDB1B603D8B4D47C86A0442A67E2D with GAMEPLAYTWEAKS_CRASH_UPDATE_BINOCULAR_GROUP and the bisect binocular-group WAIT marker. It adds dodge, binocular access, improved-binocular access, and the read-only compendium probe, then stops before plant/recon/stealth/radial/projectile/prone/child/minimap/density and later systems. Installer waits for RDR2 exit; dump watcher stays armed.

## comment 5550133483 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133483

Created: 2026-08-10T02:07:52Z; updated: 2026-08-10T02:07:52Z

Exact metadata: [source record](sources/comment-5550133483-ef4471acc05eed0083bdfd2789c3c19700680ed6958f8055543f0a3d3dc89f41.json).

Binocular-group result: stable. The game-root hash, fresh ScriptHook session, and watchdog marker all confirm 552508... was running. That clears dodge, binocular access, improved binocular access, and the read-only compendium probe.

Next diagnostic built: C37F2F5608286343CC17AFF41FBD9BE366071FB3D76841BB6801BF446811272B with GAMEPLAYTWEAKS_CRASH_UPDATE_PLANT_ONLY and the bisect plant-only WAIT marker. It adds only learnPlantModels, then stops immediately before recon. Installer waits for RDR2 exit; full-dump watcher remains armed.

## comment 5550133507 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133507

Created: 2026-08-10T02:16:10Z; updated: 2026-08-10T02:16:10Z

Exact metadata: [source record](sources/comment-5550133507-60efb1d5fbdb938e8307cbb17b1ae7d3de3b9c7705b16aa582ebd406e1665d61.json).

Replaced the one-build-per-group crash loop with a single progressive diagnostic build.

Installed ASI: `62CC667BC3478AA87D790601153AA2CA60658A29637D8DB4F19BCB6A6A35D819` (source/game-root hashes match).

After the existing 5-second controllable-save quarantine, the already-proven binocular baseline runs first. The same process then logs and activates one additional group every 15 seconds: plant learning, recon, stealth/radial/projectiles, first-half remainder, core clock/minimap, Dead Eye/stamina/horse reserve, then bandit/economy/world. The activation record is written before that group executes, and every hold has a distinct watchdog stage. Survival past 105 seconds reaches the full pipeline.

This corrects the diagnostic gap in the combined logger: Rockstar can raise `ERROR:FFFFFFFF` several frames after our script has returned to `WAIT`, so the last ordinary subsystem record is not causal. The external full-memory dump watcher remains armed as a backstop.

No labels changed; Lexer-Lux/Lexeditor#190 remains open with `test me` only. Restart RDR2 once for this run.

## comment 5550133523 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133523

Created: 2026-08-10T02:35:14Z; updated: 2026-08-10T02:35:14Z

Exact metadata: [source record](sources/comment-5550133523-8851fb29f41a0b0d0bc2feab522183079afb95794f74e361ce7b28133a80a47c.json).

The progressive run isolated the delayed `ERROR:FFFFFFFF` to `first-half-remainder`: plant learning, recon, and stealth/radial/projectiles each survived their full window; the crash appeared about 200 ms after first-half remainder activated, before core clock/minimap was allowed to run.

The external watcher also completed the first useful full-memory capture: `RDR2-75732-20260809-201911-full.dmp` (12,784,557,031 bytes). WinDbg loaded the matching GameplayTweaks PDB. The main thread is in Rockstar's deliberate `MessageBoxW` error path after the ScriptHook fiber already yielded, so the dump confirms the delayed-abort shape but contains no exception frame naming the earlier native.

A finer one-run build is ready: `4A57E306F023CEF8F3312D244BD9127276D17BBFDE8DB108B910E74E6EF5B211`. It activates ten smaller groups three seconds apart and stops before core clock/minimap. Installer PID 70732 is waiting for the current crashed RDR2 process to close, then will install and hash-verify it automatically.

No labels changed; Lexer-Lux/Lexeditor#190 remains open with `test me` only.

## comment 5550133541 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133541

Created: 2026-08-10T02:50:54Z; updated: 2026-08-10T02:50:54Z

Exact metadata: [source record](sources/comment-5550133541-445486d06a5742789f6cda83650f47f34108f964aeb7bedf68a939c681664f46.json).

The fine one-run split narrowed the crash to exactly three calls. Every group through recoverable uniques survived; `unique-weapons-gear` activated, then the delayed abort occurred before child vulnerability.

I did not attribute the final tomahawk log as causal because Ancient Tomahawk, Hunter Hatchet, and owned-gear sparkle suppression all completed before the engine raised the error.

The final automatic split is built as `DEB758C75F729896DF52475A0563CAEBC961B61217F60F792B1B1FFECF1F48A8`: Ancient Tomahawk activates at 27 seconds, Hunter Hatchet at 30, sparkle suppression at 33, and child handling at 36. Installer PID 80484 is waiting for crashed RDR2 PID 87408 to close.

No labels changed; Lexer-Lux/Lexeditor#190 remains open with `test me` only.

## comment 5550133566 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133566

Created: 2026-08-10T03:05:54Z; updated: 2026-08-10T03:05:54Z

Exact metadata: [source record](sources/comment-5550133566-284c59b35a886baa22bdca1553260e9faddbbc6a18b4ff2bc37daa72a0eedfc2.json).

Final isolation result: Ancient Tomahawk survived its three-second window, Hunter Hatchet survived its three-second window, and `ERROR:FFFFFFFF` began only after `owned-gear-sparkles` activated. Child vulnerability never ran.

Root cause in `suppressOwnedGearSparkles`: two documented SDK setters were followed by undocumented hash `0x50C14328119E1DD1`, locally mislabeled `BLOCK_PICKUP_LIGHT`, with an object handle. The SDK's actual `BLOCK_PICKUP_PLACEMENT_LIGHT` is different hash `0x0552AA3FFC5B87AA`; the third mutation had no valid evidence or signature.

Removed the fabricated native. The feature still uses the documented pickup particle-highlight and pickup-object glow setters, now with validated pickup/object handles and unified suppression logging.

Installed full non-bisect ASI: `20606EB185A06CB52AF979EFAEB8021F94E42ADC8B94172F7EFAF3CB8CA6BB6B`. Source/game-root ASI and manifest hashes match. No labels changed; Lexer-Lux/Lexeditor#190 remains `test me`.

## comment 5550133581 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133581

Created: 2026-08-10T04:35:35Z; updated: 2026-08-10T04:35:35Z

Exact metadata: [source record](sources/comment-5550133581-c7a132554a8259db0ff3cc9bb37b9dcd0ddc3edfede58e4911e434a47cad5cf9.json).

The shortened continuation run conclusively survived the repaired Ancient Tomahawk path and Hunter Hatchet, then aborted after owned-gear sparkle activation while child vulnerability was still held. The entire Lexer-Lux/Lexeditor#168 weapon-sparkle runtime has been removed from the normal build rather than hidden behind a switch. Installed normal ASI: 80105728F13BBD3CAC5D54832B252744018461DFDE296F9A52B93CC3043806CF. No runtime stability claim yet; Lexer-Lux/Lexeditor#190 remains test me and no labels were changed.

## comment 5550133599 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/190#issuecomment-5550133599

Created: 2026-08-11T02:24:21Z; updated: 2026-08-11T02:24:21Z

Exact metadata: [source record](sources/comment-5550133599-458add6f7180eeaccf31b62eaa8eb9272b004d2dd6061710f08e644fb41e9b59.json).

Came across some hostile wolves at night. They howled and immediately showed up on the map.
As red dots, nonetheless -- exactly as in vanilla.
They didn't even disappear immediately...what do the logs say?

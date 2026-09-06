# GitHub #94 — Marked-only Minimap Awareness...isn't

## 2026-08-05 implementation

The existing suppression pass deliberately returned during missions and skipped
law-group and mission-owned peds. Fort Wallace defenders therefore retained
their vanilla red entity blips even with marked-only minimap behavior enabled.

The recon module now applies the suppression pass to every untagged living human
enemy, including law and mission-owned peds. Tagged targets remain exempt and
retain the recon-created blip.

The module reads the requested `[Misc] TaggedOnlyOnMinimap` setting directly.
If the new key is absent, it falls back to the existing
`[ReconTagging] MarkedOnlyMinimap` value, preserving current installations until
the integration-owned INI and shared loader are updated.

Integration must add:

```ini
[Misc]
TaggedOnlyOnMinimap=1
```

No build or installation was performed by the feature agent. Runtime acceptance
must confirm at Fort Wallace that untagged defenders do not appear red when the
toggle is `1`, tagged defenders still appear, and setting it to `0` restores
vanilla untagged hostile blips.

Integration added `[Misc] TaggedOnlyOnMinimap=1`, removed the obsolete shipped
ReconTagging key while retaining code fallback for older INIs, and built and
installed matching ASI SHA-256
`7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`.

## 2026-08-06 camera-direction fix

The installed implementation removed only entity-backed blips returned by
`GET_BLIP_FROM_ENTITY`, on a 100 ms scan. That did not own Rockstar's separate
police-radar awareness layer. Fort Wallace visibility tracking could regenerate
that layer as defenders entered the camera frustum, explaining the exact
reported behavior: dots faded after removal while looking away, then reappeared
when looking back.

Rockstar's own scripts use `PLAYER::SET_POLICE_RADAR_BLIPS(false)` when they need
the police layer hidden. Marked-only mode now applies that native continuously,
before the throttled entity scan. The existing scan remains in place for other
hostile entity blips, and its `isReconTagged` exemption is unchanged. Recon tags
continue using explicit entity-backed blips, so the police-layer switch does not
hide them.

When `[Misc] TaggedOnlyOnMinimap` changes to `0`, the module restores
`SET_POLICE_RADAR_BLIPS(true)` once and relinquishes control, then returns
without removing vanilla hostile entity blips. The existing fallback to
`[ReconTagging] MarkedOnlyMinimap` is unchanged.

Static verification checks the engine-layer call occurs before the 100 ms
throttle, the off-toggle restoration exists, tagged targets remain exempt, and
ordinary hostile entity cleanup remains present. No build, install, or runtime
test was performed by the feature agent. Fort Wallace still requires in-game
acceptance while rotating the camera through a full circle, plus a toggle-off
check and a tagged-defender visibility check.

## 2026-08-06 persistent-handle correction

The installed camera-direction fix still failed. `SET_POLICE_RADAR_BLIPS(false)`
covered only the engine police-radar layer; the remaining Fort Wallace dots
were Rockstar-owned entity blips. Deleting those handles every 100 ms created a
regeneration loop: the owning scripts could recreate a defender's blip when he
entered the camera frustum, exactly matching the reported disappear/reappear
behavior.

The suppression pass no longer deletes engine-owned blips. It applies the
shipped `BLIP_MODIFIER_HIDDEN` to every current untagged hostile handle and
tracks those handles. The modifier is reasserted every frame, with no 100 ms
visibility window, so looking toward a defender cannot leave a regenerated
handle visible between scans.
The modifier is not inferred from its unhashed name alone: Story scripts such
as `abigail2_1.c`, `braithwaites1.c`, and `feud1.c` apply hash `-1186550032`
to hide live blips and remove that same modifier to show them again.

The tracked state is reversible. Turning `[Misc] TaggedOnlyOnMinimap` off
removes `BLIP_MODIFIER_HIDDEN` from every surviving vanilla handle and restores
the police-radar layer. Tagging a previously suppressed defender removes the
hidden modifier before the recon marker is created; the per-frame pass also
restores any tracked handle it sees on a tagged ped. Newly hidden handles are
logged once in `GameplayTweaks.recon.log`, providing concrete runtime evidence
if a different radar layer remains.

`python tools/reverse-engineering/verify_marked_only_minimap_issue_94.py`
passed. It requires per-frame hidden-modifier suppression, tracked restoration
for both tagging and toggle-off, and rejects both deletion of Rockstar-owned
hostile blips and reintroduction of the throttled visibility window.

No build, install, GitHub state/label change, commit, or push was performed in
this source pass. Runtime acceptance still requires Fort Wallace with a full
camera rotation: every untagged hostile dot must remain absent; tagging one
defender must show that defender continuously; changing the toggle to `0` must
restore vanilla hostile dots without a reload.

## 2026-08-09 freeze correction and resumable isolation

The unified log and initialization-only control established that the recurring
freeze came from GameplayTweaks feature updates. Disabling all of recon stopped
it. In the last installed failing session, `GameplayTweaks.log` stopped while a
first ped tag was being created and resumed about 100 seconds later with
`pedTags=1`; the independent watchdog showed the script thread suspended at
`WAIT`, consistent with an engine-side stall rather than a C++ loop.

The earlier 250 ms correction rate-limited the hostile-ped enumeration and
hidden-modifier writes, but left `PLAYER::SET_POLICE_RADAR_BLIPS(FALSE)` before
the throttle. It still mutated the engine-owned radar layer every frame.
Rockstar's shipped scripts call this native on state changes (`mob2.c:18609` and
the restore at `mob2.c:73159`), not continuously. The write now shares the
hostile sweep's 250 ms cadence instead of running roughly 100 times per second.

Claude's unfinished four-way recon isolation was completed. `PartMinimap`,
`PartMarkers`, `PartBlips`, and `PartPlants` now each gate the named subsystem,
hot-reload every two seconds, remove any owned state when disabled, and appear
in both idle heartbeats and pre-tag diagnostics. The pre-tag log also records a
separate post-blip readback, so another stall cannot be reported as a completed
mark if blip creation/configuration never returned.

Development ASI SHA-256
`77EB108E5106BA4E5E9993F2139828195BD3A57DB70347DD346C9AB6715D148D`
was installed and source/game hashes were verified. This is a crash-fix
candidate, not runtime acceptance. #94 remains `actionable` pending a normal ped
tag plus the Fort Wallace marked-only acceptance checks.

### Remaining wheel-transition mutation removed

The installed candidate still left three recon maintenance paths unconstrained
after a tag existed: `SET_BLIP_ROTATION` ran every frame, five texture
dictionaries were polled every frame, and all recon creation/removal/scanning
continued during the weapon-wheel/horse-weapon transaction. The remaining
FFFFFFF captures were specifically in that transaction or immediately on its
binocular/weapon exit, so this was not safe enough.

The current source returns from recon for the whole wheel transaction and its
existing 2-second commit guard. Texture checks run at 1 Hz, saddle-horse
membership at 1 Hz, and existing blip mutation at 4 Hz only after heading
changes by at least five degrees. The police layer and hostile sweep remain on
their separate 4 Hz cadence. `verify_recon_crash_guard.py` pins all of those
properties and passes.

Development ASI
`BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5`
builds with the correction. It is not installed over the earlier isolated
candidate yet; #94 remains `actionable` and no label changed.

### Installed handoff

The bounded recon maintenance/wheel guard shipped in development ASI
`BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5`;
source and game-root hashes match. #94 was manually changed from `actionable` to
`test me` and read back as open with only `test me`. Acceptance is a normal tag,
weapon-wheel/horse-rifle/binocular transitions without FFFFFFFF, then the Fort
Wallace marked-only visibility and toggle restoration checks.

## 2026-08-09 mounted-horse completion crash

The installed `BEBA903A...` candidate failed its required normal-tag check. The
player held aim with a fire bottle at a mounted man; when the recon Study dwell
filled, the game produced the same `ERROR:FFFFFFFF`. `GameplayTweaks.log` ended
at the completed tag transaction:

```text
[recon] mark begin ped=3330 kind=3
[recon] mark blip ped=3330 handle=111618 exists=1
[recon] marked ped=3330 kind=3 studied=1 ...
```

`kind=3` is `ReconDisposition::Animal`, so recon had selected the mount rather
than sending a human through an animal branch. The unsafe behavior was the
independent compendium mutation after tag creation. Rockstar's Story Mode
`short_update.c:8911-8945` validates the targeted ped through
`PLAYER::_0x0139637A3BFF8B6D` and `_0x0772F87D7B07719A`, then owns the calls to
`COMPENDIUM_HORSE_OBSERVED` / `COMPENDIUM_ANIMAL_OBSERVED_BY_STAT_NAME`.
Recon skipped that transaction owner and called the mutator itself.

Recon completion now creates only its session tag and logs
`compendium=untouched`; vanilla remains the sole owner of compendium progress.
`verify_recon_crash_guard.py` rejects either compendium mutator anywhere in the
recon module. #94 returned from `test me` to `actionable` when the failure was
reported. A rebuilt/install candidate and the same mounted-target acceptance
test remain required.

### Installed mounted-target correction

Development ASI
`D086398ABE350E919FA593A0096C14454A674FDA7856DFCA75C0CAABB292C0AF`
was built and installed while RDR2 was closed. Source, game-root artifact and
`release-manifest.json` hashes match. The recon crash guard, marked-only
minimap verifier and recon-appearance verifier all pass. #94 moved from
`actionable` to `test me` only after installation. Runtime acceptance is the
reported mounted-target reproduction: hold aim until the recon dwell completes,
confirm the tag appears without `ERROR:FFFFFFFF`, then continue into the
existing Fort Wallace marked-only checks.

## 2026-08-09 combined Study intent correction

Lexer clarified that removing compendium behavior was not an acceptable crash
repair. The requested action is explicitly combined: while a target is selected
through the binoculars, holding R fills the Study prompt; completion creates the
recon tag and, when possible, studies the target for the compendium. A human
without a compendium entry still receives the recon tag.

The prompt had only displayed `INPUT_CONTEXT_X`; its timer advanced without
reading that control. The timer is now gated by pressed/disabled-pressed state
for input groups 0 and 2, resets on release, and cannot complete unless the
control remains held.

The compendium half is restored without the failed unconditional transaction.
Before queuing a write, recon now requires a living nonhuman ped, model, animal
type, short description, Rockstar discoverable name/type pair, and the same
`PLAYER::_0x0772F87D7B07719A` player/discovery gate used by
`short_update.c:8911-8945`. It checks `COMPENDIUM_WAS_ANIMAL_OBSERVED`, delays
the write by 300 ms so it cannot overlap recon blip creation, revalidates the
entity identity and discovery pair, yields to a vanilla observation if one
landed first, calls the horse or animal mutator as appropriate, and logs a
second observed-state readback 300 ms later. It never calls a compendium mutator
inside `markReconTarget`.

`verify_recon_crash_guard.py`, the #94 marked-only verifier, and the #2 recon
appearance verifier pass. Development ASI
`B05E3C1DBDA9C58EC7E6A22C8C9FA6DF77D814F4D3B53A1436E94E8BF6096D02`
builds successfully. Runtime acceptance must hold R on a fresh ordinary animal
and a horse, confirm the tag appears, confirm the compendium observation when
the entry was previously unknown, and reproduce the mounted-person/fire-bottle
case without `ERROR:FFFFFFFF`.

The corrected build was installed while RDR2 was closed. Source, game-root ASI,
and `release-manifest.json` all read back as
`B05E3C1DBDA9C58EC7E6A22C8C9FA6DF77D814F4D3B53A1436E94E8BF6096D02`.

## 2026-08-09 automatic acquisition correction

Lexer corrected the input model before testing: the Study ring represents
progress toward the automatic tag. It must advance while the selected target
continues satisfying the tag requirements. Requiring R was incompatible with
binocular entry on Q/RB and with the separate weapon-aim tagging path.

The R hold detector and control-action prompt were removed. The same dwell timer
again advances automatically from stable target selection and resets when the
target/aim state is lost. Because there is no common tag button, the native
button prompt was replaced with a keyless world-space `Studying` ring and label
anchored to the selected target. The validated/deferred compendium transaction
is unchanged.

Development ASI
`9111F78D3EEED32D0E6BB37B288174829DE3DC082B635D9F4302802922606A26`
was built and installed while RDR2 was closed. Source, game-root ASI, and release
manifest hashes match. Runtime acceptance must confirm that acquisition starts
without another button in both binocular and weapon-aim paths, the keyless ring
tracks stable dwell, and tag plus eligible compendium observation complete.

## 2026-08-09 plant-scenario stack corruption

The next `ERROR:FFFFFFFF` was a confirmed plugin crash rather than another
compendium theory. Windows Event 1000 reported `0xC0000409` in
`GameplayTweaks.asi`; the new `RDR2.exe.75080.dmp` resolved the exception to
`__report_gsfailure` and its plugin return address to
`selectReconPlantScenarioPoint`. The installed and rebuilt ASIs had identical
`.text` sections, so the current linker map resolved the crashing build exactly.
The function's call to `_GET_SCENARIO_POINT_CLOSE_TO_COORDS` had overwritten its
stack and the compiler cookie failed when the function returned.

The animal compendium write and failed observed-state readback completed,
gameplay continued for more than three seconds, and the later human target
correctly logged `human-no-animal-entry`. Lexer clarified that the horse behind
the man was the player's own horse and that the visible crash happened at the
moment the human's tag completed. The log supports that timing: its final four
records are the human mark begin, blip creation, compendium skip, and completed
mark. The minidump independently proves that the security-cookie failure was in
the plant selector. Because the plant diagnostic is emitted only after that
selector returns, a following selector call could fail without another log
line, but that ordering is an inference rather than proof that the visible tag
completion was unrelated.

The bulk caller-owned scenario array was removed. Plant acquisition now uses the
fresh asynchronous reticle-ray world hit, queries Rockstar's one-result
`_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE` for each shipped WB_ harvestable
type, deduplicates returned handles, and caches/revalidates the best point on a
250 ms scan cadence. No native writes into a plugin-owned scenario-point buffer.

Development ASI
`BEB2B8D83DC829772957F3187C1D1C49A3B49BC0E126807D7E03DDAC75D9F446`
was built and installed while RDR2 was closed. Source, game-root ASI, and
release-manifest hashes matched. The recon crash guard, #94 marked-only verifier,
and #2 recon-appearance verifier passed. Runtime acceptance remained the same
reported aim/throw and binocular/weapon-aim flows, now with enough continued use
to exercise the no-ped plant-selection path that caused the delayed crash.

## 2026-08-09 Saint Denis world-transition failure

The `BEB2...` build ran for roughly 42 minutes before Lexer teleported to Saint
Denis and received the generic `ERROR:FFFFFFFF` again. This was not another copy
of the prior `/GS` failure: Windows created no new crash dump or Event 1000. The
independent watchdog showed the ScriptHook gameplay thread stopped being
scheduled at `WAIT`; the map-zoom hook thread continued logging until the process
ended. The same run also exposed the unrelated MMB Eagle Eye and sticky binocular
start-gate regressions recorded under #78 and #4.

Fast travel can move the player hundreds of metres between scheduled frames
while the shared 250 ms world-ped snapshot still contains streaming-out handles
from the old region. The integration layer now detects a jump over 250 metres,
immediately discards that snapshot, logs both endpoints, and quarantines all
full-world ped scans plus recon/stealth acquisition for five seconds. The next
scan is built fresh from the destination population. This is containment for the
observed transition boundary, not a claim that a dump identified a new faulting
instruction.

Development ASI
`F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28`
was built and installed while RDR2 was closed. Source, game-root ASI and release
manifest hashes matched. Runtime acceptance requires ordinary tagging followed
by the same teleport to Saint Denis and continued play after the five-second
world-transition quarantine.

## 2026-08-09 startup failure after transition containment

Lexer received the same `ERROR:FFFFFFFF` immediately after starting the game on
the `F185...` build. That invalidated the earlier wording that called the crash
fixed: the startup failure could not have exercised the post-teleport quarantine,
and that quarantine was only containment for a suspected stale-handle boundary.

The preserved `F185...` session produced neither a new Windows crash event nor a
new minidump or vectored-exception record. The independent watchdog last recorded
the script at `WAIT`, not inside a named feature call. The unified log did prove a
separate unsafe lifecycle fact: `GameplayTweaks` began running native-backed
feature mutations while Rockstar still reported player control unavailable.
Campfire banks, carried-mask sync, minimap, animal density and other systems ran
during those first loading frames. The source also read or wrote toxicity,
recoverable-unique, shop, clock, cash, bounty and honor state before the main
loop had established a live player.

The integration layer now holds every gameplay feature behind a startup gate.
It permits only file/configuration reload and liveness logging until the player
ped exists, is alive, the screen is not faded, and player control has remained
available for five continuous seconds. Any interruption resets the settle timer.
Only after release does it initialize recoverable uniques and toxicity, dump the
shop database, and seed clock/cash/bounty/honor baselines from the settled save.

`verify_startup_quarantine.py` and the #94 marked-only minimap verifier passed.
The development ASI built and was installed while RDR2 was closed. Source and
game-root ASI hashes are
`1F20B3DDE8DD78B5CF4065D11BA9DBFE04C91F168F9AF77F16EA6B56975153BA`;
project and game-root release manifests also match. This is a structural repair
for the startup lifecycle violation proven by the log. It is not evidence that
the asynchronous Rockstar abort has been reproduced at a faulting instruction,
so runtime stability remains to be confirmed.

## 2026-08-09 startup gate runtime failure and owned-mutation correction

The `1F20...` build failed immediately after startup. The gate itself behaved as
implemented: the unified log waited for the player, began its continuous settle
at +0.8 seconds, and released gameplay systems at +14.2 seconds. The failure
arrived roughly two seconds later. No C++ exception, crash event, or minidump was
produced; the watchdog showed the script had yielded at `WAIT` when Rockstar
aborted asynchronously.

The final log exposed the still-active #14 pause-map focus poll. It wrote four
times per second while MAP was closed and reached eight writes immediately
before the abort. This is the same native and symptom as the previously proven
per-frame startup freeze recorded in `fuckups.txt`; the earlier change only
reduced the call from roughly 100 Hz to 4 Hz. It did not establish an owned
transaction. The unrelated child-vulnerability feature also ran in the final
window, but it was not disabled or blamed from ordering alone.

The periodic focus mutation is removed. It now mirrors Rockstar's one-shot
focus-before-launch sequence by writing only on a direct-map or pause-menu input
edge. The development ASI built as
`144FDA14CFF5426F1406FB8909E89A0399C50F7C6A952F7F722E2A3ADAD24E19`.
The startup-quarantine, #14 pause-map, and #94 marked-only verifiers passed.
It was installed after RDR2 exited; source/game-root ASI and
project/game-root manifest hashes match. Runtime stability is not claimed
before another launch.

## 2026-08-09 input-edge map build also failed

The `144F...` build produced the same error. This run disproved the pause-map
focus mutation as the remaining trigger: `map-recenter` logged
`focusWrites=0` throughout. The startup gate released after the player was
stable, the script ran for about six seconds, then stopped at `WAIT` with no
vectored exception, Windows crash event, or minidump.

The final recorded mutation was #105 child vulnerability. The same Saint Denis
child was logged as already `damageable=1 proofs=0`, but all damage and targeting
setters were issued again. The module source also issued that same five-native
bundle on every 250 ms scan without logging each repetition. This repeated
mutation is removed without disabling the feature: targetability is one-shot per
ped, while damage layers are reapplied only after readable protection state
actually returns. The `0064...` development build contains that correction.

## 2026-08-09 update-pipeline hard bisect

The `0064...` build also failed. This run demonstrated why the previous
last-record attribution was invalid: #105 performed only one first application
to a genuinely protected child (`damageable=0 proofs=255`), no redundant repeat
occurred, and the same asynchronous abort followed. Map focus remained at zero.
The unified log stopped about three seconds after feature release; the watchdog
again showed the script already yielded at `WAIT`, with no exception, Windows
event, or minidump.

The existing compile-time update boundary is now being used instead of another
feature guess. Diagnostic development ASI
`F2890DEAA091C02D3B77540B8B7BC6291CFB893C8A98DE75B231384EEB63D5A6`
defines `GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_QUARTER`; its binary contains the
`bisect early-quarter WAIT` marker. It runs only menus, vendor/mail/campfire
policy, wanted trace, wagon stamina, horse persistence and autonomous horse
needs, then yields before pause-map, inventory, binoculars, recon, stealth,
radial, projectile, prone, child, minimap, density and the rest of the pipeline.

The hidden installer landed the build after RDR2 exited; source/game-root ASI
and project/game-root manifest hashes match. One launch of this build establishes
a real binary result: a crash places the fault in the enabled early quarter;
stability places it in the disabled remainder. No normal feature acceptance
should be attempted on this diagnostic build.

### External live-dump capture armed

The repeated failure is caught inside Rockstar: `RDR2.exe` remains alive with
the dialog, the ScriptHook thread is yielded, and Windows receives no unhandled
exception. That is why neither WER nor the in-process vectored handler creates a
dump. The prior `rundll32 comsvcs.dll, MiniDump` attempt also had invalid command
syntax and produced only a RunDLL error.

`tools/runtime/Capture-RDR2-ErrorDump.ps1` now monitors top-level windows outside
the game process. On an `ERROR:FFFFFFFF` title it calls `Dbghelp.dll`'s
`MiniDumpWriteDump` directly against the live RDR2 PID with full memory, handles,
indirect memory, unloaded modules, process/thread data and thread information.
The P/Invoke types and window detector compile under Windows PowerShell. The
watcher is running hidden as PID 86832 at a 100 ms poll interval. Dumps and its
audit log go to `C:\RDR2Mod\crash-dumps`. If the early-quarter bisect fails,
leaving the dialog open allows the watcher to capture the first useful native
process image of the engine-owned abort.

### Early-quarter result: stable

Lexer reported no crash on `F289...`. The installed log confirms the hard
boundary was active: the independent watchdog repeatedly recorded
`stage=bisect early-quarter WAIT`, script ticks continued, the unified log
showed only the enabled early-quarter systems, and the external watcher saw no
error window or dump. The crash source is therefore outside the enabled group;
menus, newspaper/mail/campfire policy, wanted trace, wagon stamina, horse
persistence and autonomous horse needs are cleared by this run.

The next diagnostic widens the boundary to
`GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_MID_A`. Development ASI
`06351B5E14B3AC1365D57E10FD6BAC8A32CCB68E31FCB81A6AB017A8201149CE`
contains the `bisect early-mid-a WAIT` marker. It adds pause-map input-edge
handling, core XP, tonics, honor shop pricing, spent casings, bottle handling,
carried-mask synchronization, partial bounty and merchant-buy overrides, then
yields before dodge/binocular/recon/stealth/radial/projectile/prone/child/minimap
and the later pipeline. A hidden installer is waiting for RDR2 to exit; the
external full-dump watcher remains armed.

### Early-mid-a result: stable

The installed ASI hash and fresh ScriptHook session prove Lexer restarted onto
`0635...`. Its watchdog repeatedly recorded `stage=bisect early-mid-a WAIT`
with advancing ticks, and Lexer reported it remained stable. This clears the
added group: pause-map input-edge handling, core XP, tonics, honor shop pricing,
spent casings, bottle handling, carried-mask synchronization, partial bounty and
merchant-buy overrides.

The next diagnostic defines `GAMEPLAYTWEAKS_CRASH_UPDATE_BINOCULAR_GROUP`.
Development ASI
`552508C2C9407B2D82D9234B03E46C71714FDB1B603D8B4D47C86A0442A67E2D`
contains the `bisect binocular-group WAIT` marker. It adds directional dodge,
binocular access, improved-binocular access and the read-only compendium probe,
then yields before plant learning, recon, stealth, radial ammo, projectiles,
prone, child vulnerability, minimap, animal density and later systems. A hidden
installer is waiting for RDR2 to exit; the dump watcher remains armed.

### Binocular-group result: stable

The game-root hash is `5525...`, ScriptHook started a fresh process with that
build, and the watchdog repeatedly records `stage=bisect binocular-group WAIT`
with advancing ticks. Lexer reported no crash. Directional dodge, binocular
access, improved-binocular access and the read-only compendium probe are cleared.

The next diagnostic defines `GAMEPLAYTWEAKS_CRASH_UPDATE_PLANT_ONLY`.
Development ASI
`C37F2F5608286343CC17AFF41FBD9BE366071FB3D76841BB6801BF446811272B`
contains the `bisect plant-only WAIT` marker. It adds only `learnPlantModels`,
then yields immediately before recon tagging. A hidden installer is waiting for
RDR2 to exit and the full-dump watcher remains armed.

### Manual one-build-per-group loop replaced

The plant-only build landed when RDR2 exited, but it was superseded before a
separate runtime result was requested. The combined log had not fulfilled its
diagnostic purpose for this failure: it ordered subsystem events, but Rockstar
raised the engine-owned error several frames after the script returned to
`WAIT`, so the last record was not a causal record. The external live-dump
watcher filled the missing process-image path, but the hard compile-time
boundaries still required one build and relaunch per group.

Development ASI
`62CC667BC3478AA87D790601153AA2CA60658A29637D8DB4F19BCB6A6A35D819`
defines `GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE` and replaces that loop with
one timed run. After the existing five-second startup quarantine it begins at
the already-proven binocular boundary, then logs and activates these groups at
15-second intervals: plant learning, recon, stealth/radial/projectiles, the
remainder of the first half, core clock/minimap, Dead Eye/stamina/horse reserve,
and bandit/economy/world. Every activation is written before the group executes,
and each hold has a distinct watchdog stage. A crash therefore identifies the
newly activated causal window without another diagnostic build; survival past
105 seconds reaches the full pipeline.

The progressive verifier passed, the compiled ASI contains every activation and
hold marker, the release manifest verified the artifact hash, and direct install
while RDR2 was closed produced matching source/game-root hashes. The external
full-dump watcher remains armed as PID 86832. No issue labels were changed.

### Progressive result and first successful full dump

The one-run activation sequence worked. Plant learning, recon, and
stealth/radial/projectiles each survived their complete 15-second window. At
`elapsed_ms=60000`, the logger activated `first-half-remainder`; the ordinary
update completed and reached the hold before core clock/minimap, then Rockstar
raised `ERROR:FFFFFFFF` roughly 200 ms after that group's first execution.
Core clock/minimap and every later group never ran. This bounds the fault to the
first-half remainder rather than the last ordinary subsystem log record.

The external watcher detected the error window for RDR2 PID 75732 and completed
`crash-dumps/RDR2-75732-20260809-201911-full.dmp` at 12,784,557,031 bytes.
WinDbg loaded the matching private GameplayTweaks PDB. The main thread was in
`MessageBoxW`, entered through Rockstar's deliberate error path at
`RDR2+0x25b5394`; the ScriptHook fiber had already yielded and no GameplayTweaks
mutation frame or unhandled exception existed. The dump therefore proves the
engine-owned delayed-abort shape and preserves the process image, but it cannot
name the earlier native by an exception stack.

The next development ASI,
`4A57E306F023CEF8F3312D244BD9127276D17BBFDE8DB108B910E74E6EF5B211`,
defines `GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE`. It begins at the
proven baseline through stealth/radial/projectiles, then activates ten smaller
first-half groups at three-second intervals: movement/prone/climbing,
caps/camera clamp, death/campsites, bloodstain/holster/lantern,
gameplay/horse camera/feed, cards/alcohol/toxic/honor, canteen/water,
recoverable uniques, unique weapons/gear, and child vulnerability. It then
holds before core clock/minimap. The verifier passed and the release manifest
matches the artifact. Installer PID 70732 is waiting for the crashed RDR2
process to close before landing and hash-verifying it. No labels changed.

### Exact crash source and repaired full build

The final three-way run proved Ancient Tomahawk stable for three seconds and
Hunter Hatchet stable for the next three. `ERROR:FFFFFFFF` occurred only after
`owned-gear-sparkles` activated; child vulnerability was still held. The crash
source was therefore `suppressOwnedGearSparkles`, not either weapon feature.

That function called the SDK's documented
`SET_PICKUP_PARTICLE_FX_HIGHLIGHT` and `_SET_PICKUP_OBJECT_GLOW_ENABLED`, then
called undocumented hash `0x50C14328119E1DD1` through a fabricated
`BLOCK_PICKUP_LIGHT` wrapper and passed it a pickup object. The SDK's actual
`BLOCK_PICKUP_PLACEMENT_LIGHT` is different hash `0x0552AA3FFC5B87AA`; the
third mutation had no evidence or valid signature.

The fabricated native was removed. The feature retains the two documented
visible-effect setters and now validates both pickup and object handles before
using them, while logging each newly suppressed owned pickup. The repair
verifier passed. Full, non-bisect development ASI
`20606EB185A06CB52AF979EFAEB8021F94E42ADC8B94172F7EFAF3CB8CA6BB6B`
was installed after the crashed process closed; the complete update pipeline is
enabled. Source/game-root hashes match. No issue labels changed.

### First-half fine split result

The fine split reached and survived movement/prone/climbing, caps/camera clamp,
death/campsites, bloodstain/holster/lantern, gameplay/horse camera/feed,
cards/alcohol/toxic/honor, canteen/water, and recoverable uniques. It crashed
after `unique-weapons-gear` activated and before child vulnerability. The
remaining causal window is exactly three calls: Ancient Tomahawk return, Hunter
Hatchet handling, and owned-gear sparkle suppression. The final tomahawk log is
not attributed as causal because all three calls completed before the delayed
abort.

A second full-dump capture began automatically, but it was redundant with the
already-completed matching-PDB dump, so watcher PID 86832 was stopped rather
than intentionally writing another complete 12.78 GB process image. The partial
second dump was not used as evidence.

Development ASI
`DEB758C75F729896DF52475A0563CAEBC961B61217F60F792B1B1FFECF1F48A8`
keeps the same one-run first-half sequence but separates those final three
calls: Ancient Tomahawk at 27 seconds, Hunter Hatchet at 30 seconds, and
owned-gear sparkle suppression at 33 seconds, followed by child vulnerability
at 36 seconds. The static verifier passed, the binary contains the three stage
markers, and the release manifest matches the artifact. Installer PID 80484 is
waiting for crashed RDR2 PID 87408 to close. No labels changed.

### First sparkle repair disproved the exact-native attribution

The complete non-bisect `20606EB1...` build was installed and the next RDR2
process loaded that exact hash, but it raised `ERROR:FFFFFFFF` roughly 2.7
seconds after the five-second startup quarantine released. The unified log had
no owned-gear suppression record, so no configured pickup matched and neither
retained sparkle setter executed. Removing undocumented hash
`0x50C14328119E1DD1` was therefore insufficient, and it was incorrect to record
that individual native as the proven exact cause.

The controller has now been narrowed at the subsystem boundary proven by the
three-way staging: it no longer traverses or mutates the pickup-placement pool.
It scans loaded unattached objects and uses only the object-typed glow setter on
matching owned gear. The ordinary full update pipeline remains enabled; runtime
stability is not claimed until the replacement build survives in-game.

The installed `0F2BD482...` object-pool replacement failed with the same timing:
about two seconds after the startup quarantine released. Inspection found a
remaining native type-contract violation in that repair. The loop excluded
attached objects but did not require `OBJECT::IS_OBJECT_A_PICKUP` before passing
an arbitrary matching weapon-model object to `_SET_PICKUP_OBJECT_GLOW_ENABLED`.
The SDK's dedicated pickup-object predicate is now mandatory before that call.

The guarded full build `E24B7216...` still produced `ERROR:FFFFFFFF` immediately
after the normal pipeline released. Its log reached child-vulnerability writes,
but the issue worklog already records that identical final-log ordering did not
prove #105 causal. A fresh first-half progressive diagnostic was therefore
built from the guarded source as `CA01E91A...`. It activates each bounded group
at three-second intervals, with owned-gear sparkle at 33 seconds and child
vulnerability separately at 36 seconds. This is diagnostic only; no issue
labels changed and no runtime result is claimed before the staged launch.

The `CA01E91A...` run survived through recoverable uniques and aborted after
Ancient Tomahawk activation while held before Hunter Hatchet. #65's unarmed idle
polling was removed in normal build `54FDAB5A...`; its next live log confirmed
`monitoring=0 equipped=0`, but the full pipeline still aborted after later
mutations. A shortened continuation diagnostic `9230C8A7...` starts with all
already-cleared groups through recoverable uniques active, then releases Ancient
Tomahawk immediately, Hunter Hatchet at +3 s, owned-gear sparkle at +6 s, and
child vulnerability at +9 s. The binary contains the continuation marker and
not the original full-start marker. No workflow labels changed.

The `9230C8A7...` continuation survived Ancient Tomahawk and Hunter Hatchet,
then aborted only after owned-gear sparkle activation while held before child
vulnerability. This independently repeated the earlier sparkle boundary after
both attempted scanner repairs. The complete owned-gear sparkle runtime was
removed from the live translation unit for the next normal build; the behavior
is recorded as failed under #69 rather than represented as working.

## 2026-08-11 recurrence audit: untagged hostile animals

- **Primary evidence/reference:** Lexer saw untagged hostile wolves howl and
  appear as persistent vanilla red dots. The installed log has no matching
  `minimap hid untagged hostile` record. The current suppression loop proves
  why: it rejects every ped for which `IS_PED_HUMAN` is false before it reads
  the entity blip or disposition.
- **Sanctioned path:** use the same reversible Rockstar
  `BLIP_MODIFIER_HIDDEN` ownership already used for untagged hostile humans,
  but include living hostile animals. Preserve the recon-tag exemption and the
  player's horse exemption. Do not delete Rockstar-owned handles and do not
  reintroduce a timed visible window.
- **Execution proof:** log newly hidden handles with human/animal classification,
  disposition, and a surviving-blip readback. The absence of a recon-created
  marker does not prove a vanilla hostile dot was hidden.
- **Player-visible acceptance:** untagged hostile wolves and human enemies stay
  absent from the minimap; tagging one restores only its recon diamond; changing
  `TaggedOnlyOnMinimap` to `0` restores the vanilla handles.
- **Cadence:** retain the bounded 250 ms hostile sweep and one-time modifier
  application per handle. Never apply the modifier or police-radar setter every
  frame.

## 2026-08-11 hostile-animal suppression repair

The current code matched the live report exactly. The 250 ms sweep returned
early on `!PED::IS_PED_HUMAN(other)`, so it could never inspect, classify, or
hide a wolf's Rockstar-owned entity blip. This also explains the installed log:
the module remained active with `PartMinimap=1`, but no `minimap hid` record was
possible for the reported wolves.

The human-only gate is removed. Living hostile animals now go through the same
relationship/combat classification and reversible `BLIP_MODIFIER_HIDDEN` path
as hostile humans. The player's saddle horse and every recon-tagged target stay
exempt. New suppression records include human/animal classification,
disposition, and a post-call blip-exists readback. The police layer, entity
handle scan, and modifier application remain on the existing 250 ms cadence;
no handle is deleted and no modifier is reapplied once tracked.

`python tools/reverse-engineering/verify_marked_only_minimap_issue_94.py`
passed. Runtime acceptance is still required with untagged hostile wolves:
their vanilla red dots must stay absent, tagging one must show only its recon
diamond, and disabling `TaggedOnlyOnMinimap` must restore vanilla dots.

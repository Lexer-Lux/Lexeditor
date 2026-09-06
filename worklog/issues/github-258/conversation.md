# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356322222 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/258

Created: 2026-08-10T18:25:42Z; updated: 2026-09-05T07:03:23Z

Exact metadata: [source record](sources/issue-5356322222-298b61f0a310e93087b8992df3eabeb92cbfccb7bd8c7cf1d4ea5ed795a7b172.json).

Instead of just mantling at the top, Arthur like...slides down a bit, then teleports back to the top, then mantles?

## issue 5356322222 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/258

Created: 2026-08-10T18:25:42Z; updated: 2026-09-06T12:56:47Z

Exact metadata: [source record](sources/issue-5356322222-0211a2c589b61bf7b30abc10323b9611c2df83b74669b5b05a89cfb3cdd3fe37.json).

Arthur should mantle smoothly at the top rather than slide down, snap upward and then animate.

**Status: The actual mantle defect was not repaired in the latest notes.** Earlier handoffs only improved the probes used to reach it, and current wall-grabbing is broken again. Restore reliable climbing and diagnose the mantle transition before another test.

## comment 5550152803 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/258#issuecomment-5550152803

Created: 2026-08-10T23:45:55Z; updated: 2026-08-10T23:45:55Z

Exact metadata: [source record](sources/comment-5550152803-f4984fb54852bb4355a7ff09675dedcf53c2ac0d2f6b8444701ff07924b91d12.json).

Installed the mantle handoff correction. Top-out no longer clears the entire task tree or releases the wall anchor merely because TASK_CLIMB was queued; it waits for Rockstar to visibly report climbing/vaulting. Confirm top-out has no slide down, snap back, or delayed teleport.

## comment 5550152837 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/258#issuecomment-5550152837

Created: 2026-08-13T01:46:05Z; updated: 2026-08-13T01:46:05Z

Exact metadata: [source record](sources/comment-5550152837-ba2d2800ecbbbd8581081391920706b85efc2cb65225d41edefd58c9d61cb8a1.json).

literally can't even test this one because every time i try to climb to the top of a wall arthur just keeps climbing into air for like 10 seconds before falling. wile e coyote shit

## comment 5550152863 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/258#issuecomment-5550152863

Created: 2026-08-14T00:39:16Z; updated: 2026-08-14T00:39:16Z

Exact metadata: [source record](sources/comment-5550152863-b925bdf2d530129b315ac035aa9210905b8be2c042ce08203843e8781229c9c6.json).

**The thing stopping you testing this may be fixed — worth one attempt before anything else here.**

You said you literally cannot test this because Arthur climbs into thin air for ten seconds and then falls. That symptom is the subject of Lexer-Lux/Lexeditor#193, and it now has a measured cause and fix installed.

The climb probe rays were fired from the ped's entity root on the assumption it sits at his feet. It does not: `GET_ENTITY_HEIGHT_ABOVE_GROUND` read 0.99–1.01 on all 620 grounded samples of your session. Every ray went out roughly a metre high — chest to overhead — so the scan almost never found a wall (14 hits in 787 lines) and nothing anchored him to a real surface. Climbing on nothing is the expected result of that.

The ray heights are now anchored to the measured ground beneath him, measured per probe batch rather than assumed. Attached probes also reach 0.35 m past the contact plane instead of 0.23 m, which was falling short of irregular bulges and dropping the grab within a quarter second.

I am not claiming this fixes mantling — that is what this issue is about and it is untouched. I am saying the wile-e-coyote behaviour that made mantling untestable has a real fix in the installed build, so a mantling attempt should now get far enough to actually judge.

If he still climbs into air, the new `manual grab abandoned reason=` line and the `rootAboveGround` value in the climbing log will say whether the ground anchoring measured what we expect.

Staying `actionable`.


## comment 5550152893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/258#issuecomment-5550152893

Created: 2026-08-14T06:10:50Z; updated: 2026-08-14T06:10:50Z

Exact metadata: [source record](sources/comment-5550152893-6a28d69e351acd131aca636583e26ef1ca9147707c9e6a84df8d27b7e928ae08.json).

The Lexer-Lux/Lexeditor#193 probe-height fix referenced above is built, installed and hash-verified, and I confirmed the code is physically present in the installed `.asi` rather than just in the source tree. So the "climbs into thin air then falls" blocker you said prevented you testing this should be gone or measurably changed.

Also relevant here: both climb animation dictionaries are now checked for existence once per session and reported outside the trace switch. If a mantle looks wrong because its clip source is missing rather than mistimed, the log now says so outright.

Moving to `test me` — there is nothing further I can determine about mantling without you being able to climb at all.


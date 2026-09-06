# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356299318 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167

Created: 2026-08-06T02:52:16Z; updated: 2026-09-05T06:58:26Z

Exact metadata: [source record](sources/issue-5356299318-b25361b70072c44aeff7b79ee7bd1d49ddfcc79c25f6e00a0b5a3787868c6658.json).

PRONE WEAPONS — EQUIPPING, SWITCHING, AIMING, FIRING, BINOCULARS
	- Is there some way to do this? Will we have to make new anims? Or can we use the old ones in a way that works when prone?
     ANSWERED, AND THE NEWS IS MIXED.
     LONGARMS: new animations, no way round it. The game contains no face-down
     two-handed aim set at all — every grounded aim dictionary Rockstar shipped
     is one-handed. The face-up roll-around workaround is the build you already
     rejected.
     ONE-HANDED: the animation exists. What has always broken it is ownership —
     the game's own aim task is what points the gun at your reticle, and every
     pose we played took the whole skeleton off it, so the gun stopped tracking.
     LEFT: one untried mechanism, and it is now built and switchable. Set
     `[Prone] GroundedAimMode=1` and a pistol/revolver/throwable comes down with
     you, can be picked from the wheel, and aiming holds the authored face-down
     pose as an UPPER-BODY layer while the game keeps aiming the gun underneath
     it. Off by default so it cannot muddy the Lexer-Lux/Lexeditor#262 movement test.
     Tell me whether the gun tracks your reticle in that mode. If it does not,
     one-handed prone aiming also needs new animations and this item closes as
     "needs custom anims", which is a real answer either way.
     Reload stays refused in both modes — nothing in the game reloads face-down.

Okay. Can you not just make them yourself? In computer control mode? Or using math? Copying the vanilla-game anims from the torso up? Surely we can find a way to do this that doesn't require someone to make em from scratch.


## issue 5356299318 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167

Created: 2026-08-06T02:52:16Z; updated: 2026-09-06T12:54:45Z

Exact metadata: [source record](sources/issue-5356299318-ef32a781cde13667daad5b315ae7d81edd29e4041335659e972957a24b473e54.json).

Support prone equipping, aiming, firing, reloading and binocular use without losing reticle tracking or breaking the pose.

**Status: The one-handed test failed.** Reusing unchanged clips did not work. A compatible animation/export workflow and modified or authored upper-body poses are needed. Asset creation is development work, not a reason to leave you with an unspecified test.

## issue 5356299318 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167

Created: 2026-08-06T02:52:16Z; updated: 2026-09-06T13:56:41Z

Exact metadata: [source record](sources/issue-5356299318-a3c08f293715640463e83f01171f1d51b953a2515fb56030263ef71136f2c991.json).

Support prone equipping, aiming, firing, reloading and binocular use without losing reticle tracking or breaking the pose.

**Status: The one-handed test failed.** Reusing unchanged clips did not work. A compatible animation/export workflow and modified or authored upper-body poses are needed. Asset creation is development work, not a reason to leave you with an unspecified test.

## comment 5550127477 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167#issuecomment-5550127477

Created: 2026-08-06T03:57:22Z; updated: 2026-08-06T03:57:22Z

Exact metadata: [source record](sources/comment-5550127477-1777c86fb3f1cb25870d3ede1de20d7ae0528a7703d92be06a3ae9dcee577df0.json).

The answer is split. One-handed aiming has one credible engine-side test already built behind `[Prone] GroundedAimMode=1`: Rockstar's authored grounded 1H aim loop runs as a secondary upper-body task while native aim retains reticle ownership. The decisive test is whether shots actually track the reticle face-down. No authored face-down longarm, reload, or binocular set was found; the reference mod only plays a canned one-second clip and clears tasks. AI/math-assisted authoring may reduce labor, but still requires a proven RDR2 animation asset pipeline, skeleton masks, contacts, root motion, recoil, reload events, and visual QA. Test Mode 1 first; if it fails, prove one modified clip can export, rebuild, load, and play before generating a full set.

## comment 5550127494 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167#issuecomment-5550127494

Created: 2026-08-06T06:54:54Z; updated: 2026-08-06T06:54:54Z

Exact metadata: [source record](sources/comment-5550127494-8083e8fff29ae35b9976c14a120c4a24ada4e8910d6eb470e72d2088a8400105.json).

well i can't open the weapon menu when prone so i 'm not sure how i'm meant to test this.

## comment 5550127502 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167#issuecomment-5550127502

Created: 2026-08-06T08:50:04Z; updated: 2026-08-06T08:50:04Z

Exact metadata: [source record](sources/comment-5550127502-8aeb1d8bc6948de8b120f3c37c31e5a07b9facf0cde57b05a8489bd97071f561.json).

Enabled the existing prone one-handed test mode so the weapon wheel, pistol/revolver aim, and attack path can actually be tested; Reload remains deliberately blocked. The INI is queued with superset build `C92A04F9AD29F8B8833264AF674F394912034D7C078ABC16A15AA662AF05CCA3`. Keeping `actionable` after installation because longarms, reload, and binoculars remain unsolved and the one-handed path still needs decisive in-game validation.

## comment 5550127513 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167#issuecomment-5550127513

Created: 2026-08-06T11:33:50Z; updated: 2026-08-06T11:33:50Z

Exact metadata: [source record](sources/comment-5550127513-fe025a6275403d03ebdab4ba8d67f6bbd7bf1f52be09f97c2919d6b1e0554fe4.json).

now i can open the weapon wheel but not switch to weapons when prone....so that was totally pointless of you.
but if i go into prone holding a revolver, while i hold aim i go into this weird stiting up position where he's bumping up and down or jittery or something for a few seconds then he goes back to prone.
aiming around does nothing. he doesn't follow the cursor and he can't shoot.

## comment 5550127527 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/167#issuecomment-5550127527

Created: 2026-08-06T12:01:59Z; updated: 2026-08-06T12:01:59Z

Exact metadata: [source record](sources/comment-5550127527-774dee6b5999c1df15354993f6b6aed80c3e7576dfa16d3f90fa3e5bd330f0a8.json).

The failed one-handed test exhausted the remaining no-new-animation path. This now needs a RDR2-compatible authored animation/export pipeline and visual animation work: face-down one- and two-handed draw/holster/idle/aim/fire/reload sets, reticle-driven yaw/pitch aim poses, recoil and reload events, binocular raise/view/lower, upper-body masks that preserve the prone lower body, correct hand/weapon contacts, and zero unintended root motion. Vanilla clips can be retargeted and modified, but arbitrary existing clips cannot be played unchanged. I am moving this to 
eeds a human because the next blocking step is authored animation asset work and visual QA, not another ASI control experiment.

# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356287453 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116

Created: 2026-08-06T01:52:13Z; updated: 2026-09-05T06:55:36Z

Exact metadata: [source record](sources/issue-5356287453-e5147a1b3f65e6fbc6006764d0cf4afedabcffa522678cae32f3b57b7f5e49b6.json).

I want them to be visible. Day or night. How will we do this? I think you said a glowing particle trail would be best? OK, what particlues we using here?
Wait now I'm seeing like, the vanilla bullet trail, and then a second trail coming from my eyes??? WTF?

## issue 5356287453 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116

Created: 2026-08-06T01:52:13Z; updated: 2026-09-06T12:46:27Z

Exact metadata: [source record](sources/issue-5356287453-c24fe90a0f71eaabc410081b95d3c4084c64f3053a0c289b2c36fce00ecce700.json).

Bullet trails should be visible by day and night, start at the weapon and not duplicate a second trail from the player’s eyes.

**Status: Latest correction is source-only, not installed.** Its presentation is an impact-synchronized trail, not proven tracking of a live projectile. Deliver and verify the candidate before another visual test.

## comment 5550113264 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113264

Created: 2026-08-06T03:57:19Z; updated: 2026-08-06T03:57:19Z

Exact metadata: [source record](sources/comment-5550113264-eead29c224aa311855c1e49479b441daabfa7c1055a7fbda9c118bebf49821b9.json).

Research result: the weapon tracer field is not the missing switch. Vanilla already assigns the standard tracer hash to 49 firearms and a separate shotgun tracer to nine effect groups; overwriting them left the 49 unchanged and regressed shotguns. The “second trail from my eyes” came from the rejected fallback drawing a synthetic camera/player-chest ray, not the projectile. The credible path is the current world-space `core/bullet_tracer` particle moved along the synchronized firearm path. Remaining proof is in-game muzzle alignment and visibility across hipfire, aim, scopes, cover, horseback, dual wield, ranges, and shotguns. Judge alignment separately from brightness.

## comment 5550113285 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113285

Created: 2026-08-06T05:25:36Z; updated: 2026-08-06T05:25:36Z

Exact metadata: [source record](sources/comment-5550113285-9c041b5fd4fe6bb7e8b714f21f73f64d13105549af536e0585062d11840ec112.json).

there's an unused bullet tracer in the files already? wtf? yeah just use that instead then

## comment 5550113299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113299

Created: 2026-08-06T06:17:29Z; updated: 2026-08-06T06:17:29Z

Exact metadata: [source record](sources/comment-5550113299-ff98a91629fb94ae952a0199108758807d3c1b3fac2ccf43690c1cb81d0f5367.json).

Implemented the tracer fix: the shipped core/bullet_tracer now starts at the real equipped weapon Gun_Muzzle and follows the barrel axis, including dual wield, with no synthetic camera/chest ray or layered HUD/corona effect. Combined release build passes; installation is queued, so this remains actionable until it lands.

## comment 5550113316 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113316

Created: 2026-08-06T08:30:18Z; updated: 2026-08-06T08:30:18Z

Exact metadata: [source record](sources/comment-5550113316-9580dc60a195bb105896bcab24d13c9089d6b95f711455e329234a726123720c.json).

no change whatsoever -- wait. is the "tracer" you're describing just the vanilla smoke trail for bullets that is already being used? that's why there's still two of them?

## comment 5550113329 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113329

Created: 2026-08-06T08:37:52Z; updated: 2026-08-06T08:37:52Z

Exact metadata: [source record](sources/comment-5550113329-c8414170525a87a32cd8f12768e35e4a7046bd5e6ff0ed0e4d451a90b3b0b27e.json).

Corrected after the in-game “no change” report: `core/bullet_tracer` was the wrong effect because it is the same smoke-like trail already used by vanilla firearms. Replaying it could only overlap or duplicate vanilla smoke, not create the requested distinct tracer.

The isolated Lexer-Lux/Lexeditor#116 module now removes that PTFX path entirely. Mode 4 draws a short incandescent orange-red world-space streak instead: a bright moving head, six fading tail segments, and a matching point light. It still starts at the equipped weapon's real `Gun_Muzzle`, follows the weapon's barrel axis, and alternates real held weapon entities for dual wield; there is no camera/eye/chest ray. The old single-corona mode remains compatibility-only.

Static check passed: balanced source braces and no PTFX request/start/move/remove calls remain in `modules/projectile_visibility.cpp`. This is a source handoff only—no combined build, install, or in-game claim. Integration still has to replace the duplicate old implementation in `recon.cpp`, build/install the ASI, then verify a clearly orange-red moving streak distinct from the single vanilla smoke trail across the issue's player/hostile and pose/lighting cases.

## comment 5550113344 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113344

Created: 2026-08-06T08:58:59Z; updated: 2026-08-06T08:58:59Z

Exact metadata: [source record](sources/comment-5550113344-4c07eb3decaede4c937e0e30d3433b3d6677a108ad3e4d8839bc527ea04d6fe4.json).

The distinct orange-red muzzle-origin tracer module is integrated in the installed `C92A04F…CCA3` build; the obsolete duplicate-smoke implementation is compile-disabled. Moved to `test me` for the listed visibility/weapon tests.

## comment 5550113355 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113355

Created: 2026-08-06T09:38:37Z; updated: 2026-08-06T09:38:37Z

Exact metadata: [source record](sources/comment-5550113355-1e26f844dedff78a21c2d8161b33c84d03568accf8eaea78d26a101acf4ae7bd.json).

okay well now instead of 2 tracer paths there are 0. i'd at least like an .ini toggle under misc to return the vanilla tracer path in case people want it.
also are there no tracer settings? can i not change the size, transparency, brightness, idk...what can you give me?

## comment 5550113364 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113364

Created: 2026-08-06T11:35:24Z; updated: 2026-08-06T11:35:24Z

Exact metadata: [source record](sources/comment-5550113364-adb3ebc4240609492eeb51de816840d544235bea214b74b616d437a924839055.json).

you didn't do anything or answer any of my questions.

## comment 5550113381 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113381

Created: 2026-08-06T12:20:58Z; updated: 2026-08-06T12:20:58Z

Exact metadata: [source record](sources/comment-5550113381-781ef247007f1e582eea124d450b781ee11cda2929237f453398581fffcdf94c.json).

you didn't do anything or answer any of my questions.

## comment 5550113398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113398

Created: 2026-08-06T14:42:00Z; updated: 2026-08-06T14:42:00Z

Exact metadata: [source record](sources/comment-5550113398-db7c4e08f97b463114f0d668ce65aac68e433ddf6480fe6df73a0cd36fc37974.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test vanilla-only and custom projectile visibility modes, size, opacity, color, tail, brightness, and range.

## comment 5550113410 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113410

Created: 2026-08-09T09:11:38Z; updated: 2026-08-09T09:11:38Z

Exact metadata: [source record](sources/comment-5550113410-93dc871c1552f89dbdf8e01ec94ff9027bb029e7c7ac699438cfa4fa47db683f.json).

Enemies sometimes have tracers and sometimes don't. When they do, they travel in wildly different directions than the native bullet trail (their actual projectile)

## comment 5550113424 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113424

Created: 2026-08-09T11:07:02Z; updated: 2026-08-09T11:07:02Z

Exact metadata: [source record](sources/comment-5550113424-81e9c2d2bbac2aae96218a89d056208d4d78a2cf86d207c8482e86a8ab3c2bd3.json).

Installed development build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53. Added tracers now derive their path from a fresh real weapon-impact readback rather than the held weapon's local axis, and ProjectileVisibility.Enabled directly controls them. Test visible alignment for several weapons and confirm Enabled=0 leaves only vanilla tracers.

## comment 5550113434 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113434

Created: 2026-08-13T07:53:08Z; updated: 2026-08-13T07:53:08Z

Exact metadata: [source record](sources/comment-5550113434-be8c3bcc16eb281c02901d1ece083dcf4db65960e79b36daf21f6449adc3abca.json).

What an absolute MESS.
- Luminous streak creates a bright yellow light on the shooter maybe 5% of the time someone shoots, which quickly disappears.
- Corona results in the same as luminous streak as far as I can tell.
- At some point the bullets were creating a trail of coronas. I can't get this to come back no matter which setting I choose. THOSE STUPID FUCKING CAR CORONAS YOU'VE USED A MILLION TIMES. WHY ARE YOU OBSESSED WITH THEM.
- At no point did MY bullets have any coronas.
- The tracer reflects the set "Global Firearm Projectile Speed", which doesn't seem to actually control the ACTUAL bullet speed anymore (if it ever did), which can be quickly proven by setting it to 0 and seeing as you still get shot.
What an absolute mess. What an absolute fucking mess.

## comment 5550113445 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113445

Created: 2026-08-13T13:07:38Z; updated: 2026-08-13T13:07:38Z

Exact metadata: [source record](sources/comment-5550113445-46672c8ba46ab0f0139b55de9ff77b799230258040838ed158540c57700246a4.json).

Never mind I didn't know that I had to run some script or something every time I wanted to change the speed const. Is there really no way around that?

## comment 5550113460 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113460

Created: 2026-08-14T00:31:32Z; updated: 2026-08-14T00:31:32Z

Exact metadata: [source record](sources/comment-5550113460-f407c9cfe2365ca484528e4d59f019646d633e1c971ac62bc6911c4455a08869.json).

**Answering the script question — and I found a bug in that exact workflow.**

**Why the script exists.** Bullet speed is not a live setting. It lives in `CWeaponInfo` weapon metadata, which the engine reads when weapon data loads, so `ApplyProjectileSpeed.ps1` rewrites those `.ymt` records and the game has to restart to pick them up. I searched the resolved native index for any runtime way to set a weapon's projectile speed and found none — so no, there is no way around the rebuild-and-restart for *bullet speed* specifically. I would rather say that plainly than invent a native.

Two things that are **not** in that boat, in case this is what actually bit you:

- The **tracer marker speed** (how fast the drawn streak travels) is `[ProjectileSpeed] GlobalFirearmSpeed`, read live and hot-reloaded in about a second. No script, no restart.
- Everything under `[ProjectileVisibility]` — size, opacity, brightness, colour, tail length, segments, distance, light range — is also live.

**The bug.** `ApplyProjectileSpeed.ps1` validated the tracer mode against `engine_tracer`, `corona`, `off` and **threw** on anything else. But the ASI accepts `luminous_streak` and `disabled` too, and `luminous_streak` is the default the code ships when the key is blank — and the INI comment advertised it as the selected mode. So running the script while Mode held its own documented default failed outright instead of applying your speed. If you ever ran it and it errored, that is why.

It now accepts all five values. Only `engine_tracer` keeps Rockstar's weapon-data tracer; `corona` and `luminous_streak` clear it, because the mod draws its own and you would otherwise get two tracers for one bullet — which is very likely the "vanilla trail plus a second trail" you reported at the top of this issue.

I also corrected the INI comment block, which listed the modes wrongly and claimed `luminous_streak` was selected when you are actually on `corona`.

Your current settings are unchanged: speed 5, mode corona.

Still `actionable` — the day/night visibility question you originally asked is not resolved by any of this, and I have not touched the particle choice.


## comment 5550113476 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113476

Created: 2026-08-20T07:04:37Z; updated: 2026-08-20T07:04:37Z

Exact metadata: [source record](sources/comment-5550113476-1bc73566ae94f8f9e0f5ee5e315fa1f95517f0b46dc562a2baf96b417a250aa6.json).

I can still see the bullet actually hitting the target long before the tracer does. Also, the corona and luminous blob options still look identical -- just a corona with a light attached? A light that, strangely enough, doesn't seem to "exist" on its own -- it's only visible when it has something to illuminate. Which is really bad! A light should be lit! It should be visible!

## comment 5550113490 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113490

Created: 2026-08-20T10:26:11Z; updated: 2026-08-20T10:26:11Z

Exact metadata: [source record](sources/comment-5550113490-65a3217167ebbe7247235fbf5e6e95ad4ad2bcc2c895e62b5c1eca698a816b4e.json).

The installed change removes the late travelling marker. A fresh hit now shows one brief impact-aligned streak: luminous is a multi-segment hot core, while corona is one point. Try both modes by day and night with player and hostile shots; no custom tracer may arrive after the actual hit. This is an impact-synchronized approximation, not a claim of true in-flight tracking.

## comment 5550113503 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113503

Created: 2026-08-20T19:16:43Z; updated: 2026-08-20T19:16:43Z

Exact metadata: [source record](sources/comment-5550113503-7de0a4d87b53e4f925e1c90648a4e2d0166392cb4264a1ddb5c88068260e80e4.json).

Returned test: the newly installed tracer implementation renders no visible tracers. Treat this as an execution/render failure, not a tuning preference. Diagnose whether shots resolve, records are created, and draw calls execute; ordinary, luminous, and corona modes must each have a visible and distinct postcondition.

## comment 5550113513 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/116#issuecomment-5550113513

Created: 2026-08-20T19:42:59Z; updated: 2026-08-20T19:42:59Z

Exact metadata: [source record](sources/comment-5550113513-6b00ea61e5dcc8dd67793d3b129e76788e759abdc0f5b0a8921d2cf37c090509.json).

Source repair is complete but unbuilt. The old streak was executing, but it was only a tiny 80 ms flash at the impact surface. The luminous dash is now placed on the confirmed muzzle-to-impact line at the point nearest the camera, stays inside that segment, and lasts 100 ms. This remains an impact-synchronized visibility aid, not true in-flight bullet tracking. After the next install, test near and distant shots in daylight and darkness.

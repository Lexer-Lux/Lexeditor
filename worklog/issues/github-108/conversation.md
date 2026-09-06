# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356285491 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108

Created: 2026-08-06T01:36:51Z; updated: 2026-09-05T06:55:10Z

Exact metadata: [source record](sources/issue-5356285491-5c8d12b8bf5e3bc78488016864e829df9425c9a29ab223faf70796b91826f38d.json).

	a) What? There's really no way whatsoever to control camera Y?
	b) Standing mode. Crouching mode. I can edit the camera for those modes. Awesome. Why no vehicle mode? Horseback mode? Aim mode?
## Current required behavior

- Camera authoring is available only while shared developer mode is enabled with tilde; Numpad 0 swaps camera/fortification ownership.
- Standing, crouched, prone, horseback, vehicle, standing-aim and crouched-aim have independent horizontal offset, distance and real LOW/NORMAL framing profiles.
- Crouched aim defaults to LOW framing. Rockstar exposes this binary lower framing state; no continuous vertical/Y coordinate has been proven.
- Horizontal calibration must not stop at the old invented narrow bound.
- Shoulder switching must move fully between sides, must not fight Rockstar's own shoulder processing, and must also work without a weapon drawn.
- Entering aim must not flash to a farther zoom before blending back, and crouching while aiming must not jump or bob vertically.

## issue 5356285491 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108

Created: 2026-08-06T01:36:51Z; updated: 2026-09-06T13:31:09Z

Exact metadata: [source record](sources/issue-5356285491-cf7250dbf0453e52a7904b9bf884a6f02c43f91eaef5cb45fe950411850df840.json).

**Actionable — partly implemented.** Standing, crouched, aiming, horseback, vehicle and prone profiles exist. Continuous Y is unsupported by the current camera path; LOW/NORMAL works on foot/horse but is ignored in vehicles.

Vehicle-height research and reported shoulder/transition defects remain (#267, #269, #270). Asking you to accept an unsupported control is not a development blocker. Developer mode must gate editing only, not application of saved presets.

## comment 5550110941 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550110941

Created: 2026-08-06T11:44:44Z; updated: 2026-08-06T11:44:44Z

Exact metadata: [source record](sources/comment-5550110941-ff5444def85c41d3a7b8a74355209e7bb9b39b6473256e7337628fa3ee29e185.json).

when i'm holding the numpad keys these adjustments get done at a snail's pace. it's way too slow.
and i don't understand. is Y positioning doable? yes or no? 

## comment 5550110960 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550110960

Created: 2026-08-06T11:51:58Z; updated: 2026-08-06T11:51:58Z

Exact metadata: [source record](sources/comment-5550110960-737023b5d2338eadebb7740f5242472e385be0670ba79ac0ef38c314fb871972.json).

Direct answer: continuous camera Y positioning is not exposed by the proven gameplay-camera native. It exposes horizontal offset and distance; the only real vertical/framing control found is binary LOW/NORMAL. I have not added a fake Y setting. I did fix the held-key speed: it now updates every 16 ms at 0.05 per step (about 9x the prior rate), with Shift retaining the 0.005 fine step. This is in the newly built deferred-install artifact; no runtime claim yet.

## comment 5550110973 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550110973

Created: 2026-08-06T12:28:07Z; updated: 2026-08-06T12:28:07Z

Exact metadata: [source record](sources/comment-5550110973-ab161b36aae774ea92b1811f9a5b0dcc65229be34f712727b99ee6713c93ce5b.json).

cool. now disable the camera calibration mode seting toggle. just have it always on as long as dev mode is on.

## comment 5550110990 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550110990

Created: 2026-08-06T12:39:34Z; updated: 2026-08-06T12:39:34Z

Exact metadata: [source record](sources/comment-5550110990-231194850b2a5224a7d6cf64dd602d6ca2c2007b781ddb0adb2f8f84ac616ed3.json).

also the shoulder swap button has been broken in a very bizarre way. it only moves the camera maybe a tenth as much as it should. hit it again, it moves in the other direction, maybe a third as much. hit it again, swaps direction again, a third as much movement. after a few times there's no movement at all. WTF?

## comment 5550111002 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111002

Created: 2026-08-06T14:41:48Z; updated: 2026-08-06T14:41:48Z

Exact metadata: [source record](sources/comment-5550111002-85f1caf1d54932059ff2dc071be2f55fd74a9a1886a63137aaafa1bf05464e79.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test keyboard and controller shoulder switching plus development-mode camera calibration; confirm the native shoulder side no longer fights the configured offset.

## comment 5550111017 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111017

Created: 2026-08-09T09:22:52Z; updated: 2026-08-09T09:23:44Z

Exact metadata: [source record](sources/comment-5550111017-90b6b2c228352d928189fef9908d0fbf55479b537f3732a386afc656a727811c.json).

Okay but now switching shoulders teleports the camera. In fact, I can kind of see the same jerky, immediate camera adjust when I enter/exit crouch mode. Is this camera smoothness/tween/whatever configurable in the .ini or something you can reenable or what?

also, the camera debug text seems just gone? and my numpad no longer moves the camera? did you compile with dev mode off or something?

## comment 5550111037 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111037

Created: 2026-08-09T11:06:53Z; updated: 2026-08-09T11:06:53Z

Exact metadata: [source record](sources/comment-5550111037-801e20102405aca29380388acaaec8b982c1976ac996fa676b1a0a8ff1013ca9.json).

Installed development build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53. Camera calibration is active in development builds, hot-reloads INI edits, defaults to blend speed 1 instead of 10, and yields numpad control to the fortification calibrator. Test smooth live adjustment and saved profiles.

## comment 5550111051 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111051

Created: 2026-08-10T08:19:27Z; updated: 2026-08-10T08:19:27Z

Exact metadata: [source record](sources/comment-5550111051-fde6b4ee8502ee874290a8c24b298cd27aac2ae794214b06456eb84efe54c7a8.json).

Keypad does nothing. Tilde does nothing. Camera editor is AWOL. This is not okay and needs to be fixed NOW.
Is it because of the golden cores editor? Because that thing is toggled with numpad 0. So I don't see why they should be interfering at all. This can just swap with yours when I hit 0.

## comment 5550111060 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111060

Created: 2026-08-10T10:37:39Z; updated: 2026-08-10T10:37:39Z

Exact metadata: [source record](sources/comment-5550111060-7c9f4210d94ef7f9b5cce682b33d091010350a2067fdc791e74f8ae9917941ab.json).

Noc hange.

## comment 5550111070 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111070

Created: 2026-08-10T10:57:15Z; updated: 2026-08-10T10:57:15Z

Exact metadata: [source record](sources/comment-5550111070-d3a151100549a61c1f520d0f4952629b3abd55bbb0e3c9ae49e84f93528874f2.json).

Returned-test root cause found: installed build E3CAD... was a release build and the prior camera editor inherited the global developer-mode gate, so its input path was unreachable. Integration will not enable every unrelated development tool. The camera editor now has its own release-build tilde latch; global F2/F3 authoring paths remain compiled out. Remains actionable until rebuilt/installed and tilde/keypad/Numpad0 behavior is visible in game.

## comment 5550111081 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111081

Created: 2026-08-10T12:01:36Z; updated: 2026-08-10T12:01:36Z

Exact metadata: [source record](sources/comment-5550111081-3580f5646e47bcbf499349e5283774ecabf2dd4df8436ea85cc10df6fe3169cc.json).

why are they compiled out?
dev tools would be restricted to dev mode. dev mode should be toggled by tilde.


## comment 5550111100 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111100

Created: 2026-08-10T12:54:00Z; updated: 2026-08-10T12:54:00Z

Exact metadata: [source record](sources/comment-5550111100-06a20c33a88bd90615779ca599ef1c0a85e5746d0c46a7bbecb6dbd4f9187eec.json).

You also seem to have put some kind of hard limit on how far I can move the camera because it won't go more than like five inches to the right from its vanilla position?
Also you seem to have broken shoulder switching. it goes from "Arthur on my left" to "Arthur in the middle of my screen" when I hit X.
Oh and if regardless of if you're the one who disabled the ability to shoulder switch without a weapon out or if that's just something you coludn't do in vanilla...yeah please make that a thing you can do

## comment 5550111115 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111115

Created: 2026-08-10T13:01:02Z; updated: 2026-08-10T13:01:02Z

Exact metadata: [source record](sources/comment-5550111115-a5b7468c483afa45b9598e4aab39776abd861a5c12dc1190e278a042dcb07812.json).

Oh, also. There's no seperate crouch aim mode, which means that your camera doesn't move down when you're crouching + aiming. Can you add a seperate crouch aim mode that does that? If yes, then didn't you say you couldn't change the camera height? If not, then doesn't the vanilla camera move down when crouch aimed?

## comment 5550111131 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111131

Created: 2026-08-10T14:55:31Z; updated: 2026-08-10T14:55:31Z

Exact metadata: [source record](sources/comment-5550111131-0bf8d5407d5f78385e335b9b48bb0c224bc965bd3afa0968a1e27af80a80f908.json).

Dude. I still can't move the camera to the right more than like 5 inches.
Now when I crouch while aiming my camera and the camera just flies up and I can't move it back down because I can't change the camera height. And then it keeps like, bobbing up and down?
And when I pull out a gun and enter aiming mode the camera jumps to being super zoomed out, then zooms back in? This would be expected if it was going from one camera mode that was super distant to a close one...but it's not. It's going from close, to jumping super far for no reason, back to close. 


## comment 5550111144 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111144

Created: 2026-08-10T15:13:59Z; updated: 2026-08-10T15:13:59Z

Exact metadata: [source record](sources/comment-5550111144-886913f647e589ab7d4cc6b8cba6e258d74d22575663abd7b7c794dd476dd76a.json).

You should not have had to repeat this. I moved Lexer-Lux/Lexeditor#108 to test me after your crouched-aim comment without answering or implementing it.

Direct answer: the proven native does not expose a continuous Y coordinate. It does expose Rockstar's real binary LOW/NORMAL framing state, and vanilla crouched aim is lower. Our shared Aim profile forced NORMAL every frame, overriding that behavior. The repair adds a separate Crouched Aim profile with LOW as its default, while retaining independently editable horizontal offset and distance.

The same repair removes the invented narrow horizontal clamp, owns shoulder-switch input instead of fighting Rockstar's simultaneous swap (including with no weapon drawn), and keeps the close zoom step active during both aim modes so it cannot flash far and then blend back. Combined build C608DBB054581906C16C3ACE932E3E23CE2970E3B0ED837837B0513A339B9D7C is compiled and queued behind the currently running game. Lexer-Lux/Lexeditor#108 stays actionable until that exact build is installed and hash-verified.

## comment 5550111165 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111165

Created: 2026-08-10T15:52:41Z; updated: 2026-08-10T15:52:41Z

Exact metadata: [source record](sources/comment-5550111165-b23476182a98705727a823da314e9acb497479fdeba3b2997cab774028954047.json).

Direct provenance answer: the old `-2.0..+2.0` clamp was hard-coded by my original camera-editor implementation as a supposed defensive validation bound. It did not come from this issue, Rockstar's scripts/native database, or an observed engine limit. Nothing in the evidence selected the number 2; I chose it arbitrarily, and it blocked the larger horizontal adjustment you explicitly needed. The current source removes that unsupported narrow bound and retains only a broad finite/corruption guard while the runtime native determines the usable range.

## comment 5550111182 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111182

Created: 2026-08-10T17:00:42Z; updated: 2026-08-10T17:00:42Z

Exact metadata: [source record](sources/comment-5550111182-27a91c419104755b8f1aeb6b96e637c56b602c147f6d124fff963d1dfcf8e89c.json).

The camera/editor repair is installed. It includes the separate lowered crouched-aim profile, removes the invented narrow horizontal clamp, keeps the close aim step owned through the transition, and accepts a physical keyboard X press while holstered without mutating weapons. Test large left/right calibration, crouched aim height/stability, entering aim without a far-camera flash, and shoulder switching both holstered and armed.

## comment 5550111197 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111197

Created: 2026-08-11T04:53:02Z; updated: 2026-08-11T04:53:02Z

Exact metadata: [source record](sources/comment-5550111197-59a59615ab64b3f383bcf0f2656ece2f6b04cfbeed888b072d9bf9648bf49062.json).

Oh my god. You broke it. You broke it completely. Pressing tilde and Numkey 0 do nothing -- there's no camera debug text, no golden bars debug text. Numpad does nothing. Camera customization is gone. What did you do? And why? Fix this NOW

## comment 5550111211 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111211

Created: 2026-08-11T09:32:26Z; updated: 2026-08-11T09:32:26Z

Exact metadata: [source record](sources/comment-5550111211-9f0fbaacf83d9e84c74636745a3d42030a045dce0dd0518ddc35c1c284b569d2.json).

The second invented horizontal calibration cap is removed. The installed development build starts the shared Tilde-controlled editor enabled; camera editing remains an authoring tool, while prone and other gameplay dispatch do not depend on that mode. Test Tilde, Numpad0 ownership, and a horizontal value beyond the old cap.

## comment 5550111224 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111224

Created: 2026-08-12T12:28:00Z; updated: 2026-08-12T12:28:00Z

Exact metadata: [source record](sources/comment-5550111224-13ddfdff92175bb094189492ec5dd9aec8c4a4eae85f1a6c77921fd4e6a277ba.json).

The installed development build starts the shared developer-mode latch off, which removes both camera and gold-core editing until the latch is enabled. I am restoring the intended development-build startup state; ordinary release builds remain off.

## comment 5550111237 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111237

Created: 2026-08-12T13:07:21Z; updated: 2026-08-12T13:07:21Z

Exact metadata: [source record](sources/comment-5550111237-fa47c43d3c4dd2b6355106da34850a9816a2d2fad206675b6fc916e13331cbbc.json).

This is a development build. Camera and gold-core authoring now start enabled, and Tilde is present in every build as the one shared runtime toggle. Confirm both editors are present at startup, Tilde disables both, and Tilde restores both.

## comment 5550111252 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111252

Created: 2026-08-13T01:20:21Z; updated: 2026-08-13T01:20:21Z

Exact metadata: [source record](sources/comment-5550111252-1cf3c646b238a58e8a3e9da77d5140e78a0bbfdd9dd0efb67e2e98f9a947788d.json).

Distance is still clamped? Can the cam really not go any closer than 0?
Would it be possible to adjust the FOV based on camera mode too? Since every player will have a different FOV, should it be a flat adjustment or a % based one or some other thing? I want aim to be more zoomed in and stuff.

## comment 5550111266 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111266

Created: 2026-08-13T01:47:53Z; updated: 2026-08-13T01:47:53Z

Exact metadata: [source record](sources/comment-5550111266-fe8419045120e1bdeb3d750fc9a78a93b98cad4d7b52394aaddeb6b9f54f8bbb.json).

Also, exiting dev mode with tilde completely undoes all the custom camera changes i made/??? dev mode is supposed to gate the EDITING. then everyone who plays my mod gets whatever presets i made with the editor. you built it so literally nobody but me would get ANYTHING from this entire feature???

## comment 5550111286 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111286

Created: 2026-08-13T03:59:54Z; updated: 2026-08-13T03:59:54Z

Exact metadata: [source record](sources/comment-5550111286-2e0a8d85bd56430bde74efcb96cf4b37ca921eb77bf5197d7c26056631d3d164.json).

**Your comment was right, and I found the mechanism.**

First, the good news on the part you feared most: **profile application is NOT developer-gated.** The early return at `gameplay_camera.cpp:540` checks enabled/ped/mission/cinematic/first-person — not dev mode. Only `calibrateGameplayCamera` is dev-gated. So presets that reach the INI **do** apply for everyone who installs your mod. The feature is not developer-only.

But your symptom is real, and here is why:

`loadGameplayCameraConfig()` runs on **every ~2 second config refresh** and overwrote `horizontal`, `distance` and `low` from the INI unconditionally. While dev mode was on, `calibrateGameplayCamera` rewrote those values every frame and masked it. The moment you left dev mode, calibration stopped, the next refresh restored the INI values, and every unsaved edit silently vanished — exactly "exiting dev mode completely undoes all the custom camera changes".

So editing was never durable unless you pressed the save key first, and nothing told you that.

**Fixed:** each profile now carries a `dirty` flag. A live nudge sets it; the config reload **skips** dirty profiles instead of clobbering them; saving writes the INI and clears it. Your edits now survive leaving dev mode, and saving still produces the values every non-developer player loads. The save also logs `profiles saved to INI; these are what non-developer players load`.

Built EXIT=0, installed `F2E16328…`.

**Still open** — two parts of this issue are not addressed:
- **(a) camera Y.** There is no continuous vertical setter proven to exist in the native surface; the binary LOW/NORMAL framing is what is exposed instead. If you want that re-investigated rather than accepted, say so.
- **Shoulder switching "must move fully between sides"** is Lexer-Lux/Lexeditor#267, and the log proves it currently does not mirror — `measLateral` never went negative across the whole session. The `AimHorizontalOverride=0` diagnostic settles whether our own offset assertion is suppressing the mirror.

Part (b) of your original question is done: STANDING, CROUCHED, PRONE, HORSEBACK, VEHICLE, AIM, CROUCHED AIM, ARMED and CROUCHED ARMED all have independent offset/distance/framing profiles.

## comment 5550111311 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111311

Created: 2026-08-13T07:39:22Z; updated: 2026-08-13T07:39:22Z

Exact metadata: [source record](sources/comment-5550111311-3f9799aae2645c0c1e9556137465880a6f26b8577d9253a4ac30d80637554556.json).

okay. hitting tilde doesn't move the camera anymore but the camera distance still can't go any closer than 0. is that just not possible?

>Distance is still clamped? Can the cam really not go any closer than 0?
Would it be possible to adjust the FOV based on camera mode too? Since every player will have a different FOV, should it be a flat adjustment or a % based one or some other thing? I want aim to be more zoomed in and stuff.

Did you do any of those things?

## comment 5550111326 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111326

Created: 2026-08-13T13:06:01Z; updated: 2026-08-13T13:06:01Z

Exact metadata: [source record](sources/comment-5550111326-4d79b72bf263964764fed3b051d724440d2de52776085a3051d118eec3de5326.json).

hello? are you even reading these?

## comment 5550111342 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111342

Created: 2026-08-13T13:06:46Z; updated: 2026-08-13T13:06:46Z

Exact metadata: [source record](sources/comment-5550111342-804e44dfc4db1ad6ddd0c5d6a8f518aa48dfa57a5a0009ecabb85b5e6cdf37fd.json).

Direct answer: no, those two requests were not implemented.

- Distance below 0: the 0 limit is our own clamp in `gameplay_camera.cpp`, not a proven engine minimum. `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` accepts a float distance and the native record does not document a minimum. The current code prevents negative values from reaching the engine, so I cannot honestly call closer-than-0 impossible without removing that clamp in a controlled test and measuring the rendered result.
- Per-mode FOV: not implemented. The public native surface exposes `GET_GAMEPLAY_CAM_FOV`, but no setter for the live gameplay camera. `SET_CAM_FOV` requires a separate scripted-camera handle, so it is not a drop-in solution. This needs a sanctioned gameplay-camera mechanism or a carefully isolated scripted-camera design before implementation. If an adjustment mechanism is found, a relative change from the player's current FOV is safer than replacing it with one absolute FOV, because it preserves each player's base setting.

The Tilde/durable-save repair addressed only the editor-state loss. It did not answer or complete these requests. This issue is back at `actionable, claude`.

## comment 5550111355 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111355

Created: 2026-08-14T06:07:15Z; updated: 2026-08-14T06:07:15Z

Exact metadata: [source record](sources/comment-5550111355-57aa804143b2bdc89a0052c54078250a2a67e305515ae2560a6325f8d5a392da.json).

**Distance below 0 is now actually testable. The FOV half is still not implemented.**

**On distance.** I said last time that the 0 floor was our own clamp rather than a proven engine minimum, and that I could not honestly call sub-zero impossible without removing it and measuring. That was correct and then nothing happened, because the clamp kept blocking the very thing that would answer it — we were enforcing a limit and then reporting it as the engine's.

The floor is now `-2.0`, as a named single-source constant explicitly documented as a **probe bound, not a documented engine minimum** (`_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` documents no minimum). Both the config loader and the live in-game nudge path allow it, so the value no longer snaps back to 0 the moment you adjust it.

The camera sample line already reports the **measured** orbit next to what was sent:

```
sentDistance=… measOrbit=…
```

so this answers itself. Set a negative distance and read those two on the same line:
- `measOrbit` follows below the old floor → sub-zero works and the limit was ours all along.
- `measOrbit` stops tracking at some value → that is the engine's real minimum, measured rather than assumed, and I will pin the clamp there.

**A note on how this landed, because I changed a safety check.** The Lexer-Lux/Lexeditor#108 verifier forbids the literals `-2.0f/+2.0f/-20.0f/+20.0f` anywhere in the file — they were once invented *horizontal* bounds. My distance constant tripped it on the string while having nothing to do with the horizontal axis. Rather than pick a different number to dodge the check, I scoped it to lines that actually concern the horizontal axis, and then verified it still fails by injecting a fake horizontal bound. The original prohibition is unchanged in strength. I also added two new requirements: the distance floor must stay a named constant, and the measured-orbit readback must remain.

**On per-mode FOV: still not implemented, and I am not going to pretend otherwise.** There is no setter for the live gameplay camera's FOV. `GET_GAMEPLAY_CAM_FOV` reads it, but `SET_CAM_FOV` needs a separate scripted-camera handle, which is a different and much more invasive design. If it is done, a relative adjustment from your current FOV is safer than forcing one absolute value, because it preserves your own base setting.

Staying `actionable` for the FOV half. The distance probe is ready for you now.


## comment 5550111375 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111375

Created: 2026-08-15T02:22:39Z; updated: 2026-08-15T02:22:39Z

Exact metadata: [source record](sources/comment-5550111375-ce6f465b69dd9f23f67c0f4eb7587dd21aea8df677f63fbf689b3724f79a09c0.json).

How do I change the camera FOV? I don't see the setting anywhere.

## comment 5550111383 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111383

Created: 2026-08-15T04:32:04Z; updated: 2026-08-15T04:32:04Z

Exact metadata: [source record](sources/comment-5550111383-4e900e7d4bf9c6d181d8ba82a03da05471b4792a240887d2ecd1bd5edd618a70.json).

**Per-mode FOV: the engine has no setter for it, and Rockstar's own scripts prove it.**

I went looking for a way to do this rather than repeating "not implemented":

- `CAMERA::GET_GAMEPLAY_CAM_FOV()` — read only.
- `CAMERA::SET_CAM_FOV(Cam cam, float)` — needs a **scripted camera handle**, documented min 1.0 / max 130.0. It cannot address the gameplay camera.
- Searching every decompiled Story script for a gameplay-camera FOV setter returns **nothing**. There is no such native in use anywhere.

What Rockstar actually does is the tell. The only use of `GET_GAMEPLAY_CAM_FOV` is to *read* the current value and feed it into the creation of a **scripted camera** (`act_bankrobbery01.c:9761/9785/9809`). When Rockstar wants a different FOV, it does not set one on the gameplay camera — it builds a separate camera seeded from it.

So per-mode FOV cannot be done the way distance and horizontal offset are done. It would mean creating and driving a scripted camera that shadows the gameplay camera in every mode, which takes over camera control entirely and puts every existing behaviour in this issue — shoulder switching, the zoom steps, aim transitions, mounted framing — behind our own reimplementation. That is a much larger and riskier change than a settings addition, and it is not one I will start on my own.

**This needs your decision, so it goes to `needs a human`:**

1. **Drop per-mode FOV** — accept that the gameplay camera's FOV is not ours to set, and I mark it unfeasible with this evidence recorded.
2. **Authorise the scripted-camera approach** — I scope it properly first, including what it would put at risk.

For the record, so nobody re-researches it: if it is ever done, a *relative* adjustment from the player's current FOV is safer than forcing an absolute value, because it preserves whatever base FOV you have set in the game's own options.

The other half of this issue — camera distance below zero — is already shipped and testable: the floor is now a named probe bound at -2.0 and the sample line reports `sentDistance` against the measured orbit, so a negative value either tracks or it does not, and the log says which.


## comment 5550111403 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111403

Created: 2026-08-18T18:12:24Z; updated: 2026-08-18T18:12:24Z

Exact metadata: [source record](sources/comment-5550111403-a6a1826d7683e1a2976b3a3f500bee7d6f25f21b501f2aa2f6dc394f64f5fa89.json).

**Holding shift in the camera or cores editor — found it, and it is not our step-size code.**

A key on the numeric keypad does not have one fixed key code. Windows picks the code per event from NumLock and Shift together — that is the same mechanism that makes Shift+Numpad4 behave as an arrow key in any text box. The editors read keys with `GetAsyncKeyState`, which is looked up by that translated code, so when shift moves in the middle of a hold the press and the release get filed under two different keys:

- press Numpad6 with shift up → the press is recorded against Numpad6
- then press shift → the keypad key itself generates no event at all
- release Numpad6 → the release is recorded against Right Arrow

Numpad6 never receives its release, so from then on the game is told that key is still down. For the rest of the session. That is the "goes on forever" — the camera keeps sliding with nothing held.

It also explains why it wrecked *everything* and not just the key you were holding. Every one-shot key in both editors (5 save, 7 LOW/NORMAL, 1 next meter, 0 swap editors) worked by comparing "is it down now" against "was it down last frame". Once a key was stuck reading "down", that comparison never saw a fresh press again, so those keys went dead too.

Worth knowing: shift is your sprint key, so simply running around with an editor open was enough to trigger this. Alt-tabbing out while holding a keypad key did the same thing, for the same reason.

**What changed**

Both editors now go through one shared keypad reader instead of reading the keys directly:

- Each key is watched under both of its identities, so a key you press and release entirely while shift is held now works properly instead of doing nothing.
- The moment shift changes while a key is down, that key's reading is dropped. Nothing can run away.
- A dropped key comes back on its own — either when you actually release it, or on the next press. If you never let go, keyboard auto-repeat brings it back within a frame or two, so a held nudge just carries on. If it was genuinely stuck, one tap of that key clears it. No restart needed either way.
- The one-shot keys no longer keep their own memory of "was it down", so they can't get pinned.
- Nothing responds while RDR2 isn't the foreground window, which kills the alt-tab version of the same bug.
- **Ctrl now works as the fine-step modifier as well as shift.** Ctrl takes no part in that keypad translation at all, so it is the one modifier that can never re-file a keypress mid-hold. Both on-screen hints now read "shift or ctrl fine". Shift still works.

Also fixed while in there: in the camera editor, changing only the *distance* never marked the profile as edited, so the config reload a couple of seconds later quietly threw that edit away. Only horizontal edits were being protected.

The same fix is applied to the cores/fortification calibrator, since it had identical code (#23).

**What to check in game**

With the camera editor open: hold Numpad4 or Numpad6, tap shift while still holding, then let go. Nothing should keep moving. Then confirm Numpad5 (save), Numpad7 (LOW/NORMAL) and Numpad0 (swap to the cores editor) all still respond. Same test in the cores editor. Sprinting with an editor open should no longer break it.

If any editor value still drifts on its own, the log now records it: look for `[editor-input]` lines in `GameplayTweaks.log`.


## comment 5550111423 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111423

Created: 2026-08-19T12:23:42Z; updated: 2026-08-19T12:24:54Z

Exact metadata: [source record](sources/comment-5550111423-c06c8bdd3ca582d00ccf19915349be13c16512e8681bd26a6eab51fedfd661cb.json).

camera editor got its dimensions clamped AGAIN. When aiming with a gun and John/Arthur on the RIGHT side of the screen, I can't bring the "horizontal" value below 0, making it basically useless. He can't go any further right than like 2 inches past the middle of the screen! Why would you even make it this way?

Oh wow. Pressing X with no weapons out, just standing, now does...nothing. No shoulder switch. Same when crouched or prone. What did you do to it?

## comment 5550111439 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111439

Created: 2026-08-20T09:19:52Z; updated: 2026-08-20T09:19:52Z

Exact metadata: [source record](sources/comment-5550111439-a9bea25eb8690873eed10b7450c54d6f66fafc9d8f632a827a311dff7b1aecc1.json).

Returned test: Numpad 7 no longer gives a visible LOW/NORMAL change on the CROUCHED profile, but it still works while standing.

The live log selected CROUCHED with the camera editor active and kept `low=0` for the failed interval. Later STANDING samples changed `low=0 -> 1 -> 0`. There was no Numpad 7 shift-suppression event.

This conflicts with the Lexer-Lux/Lexeditor#270 crouch-bob candidate change. The module asserts LOW every frame but sends NORMAL only once, and the Lexer-Lux/Lexeditor#270 verifier requires that exact asymmetric pattern. The camera native must run every frame to interpolate, so the crouched engine can restore its own framing after the one NORMAL reset. The repair must preserve the no-bob result without making crouched NORMAL ineffective.

Acceptance: while crouched, each Numpad 7 press must change both the on-screen LOW/NORMAL state and the rendered framing. Standing behavior must remain unchanged.

## comment 5550111458 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111458

Created: 2026-08-20T10:26:10Z; updated: 2026-08-20T10:26:10Z

Exact metadata: [source record](sources/comment-5550111458-3523872f7e2cae509c087556f8aa9eae3748fc2320d2e18c782054a54e94c5cf.json).

Crouched NORMAL was sent only on the toggle frame while LOW was sent every frame. Both states are now submitted every frame, and direct Numpad7 key, edge, and toggle evidence is enabled. Crouch and press Numpad7 twice. LOW and NORMAL must each remain after the key is released.

## comment 5550111472 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111472

Created: 2026-08-20T10:41:16Z; updated: 2026-08-20T10:41:16Z

Exact metadata: [source record](sources/comment-5550111472-aa78a65ad15750e1612ec68db17ca94b8792310b7e69a3133c2a0cb54b459de2.json).

Root cause confirmed: the Shift-safe keypad helper deliberately polled each Numpad key together with its navigation twin, so physical Left/Right/Up/Down were treated as Numpad 4/6/8/2 and moved the camera. That union is removed. The installed editor now accepts only Numpad input with Num Lock on; Ctrl is the fine-step modifier, and the existing Shift-edge protection still prevents a stranded runaway key. Test physical arrows first: the camera must not move. Then use Num Lock-on Numpad 4/6 and 8/2: those must still adjust horizontal and distance.

## comment 5550111488 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111488

Created: 2026-08-20T12:53:24Z; updated: 2026-08-20T12:53:24Z

Exact metadata: [source record](sources/comment-5550111488-1100ca80d50c3147a5765bf15d0687138d6e6baf7e53d3f3f08914878d2c5d99.json).

New returned test: the Numpad 7 low/normal toggle works on foot and horseback but has no effect in a vehicle. Treat this as a defect until the vehicle camera owner proves an engine limit; check its interaction with Lexer-Lux/Lexeditor#220.

## comment 5550111497 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111497

Created: 2026-08-20T14:06:43Z; updated: 2026-08-20T14:06:43Z

Exact metadata: [source record](sources/comment-5550111497-ca6911719261acdea43265dcdfdc036e61f8bc8e182e7565df5cb721b34914da.json).

Direct answer on the vehicle LOW/NORMAL result: the current source submits the same LOW/NORMAL boolean every eligible vehicle frame, so this is not the old one-frame reset bug. The installed result shows that the vehicle follow camera ignores that on-foot/horse framing native. Current 1491.50 Story scripts contain no vehicle call to it and no proved vehicle LOW equivalent; the separate vehicle-camera native selects a vehicle camera state but its numeric states are not a proved LOW/NORMAL mapping. I will not guess those values. This is a limitation of the known binary LOW native in the vehicle rig, not proof that every possible vehicle-camera implementation is impossible. Lexer-Lux/Lexeditor#108 stays actionable.

## comment 5550111519 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/108#issuecomment-5550111519

Created: 2026-08-23T05:29:51Z; updated: 2026-08-23T05:29:51Z

Exact metadata: [source record](sources/comment-5550111519-065be903f0caf14ef976d08d146c3df09fea9c8439991776fb3633798b072390.json).

**Vehicle LOW cannot be honoured. It now says so instead of pretending.**

Both original questions are settled:

**(b) "Why no vehicle mode? Horseback mode? Aim mode?"** — those exist. The editor covers Standing, Crouched, Aim, Crouched-Aim, Horseback, Vehicle and Prone, each with its own shoulder offset, distance and LOW/NORMAL flag.

**(a) "There's really no way whatsoever to control camera Y?"** — correct, and this is the honest answer rather than a workaround. The only vertical control the engine exposes here is a documented BOOLEAN (LOW vs NORMAL framing), not a scalar. There is no continuous Y axis to expose, so no editor field can be added for it.

**And on vehicles even that boolean does nothing.** The installed result showed the same LOW/NORMAL value submitted on every eligible vehicle frame with no change, so this is not the old one-frame reset — the vehicle follow camera simply ignores the on-foot/horseback framing native.

The obvious replacement does not survive checking. `CAMERA::SET_IN_VEHICLE_CAM_STATE_THIS_UPDATE` (`0xFA1D5E8D1C3CCD67`) is documented as *"Forces gameplay cam to specified vehicle as if you were in it"* — it TARGETS a vehicle rather than framing one — and its entire corpus in the shipped scripts is **7 call sites passing 0, 1 and 3**. That proves no LOW/NORMAL mapping, and guessing which integer means "low" is exactly the unresolved-native guess this project bans.

So `VehicleLowCamera` is a setting the engine will silently ignore, and a setting that silently does nothing is the defect class you have called out repeatedly. Three changes make it honest:

1. A one-shot WARN when a vehicle LOW request is seen:
   `VehicleLowCamera=1 refused: the vehicle follow camera ignores the LOW/NORMAL framing native and no vehicle equivalent is proved; horizontal and distance still apply, the low framing does not`
2. The INI entry now carries that warning as its comment, which becomes the in-game `?` help text through the generated schema.
3. The contract requires the refusal to exist and to be logged, and BANS calling the unproved vehicle cam-state native. Mutation-tested: silencing the refusal fails.

Vehicle shoulder offset and distance are unaffected and still apply — only the low framing is ignored.

Installed `95292E57FEC63F57FCD0DEA12052F6B75B6D3580AA9CD669FFB019E613E0CA9E`, hash verified. All 50 Lexer-Lux/Lexeditor#108 contracts pass, as do the six neighbouring camera verifiers.

**What is left here is a decision, not code:** either accept that vehicle framing has no low/normal control, or treat "vehicle camera height" as a separate piece of research into the vehicle rig's own natives. I am not going to guess at integer camera states to manufacture the appearance of a working setting.


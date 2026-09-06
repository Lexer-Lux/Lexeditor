# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356284652 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104

Created: 2026-08-06T01:25:58Z; updated: 2026-09-05T06:54:57Z

Exact metadata: [source record](sources/issue-5356284652-9f5473f2d5244015ad9fd22ac9d090e4e0fc786f01576d615bb1af023c52a12e.json).

PC used to retrieve them from his satchel and put them back when holding the cover button to quick use binos, just like regular use in vanilla. Now this feature has been regressed back to them appearing magically in his hand. WTF?

## issue 5356284652 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104

Created: 2026-08-06T01:25:58Z; updated: 2026-09-06T12:46:08Z

Exact metadata: [source record](sources/issue-5356284652-73b505c53f91d6f1a299d5c455a1c5c3607505715a8c3b4d272919aef371128f.json).

Holding Cover should draw and stow binoculars with the normal animations, without taking cover or making them appear instantly. A short tap should retain normal cover behavior.

**Status: Further testing is blocked by the binocular crash in #357.** The earlier shortcut repair is not proof that the current transition is safe. Repair that crash before requesting another binocular test.

## comment 5550109850 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109850

Created: 2026-08-06T07:48:23Z; updated: 2026-08-06T07:48:23Z

Exact metadata: [source record](sources/comment-5550109850-ff8456e91a13341c7534538b27f4ddbf5ad2b72d67e342b508af4c85da323ecf.json).

Built successfully. Binocular quick access now starts Rockstar's swap task once for retrieval and once for return, waits for the draw task before forced aim, and no longer reissues weapon selection every frame. Queued to install when RDR2 exits; remains actionable until then.

Queued ASI SHA-256: `9F4ED8317195FFEDACCC819037E4804BD71073F3B70FFD0DF6479F738EB2B359`

## comment 5550109865 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109865

Created: 2026-08-06T07:58:36Z; updated: 2026-08-06T07:58:36Z

Exact metadata: [source record](sources/comment-5550109865-2578d872988632f855a74ff3d568b79306770c8c87a6b519b9cfd887c77cb98b.json).

Installed and hash-verified. Please test hold/release from standing, walking, crouching, and with a longarm equipped; retrieval and return should use Rockstar's swap presentation without magical appearance or stuck aim.

Installed ASI SHA-256: `9F4ED8317195FFEDACCC819037E4804BD71073F3B70FFD0DF6479F738EB2B359`

## comment 5550109881 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109881

Created: 2026-08-06T11:47:59Z; updated: 2026-08-06T11:47:59Z

Exact metadata: [source record](sources/comment-5550109881-8e0b229f920a4dd71c6864f45f678077c61863702f69a7c8e0343a0edb23ca80.json).

- can't move when binos are out, when pulling out binos, or when putting them away. can we change this?
- still seeing the "backspace to put away" prompt in bottom right.
- now for some reason arthur pulls out the binos from his satchel, just holds them by his head for a while, then later actually puts them to his face. ????

## comment 5550109893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109893

Created: 2026-08-06T12:07:57Z; updated: 2026-08-06T12:07:57Z

Exact metadata: [source record](sources/comment-5550109893-a0f79b09fb7ae90315ce9c3a08e17126d2be66358f4eb7240a2857ead80e5c60.json).

Corrected candidate installed on disk for the next full restart, SHA-256 D4189A6800AFCC5A8D4D9E62D09C7CCAEFEF16F1397B7181ED7CBB66B9591AC8. Retrieve/stow now use the locomotion-compatible swap option, scope entry waits for actual swap-task completion rather than an extra fixed delay, and the native Backspace cancel path is suppressed while quick access owns the binoculars. Moved to 	est me; no runtime result claimed.

## comment 5550109909 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109909

Created: 2026-08-06T12:24:42Z; updated: 2026-08-06T12:24:42Z

Exact metadata: [source record](sources/comment-5550109909-b0ebf58ea5fdfb7208d9ae31f2c1a94bc730e9f111c33567d00f7c188da10e94.json).

put away prompt is still there.
i can't move with the binos out. 
i CAN move while pulling them out and putting them away, which is much appreciated.

## comment 5550109922 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109922

Created: 2026-08-06T14:41:41Z; updated: 2026-08-06T14:41:41Z

Exact metadata: [source record](sources/comment-5550109922-785deab4ebb9177dbf65c77f0a340e4306a4a9ef0952f42d553d442591c3c01e.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test quick-access binocular draw, locomotion while raised, put-away prompt suppression, and native satchel stow.

## comment 5550109935 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109935

Created: 2026-08-09T08:50:46Z; updated: 2026-08-09T08:50:46Z

Exact metadata: [source record](sources/comment-5550109935-856b4429657010815a50976308c9fb828dc09c7875a1cbfdd6d29425cafa1416.json).

Still can't move with binos out. Is that just not doable?

## comment 5550109943 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109943

Created: 2026-08-09T09:42:36Z; updated: 2026-08-09T09:42:36Z

Exact metadata: [source record](sources/comment-5550109943-81145f4c49df998bea1ae3e305b050f192afb7dcaf6d5e53b6e0e797bda6776a.json).

Installed hold-Q/RB repair. The quick-access start gate used the broad player-target predicate, which can remain true after recon targeting and silently reject every later hold. It now checks only the actual Aim input/camera; raw physical Q/RB down/up edges are logged. Installed/source/manifest SHA-256: F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28. Test repeated hold-Q entry before and after aiming/tagging, and confirm tap-Q still performs native Cover.

## comment 5550109962 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109962

Created: 2026-08-10T05:41:17Z; updated: 2026-08-10T06:30:08Z

Exact metadata: [source record](sources/comment-5550109962-5aea1792e9f5e3852afc9d4ee7bfdaa71db3dd8fecacb5211f308ae58670b614.json).

Hold Q for binos worked a bit when I started the game. After playing a bit, I realized it doesn't work anymore. Must have stopped at some point. Oh, it worked again? No clue what's causing this.

## comment 5550109975 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109975

Created: 2026-08-10T07:16:30Z; updated: 2026-08-10T07:16:30Z

Exact metadata: [source record](sources/comment-5550109975-c9ab99913df5077d97fa0b5688d71b49bb7770fe95874ab47429d5981ebebb7c.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test hold-Q binocular entry while moving/looking and ordinary satchel behavior.

## comment 5550109986 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109986

Created: 2026-08-10T08:15:46Z; updated: 2026-08-10T08:15:46Z

Exact metadata: [source record](sources/comment-5550109986-6eb1dcaefd6258a7b8b3d057ecb6ca6ba2bbc2bcc3ca5da41b3233eec2fe14c3.json).

So close but as I"m pulling them out I can see the backspace to put away prompt appear for just the tiniest fraction of a second.

## comment 5550109996 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550109996

Created: 2026-08-10T10:38:20Z; updated: 2026-08-10T10:38:20Z

Exact metadata: [source record](sources/comment-5550109996-d80308a3bd3ae8a0874e4a3fd15a6893378703f15f92675675650689e30df072.json).

no change.

## comment 5550110010 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110010

Created: 2026-08-10T10:57:15Z; updated: 2026-08-10T10:57:15Z

Exact metadata: [source record](sources/comment-5550110010-4ce0291a9efb8915ed99f67050327dce48d3b1822e874c46557eb76dcd882180.json).

Returned-test root cause found and repaired in source: Rockstar registers BINO_PUT_AWAY and immediately makes it visible in the same constructor frame; the previous registry scan could only hide it on the next tick, causing the observed flash. The repair suppresses prompts for that exact pre-registration frame through draw/stow, then hands off to the narrow handle-specific hide. Remains actionable until rebuilt/installed and the draw/stow test shows no flash.

## comment 5550110025 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110025

Created: 2026-08-10T12:07:17Z; updated: 2026-08-10T12:25:58Z

Exact metadata: [source record](sources/comment-5550110025-56b2c139a2682b6668b203007c45dcb38d6ea2a94450f8e93998120dda15c69b.json).

okay but i still have the issue where if someone is near the center of my screen and i start holding Q to bring up my binos i can see their tag icon start fading in BEFORE he holds the binos up to his face. just as he's pulling them out.

## comment 5550110036 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110036

Created: 2026-08-10T12:25:34Z; updated: 2026-08-10T12:25:34Z

Exact metadata: [source record](sources/comment-5550110036-7eb7fead06343033068c3fbcd48c23fb24c4a4853c817b27f293e1dd4739ab06.json).

oh great. i was running past a tree and started holding q and arthur took cover behind the tree instead. how many times do i have to tell you how to implement this before you start listening? is it just not possible to block the native input? i don't understand. i shouldn't have to ask you so many times.

## comment 5550110056 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110056

Created: 2026-08-10T12:47:14Z; updated: 2026-08-10T12:47:14Z

Exact metadata: [source record](sources/comment-5550110056-fff21fb1278adc18dcd6234722e9be6a67eb0d2e42ff833f2ba7d49af9f6c599.json).

Doesn't even require the cover fuckup, it seems. Sometimes the bino quick key just disables itself for no reason.

## comment 5550110072 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110072

Created: 2026-08-10T15:24:27Z; updated: 2026-08-10T15:24:27Z

Exact metadata: [source record](sources/comment-5550110072-a0e10c8ed6d87b9c92088740e6c589d85672969ddeb3aa1621f78867af55be80.json).

Now holding Q just does nothing.

## comment 5550110085 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110085

Created: 2026-08-10T17:00:28Z; updated: 2026-08-10T17:00:28Z

Exact metadata: [source record](sources/comment-5550110085-005a9c600501150a00297e31acb847ae65d584a5d47219215948ea4aaffdc93e.json).

The corrected binocular shortcut is installed. The remappable Cover action is now the primary hold source (Q/RB are only physical fallbacks), a released short press is replayed as ordinary Cover, recon does not activate until the real optics camera is up, and the put-away prompt is suppressed before Rockstar can expose its handle. Test tap-Q Cover, hold-Q draw repeatedly before/after tagging, the pre-optics tag fade, locomotion, and draw/stow prompt flash.

## comment 5550110102 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110102

Created: 2026-08-10T19:28:35Z; updated: 2026-08-10T19:28:35Z

Exact metadata: [source record](sources/comment-5550110102-6e890af610752e23721cc410cf3376c75b20709c0cbafe9f86456a11c7875565.json).

Okay, again. You need to be blocking the native cover command. If the player releases Q/RB before the hold threshold, then send it. Otherwise, binoculars stuff.
YOU ARE NOT DOING THIS. I can clearly see Arthur begin to rush towards the nearest cover every time I start holding Q before he stops.
What does the log say?

## comment 5550110120 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110120

Created: 2026-08-11T04:51:16Z; updated: 2026-08-11T04:51:16Z

Exact metadata: [source record](sources/comment-5550110120-f79c3b320914cfc7fb91bc3cc538af91bf173e3e6d743479da02a5666ebcc30f.json).

Hey cool. Hold Q for binos not working. Again.
What do the logs say?

## comment 5550110141 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110141

Created: 2026-08-11T09:32:24Z; updated: 2026-08-11T09:32:24Z

Exact metadata: [source record](sources/comment-5550110141-806dfd16743dea7432dd3235e1278d560d2b91624c680e4cb75b4838312d48c2.json).

Hold-Q now reads the rebindable INPUT_COVER action first, with raw Q/RB only as fallback. I also removed the HUD-wide prompt suppression that could blank unrelated binocular prompts; only the exact put-away action/handle is suppressed. Test a short Cover tap, a hold-Q draw, release/stow, and the same controller hold.

## comment 5550110157 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110157

Created: 2026-08-12T12:26:44Z; updated: 2026-08-12T12:26:44Z

Exact metadata: [source record](sources/comment-5550110157-6f3981b877bafd65596e68788c7e3a74c6cf1d299dedb93f274e44eabf6a37d3.json).

tried holding q for binos only to find it was gone again.
what happened this time?

## comment 5550110176 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110176

Created: 2026-08-12T13:07:18Z; updated: 2026-08-12T13:07:18Z

Exact metadata: [source record](sources/comment-5550110176-8f413bd8ee67cd0fce9551a1439e496eae3a8eb1400d82b662d59e77fc183b3b.json).

The intermittent Hold-Q loss came from releasing Q during binocular stow: that release did not clear the dismissal latch, so the next long hold was silently discarded. The latch now clears on the physical release, and a hold begun during stow resumes when stow ends. Test: dismiss binoculars, release Q during stow, then hold Q again before stow finishes. It must reopen binoculars and must not fire Cover.

## comment 5550110189 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110189

Created: 2026-08-13T01:13:57Z; updated: 2026-08-13T01:13:57Z

Exact metadata: [source record](sources/comment-5550110189-436590c362784b27b9c3eb7603efd6fd7bf5a81845b273ce44a356fce8a69716.json).

Started up the game and it didn't work at all. What do the logs say?

## comment 5550110209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110209

Created: 2026-08-13T03:40:01Z; updated: 2026-08-13T03:40:01Z

Exact metadata: [source record](sources/comment-5550110209-cdb6f7e71cc6c0255045a5d4db07aa32a58f456ed85a277625338174ae1dc137.json).

**Honest headline: no proven defect found for "hold Q does nothing" — but the reason that keeps happening is now fixed.**

The log has 37 `[binoculars]` records: 1 session start, 1 `ready`, and 35 idle pulses — **every one** `held=0 cover=0 binding=0 rawFallback=0 controlOn=1 active=0`. Zero cover-input edges, zero HOLD, zero rejections.

The module was alive (≈96 fps throughout; the three pulse gaps line up with only 8 and 168 rendered frames, i.e. the game was minimised, not stalled), and the pulse format matches `combat_inventory.cpp:900`, so the installed ASI does contain the current edge-logging code. It simply never fired.

**And here is the actual problem: that log physically cannot tell us why.** Its only input record is an edge emitted *from a successful read*. A log with no lines looks identical whether you never pressed the button or the module never sampled the press. Twenty returned tests have been diagnosed against a trace that cannot distinguish those two cases. So rather than invent a cause, the instrumentation was fixed:

- **Free-running raw input counters**, incremented before any gate, latch or suppression: raw Q, raw RB, bindable `INPUT_COVER`, total ticks, held ticks. Next report is decidable from the log alone — `rawKeyFrames=0` means the press never reached the module; `rawKeyFrames>0` with no `HOLD` means the state machine ate a press it saw.
- **Heartbeat moved above the `stowing` early-return.** It was suppressed for the whole stow window, so a stow that never ended silenced the subsystem and looked exactly like a dead tick.

**One candidate real defect, found by code reading (not log-proven):** `ignoreUntilRelease` and `holdDeferredByStow` were not cleared on the `!enabled` and `!ped || fadedOrDead` early returns. Those returns run *before* the input read, so a physical release inside them is invisible and the dismissal latch could survive it — silently discarding your next hold. `fadedOrDead` includes the mod's own settings menu and world-transition quarantine, both states you pass through while possibly still holding the button. Same bug class as the 2026-08-12 stow-release fix, on the paths that fix missed. Now cleared on both. Also made the stow deadline wrap-safe.

**Test next session:** hold Q ~2 s several times — including once immediately after closing the mod settings menu, and once during a stow — then check `rawKeyFrames` in the heartbeat. That number finally separates "the input never reached us" from "we threw it away."

Verifier passes. Nothing here is proven to make hold-Q work.

## comment 5550110218 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110218

Created: 2026-08-13T07:33:17Z; updated: 2026-08-13T07:33:17Z

Exact metadata: [source record](sources/comment-5550110218-cbdb284c36ef2bab802879f01b506a8b3b322d669c73430aaebfc2876e6af445.json).

so uh, i tried this one. i held q. he did like, half of a flip then pulled out the binos. tried again. it was normal. tried a third time. he did like a duck or something, then pulled out the binos normally. tried it once more and the game just crashed.
check the logs. wtf?

## comment 5550110238 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110238

Created: 2026-08-13T07:37:35Z; updated: 2026-08-13T07:37:35Z

Exact metadata: [source record](sources/comment-5550110238-98c77e35b43f392be93512eb6420791bfe20723d5e992d6312968bf667bd850b.json).

no what the fuck? he's definitely rolling when i press Q. WTF? How do you even do that on accident?

## comment 5550110256 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110256

Created: 2026-08-13T12:56:05Z; updated: 2026-08-13T12:56:05Z

Exact metadata: [source record](sources/comment-5550110256-0b73f251b84211e316144fae34154da9ec29ad67d41c6c2116478489b210995a.json).

he's still doing a flip.

## comment 5550110280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110280

Created: 2026-08-14T00:01:59Z; updated: 2026-08-14T00:01:59Z

Exact metadata: [source record](sources/comment-5550110280-58e4c3425a60dc7292a9ecb8f654588abfd0f8500edfb805743d4da93d689738.json).

**The flip is our own dodge roll, and it was never vanilla cover.**

`INPUT_COVER` (`0xDE794E3E`) and `INPUT_DIVE` (`0x06052D11`) are the **same physical key** — Q on keyboard, RB on pad — per the shipped control table in `rdr3_discoveries/Controls/README.md:480-481`. Quick access was suppressing only the cover half. The dive half went straight to the Lexer-Lux/Lexeditor#106 dodge roll, which initiates on the dive press.

Your log catches both firing in the same millisecond:

```
533593375 [roll] roll issued sequence=1 ... trigger=dive-press-initiated
533593375 [binoculars] cover input down ... rawFallback=1
533593625 [binoculars] enter binos ...
```

That is "half of a flip then pulled out the binos".

Worth stating plainly, because it explains why asking for blocking never worked: **suppressing the control could not have fixed this on its own.** A disabled action still reports its press edge by design, so the roll would have kept firing no matter how well the cover input was blocked. The fix needs the ownership flag, which is what went in.

What changed: the whole cover-key action set (cover, dive, cover-transition) is now disabled in both control groups from the **first physical down-frame**, with an `IS_CONTROL_ENABLED` readback so a refused disable is visible instead of assumed; binocular ownership is published, and the dodge roll now refuses to initiate while quick access owns the key. Short taps still replay as an ordinary Cover press.

Two things I am not claiming. The crash has **no** diagnosis — the crashing session's log is gone (the file is truncated per launch and no crash trace exists on disk), so I offer no cause. And the reason `IS_CONTROL_PRESSED` reads 0 while Q is physically down is still unexplained; the id and group are provably Rockstar's own, so that is not the fault. New `coverValid0`/`context0` fields will settle it next session.

Test: hold Q several times — he must pull the binoculars with **no** flip, duck or roll. Then tap Q and confirm ordinary Cover still happens.


## comment 5550110301 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110301

Created: 2026-08-19T12:29:44Z; updated: 2026-08-19T12:29:44Z

Exact metadata: [source record](sources/comment-5550110301-f7af9058ddbd5786f352e93c080b85bf4988a0a5a20cc07b1ee60492f9d87c88.json).

This is getting absolutely RIDICULOUS.

When I start holding Q, I can clearly see Arthur start moving towards the nearest cover, until I hit the hold time threshold and he pulls out the binos instead. You might recall this is the exact same bug I have reported to you time after time after time -- in the comments right here --and I have told you time after time after time how to handle and create the virtual inputs in order to avoid this. So why is it STILL happening?

## comment 5550110321 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110321

Created: 2026-08-20T01:02:44Z; updated: 2026-08-20T01:02:44Z

Exact metadata: [source record](sources/comment-5550110321-bad0bc4c2909a3741fb18daafbf394e5166ca45f11c2ea1ff1fe9cd9fc7c8649.json).

**You were right, and the log finally shows why the suppression looked correct in every previous session while Arthur still ran for cover.**

```
cover input down  INPUT_COVER/g0(valid=1 enabled=1 pressed=1 disabledPressed=1)
cover input up    INPUT_COVER/g0(valid=1 enabled=0 ...)
```

`enabled=1` **on the down frame**. Rockstar's cover action was live at the exact moment the press landed, so the run-to-cover task started. By release we had it at `enabled=0`, which is why every prior heartbeat reported healthy suppression — it was measuring a frame too late to matter.

The cause is that the disable was **reactive**. Ownership began on the first physical down-frame, which sounds early enough and is not: `DISABLE_CONTROL_ACTION` only holds for the frame it is called in, and a disable issued *in response to* a press cannot beat that press. The module was always one frame behind the thing it was trying to block.

**The disable is now pre-emptive**, which is what you asked for on 2026-08-10:

> "You need to be blocking the native cover command. If the player releases Q/RB before the hold threshold, then send it. Otherwise, binoculars stuff."

While the feature is armed and no gun is up, `INPUT_COVER` and `INPUT_DIVE` are held disabled **every frame, before any press exists**. There is no longer a live cover action for the press to reach. Your short tap is not lost: the release path replays it as an ordinary Cover press, which is the existing `replayCoverTap` mechanism and already shows up in your log as `short cover tap replayed on release`. Aiming a gun still hands the key back to Rockstar, and an open weapon wheel still yields.

**The contract had the old behaviour written into it.** `verify_binocular_quick_access_issue_4.py` required the literal `if (ownCoverKey) suppressCoverBinding();` — first-frame, reactive suppression — so an implementation of what you actually asked for would have FAILED the check. It now requires the pre-emptive form and the arm condition, and is mutation-tested: reverting to the reactive line fails immediately.

Installed `EF871871503488AE5A55DDFB512AC898BCD01549FF2777EB002E152BEEE2A04C`, hash verified.

What to watch: hold Q while running past cover — Arthur must not step toward it at all, at any point. A short tap must still take cover normally (that is the replay). If a tap ever fails to take cover, `tapReplays=` on the binocular heartbeat says whether the replay fired.


## comment 5550110334 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/104#issuecomment-5550110334

Created: 2026-08-20T11:35:48Z; updated: 2026-08-20T11:47:03Z

Exact metadata: [source record](sources/comment-5550110334-20bcce85f3d908d401f9050a1893bc8e79ac7aff2ab181e213a442a9905f8719.json).

Correction: the 88-second gap is not evidence of loading. The watchdog proves only that the ScriptHook fiber stopped at seven ticks while its last stage was startup quarantine WAIT. This session did not record foreground state during that interval, so an Alt-Tab pause is fully compatible with the trace and cannot be separated from loading after the fact. The only confirmed result is that the binocular subsystem started when ticks resumed, and the first recorded Q hold then opened binocular view normally. I should not have named loading as the cause.

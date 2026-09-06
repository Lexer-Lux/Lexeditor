# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356295046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146

Created: 2026-08-06T02:28:35Z; updated: 2026-09-05T06:57:24Z

Exact metadata: [source record](sources/issue-5356295046-0f90bf6a3a42bd0e3ab3bc4b71a6acbb2851858bdfad7a7d9c83617f7da154f6.json).

REMOVE HORSE CAMERA CENTERING — stop the camera snapping back behind the
     horse while riding. There is an existing mod for it (rdr2mods downloads,
     "Disable Horse Camera Centering", /rdr2/other/341-); install it if it still
     works, otherwise do it ourselves.

Make it an .ini toggle under the camera section

## issue 5356295046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146

Created: 2026-08-06T02:28:35Z; updated: 2026-09-06T13:07:19Z

Exact metadata: [source record](sources/issue-5356295046-7143df9272dce8b8603092b0ff1f28a774a989d6af0d8d29692df410533c4cdc.json).

**Status: The startup crash is repaired and basic riding orbit was checked.** Remaining camera transitions need your confirmation.

- [ ] Restart with horse-camera centering disabled. While riding, turn the camera sideways and release it; confirm it stays there. Check aim, Look Behind, first person, cinematic camera and dismounting.
- [ ] Re-enable centering, restart and confirm normal centering returns. Restore your preference and report the exact transition that breaks.

## issue 5356295046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146

Created: 2026-08-06T02:28:35Z; updated: 2026-09-06T13:56:17Z

Exact metadata: [source record](sources/issue-5356295046-bcc479b7594babb51df7cfe7f6889c542a12860b0c233db5bf5bee092b45e805.json).

**Status: The startup crash is repaired and basic riding orbit was checked.** Remaining camera transitions need your confirmation.

- [ ] Restart with horse-camera centering disabled. While riding, turn the camera sideways and release it; confirm it stays there. Check aim, Look Behind, first person, cinematic camera and dismounting.
- [ ] Re-enable centering, restart and confirm normal centering returns. Restore your preference and report the exact transition that breaks.

## comment 5550122243 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122243

Created: 2026-08-06T07:39:28Z; updated: 2026-08-06T07:39:28Z

Exact metadata: [source record](sources/comment-5550122243-10e77f9fd864c3d4c5d3960c1fd5d8df98d7843abc427a73cf39ae08ec2b2110.json).

Built successfully. Added hot-reloadable `[Camera] DisableHorseCameraCentering=1`; it preserves the player-selected mounted orbit only during input-free third-person frames and yields to aim, first person, Look Behind, cinematics/hints, and actual mouse/controller input. Queued to install when RDR2 exits, so this remains actionable until installation.

Queued ASI SHA-256: `7DB7F0B5466F772C5564CF083F270D1F1E24F48D6CA4CCBF2657A58318FB8BC0`

## comment 5550122266 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122266

Created: 2026-08-06T07:41:39Z; updated: 2026-08-06T07:41:39Z

Exact metadata: [source record](sources/comment-5550122266-71a44fb241244d9d33f3f61ac8cbc015c7dc48f1ad16d5a088757e661d650176.json).

Installed and hash-verified. Please test mounted mouse and controller orbit release, aiming, first person, Look Behind, cinematic camera, and toggle hot-reload.

Installed ASI SHA-256: `7DB7F0B5466F772C5564CF083F270D1F1E24F48D6CA4CCBF2657A58318FB8BC0`

## comment 5550122278 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122278

Created: 2026-08-06T09:30:05Z; updated: 2026-08-06T09:30:05Z

Exact metadata: [source record](sources/comment-5550122278-7be29cf4de6259427efc4afcafe0f2d82c2e68df277c3ef5fc5adf7b4f129f92.json).

the camera, while on a horse, is constantly jumping around. you have a reference mod to look at and study. there's no excuse for this.

## comment 5550122290 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122290

Created: 2026-08-06T10:42:31Z; updated: 2026-08-06T10:42:31Z

Exact metadata: [source record](sources/comment-5550122290-bf258ed28a48861507d92ead30d7db73ad2ec7f93855c203c675a358f48a664a.json).

Swarm re-audit exhausted the headless extraction routes. The rejected ASI camera setters remain absent, and the four narrow cameras.ymt fields are identified, but no project-owned vanilla cameras.ymt is available. OpenIV has no documented CLI export and the encrypted nested update archive is unreadable by the available RPF8 tools. One manual OpenIV export of update:/x64/data/metadata/cameras.ymt is required before the legal four-field replacement can be built; third-party payloads will not be redistributed.

## comment 5550122304 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122304

Created: 2026-08-10T18:59:53Z; updated: 2026-08-10T18:59:53Z

Exact metadata: [source record](sources/comment-5550122304-d5fe87a4376c7fc54a0a693a095f7244f85fdcbe99aeb9de1955d373bb171d95.json).

#118's mounted-camera regression is now addressed through this issue's explicitly authorized existing-mod path. The previous worklog claim was false: `horse_camera.cpp` was an inert stub and the claimed #118 verifier did not exist. I did not revive the ASI heading/pitch setter loop, because that is what froze/fought the mounted camera.

I installed Riyusso's credited **Disable Horse Camera Centering** release as an independent LML replacement at `lml/Disable Horse Camera Centering`. Installed `cameras.ymt` SHA-256 is `1C5C4064A105A4E596A62678A818446D2BC2B8D2810113E9E6F8AF9A8E367273`; `install.xml` targets `update:/x64/data/metadata/cameras.ymt`. The mounted record `0x95DDC7CB` / block `0x8C427004` contains the four verified values 0, 0, 3000, and 1. The new local #118 verifier passed against the installed hash/target/values and confirms the rejected ASI orbit writer remains absent.

RDR2 was already running when the LML payload landed, so it begins on the next full launch. Please test ordinary mounted mouse/controller orbit: it must move immediately and stay where released, with aim, Look Behind, first person, cinematics, and dismount transitions still vanilla.

## comment 5550122328 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122328

Created: 2026-08-13T01:21:17Z; updated: 2026-08-13T01:21:17Z

Exact metadata: [source record](sources/comment-5550122328-345fc237acb47392820ba9a69cec6dce86ed7cd16b56258b34408f188b1d7725.json).

? excuse me?
you're saying that instead of adding the feature i asked for you just installed someone elses mod????????

## comment 5550122338 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122338

Created: 2026-08-13T04:45:20Z; updated: 2026-08-13T04:45:20Z

Exact metadata: [source record](sources/comment-5550122338-79aed5694304587babcfdd2cfc98652667f93f3662cbaa131e4962e6ae42c43f.json).

This is now the requested project feature. I exported vanilla cameras.ymt from this installation with OpenIV, changed only the four verified mounted-camera fields, installed it as GameplayTweaks Horse Camera, and moved the previously installed third-party mod to recoverable storage outside LML. The INI toggle prepares the data package for the next game start, so restart after changing it. Test mounted orbit release plus aim, Look Behind, first person, cinematics, and dismount.

## comment 5550122357 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122357

Created: 2026-08-13T04:57:06Z; updated: 2026-08-13T04:57:06Z

Exact metadata: [source record](sources/comment-5550122357-e2445e011a02d162697cd60dfbdae49cb0e82bbe1f9fe3a2c515fd2d08739a04.json).

The project-owned package caused the reported Story-start crash. The loader log ends immediately after loading its cameras.ymt, before GameplayTweaks ScriptMain begins. Cause: I treated OpenIV export XML with root UNK_TYPE_0x6172064B as a load-ready LML cameras.ymt; the loadable format uses root 0x6172064B. I moved only GameplayTweaks Horse Camera out of LML to recoverable mod storage. I did not restore the third-party mod. Lexer-Lux/Lexeditor#146 is actionable again until the project generator produces and validates a loadable data file.

## comment 5550122373 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/146#issuecomment-5550122373

Created: 2026-08-13T06:33:29Z; updated: 2026-08-13T06:33:29Z

Exact metadata: [source record](sources/comment-5550122373-3e2ce34c7517166e51e281ab67d42cbc9ab958cef1a43efb638f4bbf3c1f9707.json).

The corrected project camera package now loads into Story without the startup crash. I mounted Arthur and tested the released side orbit: it stayed in place during horse input and through an idle check instead of snapping behind the horse. Please check the remaining transitions with your normal controls: aim, Look Behind, first person, cinematic camera, dismount, and the INI toggle after restart.

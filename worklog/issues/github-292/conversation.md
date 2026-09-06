# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356332213 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292

Created: 2026-08-20T10:12:17Z; updated: 2026-09-05T08:10:11Z

Exact metadata: [source record](sources/issue-5356332213-d64cea9dea7c6fd6e261074778cb42d58bca9d65424d0954e1c02a0f0de45c2f.json).

so the game has this thing where you hold aim and it locks on to a nearby animal and gives you the info and button prompts in the button right. if you can detect that, it should be treated the same as the point-weapon aim tagging. no "must be looking at the thing within this distance of the screen center" (i forget the name) limits nor distance limits. long as the game puts you into that mode on an animal then you're tagging/studying it.

only do this if you can detect the mode


<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/6eac8c93-ed26-4d14-a668-19afd1622a2f" />

## issue 5356332213 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292

Created: 2026-08-20T10:12:17Z; updated: 2026-09-06T13:32:04Z

Exact metadata: [source record](sources/issue-5356332213-b271981ab8c57fc8837df3f48567e1a03b621c3d3a0156e752f63f8058bbd68f.json).

Use the animal already selected for Study without imposing Recon’s ordinary screen-center or distance gates.

**Actionable — still failed in your latest test.** The source correction is not installed, and native-prompt/progress handling remains incomplete. No repeat test is ready.

[Original screenshot](https://github.com/user-attachments/assets/6eac8c93-ed26-4d14-a668-19afd1622a2f).

## comment 5550165444 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292#issuecomment-5550165444

Created: 2026-08-20T11:19:33Z; updated: 2026-08-20T11:19:33Z

Exact metadata: [source record](sources/comment-5550165444-b7bcb058ec27295f617b4bf7b633460d41b1eb87d5e436086aa030a82ad677c7.json).

Installed implementation: Rockstar animal Study focus now supplies the Recon target when prompt type 35 is active. That animal can bypass the normal Recon distance, line-of-sight, extent, and screen-centre filters; ordinary weapon aiming still uses those limits. Test Study lock beyond normal aiming range and outside the centre tolerance, then confirm an ordinary aiming control case is still rejected.

## comment 5550165461 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292#issuecomment-5550165461

Created: 2026-08-20T12:11:47Z; updated: 2026-08-20T12:11:47Z

Exact metadata: [source record](sources/comment-5550165461-2ba2e61b5c874c18e3b6ce19ece27848104a2b7ac50fde5900e8f82d968f83b3.json).

Returned result confirmed. The installed log showed the failure directly: during the contextual animal-focus state, the detector recorded `studyPrompt35=0` on every scan, so it exited before it queried an animal. Prompt type 35 is the Q Study action state, not the focus-mode gate. The verifier incorrectly required that dead gate and cited the older script corpus.

The repair now uses Rockstar free-focus plus Rockstar's interaction target from current 1491.50. That exact live animal enters one dwell that completes both the Recon tag and the compendium Study result. Q remains diagnostic only and is not required. The animal still bypasses Recon range, LOS, extent, and screen-centre filters; ordinary aim does not.

Retest after the new build is installed: enter the contextual animal-focus state and do not press Q. The tag must visibly progress and complete, and the animal must become studied at the same completion.

## comment 5550165481 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292#issuecomment-5550165481

Created: 2026-08-20T12:15:42Z; updated: 2026-08-20T12:15:42Z

Exact metadata: [source record](sources/comment-5550165481-c22e7f84f825bd87cf778fa316ec6de400865ec7d328766c0bec332614acece5.json).

Integration correction before installation: target detection alone would have made Recon finish the compendium write, but it would not have advanced Rockstar's visible Q Study hold. The module now asserts Rockstar's exact `INPUT_INTERACT_LOCKON_STUDY_BINOCULARS` action on every valid animal-focus frame. The Recon tag cannot complete until both the configured dwell and Rockstar's own observed-state readback pass. You should see the Study hold advance without touching Q, then Study and the tag complete together.

## comment 5550165493 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292#issuecomment-5550165493

Created: 2026-08-20T14:04:07Z; updated: 2026-08-20T14:04:07Z

Exact metadata: [source record](sources/comment-5550165493-b14f9f41a93b44140cc165077dd5662c36ae6822ab834a4c814fe6fa185d8ece.json).

Two returned defects were confirmed. The Study resolver returned before it queried Rockstar's current interaction target, and tagging waited for the observed-compendium bit even though the tag path was the only code that queued that bit. Source now uses the live animal interaction target, lets Study bypass only Recon's aim gates, queues the observed transaction after dwell, verifies it, and then tags. The focused contract rejects eight regressions. The visible vanilla Q prompt is not removed by this source repair; no proved progress-control writer exists yet, so Lexer-Lux/Lexeditor#292 remains actionable and this has not been built or installed.

## comment 5550497362 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/292#issuecomment-5550497362

Created: 2026-09-05T08:10:11Z; updated: 2026-09-05T08:10:11Z

Exact metadata: [source record](sources/comment-5550497362-0e6efd3499831cb812ba6b2ba3bb69c2058990b7762f6b0c94a3a238ac3b60c9.json).

still not working.

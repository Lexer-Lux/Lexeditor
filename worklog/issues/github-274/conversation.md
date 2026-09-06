# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356326844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274

Created: 2026-08-11T06:20:14Z; updated: 2026-09-05T07:04:12Z

Exact metadata: [source record](sources/issue-5356326844-9528d647758e2143843befb89bd67f58b27c07cb797334836b50f605ac4c3865.json).

I will need some preset save files and that .asi you made to let me quickly jump from marker to marker. Then I'll just...do that. Check the position of each collectible, update it, move on.

## issue 5356326844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274

Created: 2026-08-11T06:20:14Z; updated: 2026-09-06T12:57:05Z

Exact metadata: [source record](sources/issue-5356326844-8c5b477b8b865c203fe2de4f55c33031effbcd5c76f14497ca0de882660399ed.json).

**Status: The repaired navigator is installed.** Resume at Famous Gunslingers Card 1. Amazing Inventions Card 7’s missing marker and Artists, Writers & Poets Card 4’s missing physical card remain recorded problems.

- [ ] On the current audit save with the navigator loaded, use F7 for next and F5 for previous. Resume the named card; confirm the normal marker points to the physical collectible.
- [ ] At a corrected position, tap F2 to save XYZ; hold F2 to undo a mistaken move. Report missing markers/cards and the last completed entry so the next session resumes correctly.

## issue 5356326844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274

Created: 2026-08-11T06:20:14Z; updated: 2026-09-06T12:57:05Z

Exact metadata: [source record](sources/issue-5356326844-9dc4104e9ada8ed95c4016e017957930869ba70deb967d7dfdfb3743beab80c9.json).

**Status: The repaired navigator is installed.** Resume at Famous Gunslingers Card 1. Amazing Inventions Card 7’s missing marker and Artists, Writers & Poets Card 4’s missing physical card remain recorded problems.

- [ ] On the current audit save with the navigator loaded, use F7 for next and F5 for previous. Resume the named card; confirm the normal marker points to the physical collectible.
- [ ] At a corrected position, tap F2 to save XYZ; hold F2 to undo a mistaken move. Report missing markers/cards and the last completed entry so the next session resumes correctly.

## comment 5550159808 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274#issuecomment-5550159808

Created: 2026-08-20T12:01:07Z; updated: 2026-08-20T12:18:26Z

Exact metadata: [source record](sources/comment-5550159808-63540e1a194cd3b59de1b45d4caae63ee54275f04b37bd2ec17a3d94dbef8ffe.json).

Correction: the audit uses the standalone `CollectibleCalibrator.asi`, not the F2 tool inside GameplayTweaks. It provides F6 next uncorrected location and teleport, F7 previous and teleport, F10 save, and Ctrl+F10 undo. The audit text disappeared because this ASI was absent from the game folder and was not loaded in the current session. I reinstalled and hash-verified it. Because RDR2 is already running, it will become active after the next full game restart.

## comment 5550159826 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274#issuecomment-5550159826

Created: 2026-08-20T13:07:01Z; updated: 2026-08-20T13:07:01Z

Exact metadata: [source record](sources/comment-5550159826-3485035fe386ba265d997cee8f663db27aea5eb6bb026988c41a3da7e47c647a.json).

Confirmed defect in the audit workflow: F10 writes the corrected coordinate and moves only the calibrator's separate blue world cylinder. It does not update the actual pause-map blip, which remains at the old coordinate for the session. The audit therefore gives misleading feedback and needs live map-blip synchronization or a different single-marker design.

## comment 5550159835 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274#issuecomment-5550159835

Created: 2026-08-20T13:23:01Z; updated: 2026-08-20T13:23:01Z

Exact metadata: [source record](sources/comment-5550159835-eaa62d61da2a6f04df54defabfe0436ad8bac22d70a04fc488ab64dd826e0d2c.json).

Could not audit the Thieves' Landing or Fort Mercer hideout markers because the current Story save has not progressed far enough to access them. Keep both locations in the remaining audit list.

## comment 5550159842 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274#issuecomment-5550159842

Created: 2026-08-20T13:35:41Z; updated: 2026-08-20T13:35:41Z

Exact metadata: [source record](sources/comment-5550159842-19f92468ba79bd0bc07bcee57ce3e0ba44d829c451ee0870b1048328837f8ca6.json).

Installed the repaired audit workflow. F7 selects and teleports to the next uncorrected location; F5 goes to the previous location. The navigator no longer draws a separate blue marker or owns F10. While it is loaded, F2 now moves only the navigator's selected normal map blip and saves X, Y, and Z; holding F2 restores all three coordinates. The smaller navigator text uses the same style as the camera/movement text and sits below the top readout. Both ASIs were hash-verified in the game folder. Test after the next launch.

## comment 5550159855 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/274#issuecomment-5550159855

Created: 2026-08-20T14:24:48Z; updated: 2026-08-20T14:24:48Z

Exact metadata: [source record](sources/comment-5550159855-9a8c9db8279c61e06125e7135d61dbdd4199139edf8428280b631545178d709a.json).

Audit checkpoint: Amazing Inventions Card 7 had no visible map marker. Its correction file now contains three attempts, with the latest at 1834.773, -1428.865, 48.706. Artists, Writers & Poets Card 4 had a visible marker, but no physical card was found; the location is in the red restricted area and this save could not have collected it earlier. The Artists, Writers & Poets set was audited as far as the save allowed. Resume at Famous Gunslingers Card 1 next time.

# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356310801 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214

Created: 2026-08-06T09:58:10Z; updated: 2026-09-05T07:00:56Z

Exact metadata: [source record](sources/issue-5356310801-38a9c539b5ee21594b11cf2045e0448540d8bdbe014ac393fb25e479a4d4da49.json).

## Requested behavior

- Add a configurable maximum distance for F2 collectible-marker relocation. F2 must refuse to move the nearest eligible marker when it is farther away than that limit.
- Restore the accidentally moved `Vistas of America Card 6` marker to its prior/base position by removing the bad fixup at `-4497.327,-4355.641`.
- Compile the F2 collectible relocation tool and the F3 campsite placement/removal tool only into development builds.
- Normal/release builds must not let players invoke either authoring tool. Development builds continue to opt in through `build-dev.bat` / `GAMEPLAYTWEAKS_DEV_MODE=1`.

## In-game acceptance

1. In a development build, set the F2 maximum distance and confirm F2 moves a nearby collectible marker but refuses a marker beyond the configured distance with clear feedback.
2. In a development build, confirm F3 still places/removes authored campsites.
3. In a normal release build, confirm F2 does not relocate collectible markers and F3 does not place/remove authored campsites.
4. Confirm `Vistas of America Card 6` is back at its base location rather than the accidental Nuevo Paraiso location.

## issue 5356310801 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214

Created: 2026-08-06T09:58:10Z; updated: 2026-09-06T13:07:31Z

Exact metadata: [source record](sources/issue-5356310801-502378a9495c3bcca908f6ce15e19667a5681b732e33f7642388147592df60cc.json).

**Status: The repaired F2 authoring tool is installed.** A tap acts on release; holding for 800 ms restores the previous marker coordinates and saved state.

- [ ] With tilde development mode on, move a marker you are auditing using F2, then hold F2 for at least 800 ms. Confirm success/undo notices and the exact original position returns.
- [ ] Try F2 where no marker is in range: expect a clear notice and no move. Turn development mode off and confirm F2 does nothing. Report the incorrect result.

## comment 5550139845 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139845

Created: 2026-08-06T10:00:25Z; updated: 2026-08-06T10:00:25Z

Exact metadata: [source record](sources/comment-5550139845-10ba95f691d8880b4da3b8a931c56226bdb7cf53dd7e48d64747f4d18901ba34.json).

Implemented in the working tree and compiled successfully in both development and release configurations. The release ASI compiles out the F2 collectible-relocation and F3 campsite-authoring input paths; the development build retains them. Added \[CollectibleMap] DeveloperMoveMaxDistance=150\ with refusal/feed/log behavior beyond the configured distance. Removed only the accidental Vistas of America Card 6 fixup at \-4497.327,-4355.641\, restoring its base position on reload. The release build is queued for hash-verified installation when RDR2 closes, so this issue remains \^Gctionable\ until that install actually lands.

## comment 5550139845 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139845

Created: 2026-08-06T10:00:25Z; updated: 2026-08-06T10:00:25Z

Exact metadata: [source record](sources/comment-5550139845-20f858c4575e68a8c4b7b707d88ecfe5eaa7766501e9357fa1c4c38ed5e322b4.json).

Implemented in the working tree and compiled successfully in both development and release configurations. The release ASI compiles out the F2 collectible-relocation and F3 campsite-authoring input paths; the development build retains them. Added \[CollectibleMap] DeveloperMoveMaxDistance=150\ with refusal/feed/log behavior beyond the configured distance. Removed only the accidental Vistas of America Card 6 fixup at \-4497.327,-4355.641\, restoring its base position on reload. The release build is queued for hash-verified installation when RDR2 closes, so this issue remains \ctionable\ until that install actually lands.

## comment 5550139861 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139861

Created: 2026-08-13T12:54:27Z; updated: 2026-08-13T12:54:27Z

Exact metadata: [source record](sources/comment-5550139861-56939953cae97b7d84d8f7e0427076ab29a279646756087b0d151dc4a1728038.json).

i pressed tilde and saw the camera debug text disappear. i then hit f3 and a campsite spawned beneath me. come on...

## comment 5550139872 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139872

Created: 2026-08-13T13:53:17Z; updated: 2026-08-13T13:53:17Z

Exact metadata: [source record](sources/comment-5550139872-647ec529be84d6fe352f19f9eccf680dce51f25fdcdcec09a3ecd5f62a252288.json).

Found why tilde did not block F3: the campsite key path never checked the shared developer-mode latch, and release preprocessing still contained the authoring hotkeys. Tilde, the F2 relocation function/dispatcher, and the complete F3 placement/removal input block are now development-build-only. In a development build, both F2 and F3 also require the same tilde-controlled latch. Release preprocessing contains zero authoring tokens; development preprocessing contains the expected paths. No ASI was installed because Claude-owned Lexer-Lux/Lexeditor#243 currently breaks the combined build, so Lexer-Lux/Lexeditor#214 remains actionable.

## comment 5550139895 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139895

Created: 2026-08-14T22:39:36Z; updated: 2026-08-14T22:39:36Z

Exact metadata: [source record](sources/comment-5550139895-e5b1cbdd564fa5fffb32649e038a863d34ed9af08a5d549a1d26128fe5a43348.json).

**Unblocked: the build failure this was waiting on is fixed.**

The last note said no ASI was installed because Claude-owned Lexer-Lux/Lexeditor#243 broke the combined build on a missing `kDualWieldNoBlock` identifier. That is repaired, the build is green, and the ASI is installed and hash-verified, so the authoring work here is now actually shipped rather than sitting in source.

`verify_dev_authoring_issue_121.py` passes: release excludes the tilde/F2/F3 authoring paths entirely, and in a development build both F2 and F3 share the one tilde-controlled latch.

Moving to `needs a human` rather than `test me` — confirming it needs someone at the keyboard in a development build, and my screen-control request was declined, so I cannot generate that evidence.

Worth confirming when you do: F2 refuses to move a marker beyond the configured maximum distance, F3 is inert in a release build, and the Vistas of America Card 6 marker sits at its base position rather than the bad fixup coordinate.


## comment 5550139903 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139903

Created: 2026-08-15T01:46:40Z; updated: 2026-08-15T01:46:40Z

Exact metadata: [source record](sources/comment-5550139903-95b7695b24b36256ffaa7479a8c5e453ad31d21c39e0382f198df6d1d76a2efc.json).

**All three parts verified present, and the build blocker is cleared.**

1. **F2 distance limit** — `DeveloperMoveMaxDistance=150` in the INI, with the guard `moved > g_collectMoveMaxDistance` and an explicit refusal message at `collectibles_map.cpp:515-523`.
2. **Vistas of America Card 6** — the bad fixup coordinate `-4497.327,-4355.641` appears nowhere in the repo any more.
3. **Dev-only gating** — `verify_dev_authoring_issue_121.py` passes.

One thing I chased down before reporting, because it looked wrong: `DeveloperMoveMaxDistance` **is** present as a string in the installed release binary, via the generated settings-menu table. That would mean a control in your menu that does nothing, since the F2 code is compiled out of release. It is not a dead control: in release `GAMEPLAYTWEAKS_DEV_MODE` is 0, so the tilde toggle is compiled out entirely and `g_runtimeDevelopmentMode` can never become true, and `settings_menu.cpp:152` skips every developer row when development mode is inactive. The row cannot appear.

**What is testable in the release build you have now:** tilde does nothing, F2 does nothing, F3 does nothing, and no Developer Tools rows appear in the in-game menu.

**What is not:** the F2 refusal beyond 150 m and the F3 placement/removal behaviour only exist in a development build. Those need a dev build installed before they can be confirmed — say the word and I will build one.

Moving to `test me` for the release-side behaviour.


## comment 5550139914 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139914

Created: 2026-08-20T10:04:36Z; updated: 2026-08-20T10:04:36Z

Exact metadata: [source record](sources/comment-5550139914-cbe0eebf83ddf290d1ebdf1a2dd8140cd648a10163d2b905d2ee7c7ad28385ad.json).

should give a notif (with the proper vanilla notif system we discovered!) if you hit the button and it doesn't detect a collectible in range. it should also give a notif if it DOES successfuly move one. oh, and if i hold the button, it should undo the last move. notif for that too.

## comment 5550139921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/214#issuecomment-5550139921

Created: 2026-08-20T11:19:22Z; updated: 2026-08-20T11:19:22Z

Exact metadata: [source record](sources/comment-5550139921-388f4907ba3a3317d2397e993395f50d2b39de3dcda7ab3ede1215ead1adfdfd.json).

Installed repair: F2 now acts on release. A tap moves the nearest eligible marker and reports success; no eligible marker also reports clearly. Holding F2 for 800 ms restores the exact prior marker and persistence-file state and reports the undo. Test all three results with tilde development mode on, then confirm F2 is inert with tilde mode off.

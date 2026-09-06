# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356292236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135

Created: 2026-08-06T02:13:21Z; updated: 2026-09-05T06:56:45Z

Exact metadata: [source record](sources/issue-5356292236-514d9eee5c66414c17ee283749ba9f077b1b1536cc03f981b88066702f6859d2.json).

     a) Look at how RDO does trains: they have trains on the map with little
        arrows showing which way they're moving. Awesome — I want that.
     b) A train marker must exist only while a real live train backs it. Retire
        stale markers after despawn, mission cleanup, streaming loss or fast
        travel, and only reacquire from an actual train, never a cached route or
        timetable. Reproduce the failure in the existing train marker mod.
		Yeah I think the train markres mod does this too, which is weird. Why? Also, RDO does this right too. Can we not copy them

## issue 5356292236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135

Created: 2026-08-06T02:13:21Z; updated: 2026-09-06T12:47:07Z

Exact metadata: [source record](sources/issue-5356292236-286075b4a4a96d5ca52af20b0f93fc97fcc9f4c2a7e51ab86effcd2773f20118.json).

Show markers only for real live trains, with their direction and distinct cargo/passenger/streetcar artwork. Remove markers when trains disappear.

**Status: Still incomplete.** The latest report says train markers are missing. Repair reliable detection and cleanup before delivering new artwork or requesting a visual test.

## issue 5356292236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135

Created: 2026-08-06T02:13:21Z; updated: 2026-09-06T13:57:02Z

Exact metadata: [source record](sources/issue-5356292236-63d77c3990053cca25fa73ae5c53840929d28a75b69a9f1425c9668e0626c653.json).

Show markers only for real live trains, with their direction and distinct cargo/passenger/streetcar artwork. Remove markers when trains disappear.

**Status: Still incomplete.** The latest report says train markers are missing. Repair reliable detection and cleanup before delivering new artwork or requesting a visual test.

## comment 5550119122 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119122

Created: 2026-08-06T05:20:15Z; updated: 2026-08-06T05:20:15Z

Exact metadata: [source record](sources/comment-5550119122-dcc1fd59d55a71cdd8b9e13c1dd36f1002a428421b3cd3236225b9c1bfda5973.json).

Built and installed in GameplayTweaks ASI `7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`. Test a real train marker follows the live locomotive with a direction arrow, then disappears on stream-out/despawn/mission cleanup/fast travel. Confirm trolley, dummy, and ghost-train exclusions.

## comment 5550119155 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119155

Created: 2026-08-06T11:52:01Z; updated: 2026-08-06T11:52:01Z

Exact metadata: [source record](sources/comment-5550119155-8e29e799bae04ca33d761cd95403b5aae663974e930a0b93f41801bd16dc69f7.json).

all train map markers are gone.

## comment 5550119169 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119169

Created: 2026-08-06T12:07:59Z; updated: 2026-08-06T12:07:59Z

Exact metadata: [source record](sources/comment-5550119169-7a2f733bb461c5a3e6a1dfda7b819867e2150b8c7704d8d6db343648232c2b33.json).

Corrected candidate installed on disk for the next full restart, SHA-256 D4189A6800AFCC5A8D4D9E62D09C7CCAEFEF16F1397B7181ED7CBB66B9591AC8. The missing-marker test invalidated the three-model locomotive allowlist; detection now uses Rockstar's train-model predicate and selects the driver-controlled locomotive rather than its carriages. Moved to 	est me; no runtime result claimed.

## comment 5550119185 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119185

Created: 2026-08-06T12:46:00Z; updated: 2026-08-06T12:46:00Z

Exact metadata: [source record](sources/comment-5550119185-a84d8e1a6409298ead06a2a1343e1f78341a544119ed61d5a4b1811093ae1539.json).

still no trains.

## comment 5550119207 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119207

Created: 2026-08-10T08:06:47Z; updated: 2026-08-10T08:06:47Z

Exact metadata: [source record](sources/comment-5550119207-d2970655d33a20dafe8cefffe459d54046b6f64136f818cc57c7bf2239a17fb7.json).

Can we get different map icons for cargo trains, passenger trains, and the St. Denis streetcar?

## comment 5550119224 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119224

Created: 2026-08-11T07:13:32Z; updated: 2026-08-11T07:13:32Z

Exact metadata: [source record](sources/comment-5550119224-d11349819f431214a750fdad9e0caf401fe2246dcd45d77c89e7b9cd408a4233.json).

Yes. We can classify a live train and give each class different art.

The Saint Denis streetcar is the simple case: Rockstar defines `trolley01x` as a train engine with `LAYOUT_TRAIN_TROLLEY`.

Passenger and cargo trains can share locomotive models, so classification must inspect the live carriages. The resolved train natives provide the carriage count and each carriage entity. Passenger models include passenger, dining, sleeper, room, and observation cars. Cargo models include boxcars, flatcars, coal cars, refrigerator cars, and cabooses. A mixed consist should use the passenger icon when it contains a passenger carriage.

Rockstar supplies one general train icon. Three distinct markers therefore need three custom icon linkages and three train styles. Each can keep Rockstar's heading arrow. The art must use the project's working complete `INVENTORY_ITEMS_MP` replacement; the old standalone dictionary produced black squares and must not return.

One correction: the current source comment says the trolley is excluded, but the code no longer excludes it. It accepts any train model with a driver. The basic live marker still needs an in-game result before the three class-specific icons can be called working.

## comment 5550119243 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/135#issuecomment-5550119243

Created: 2026-08-12T12:06:56Z; updated: 2026-08-12T12:06:56Z

Exact metadata: [source record](sources/comment-5550119243-b21e898383fab5e21e0cda495b69c21c88a4eafdaf9b29276f753853e5f27c67.json).

Correction: three train classes do not require three train styles.

Rockstar's RDO train script creates one entity blip with `BLIP_STYLE_TRAIN`, then changes its sprite separately. The existing train style already supplies the heading arrow.

Cargo, passenger, and streetcar markers therefore need three custom sprite linkages plus live-consist classification, but they can share the one train style. The earlier requirement for three separate styles was wrong.

The two earlier missing-marker tests still mean that the basic detection path needs execution diagnostics and an in-game result before class-specific markers can be called working.

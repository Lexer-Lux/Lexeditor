# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356318543 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246

Created: 2026-08-10T14:54:53Z; updated: 2026-09-05T07:02:40Z

Exact metadata: [source record](sources/issue-5356318543-19f8c7e43206b5c605f25915588588048bb448dfa919ee4f6796dfdb912b0605.json).

Still no shoulder switch with my gun holstered. So is that possible? Impossible? Hello? You are an LLM. You can talk to me. Stop ignoring me.

## issue 5356318543 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246

Created: 2026-08-10T14:54:53Z; updated: 2026-09-06T13:18:01Z

Exact metadata: [source record](sources/issue-5356318543-2b10b35c6f0270344455d4403e24e867021bd7a90e8559015e765012dbf773d1.json).

**Status: Not implemented with the resolved camera interfaces.** The tested shoulder control works in aiming context, not with a holstered weapon. A key listener or generic offset does not create the missing shoulder state. This is a technical blocker, not completed functionality.

## issue 5356318543 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246

Created: 2026-08-10T14:54:53Z; updated: 2026-09-06T13:18:01Z

Exact metadata: [source record](sources/issue-5356318543-c70c64dddcde62016a31afb136a5cc9c259ee90ecbb482ad982fa65ecfcf4959.json).

**Status: Not implemented with the resolved camera interfaces.** The tested shoulder control works in aiming context, not with a holstered weapon. A key listener or generic offset does not create the missing shoulder state. This is a technical blocker, not completed functionality.

## comment 5550148714 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148714

Created: 2026-08-10T17:01:16Z; updated: 2026-08-10T17:01:16Z

Exact metadata: [source record](sources/comment-5550148714-5148c1b8a6bbd15883405b19457e7ed87236a89225a4d4b9774110028b4a04d3.json).

The holstered shoulder-switch candidate is installed. A physical keyboard X rising edge is now an explicit fallback when Rockstar's contextual shoulder action is unavailable, while the normal remappable action remains primary. It performs exactly one camera-side flip and never draws/holsters or changes a weapon. Test X twice while holstered and armed; each press should reverse side once without centering, double-flipping, or moving the weapon state.

## comment 5550148732 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148732

Created: 2026-08-10T18:59:55Z; updated: 2026-08-10T18:59:55Z

Exact metadata: [source record](sources/comment-5550148732-fb01e164d230b0c5833fad24bc6f8f68f68426a76d576a84c0246a39d8f0ca96.json).

I can see the camera start moving for a brief moment then it goes back into its original place.

## comment 5550148744 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148744

Created: 2026-08-10T23:45:48Z; updated: 2026-08-10T23:45:48Z

Exact metadata: [source record](sources/comment-5550148744-8224c4ad710b1d8b2a810d4501cebd8742c64b3267cb0ce1fbe065c031abe7c0.json).

Installed the shoulder-switch edge correction. One physical X press can no longer fire a raw edge and then a delayed mapped edge that reverses the first swap. Test holstered and armed X presses in both directions; each press must produce one stable side change with no snapback.

## comment 5550148755 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148755

Created: 2026-08-11T01:10:40Z; updated: 2026-08-11T01:10:40Z

Exact metadata: [source record](sources/comment-5550148755-030418af300837f71ce0ec7bfa69ca8d9c40d0d9597a3c17dc47cc3d7cd7daa7.json).

No change.

## comment 5550148772 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148772

Created: 2026-08-11T01:46:01Z; updated: 2026-08-11T01:46:01Z

Exact metadata: [source record](sources/comment-5550148772-6b640826bad64b9155f60a0031493c68308ef5279037d711d7370e1ec781a270.json).

One physical X press was being counted twice: once as raw X and again as the mapped shoulder action on the next frame. The mapped edge is now ignored while X is physically held, so one press produces one side change. Test X in both holstered and armed states.

## comment 5550148784 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148784

Created: 2026-08-11T04:19:12Z; updated: 2026-08-11T04:19:12Z

Exact metadata: [source record](sources/comment-5550148784-f08bd3f9618ddb4fb819e3b931a9474ece3c242743a86d4ea56dab770c563047.json).

Also, swapping shoulders with no weapon drawn results in very abrupt camera movement. Also, the shoulder switch just doesn't seem right. The apparent distance between the PC and the imaginary vertical line splitting the monitor into 2 equal halves should be the same regardless of the shoulder. Get it? The shoulder should just mirror it along that axis. But that's not it -- with Arthur on the left, he's maybe 25% of the way to the right side of the screen. Hit X and he's like 55%, while he should be 75%. 
What does the log say?

## comment 5550148800 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148800

Created: 2026-08-11T04:22:16Z; updated: 2026-08-11T04:22:16Z

Exact metadata: [source record](sources/comment-5550148800-d03e7b7ab8a78f38ff5ed5ee88f6da0be96be3e49e3639b183eab8dc056ab0e5.json).

Also, if I hold RMB to start aiming while using X to put the PC on the right side of the screen, it just jumps to put him on the left side and hitting X while in this mode gives a one-time little horizontal jump and that's it.

## comment 5550148820 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/246#issuecomment-5550148820

Created: 2026-08-11T09:34:02Z; updated: 2026-08-11T09:34:02Z

Exact metadata: [source record](sources/comment-5550148820-db562666d4478224a15a9c607e56687a172ae09e4b811e2a7b1af2b1bd7580bc.json).

I cannot implement the requested holstered shoulder switch through the resolved Story/ScriptHook camera API. Rockstar exposes shoulder switching only in the aiming context, and the available camera offset call has no weapon-side or holstered-shoulder setter. Reading physical X only detects the request; it does not create the missing engine state. I am marking this unfeasible instead of leaving a nonfunctional key listener in test.

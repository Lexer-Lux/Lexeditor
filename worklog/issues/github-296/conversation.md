# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356333396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/296

Created: 2026-08-20T19:16:49Z; updated: 2026-09-05T07:05:29Z

Exact metadata: [source record](sources/issue-5356333396-9e0b9c29632cac08ccdaa0b6eed888fe8c4750e4a5f4066c8aaddb03d0b60ffe.json).

Enemy minimap blips must show the same facing/FOV indicator that animal blips show. This is presentation on an existing visible enemy blip, not permission to reveal untagged enemies.

Requirements:
- Identify the exact current animal blip mechanism and reuse it for tagged enemy blips.
- Preserve marked-only visibility and existing hostile-state colors.
- Update facing at a bounded justified cadence.
- Do not create a second blip or a separate HUD overlay.
- Confirm the indicator appears, rotates with the ped, and disappears with the owning blip.

## issue 5356333396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/296

Created: 2026-08-20T19:16:49Z; updated: 2026-09-06T12:57:23Z

Exact metadata: [source record](sources/issue-5356333396-98d7ea22e7e1574de5dc63f76041674a924589f8814337100ff123d6a1761563.json).

Tagged generic enemies should get the same facing/FOV presentation as tagged animals, without revealing untagged targets or duplicating law/bounty cones.

**Status: Source implementation complete, but unbuilt.** Deliver the combined marker build before asking you to compare generic enemies, lawmen and bounty hunters.

## issue 5356333396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/296

Created: 2026-08-20T19:16:49Z; updated: 2026-09-06T12:57:23Z

Exact metadata: [source record](sources/issue-5356333396-ff9a5ae7bac7a622f25e4e788721c816ef8fa269dc64738d779cff57e83ebb3f.json).

Tagged generic enemies should get the same facing/FOV presentation as tagged animals, without revealing untagged targets or duplicating law/bounty cones.

**Status: Source implementation complete, but unbuilt.** Deliver the combined marker build before asking you to compare generic enemies, lawmen and bounty hunters.

## issue 5356333396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/296

Created: 2026-08-20T19:16:49Z; updated: 2026-09-06T18:41:56Z

Exact metadata: [source record](sources/issue-5356333396-4e3e0d7df0e9b1878ea7504f67202dd9659b188e634c54b170252274c887eea4.json).

Tagged generic enemies should get the same facing/FOV presentation as tagged animals, without revealing untagged targets or duplicating law/bounty cones.

**Status: Source implementation complete, but unbuilt.** Deliver the combined marker build before asking you to compare generic enemies, lawmen and bounty hunters.

## issue 5356333396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/296

Created: 2026-08-20T19:16:49Z; updated: 2026-09-06T18:41:56Z

Exact metadata: [source record](sources/issue-5356333396-b3a12dd23945b1cda3646b149e0585d660f6834c6b0b8819488e56d748abaef7.json).

Tagged generic enemies should get the same facing/FOV presentation as tagged animals, without revealing untagged targets or duplicating law/bounty cones.

**Status: Built candidate ready for gameplay test.** Runtime PR #212 classifies law/bounty roles separately and applies the proven Recon cone modifier only to `Generic + Enemy` humans. Lawmen and bounty hunters keep Rockstar's authored cop-style cone behavior instead of receiving a duplicate custom cone. Neutral/allied humans remain cone-free.

Permanent source checks passed in run 34052368724. Complete Windows release and development builds both passed in run 34052368730.

- [ ] Tag a generic hostile human and verify a facing/FOV cone appears and rotates with the target.
- [ ] Verify an untagged hostile does not gain the Recon cone.
- [ ] Tag a neutral/allied human and verify no enemy cone appears.
- [ ] Tag/observe lawmen and bounty hunters and verify there is only the authored law-style cone, not a doubled/overlapping cone.

Candidate: runtime PR #212. No installation or gameplay acceptance is claimed yet.

## comment 5550166702 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/296#issuecomment-5550166702

Created: 2026-08-20T19:43:05Z; updated: 2026-08-20T19:43:05Z

Exact metadata: [source record](sources/comment-5550166702-ea06ce94f0f9a5d9e1ee4a7f7c68908b967cbc3359094d72708383397110c408.json).

Source implementation is complete but unbuilt. Generic tagged enemies now receive the same proved Recon facing/FOV cone used by tagged animals. Law and bounty targets keep their authored conditional cop cone, so the module does not create a duplicate cone or rotate one in script. After the next install, compare a generic enemy, a lawman, and a bounty hunter on the minimap.

# #328: Correct battle HP bars and XP bars

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/328)

## Requirements and decisions

Latest human test (September 19): match the supplied vanilla reserve HP rail.
Main-menu XP belongs below LV for active and reserve characters, not below
names. Add active-party HP below HP X/Y. Preserve the battle placement,
right-to-left fill and maximum-HP scaling requirements on the live issue.
Do not claim visual acceptance from native checks.

## Current implementation and evidence

Source 38c9dad replaces wrong save-browser and fixed Status hooks with 13 native
widget call captures. Each capture stores the native viewport and clears after
the frame. GF progress uses the native level function and its XP boundaries.
28fe408 fixes the expired dependency artifact reference in the Windows workflow.

Windows run 34700395103 passed on 2026-09-12. Native widget coordinate checks,
compiled menu capture/projection checks, renderer projection checks, and the
post-battle state/animated-total checks pass locally. Package verification and
installation passed. Installed driver SHA-256:
`6f8b3b67397a9fce8eff7f0258ba8c4fc1bcb4f9702bc31ecfc932bac84fce24`.
XP Bars remains enabled in FFNx.toml. Source package backup is hash-checked under local
Lexeditor helpers/backups/ffnx/xp-widgets-source-20260912.
Installed runtime backup: helpers/backups/ffnx/20260912-085703-176333.

## Current candidate (2026-09-19, second replacement)

The previous one-line candidate failed the human test. The replacement uses the new vanilla close-up supplied on September 19: two horizontal lines, one above the other. Pixel measurements establish their spacing and partial edge coverage. The shared gauge applies this design to HP, GF HP/MP and XP, while keeping each gauge's placement and fill direction.

The driver was rebuilt, package-checked and installed. The production drawing check covers the measured pixel profile, fill directions and three scales. Menu capture checks and linked-driver checks passed. This is prepared for human acceptance, not yet visually accepted in-game.

Acceptance test (no build needed):
- [ ] Restart FF8 through Lexeditor with the bar tweaks enabled. Compare the bars with the supplied vanilla close-up: two horizontal lines, not a thick box or a single hairline.
- [ ] In the main menu, check active/reserve XP below LV and active HP below HP X/Y. Reserve XP must match native HP height and width.
- [ ] In battle, check HP below its numbers, right-to-left fill and track length based on maximum HP. Check the GF MP bar too.
- [ ] Check character, Magic, GF and result level widgets. Report the screen and a screenshot for any mismatch.

Installed candidate: `D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/AF3DN.P`, SHA-256 `398062ac3da8c632bcb75410dd51406792c11bafa85108fe5f4913f553c68663`. The prior driver was backed up. Settings and saves were preserved. No visible game window was opened.

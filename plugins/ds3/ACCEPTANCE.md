# Dark Souls III offline acceptance

Target: Steam PC App Ver. 1.15.2 / Regulation Ver. 1.35.

Lexeditor does not install a mod loader, modify anti-cheat or online settings,
or overwrite the game installation. The candidate produced by Save is
\`<project>/Data0.bdt\`.

1. Create/select a fresh Lexeditor DS3 project; do not point it at the game folder.
2. Open Weapons, record one test weapon's current Physical Damage, make a
   distinctive reversible change, and Save.
3. Confirm \`<project>/Data0.bdt\` exists. Hash
   \`<Dark Souls III>/Game/Data0.bdt\` before and after; it must be unchanged.
4. Configure a compatible external DS3 loader separately to load only the
   project candidate. Keep this acceptance session offline and do not enter
   multiplayer.
5. Launch the game using the loader's documented offline workflow, inspect the
   edited weapon, and confirm the changed value is present.
6. Exit, stop loading the project candidate, and relaunch without it. Confirm
   the original value returns.
7. Report the game App/Regulation versions, record ID/name, old/new value,
   whether the modded value appeared, whether vanilla restored, and both
   installed-archive hashes.

Parser tests, browser screenshots, and an exported synthetic fixture do not
count as this real-game acceptance.

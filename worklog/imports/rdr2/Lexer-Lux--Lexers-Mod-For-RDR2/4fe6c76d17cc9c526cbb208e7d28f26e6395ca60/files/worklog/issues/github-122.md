# GitHub #122 — Respawn camera flies across the wilderness

## Reported

After death, the camera flew left/right/up/down across the wilderness for roughly ten seconds before settling on the player. The campsite respawn system was suspected.

## Cause

The campsite respawn window called `SET_COORDS_HEADING` every frame while waiting for collision, fade, and player-control conditions. The gameplay camera repeatedly chased those world-space corrections for up to the configured fifteen-second window.

## Implementation

- Wait for the existing post-death latch, which already requires an alive, unfaded, controllable ped.
- Resolve the validated point beside the activated campfire.
- Instantly fade out and move the ped exactly once.
- Wait for collision without issuing any further coordinate writes, then fade in over 300 ms.
- If no safe destination resolves, leave the player at Rockstar's respawn.

## Verification remaining

- Build/static verification.
- In-game death/respawn acceptance with a distant activated campsite and with no activated campsite.

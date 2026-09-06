# GitHub #167 - Ledge Grab

## Recurrence audit

- Read `fuckups.txt` before editing runtime code.
- The requested behavior is walking or sneaking off a climbable ledge into a reverse grab; a generic midair auto-grab is not equivalent.
- Do not substitute a horse-leading or unrelated scene animation.

## 2026-08-10 source diagnosis

The earlier reverse probe reused ordinary body-height forward-probe geometry, merely negating the direction. Most rays therefore remained above the newly departed ledge, and camera-relative batches could point somewhere other than opposite the player's actual travel. It also admitted running/sprinting despite the requested walk/sneak boundary. A reverse-grab probe needs its own below-root samples, movement-relative direction, latched batch identity, and walk/sneak-only gate.

The reverse batch now samples from 0.40 m below the root through torso height, points opposite observed planar travel, requires two steep-face hits, and is eligible only while neither running nor sprinting. Its transition uses shipped generic `mech_climb@base@vertical@clamber_exits` / `vault_down`; the rejected Story horse-leading scene is absent. The exact asset/detector and adjacent climbing verifiers passed. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; walk/sneak visual acceptance remains `test me`.

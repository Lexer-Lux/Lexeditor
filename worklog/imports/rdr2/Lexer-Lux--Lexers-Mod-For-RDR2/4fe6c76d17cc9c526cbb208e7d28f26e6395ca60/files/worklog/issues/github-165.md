# GitHub #165 - Jittering While Climbing

## Recurrence audit

- Read `fuckups.txt` before editing runtime code.
- Treat compile/static animation presence as insufficient; the requested result is visibly continuous traversal.
- Do not hide an internal clip transition by calling eventual movement a pass.

## 2026-08-10 source diagnosis

The vertical motion state deliberately changes from a start clip to its loop after 240 ms. The clip-change block reset `g_climbLastAnim` for that internal phase change, which forced `motionGain` back to zero and ramped it again while the player continued holding the same direction. That manufactured a brief stop in otherwise continuous climbing.

The source now treats up-start to up-loop and down-start to down-loop as phase changes within one continuous motion, preserving the earned gain. The exact #165 verifier plus #159/#160/#161/#97, prone parity, #9 and #6 all passed. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; visible continuity remains a `test me` result.

## 2026-08-10 returned test and live trace

The installed trace did capture the remaining jitter. Near a possible ledge
with no valid landing, the rejection branch wrote `g_climbMotion = Idle` while
Up was still held. The following frame selected the Up start clip again. The
trace repeatedly alternated `climb_up` and `climb_up_start_right_hand`, with
gain falling from 1 to 0. A rejected ledge now backs the anchor away without
changing the held movement state or restarting its animation.

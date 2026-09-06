# Worklog: Todo 195

## #195 — the four options, in full, 2026-08-04

Task ownership is the blocker: RDR2's native aim task points the weapon at the
reticle and is authored standing; a full-body grounded clip preempts it.
  1. Native aim task runs -> he stands. Current behaviour, rejected in play.
  2. Grounded clip owns the body -> no reticle tracking. What Dive - Crawl N' Gun
     does (one canned clip, 1000 ms wait loop, clear tasks). Rejected in play.
  3. UNTRIED, most promising: issue the grounded clip as a PARTIAL/UPPER-BODY
     anim so the native aim task keeps driving the gun underneath it. Every clip
     we issue today is full-body — prone uses flags 0x10000410 (aim/exit) and
     0x30000401 / 0x30001C01 (crawl idle/walk). RAGE supports partial-body masks.
  4. Bone-level IK aiming the arms at the reticle over a static grounded pose.
     Most control, most work.
Prove the gun still fires at the reticle before building the longarm
roll-to-back rig on top of whichever wins.


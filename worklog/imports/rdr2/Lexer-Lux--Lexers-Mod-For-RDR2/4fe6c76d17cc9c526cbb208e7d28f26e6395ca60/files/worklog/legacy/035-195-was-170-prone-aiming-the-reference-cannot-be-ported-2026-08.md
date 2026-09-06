# Worklog: 035 195 Was 170 Prone Aiming The Reference Cannot Be Ported 2026 08

## #195 (was #170) prone aiming — the reference cannot be ported, 2026-08-04

Read the actual decompilation instead of assuming. `Dive-Crawl-N-Gun.c` has
exactly two grounded-aim call sites, lines ~10225 and ~10689, and they are
identical:

    CLEAR_PED_TASKS (0xe1ef3c1216aff2cd)
    clip = "ai_combat@aim_sweeps@cowboy@grounded@base@1h" / "aim_med_0"
        or "ai_getup@aim_from_ground@cop@pistol@on_back" / "intro_0"
    TASK_PLAY_ANIM(..., flags 0x10000410, task filter 0x2000000)
    t0 = GET_GAME_TIMER (0x4f67e8eca7d3f667)
    while (GET_GAME_TIMER - t0 < 1000) scriptWait(0)
    CLEAR_PED_TASKS_IMMEDIATELY (0x176cecf6f920d707)
    ... re-enable INPUT_JUMP (0xd9d0e1c0) etc.

THE REFERENCE HAS NO CONTINUOUS PRONE AIMING. It plays one canned clip for a
fixed 1000 ms and clears. There is no yaw/pitch clip selection, no sweep
blending, no additive fire/breathe layering, and no reticle tracking anywhere in
it. The old TODO text describing a "directional blend rig" in the reference was
inferred, not read, and is wrong.

Consequence: "port the reference" cannot produce what Lexer asked for, and
re-enabling `customBackRigEnabled` / `customOneHandAimEnabled` would only
reproduce the build he already rejected in-game.

The unsolved core problem is task ownership: Rockstar's native aim task points
the weapon at the reticle and is authored standing; a full-body grounded clip
takes the skeleton from it, so the gun stops tracking. Ranked options recorded in
TODO #170. Next thing to try is issuing the grounded clip as a PARTIAL/UPPER-BODY
anim so the native aim task keeps driving the gun underneath it — every clip we
issue today is full-body (0x10000410 / 0x30000401). Prove the gun still fires at
the reticle before building the longarm roll-to-back on top.


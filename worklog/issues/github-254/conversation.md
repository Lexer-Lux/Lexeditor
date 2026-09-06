# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356320882 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254

Created: 2026-08-10T15:41:15Z; updated: 2026-09-05T07:03:10Z

Exact metadata: [source record](sources/issue-5356320882-d5cf82b5fd04d7c28c641e902d20c96b71f1d37970dbee4890f34bad5fe2500f.json).

(No body was present in this captured version.)

## issue 5356320882 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254

Created: 2026-08-10T15:41:15Z; updated: 2026-09-06T12:56:45Z

Exact metadata: [source record](sources/issue-5356320882-b780bd9013aa1de1d1704a4966c1c55857602fef71d1d71a17d6e56bcbf7f69d.json).

Screen Center Tolerance now displays a real percentage, but that alone does not implement your proposed targeting circle with rays across its area.

**Status: Partly implemented.** Establish reliable animal/plant hits, performance and the visible acquisition area. The percentage-label repair is not acceptance of the requested targeting change; binocular testing is also blocked by #357.

## comment 5550151318 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254#issuecomment-5550151318

Created: 2026-08-10T17:01:20Z; updated: 2026-08-10T17:01:20Z

Exact metadata: [source record](sources/comment-5550151318-03e554fe97c7d8ce0e764bcf9a95591bc339c35a6a7a6618540aaae33b956254.json).

The aim-tolerance repair is installed. AimToleranceScreenRadius now hot-reloads every two seconds and accepts the full normalized-screen geometric range up to 0.7071 instead of silently clamping 1 to 0.15 at startup. Test clearly different small and large values on both peds and plants; the log now records the nearest measured screen distance and whether the configured radius accepted or rejected it.

## comment 5550151336 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254#issuecomment-5550151336

Created: 2026-08-13T01:53:13Z; updated: 2026-08-13T01:53:13Z

Exact metadata: [source record](sources/comment-5550151336-331b656cbcefe2f303534db28bfbf5bdf275878fec4e2a466b93cd20310233fc.json).

still does nothing.
also i would like separate values for gun tagging and bino tagging. because the radius on gun tagging seems unlimited lol?

## comment 5550151349 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254#issuecomment-5550151349

Created: 2026-08-13T03:33:51Z; updated: 2026-08-13T03:33:51Z

Exact metadata: [source record](sources/comment-5550151349-ebebf6b628a80f0ff77e0730f40688c912af2244fa9b8ec1ea6f6435e547954e.json).

**Diagnosed. It is a mathematical no-op by construction — three stacked causes.**

**1. The shipped value makes the check impossible to fail.**

`GameplayTweaks.ini:632` is `AimToleranceScreenRadius=1`, and the previous repair raised the ceiling to `0.70710678` (`recon.cpp:626-627`). The log confirms it applies correctly:

```
[recon] aim-radius config requested=1.000000 effective=0.707107 hotReloadMs=2000
```

But screen coords are normalized 0..1, so the farthest any on-screen point can be from centre is exactly `sqrt(0.5² + 0.5²) = 0.7071` — the **corner**. The ceiling was set to precisely the value at which the feature can never reject anything, and the INI ships at that ceiling. It is read, applied and hot-reloaded correctly, and gates nothing.

**2. The aimed entity bypasses the radius entirely** — this is the "unlimited" part.

`recon.cpp:2358` calls `considerPed(aimedEntity, 0.0f)`. That forced `0.0f` skips the real screen projection, and `0.0 > radius` is false for any radius. **The entity under your crosshair always passes the gate regardless of the setting.** Its real limits are `WeaponAimMaxDistanceMeters` (50) and the LOS test. Only *secondary* nearby peds get a genuine projection. Same path in binocular mode.

Plants are clean — they compute a real `screenDistance` — but cause 1 kills them too.

**3. A stale duplicate reader races it.** `script.cpp:1366-1367` re-reads the same global and clamps it to `0.15`. That is inside `loadConfig()`, which is **not** startup-only — it runs from the settings menu and world-economy paths too, so applying any setting stomps the radius to 0.15 until recon's 2 s refresh restores it. Not the current symptom, but a live race.

**Evidence limit, stated honestly:** the aiming scan never executed in the logged 375 s session — all 22 recon heartbeats read `state=notaiming`, and there are zero `scan` lines. So causes 1 and 2 are proven by arithmetic on the code plus the confirmed `effective=0.707107` line, **not** by observed rejection counts.

**Fix required (4 parts):** lower the ceiling to something that can bind (~0.35) and ship a testable default like `0.060`; pass `-1.0f` instead of `0.0f` at `recon.cpp:2358` so the aimed entity is gated like everything else; delete the duplicate reader at `script.cpp:1366-1367`; and add an explicit max to the editor schema, which currently types this as 0..1 while code clamps to 0.7071.

Your separate gun-vs-binocular radius request is a clean follow-up — the call site already branches on `g_binocularsActive || scopeViewActive` to pick the distance limit, so a `WeaponAimToleranceScreenRadius` selects alongside it.

Not applying these yet: `recon.cpp` is being edited concurrently for Lexer-Lux/Lexeditor#102, and stacking edits would conflict.

## comment 5550151368 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254#issuecomment-5550151368

Created: 2026-08-14T00:16:54Z; updated: 2026-08-14T00:16:54Z

Exact metadata: [source record](sources/comment-5550151368-de996eb32657950f6f4f151421eb4505a9475de796ce805891c1d52b93720c54.json).

**All four parts of the diagnosis are now implemented and installed.**

1. **The ceiling made the setting impossible to bind.** Screen coords are normalized 0..1, so 0.7071 is the distance to the *corner* — the farthest anything on screen can be from centre. The ceiling was exactly that, and the INI shipped at `1`, which clamped straight to it. Ceiling is now `0.35`, and the INI ships `0.060` (6% of screen size), so the value can actually reject something.

2. **The aimed entity bypassed the gate entirely.** The call site forced a screen distance of `0.0f`, and `0.0 > radius` is false for every radius — so whatever was under your crosshair always passed, no matter what you set. It now passes `-1.0f`, the same sentinel the nearby-ped loop uses to mean "compute the real projection". Its distance and line-of-sight limits are unchanged. This was the "unlimited" half of the complaint.

3. **A duplicate reader was racing it.** A second copy in `loadConfig()` re-read the same key and clamped it to `0.15`. That function is not startup-only — the settings menu and world-economy paths call it — so applying any unrelated setting stomped your radius to 0.15 until recon's 2-second refresh restored it. Deleted; recon now owns the value outright.

4. **The editor let you set values the engine would throw away.** It typed this as 0..1 while the code clamped lower. It is now explicitly 0.001–0.35 with a 0.005 step in both the editor and the in-game menu, so what you set is what applies.

Test: aim at someone slightly off-centre. At `0.060` a target well away from the crosshair should now refuse to acquire, and raising the value toward `0.35` should widen it noticeably. Both hot-reload in about two seconds, so you can sweep it without restarting.

Worth flagging honestly: causes 1 and 2 are proven by arithmetic on the code plus the confirmed `effective=` log line, not by watching a rejection happen — the aiming scan never ran in the logged session. So this needs your eyes to confirm the gate now bites.

Your separate gun-vs-binocular radius request is still a clean follow-up; the call site already branches for the distance limit, so a second key can select alongside it. Say the word and I will add it.


## comment 5550151381 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254#issuecomment-5550151381

Created: 2026-08-20T10:17:33Z; updated: 2026-08-20T10:17:33Z

Exact metadata: [source record](sources/comment-5550151381-bc9239af3ed235372e4d6aed42f888d06f3b1e9602e40f893cc0f8aea9152a66.json).

With low values you can have a big animal right by you and not be studying it even when your crosshair is right on it. I'm assuming this is because you're checking against the animal's registration point and not its hitbox or something? Perhaps we should move on to a raycast-based version: you set the % of your screen width as a radius. It draws a circle around y our crosshair when in aiming/bino mode. It casts rays within that circle. Not just on the center and edge. Number of rays unknown. Performance implications? Returns animals/herbs hit. Studies them. Feasible?

## comment 5550151393 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/254#issuecomment-5550151393

Created: 2026-08-20T10:53:19Z; updated: 2026-08-20T10:53:19Z

Exact metadata: [source record](sources/comment-5550151393-7fecc1b6bc0f6f52bf2ffdbe01837af43f9bd94c2908d9b4bd842357af11e04d.json).

Installed: Screen Center Tolerance now accepts and displays a real percentage. The default is 5%, which is exactly the old normalized 0.05 value; the old fraction setting was removed. Test a low and high percentage while aiming or using binoculars and confirm the acquisition area narrows and widens after about two seconds.

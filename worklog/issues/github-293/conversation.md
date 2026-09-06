# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356332463 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/293

Created: 2026-08-20T10:24:01Z; updated: 2026-09-05T07:05:19Z

Exact metadata: [source record](sources/issue-5356332463-d7e483b05cb0e7ccc871052347a24960a970a60df977dffdbea124a7d80184c0.json).

<img width="1106" height="681" alt="Image" src="https://github.com/user-attachments/assets/e2420970-68cf-4a8a-82cf-88eba549fbdd" />

let me swap 2D (current) and 3D tag modes in settings. 

oh, in both modes the "tag head gap pixels" should be replaced with a "Tag Head Gap" setting, in M, that sets the distance in m it is projected above their head, in both 2D and 3D modes. In 2D mode I guess it would just find that point and place it as if...look, I'm sure you can figure out. My point is that even in 2D mode the gap should shrink realistically with distance. meters-based mode, no longer pixels!

## issue 5356332463 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/293

Created: 2026-08-20T10:24:01Z; updated: 2026-09-06T13:32:06Z

Exact metadata: [source record](sources/issue-5356332463-495fff08c1a5af05217c97ba2d3d704871fc76d72176e542cc9d38a3a0d6ed44.json).

Scale symbols, health rings and distance text together between the configured near/far sizes. Keep a world-distance head gap; 2D tag sizes stay fixed.

**Actionable — latest correction is source-only.** Defaults are 1.50 near and 0.75 far; the updated build is not installed.

[Original screenshot](https://github.com/user-attachments/assets/e2420970-68cf-4a8a-82cf-88eba549fbdd).

## comment 5550165765 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/293#issuecomment-5550165765

Created: 2026-08-20T11:19:35Z; updated: 2026-08-20T11:19:35Z

Exact metadata: [source record](sources/comment-5550165765-3cc9427f2617d6f67ea4b12e8df81d2582d88b5dfad08357b04804892e6bfed5.json).

Installed implementation: Recon now has Tag Display Mode choices 2D and 3D plus Tag Head Gap in metres. 2D keeps a fixed screen size; 3D projects a 0.30 m physical size and metre gap with perspective. Compare near and far human, animal, horse, and plant tags in both modes, including through scenery and after changing the settings live.

## comment 5550165775 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/293#issuecomment-5550165775

Created: 2026-08-20T11:46:09Z; updated: 2026-08-20T11:46:09Z

Exact metadata: [source record](sources/comment-5550165775-36e25fca25d334dde6ab010cb21aee8cb5c65afc505bd6364e66de12e785c1e9.json).

The returned test exposed two concrete defects. Raw world projection produced a 65.7-times size swing in the live trace, while the distance label stayed fixed at size 18. The prepared repair adds 3D Minimum Size Multiplier and 3D Maximum Size Multiplier, defaulting to 0.75 and 1.50. The complete tag, distance text, and text gap now share one linear multiplier: maximum at zero distance and minimum exactly at Tag Fadeout End. 2D remains fixed-size. The current running session still has the prior build, so this issue correctly remains actionable until the exit installer lands the repair.

## comment 5550165792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/293#issuecomment-5550165792

Created: 2026-08-20T14:08:01Z; updated: 2026-08-20T14:08:01Z

Exact metadata: [source record](sources/comment-5550165792-57a6029259b950b8f7048806a9d82ed127801f1e927a58a7bca5f4e86d359e94.json).

The requested bounded 3D scaling is now in source. 3D starts at the configured maximum size multiplier nearby and interpolates linearly to the configured minimum exactly at Tag Fadeout End. The symbol, rings, health layers, distance text, font size, and text gap all use the same multiplier. Defaults are 1.50 near and 0.75 far; both are editable from 0.10 to 4.00. 2D remains fixed-size. The focused contract rejects seven regressions and the shared settings checks pass. This has not been built or installed, so Lexer-Lux/Lexeditor#293 stays actionable.

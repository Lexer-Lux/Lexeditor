# #293: Scale 3D tags consistently with distance

[Full request and discussion archive](github-293/conversation.md)

## Requirements and decisions

2D tags keep fixed screen size. 3D tags scale the complete presentation with distance. The head gap is authored in world metres in both modes. Glyph/symbol, health rings, distance text and text spacing scale together.

## 2026-09-06 — clean follow-up runtime candidate

The prior “source-only” status was stale: current runtime `master` still used a fixed pixel head gap and fixed text size. Runtime PR [Lexer-Lux/Lexers-Mod-For-RDR2#212](https://github.com/Lexer-Lux/Lexers-Mod-For-RDR2/pull/212) now provides `TagDisplayMode` (0 fixed 2D, 1 distance-scaled 3D), `TagHeadGapMeters`, and bounded 3D minimum/maximum multipliers. Defaults are 1.50 nearby and 0.75 at `MaximumTagDisplayDistanceMeters`. One shared linear multiplier is applied to marker radius/glyph, health rings, distance-text size and distance-text spacing; 2D returns a fixed 1.0 scale. The world-metre head gap is projected to screen space instead of remaining a constant pixel gap.

Permanent `verify_recon_scaling_decay.py` guards the mode, world-space gap, shared multiplier and defaults. Source CI run 34050295438 passed. Both release and development Windows variants built and packaged successfully in run 34050295402.

## Acceptance boundary

No game installation or visual acceptance is claimed. Compare near/far tagged targets in 2D and 3D. 2D should remain fixed-size; 3D should shrink the whole tag proportionately from 1.50 toward 0.75; the world-space head gap should appear smaller with distance. Preserve the user's existing INI when installing the candidate.

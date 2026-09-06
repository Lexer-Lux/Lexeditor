# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356482365 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/303

Created: 2026-08-30T22:25:53Z; updated: 2026-09-05T07:39:15Z

Exact metadata: [source record](sources/issue-5356482365-ea72c07d4be5d9c57dab3644339bd2fe8df8f4a7b9cd95f8386d749d219d1127.json).

# Goal

Make FF8 render at the active display refresh rate without making the game simulation, battle timing, input windows, animations, or effects run faster. The main player-visible target is smooth battle rendering instead of the original 15 FPS presentation.

# Preliminary result

This is plausible, but it is not a normal Hext patch or a larger FPS-limit value.

FFNx already replaces FF8's clock and frame limiter. Its current FF8 modes preserve 15 FPS battles, raise only battles to 30 FPS, or run supported modes at 60 FPS. The current implementation still advances the game loop once for each permitted frame. It does not provide the broad simulation/render separation that this request needs. The current configuration also clamps the FF8 limiter to its 60 FPS enum value.

FF8 battle data confirms direct frame coupling. Status timers are consumed per idle battle frame at about 15 FPS, and other battle counters use battle ticks. Raising the loop rate alone can therefore change gameplay and animation speed.

# Likely implementation path

Use FFNx-level C++ hooks, not only generated Hext:

1. Keep game simulation on fixed logical ticks for each driver mode.
2. Accumulate real elapsed time with FFNx's existing high-resolution clock.
3. Render at the selected display refresh rate.
4. Interpolate model, camera, and effect presentation between completed simulation states.
5. Never repeat gameplay side effects during interpolation-only frames.
6. Audit battle ATB and status timers, animation events, input windows, cameras, effects, field scripts, world-map movement, menus, card game, minigames, fades, movies, and audio synchronization.

The safest first milestone is battle-only: retain the original 15 Hz battle simulation, render at 60 FPS first, and interpolate battle presentation. After that works, test arbitrary refresh rates and other game modes.

# Scope now

Research only. Do not implement this issue until Lexer chooses a first milestone.

# Decision needed

Choose one initial target:

- 60 FPS battle presentation with original 15 Hz battle logic.
- Display-refresh battle presentation with original 15 Hz battle logic.
- Full-game arbitrary-refresh rendering and fixed-step simulation.

# Primary references

- FFNx `src/ff8_opengl.cpp`, current frame limiter and high-resolution clock replacement.
- FFNx `src/cfg.cpp`, current limiter range.
- FFNx `misc/FFNx.toml`, documented FF8 FPS modes and risk warning.
- Lexeditor `games/ff8/schema/kernel_section_fields.json`, confirmed battle-frame and battle-tick timer behavior.
- FFNx issue 347, an FF7 60 FPS defect inventory used only as analogous evidence for the likely audit size.

# Acceptance boundary for later work

Source, build, and FPS-counter results will not prove this feature. Acceptance needs timed and recorded checks of battle duration, ATB, status duration, input windows, animation events, cameras, effects, field scripts, menus, card game, movies, and audio at several refresh rates.


## issue 5356482365 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/303

Created: 2026-08-30T22:25:53Z; updated: 2026-09-06T12:59:22Z

Exact metadata: [source record](sources/issue-5356482365-b9cf4602375e10be5ac419324e8bbedafe0b2ba481943c743ebd9a9fb97455f6.json).

Make rendering smoother without speeding up battle logic, animations, timers or input. This needs more than raising an FPS limit.

**Status: Research only; initial scope needs your decision.**

- [ ] Choose one first milestone: 60 FPS battles with original 15 Hz logic; display-refresh battles with original logic; or full-game arbitrary-refresh rendering with fixed-step simulation. No implementation is claimed yet.

## issue 5356482365 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/303

Created: 2026-08-30T22:25:53Z; updated: 2026-09-06T12:59:22Z

Exact metadata: [source record](sources/issue-5356482365-c59dd0df97415c9dcd3a9f1145544825e0ebcae8c80e09c9641dabd62a2409f5.json).

Make rendering smoother without speeding up battle logic, animations, timers or input. This needs more than raising an FPS limit.

**Status: Research only; initial scope needs your decision.**

- [ ] Choose one first milestone: 60 FPS battles with original 15 Hz logic; display-refresh battles with original logic; or full-game arbitrary-refresh rendering with fixed-step simulation. No implementation is claimed yet.

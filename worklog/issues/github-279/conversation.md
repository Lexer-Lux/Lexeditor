# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356328089 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/279

Created: 2026-08-12T13:35:53Z; updated: 2026-09-05T07:04:29Z

Exact metadata: [source record](sources/issue-5356328089-23d555e37268c4a38fbac2fc0ceada22d2c39e0a7a97f7f99d34cfddd40fc4b2.json).

Child of Lexer-Lux/Lexeditor#236.

Requested behavior:
- Set the player's base movement speed in metres per second.
- Set crouched movement speed as a multiplier of that base speed.
- Set sprint speed as a multiplier of that base speed.

The resolved Story Mode movement-rate native is only a relative per-gait scalar in the documented 0.0-1.15 range. It cannot set absolute metres per second or make crouch and sprint exact multiples of one common world-speed value. The prior relative-scalar implementation was removed from Lexer-Lux/Lexeditor#236 at Lexer's request. No sanctioned absolute-speed mechanism was found; velocity, coordinate, or animation-graph fights are rejected because they already caused visible movement failures.

This is recorded as unfeasible with the currently resolved ScriptHook surface.

## issue 5356328089 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/279

Created: 2026-08-12T13:35:53Z; updated: 2026-09-06T13:18:38Z

Exact metadata: [source record](sources/issue-5356328089-aca3491aabc8b35c3e108224c5c59791cf8ffc6d307a8ee575526bfb6ae65ddf.json).

**Status: Not implemented with the tested movement control.** It supplies a limited relative gait multiplier, not an absolute metres-per-second speed or exact crouch/sprint multiples. Forced velocity/position workarounds were rejected after visible failures; the nonfunctional substitute was removed.

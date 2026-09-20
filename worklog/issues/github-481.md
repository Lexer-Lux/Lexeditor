# GitHub #481 — Better HP Colors

State: in progress; native implementation and candidate checks are being wired.
Scope: FF8 only.

## Requirements / evidence

- [x] True smooth RGB is technically supported: current and pinned FFNx pass
  8-bit vertex colour into textured 2D rendering; no palette-step substitute.
- [x] Anchors are white 100%, yellow 50%, orange 25%, red 0%, piecewise linear.
- [x] KO is excluded from live tinting; full HP is left native white.
- [x] Native non-white/yellow or non-white vertex presentation has precedence.
- [x] Unsupported layout fails closed behind FF8 US plus the already-verified
  battle and seven shared-character-widget call identities.
- [x] Disabled candidate selects FFNx's original `common_draw_paletted2D`.
- [ ] Lexeditor tweak persistence/UI and disable transaction checks.
- [ ] Windows derivative build + isolated artifact evidence on this branch.
- [ ] Actual FF8 battle/menu visual acceptance (cannot be proven by CI).

## Handoff

The candidate workflow must package `AF3DN.P`, `FFNx.toml.sample`, provenance,
and `ISSUE481-ACCEPTANCE.txt`. Test only an isolated copy of the supported
Steam English executable (SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`).
Do not treat source/unit/build success as live colour acceptance.

# Worklog: Github 92

## GitHub #92 GameplayTweaks source split — 2026-08-05

Mechanically split the current dirty `GameplayTweaks/script.cpp` into six topic
modules without changing the extracted implementation bytes or reordering any
feature code. The central file retained native wrappers, shared state/config,
and `ScriptMain`; module files remained in one translation unit through ordered
includes so existing internal linkage and frame order did not change.

Before the split, `script.cpp` was 9,481 lines and built successfully. After the
split it was 2,247 lines, the concatenated module bodies SHA-256-matched the
entire extracted middle of the pre-refactor source, and the normal project build
succeeded with only the same two pre-existing C4838 warnings. Runtime smoke
testing was still required after installation.

The modular build produced SHA-256
`69E55056160CB6D9C144097F7A502CBCDE56EC1E7A30B2E425BAAFD021C86085` and was
copied to the closed game root with a matching installed hash. The existing
prone/climb parity script was taught to expand the ordered module includes. It
then reported the same non-zeroing prone-velocity invariant failure against both
the untouched pre-refactor backup and the modular source; that stale/pre-existing
prone result was not rewritten during an architecture-only change.

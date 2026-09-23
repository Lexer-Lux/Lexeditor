# #226: Remove built-in weight and mounted core-drain modifiers

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/226)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 writer-boundary research

Live issue and existing history were read. Requirement remains removal of the built-in weight and mounted core-drain terms, not a change to unrelated rates. No runtime edit was made.

Current 1491.50 `short_update.ysc.c` exposes exact forecast math: func_2976 reads weight attribute13, returns +0.15 for perfect weight, -0.25 for either extreme and zero otherwise. Func_3740 returns +0.25 when mounted. Funcs2880/2881/2882 include both terms in the core forecast along with special-edition, illness and independent perk terms. The equivalent pause_menu funcs70/71 match.

Crucial boundary: short_update func1632 discards those three return values. Their side effects are funcs2876/2877 DataBinding writes for time/rate labels. Changing these routines alone would change the screen, not establish real drain removal. Global fields49/50/51 also feed the formulas, but many item scripts add trinket/outfit benefits there; zeroing or compensating these shared persisted fields is not a safe isolated removal.

`tools/audit_rdr2_core_modifiers.py` checks the source evidence and reports its limit. Existing CoreClock in script.cpp replaces ordinary one-point changes, but it does not prove removal of these engine terms and must not be presented as this request's implementation.

Next: identify the actual engine core decrement function and its two specific term inputs from a matching game binary or established hook source. Then prove exact ownership and cadence before mutation. A script forecast patch or undocumented native name is insufficient. Keep actionable; no prepared human test exists yet.

## 2026-09-22 misc-fixes evidence
Re-ran tools/audit_rdr2_core_modifiers.py today: UI forecast values confirmed (+0.15 perfect weight, -0.25 extreme, +0.25 mounted) but discarded as unproved core writers; removal stays unimplemented. The recorded next step stands: identify the engine decrement function and its two term inputs from a matching binary. No code written. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (engine research/agent-side
candidate still owed), so flipping to waiting would be a fake checklist.
Left actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. No verified field or safe hook
removes the built-in weight and mounted core-drain modifiers yet, and
changing unrelated core rates would not meet the request.
tools/audit_rdr2_core_modifiers.py still records the evidence limit.
Exact needs: identify the engine core-decrement function and its two term
inputs from a matching game binary, then prove ownership and cadence.
No code written; recording the needs here instead of inventing a hook.

## 2026-09-23 agent slice (per-game-rdr2): boundary contract

games/rdr2/core_modifiers.py pins the evidenced forecast math as data
(+0.15 perfect weight, -0.25 extremes, +0.25 mounted) plus
validate_removal_proposal(), which requires the named engine decrement
routine, rejects forecast-only and shared-field targets and unrelated
rate changes, and requires ownership of unproven ownership/cadence.
Covered by tests/test_rdr2_core_modifiers.py (8 hermetic tests). No
gameplay claim: the engine routine identity still needs a matching
binary.

## 2026-09-23 agent slice (impl/rdr2-wave2): verified, no new code

Re-ran tests/test_rdr2_core_modifiers.py: 8 green. No new agent-side slice was owed beyond the existing contract; the engine decrement function and the game session are still owed.

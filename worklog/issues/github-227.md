# #227: Replace kill-based Dead Eye gains with core regeneration

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/227)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 suppression-path research

Requirements recovered from the live issue, retained #227 conversation, legacy
047 native findings, and central runtime-engine-limits. The requested result is
replacement of kill/headshot refill, not additional core regeneration. No runtime
code, game data, or player save was changed.

Read the existing Dead Eye consumption/exhaustion verifiers and recurrence notes
before reading runtime code. Progression attribute points must never stand in for
current core fill. Current script.cpp has consumption and reserve handling, but no
complete kill-gain replacement. The old additive design is not accepted.

New executable research tool: tools/research_rdr2_deadeye_gains.py. It scans local
script callers and reports bounded source references, without copying game scripts.
Run with --output out/rdr2-deadeye-research.json. Current result:1639 scripts,
142 general multiplier setter calls,71 getter calls,519 restore-by-amount calls,
one outer-ring restore call,zero calls to unknown0x4D1699543B1C023C, and6 calls to
unknown0xFA437FA0738C370C. The output explicitly says research-only.

Concrete source findings:
- bathing.c11329-11348 and matching consumable helpers save the special-ability
  multiplier, temporarily set1 for an explicit restore/drain, then restore it.
  Therefore zeroing0x5A498FCA232F71E1 globally is not yet a proven kill-only switch.
  It can affect other restoration paths; zero may also have sentinel behavior.
- short_update.c47884 helperfunc_1500 restores iParam0*14 points. Its101096
  caller handles consumable effect records, not kills. Deleting or intercepting
  this helper would damage consumable behavior.
- XP_DEADEYE_KILL atshort_update.c70426 maps an XP category. It does not identify
  a current outer-meter refill write and must not be used to alter progression.
- All6 unknown0xFA437FA0738C370C calls are in hunting1.c, in tracking/tutorial
  states adjacent to Eagle Eye/infinite-vision controls. They supply no evidence
  of a selective kill-refill suppressor.0x4D1699543B1C023C has no script caller.
- Current public native metadata was checked at
  https://raw.githubusercontent.com/alloc8or/rdr3-nativedb-data/master/natives.json .
  Its general multiplier name does not establish selective kill behavior.

Next exact investigation:
1. Resolve the engine routine behind the verified multiplier/restore hashes for
   the installed executable build. Trace automatic kill/headshot callers versus
   script/consumable callers before selecting a hook or tunable. Do not substitute
   an unknown hash or an unverified per-frame negative refill correction.
2. If the general multiplier is the engine kill-gain factor, prepare a disposable
   causal comparison at baseline1 and candidate0, including body kill, headshot,
   consumable, mission refill, active Dead Eye drain, and Eagle Eye. Require meter
   before/after and restoration of the previous multiplier. No such comparison
   has run, so no gameplay candidate is ready.
3. Only after selective suppression is shown, integrate core-scaled regeneration
   with the existing consumption/reserve state. Preserve item/mission restoration
   and permanent progression. Core-empty must yield no regeneration.

The issue remains actionable. The limitation is current evidence, not a claim that
replacement is impossible. No build, install, native window, or game launch ran.

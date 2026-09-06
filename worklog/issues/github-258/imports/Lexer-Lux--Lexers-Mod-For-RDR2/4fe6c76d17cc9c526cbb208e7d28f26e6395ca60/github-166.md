# GitHub #166 - Mantling Weirdness

## Recurrence audit

- Read `fuckups.txt` before editing runtime code.
- No delayed coordinate snap, fabricated acceptance, or timeout may be reported as a visually accepted mantle.
- Preserve the custom climbing task until Rockstar visibly owns traversal.

## 2026-08-10 source diagnosis

The top-out transition cleared the authored climbing animation, issued `TASK_CLIMB`, and released coordinate ownership when the script task merely reported status 1. Status 1 proves task-manager acceptance, not visible climbing/vaulting. This allowed the low wall anchor pose to disappear before Rockstar exposed a traversal state, producing the reported slide and later reposition.

The transition now stops only the owned traversal clip, never clears the complete task tree, and keeps the lip anchor until `IS_PED_CLIMBING` or `IS_PED_VAULTING` proves visible Rockstar ownership. A queued task is no longer acceptance, and no target-coordinate snap exists. The exact and adjacent climbing verifiers passed. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; the visible mantle remains `test me`.

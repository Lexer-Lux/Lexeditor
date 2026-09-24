# #87: Add the Journal and next-objective menu

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/87)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes finding
No journal or quest-state code exists anywhere in the FF8 plugin (searched). The Journal needs quest-state mapping research with the game first, plus editable progression rules compatible with #88. No code written. Issue stays actionable.

## 2026-09-22 misc-fixes research leads (unverified, record sources in Credits if used)
Public research path, no local saves exist (no Square Enix savedata found):
- Main Story quest progress is a word variable (PSHM_W 256), at save offset
  0xD10 in uncompressed PC saves; see ff7-mods/ff7-flat-wiki docs/FF8/Variables.md
  and ampage87/ffviii-accessibility-mod research notes.
- Save format: [u32 compressedSize][LZSS stream] to an 8192-byte PSX block;
  see hobbitdur/ff8moddingwiki FF8/TechnicalReference/DecompStudy/SaveSystem.md.
- Survey the Hyne save editor (qhimm forums) before writing a new parser.
Next agent work: map side-quest flags against real saves (request a Lexer
save set spanning story points if none can be generated headlessly), then
design the Journal data model. Record provenance in Credits as used.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.

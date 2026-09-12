# #139: Repair the empty pause menu before removing entries

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/139)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #39 worklog](github-139/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-39.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 current delivery audit

Latest live request removes Online and Social Club only; all other entries stay.
The older imported request retained Social Club and is superseded by this decision.
The corrected RBF0 file is already installed and enabled in LML. Source and installed
SHA-256 both equal 6E34959F7F770DCDE5D29ECFFE213771EDD0925CA854440B57E522716C3D1873.
The installed manifest targets exactly update:/x64/data/ui/screens/0xA900038B.ymt.
The live issue body saying delivery is pending is stale; no new installation was needed.

Extended verify_pause_buttons_issue_39.py to compare the full parsed tree against
vanilla with only the two requested nodes removed. The prior check covered item
contents and order but could accept a changed outer root. The new root-change mutant
is rejected; existing XML, restored-item and missing-item mutants remain rejected.
The production file passes, with ten retained entries. Available enabled manifests
have no second direct file or screen-directory replacement; six enabled entries have
missing install.xml files, so this is not a claim about absent package content.

No game files changed and no game was launched. Remaining acceptance: open Story
Pause, confirm all ten retained entries appear and navigate; Online and Social Club
are absent; Back resumes play; reopen Pause and check again. Duration #151 remains
active; do not change its setup for this check.

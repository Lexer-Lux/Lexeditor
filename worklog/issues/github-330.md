# #330: Research analog battle-camera controls

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/330)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## September 19 replacement

September 19 human test failed: battle pitch allowed underground movement and almost no upward movement. A replacement is installed: SHA-256 `398062ac3da8c632bcb75410dd51406792c11bafa85108fe5f4913f553c68663` at `D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/AF3DN.P`.

The repair converts FF8 battle Y (positive down) into elevation before applying the floor/upper limits, then converts it back. Compiled tests cover both extremes, native pose handoff, no drift, proportional control and radius; full build and package checks passed. No visible game test was run by the agent.

Retest: restart FF8, enter a battle with Modern Controls enabled, and move the right stick upward/downward. The camera must have useful upward travel and must stop at the floor. Release the stick and trigger an attack to check no drift and normal scripted-camera ownership. Report the battle/location and a screenshot for any failure.

# #168: Rebuild owned-gear sparkle suppression safely

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/168)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #69 worklog](github-168/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-69.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 identity-capture repair

Live issue/full comments and prior crash handoff were read, along with the existing sparkle-crash and compendium-probe verifiers. Both former pickup and object pool scanners reproduced delayed failures before a matched suppression log; no individual native was proven causal. The old one-item-per-model CSV is also insufficient identity: current source `MyOverhaul/pickups.meta` maps both ordinary and exotic double-barrel pickups to `w_shotgun_doublebarrel01`, while the CSV records only the exotic item. A model match cannot prove exact ownership.

The existing opt-in F10 CompendiumGlintProbe now adds one asynchronous final-camera reticle ray, because player target/free-aim queries alone can miss ground hats and weapons. It records raw hit status, coordinates and entity, then passes a still-live result through the existing model/discoverable-identity log. It makes no ownership inference and no effect/progress mutation. Only one handle can be pending; expiration after 1.5 seconds cancels publication but retains and polls the handle to prevent leaks. Menu blocking, player changes and deleted targets discard stale results. Held F10 across a menu does not create another capture. Defaults stay off; no new control or dispatcher is needed.

Recurrence audit: no pickup/object pool is restored and no former sparkle setter is enabled. Execution evidence is `tools/verify_rdr2_gear_identity_probe.py`: production passes and five mutants fail (duplicate pending probes, expired/menu/player-stale results, deleted object query). Existing owned-gear crash guard and compendium probe checks pass. The actual captured entity/native identity fields still require gameplay observation. Root owns build; no game or #151 experiment files were changed.

After the experiment is restored and this candidate is delivered, enable the existing CompendiumGlintProbe, aim at one ground collectible hat or weapon, and tap F10. The glint log should contain a `ray capture` result and the exact hit entity/model/identity fields. This is a prepared identification slice, not suppression acceptance. Exact weapon-variant identity, hat ownership and safe glow suppression remain actionable.

Focus review follow-up: the caller's blocked flag excluded foreground ownership. The capture now uses the existing `EditorNumpadInput::editorWindowFocused()` predicate. F10 in another application cannot start a capture; focus loss cancels publication while the pending handle is still polled. Held F10 on return does not create an edge. The executable verifier now rejects six regressions, including off-app capture. The added block uses the module's tab indentation. Legacy compendium checks still pass.

Root built and hash-verified the reviewed diagnostic, SHA-256 `5028C5B91751FF7B941CCEC9664F481679811A4EFF42297825AC266B1A335B8E`. Candidate and matching release manifest are held in `out/rdr2-after-duration`. No installation occurred while #151 is active; full suppression remains unimplemented and actionable.

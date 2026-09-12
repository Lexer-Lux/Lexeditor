# #267: Make shoulder switching reach both sides evenly

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/267)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #175 worklog](github-267/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-175.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 interrupted-switch repair

Live #267 still requires comparable settled left/right offsets and a smooth transition. Crossing the centre is insufficient. #108 and #220 were also read; continuous vehicle height and vehicle delivery remain separate work.

The camera branch selected every new bias target from the rendered camera side. During a transition that side can still be the old side, so a second press repeated the first target. The new branch reverses the pending target while a switch readback is pending, then uses measured side at rest. Leaving aim clears stale pending readback. Rockstar still owns the mapped action; no input suppression, new native, weapon or task change was added.

Evidence: `tools/verify_rdr2_camera_switch.py` compiles and executes the actual production target branch with controlled input and rendered positions. Rapid reversal, unchanged magnitude and aim exit pass. Two mutations (lost second press and stale readback) fail. Existing runtime verifiers 154, 175 and 128 pass. Temporary compiler output is removed on exit. Camera source remains LF with byte-preserving edits.

This is a source candidate only. It does not prove the engine maps the two targets to equal settled positions. Full build/install belongs to integration. Keep actionable until the symmetry requirement and remaining delivery are resolved; do not repeat a human test on this partial repair alone.

Further evidence search: the installed game-root GameplayTweaks.log has one physical-X event in STANDING (aimHeld=0), with lateral 0.441963 to 0.442228 and engine-ignored-press. It contains no current aiming shoulder pair. The existing camera-right projection is consistent with the runtime yaw convention. Local native metadata defines horizontal offset and distance but gives no inverse mapping from measured lateral position to offset. A new symmetry correction curve cannot be justified from these inputs. The prior asymmetric aim measurements remain historical evidence, not proof of the current repaired branch's settled result. No guessed correction gain or native was added.

Integration delivery: installed in combined ASI12C8E7078225280EF18E365FFB49EE6FBE92E3CB023B44F335D370308168DA81, hash-verified with game root. Rapid reversal is a repaired slice; settled left/right equality is still not confirmed.

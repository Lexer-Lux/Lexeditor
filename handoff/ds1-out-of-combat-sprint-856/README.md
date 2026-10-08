# DS1 out-of-combat sprint handoff

This directory puts the actual issue #856 sprint mod work into PR #918 so a successor can take it over without relying on a conversation attachment.

- issue: #856, "Infinite Out-of-Combat Sprint Stamina"
- PR: #918
- branch: `codex/ds1-out-of-combat-sprint-856`
- package candidate: `out-of-combat-sprint` v0.2.0-candidate
- exact prior package SHA-256: `24271ca1ef129990340cd66e90f751efa2b2741a46bfc839dd60bd5be2dc07bb`
- supported executable: DarkSoulsRemastered.exe, 50,286,344 bytes, SHA-256 `a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`

## What is here

`package/` is the unpacked source/test package that was previously delivered outside GitHub. It is intentionally under `handoff/` rather than `plugins/ds1/`: the repository's AGENTS.md says tweak payloads belong in the mod library, not in the editor source tree. This handoff exists specifically because the task owner requested that the completed work be present in the PR for the next agent.

The implementation redirects only the native sprint stamina charge. Outside combat, when no living AI character is in its native battle state targeting the local player, that charge does not consume stamina. Combat and uncertain/co-op states retain normal sprint costs. Attacks, rolls, blocking, stamina recovery and the cap are untouched.

## Verification already performed

- package tests: 16 passed, 0 skipped
- native harness: 156 calls, using inspected native getters and a stamina-writer spy
- generic branch-boundary regression: 4 passed, 0 skipped
- single-mod projection: 51,676,160 bytes, SHA-256 `41ebd8afaca01bc76b5f33c5f391f3edde82ab8d67347dee6071bff8eefdd8cf`
- no retail game launch or gameplay acceptance has been established

## Important handoff point

The package is not being declared retail-ready. Windows startup, actual traversal/aggro/de-aggro, bosses, death/reload, dense-area performance, entity lifetime/thread safety, save safety, and multiplayer/anti-cheat safety remain unverified.

Do not merge this PR until the owner explicitly asks for that.

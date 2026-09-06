# FF7 completion pass — 2026-09-06

User instruction: "Okay then do every issue", continuing the recovered PR #359. Scope: every remaining FF7 implementation item in #79 and the FF7 portions of #73/#72. This session does not replace another agent's game work or erase canonical issue archives.

Implemented the missing scene/formation/character AI editors, growth coefficients and bonus tables, inline/default names, executable-only Cait Sith/Vincent starting records, field encounter tables and world/Yuffie/Chocobo encounter tables. These are connected UI/HTTP/project-save paths, not status cards or disconnected parsers. Active guide: `codex/ff7-data.md`.

Real shared-UI testing exposed and fixed blank textarea initialization and overflowing list text missed by component doubles. Added grouped subtabs, single-emission move/confirm sounds, mute interruption/suppression tests, strict snapshot payloads in both plugin smoke checks, complete process identities, and central project path/backup/replacement guards. Added a read-only-installed/disposable-project diagnostic and Windows launcher at `tools/FF7-checks.cmd`.

Local tests passed: 19 kernel/HTTP, 15 extended, 23 completion; seven existing browser scenarios plus three new real-shared-UI scenarios. New controls save/reopen through the actual handler. Both edition identities render at 900x620, 1200x800 and 1600x1000. Tests use synthetic files; OS-host and audio playback are doubles. No native game session or listening acceptance is asserted.

Repository delivery and final CI/merge results belong in the PR record. Keep publication separate from proof: fixed AI pools and scene blocks still reject overflow; arbitrary unsupported executables, general field scripting, world geometry, automatic deployment and gameplay correctness are not claimed. Human/installed-game acceptance is distinct from missing code. Mixed-game #73 and listening-oriented #72 cannot be globally closed merely by this FF7 pass.

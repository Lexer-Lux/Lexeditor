# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5311779665 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/77

Created: 2026-09-01T12:23:35Z; updated: 2026-09-04T12:25:08Z

Exact metadata: [source record](sources/issue-5311779665-07cf390b5beef95cc68199f1c4b6661bc9cc6293aed517e7942e80d47b12a625.json).

Manage Memoria for the FF9 plugin without forcing its launcher into the normal game-start path.

Requirements:

- Detect whether Memoria is installed and report its version.
- Download and verify the pinned Memoria release when installation is requested.
- Refuse installation while FF9 is running, use the publisher's patcher for installation, verify the result, and support safe recovery.
- Show Memoria state in the FF9 plugin.
- The normal Lexeditor Play control launches FF9 directly. It must never open the Memoria launcher first.
- Treat the Memoria launcher as a settings utility only. It may open only after an explicit settings action.
- Lexeditor's Tweaks view remains the primary typed editor for Memoria.ini under #73.
- Do not overwrite unknown Memoria settings or user configuration.
- Do not let the Memoria launcher reassert itself as the default Play target after an update.

Acceptance:

- Play starts FF9 without showing the Memoria launcher.
- An explicit settings action can open the Memoria launcher when installed.
- A clean FF9 installation can install the pinned Memoria runtime.
- Existing Memoria installs are detected without modification.
- Installation and update failures leave the game recoverable.
- The installed version is visible.

## issue 5311779665 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/77

Created: 2026-09-01T12:23:35Z; updated: 2026-09-06T12:45:38Z

Exact metadata: [source record](sources/issue-5311779665-e3d97d37dd4040e8981891fe5db6b830d58cf2aabc3d10d4094eb43a0d2323ff.json).

The detection/download/install backend exists, but installation has not been exercised and the install/update controls and update-frequency behavior remain unfinished.

Finish those paths without losing user settings. Follow your later decision in #73: use Memoria's own launcher for FF9 settings rather than recreating its interface. No installation test is ready for you yet.

## comment 5502628962 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/77#issuecomment-5502628962

Created: 2026-09-02T00:45:48Z; updated: 2026-09-02T00:45:48Z

Exact metadata: [source record](sources/comment-5502628962-efca1f8f9ce8816b1a58d3a3a215de60cfce5d153d71a7ca7499ebb21b29719b.json).

Manager landed in `games/ff9/memoria_manager.py`, mirroring `games/ff8/ffnx_manager.py`.

- `status(game_root)` detects an install offline: `Memoria.ini` at the game root plus `Memoria*.dll` under `x64/FF9_Data/Managed`, and reads the installed version out of `Memoria.ini`.
- `available()` / `release()` read the latest GitHub release. Memoria publishes a single asset, `Memoria.Patcher.exe`, with a SHA-256 digest; a release without a valid digest is refused rather than installed.
- `stage()` downloads to the shared helper cache and verifies the digest before anything is executed, re-downloading if a cached copy does not match.
- `install()` refuses if `FF9.exe` is running (the patcher rewrites managed assemblies), runs the publisher's own patcher against the game root, then re-checks detection and only records state if the install actually appears.

Server routes: `GET /api/runtime`, `GET /api/runtime/available`, `POST /api/runtime/install`. Dashboard payload now carries `runtime`.

Verified against the live install: detection correctly reports not-installed, and the release lookup resolves v2025.07.04. The install itself has not been run.

Remaining for this issue: the dashboard install/update control in `games/ff9/editor.html`, and honouring the shared update-check frequency.

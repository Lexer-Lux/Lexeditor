# WSE2 / helper panel integration — 2026-09-06

PR #366 is merged as `a49464326ec269d02e957e8cf6c2a89a546ac8ac`.
This is an additive session record; it does not replace #81's canonical handoff or
request archive. Full WSE2 handoff: [#365](../../github-365.md).

Changed shared files: `plugin_api.py`, `game_installation.py`, `desktop_host.py`,
`ui/chooser.html`. Existing zero-argument helper callbacks remain supported;
new root-aware status/install callbacks and an explicit helper pin are optional.
Warband uses the selected installation rather than its import-time default.

Home helper rows now display pinned, installed and newest upstream versions,
package version, publication date and external GitHub release notes. Absent games
stay listed. A remote error retains the pin and local state; upstream metadata is
cached for the session, Check again refreshes, and installed state stays fresh.
The panel remains Lexer-Mode-only and read-only. Explicit Install/Repair lives in
the separate game-status dialog, including when a project warning masks Broken.

Tests: `test_wse2_helper_panel.py`, `wse2_helper_browser_check.py` plus actual-bundle
installer tests. Final runs 34046060075 and 34046060066 passed: Windows/Linux on
Python 3.10/3.11, real Home HTML/CSS/JS at 900x620 and 1440x900, and Warband WebGL.
Bridge responses in rendered Home tests are fixtures. No installed WebView2 or
actual Steam session acceptance is inferred. #81's human acceptance/status remains
with its global issue owner; no issue was automatically closed by this merge.

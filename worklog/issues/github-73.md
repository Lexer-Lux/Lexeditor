# #73 — FF9 platform-configuration lifecycle

## 2026-09-06 — FF9-only changes

Refresh the real Memoria configuration and Data Map after explicit installation,
on entering Information/Tweaks and when the settings window returns focus.
Never replace a dirty configuration while a refresh is in flight. Discard now
reloads the actual file rather than restoring a stale cached snapshot. Config
writes share the Memoria operation lock and refuse interrupted installations.

Evidence: JS controller regressions for absent-to-present configuration, explicit
launcher use, dirty-edit preservation, cancellation and fresh discard; HTTP guard
regression. The existing shared platform_config implementation was not modified
or revalidated by these isolated tests. FFNx/FF8 files are untouched.

Status: partial; real-shell and Windows acceptance remain, and this FF9 increment
does not close the cross-game issue.

Prepared acceptance checklist:
- [ ] Start without Memoria.ini, install Memoria explicitly, and open Tweaks without restarting Lexeditor; real values must appear.
- [ ] Edit a value, switch away and return/focus the editor; the unsaved value must survive.
- [ ] Change the INI externally; a stale save must refuse. Discard must load the external value.
- [ ] Confirm a saved value retains unrelated comments, ordering and unknown keys.

# #73 — FF9 uses Memoria's existing launcher

## 2026-09-06 — correction to PR #360

The earlier embedded-settings work followed the superseded issue body and missed
Lexer's explicit comment:
https://github.com/Lexer-Lux/Lexeditor/issues/73#issuecomment-5550129793

Removed the FF9 settings form, configuration state/fetch/save lifecycle and the
`/api/platform-config` and `/api/platform-config/save` routes. Tweaks now has a
Memoria subtab containing the exact requested message, with no settings controls.
Play targets `FF9_Launcher.exe`, not `x64/FF9.exe`. The dashboard, Information help
and Data Map agree on the launcher handoff. Installation/recovery and CSV editing
remain; FF7/FF8 and shared configuration/UI modules are untouched.

Validation for this correction:
- `python -m pytest -q tests/test_ff9_http.py`: 22 passed.
- `node --test tests/ff9_editor.test.cjs`: 10 passed.
- `python -m compileall -q games/ff9`: passed for the changed Python files.

HTTP tests execute the real handler with isolated data/runtime fixtures; the
launcher target is checked in the plugin's AST. JS tests execute the controller
with shared UI stubs. The three original production files were reconstructed
from connector contents and matched their original Git blob hashes before
applying the correction. No full-repository, rendered-editor or Windows launch
acceptance is claimed. PR remains draft and unmerged.

Prepared acceptance checks once the branch is integrated:
- [ ] Open FF9 → Tweaks → Memoria. Confirm the requested message and no INI settings form.
- [ ] With Memoria installed and FF9 closed, press Play. Confirm Memoria's existing launcher appears and allows settings edits before starting FF9.
- [ ] Save/reload a normal CSV edit. Confirm removing the settings form did not affect game-data editing.

Status: agent integration and Windows/render checks remain; do not close this
cross-game issue on the basis of this FF9-only correction.

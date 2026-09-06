# #77 — managed Memoria

## 2026-09-06 — isolated FF9 branch

Implemented verified publisher-payload inspection, preflight destination backup,
rollback and persistent interrupted-operation recovery. Added root-scoped version
records, binary version inspection, fail-closed running-process checks and
per-game OS locks. Existing INI bytes survive patching. The exact release tag,
asset URL and SHA-256 must match before execution.

Fixed the unreachable `/api/runtime/install` route and its double-response bug.
Runtime POSTs require the editor's loopback Host/Origin and bounded JSON; forms,
foreign origins and DNS-rebinding hosts cannot launch a patcher. Information has
Install, Recover and a launcher-delegating Settings action.

Correction following Lexer's #73 comment: normal Play is launcher-first via
`FF9_Launcher.exe`. The obsolete embedded settings editor and its configuration
read/write routes have been removed. Memoria's own launcher owns settings;
Lexeditor's installer still preserves the existing INI files. The earlier claim
that normal Play should bypass the launcher is superseded.

The original targeted tests cover synthetic payloads, unsafe paths, bad metadata,
cache, partial writes, false-success exits, exceptions, timeouts, damaged backups,
started games and concurrent/crashed lock owners. These are not real-patcher or
in-game acceptance results. For the settings-handoff correction, 22 isolated HTTP
and plugin-contract tests plus 10 JS controller tests passed. The full original
suite was not rerun in this correction's partial checkout.

Status: draft implementation, not closed. Real Windows API/version-resource,
full publisher executable, Steam-overlay `.fix`, rendering and in-game checks
remain. Do not ask the user to deliberately interrupt a primary game install.

Prepared acceptance checklist (use a disposable complete Steam installation):
- [ ] Install the pinned helper with FF9/launcher closed; verify the installed version and preserved INI comments/unknown keys.
- [ ] Reinstall, then compare existing INI bytes and confirm a recovery copy exists.
- [ ] Keep FF9 or its launcher open; confirm installation refuses without changing game files.
- [ ] Use Play: it must open FF9_Launcher.exe so Memoria's existing settings UI is available before starting FF9.
- [ ] Repeat the launcher-first Play check with the Steam-overlay fix enabled.

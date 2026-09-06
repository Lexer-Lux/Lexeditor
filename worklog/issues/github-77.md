# #77 — managed Memoria

## 2026-09-06 — isolated FF9 branch

Implemented verified publisher-payload inspection, preflight destination backup,
rollback and persistent interrupted-operation recovery. Added root-scoped version
records, binary version inspection, fail-closed running-process checks, per-game
OS locks and serialized configuration writes. Existing INI bytes survive patching.
The exact release tag, asset URL and SHA-256 must match before execution.

Fixed the unreachable `/api/runtime/install` route and its double-response bug.
Runtime POSTs require the editor's loopback Host/Origin and bounded JSON; forms,
foreign origins and DNS-rebinding hosts cannot launch a patcher. Information now
has separate Install, Recover and Settings actions; normal Play is unchanged.

Evidence: targeted Python tests cover signed/unsigned synthetic payloads, unsafe
paths, bad metadata/cache, partial writes and false-success exits, exceptions,
timeouts, damaged backups, started games, concurrent processes and crashed lock
owners. Controller tests cover explicit actions, cancellation and refresh.
These are not Windows-patcher or in-game acceptance results.

Status: draft implementation, not closed. Real Windows API/version-resource,
full publisher executable, Steam-overlay `.fix`, rendering and in-game checks
remain. Do not ask the user to deliberately interrupt a primary game install.

Prepared acceptance checklist (use a disposable complete Steam installation):
- [ ] Install the pinned helper with FF9/launcher closed; verify the installed version and preserved INI comments/unknown keys.
- [ ] Reinstall, then compare existing INI bytes and confirm a recovery copy exists.
- [ ] Keep FF9 or its launcher open; confirm installation/settings writes refuse without changing game files.
- [ ] Use Play: it must start x64/FF9.exe without opening the launcher. Only Open Memoria settings may open it.
- [ ] Repeat the explicit settings and Play checks with the Steam-overlay fix enabled.

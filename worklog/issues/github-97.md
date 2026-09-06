# #97 — Play without a game window

Branch: `fix/warband-issue-batch`. Latest request resumes the deferred Warband queue.

Implemented a plugin-specific process controller, selected-module resolution,
direct WSE2 arguments, owned Windows Job Object tracking, stable visible-window
readiness, early-exit/timeout cleanup, and owned-job Stop. Shared host behavior is
unchanged for plugins without the optional factory.

Remaining agent work: native/stock Warband launch is not implemented. The branch
fails explicitly when WSE2 is absent; do not close this issue or call it wholly fixed.
Window detection is a readiness heuristic, not campaign acceptance.

Validation: fake-job tests cover success, handoff, failure, timeout, stale status,
spaces in module names and installed aliases. Windows-only tests exercise a real
owned process and host delegation. Linux cannot validate Win32 APIs or the game.

Prepared owner test (WSE2 path): open this branch in a separate checkout; select
an installed source mod in Warband, press Play, confirm that mod's menu and load a
save. Press Stop and check all owned game windows close and Play returns. Repeat
with a disposable module that fails loading; expect an error, never a latched Stop.
Report module name, executable/version, visible error and WSE2 log on failure.

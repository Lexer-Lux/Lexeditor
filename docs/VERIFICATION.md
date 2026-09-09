# Regression checks

Install the test packages in the editor's Python environment:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-test.txt
.venv/Scripts/python.exe -m playwright install chromium
```

Node.js must also be on PATH. Run the baseline checks with:

```powershell
.venv/Scripts/python.exe tools/verify_all.py verify_regressions.py verify_browser_regressions.py frontend_syntax shared_ui_contract --jobs 2 --timeout 300 --retries 0
```

This checks Python behavior, JavaScript behavior and syntax, shared UI rules,
and the browser fixture suites. The service tests start Blank with no game
data. They check normal stop, restart, the Windows GUI interpreter, and forced
host exit. Visible Windows launcher fixtures are disabled by default. Run them
only after explicit approval by setting `LEXEDITOR_NATIVE_WINDOW_TESTS=1`.
The Windows CI job opts in on its own test machine.

Full output for each attempt and `report.json` are in `_scratch/verify-results`.
Use `--output <folder>` to keep a separate run. Failures return a nonzero exit
code. Each log is limited to 8 MiB. A timeout or excess output is a failure and
is not retried. With `--retries 1`, a pass on
retry is reported as `FLAKY`, and both logs are kept.

Use `--list` to inspect the selection. Repeat `--exclude <name>` to omit active
work. The default command without name filters runs all legacy verifiers too;
some need installed game data, separate build tools, or a specific platform.
For example, `verify_ff8_native_compiled.py` requires the Linux/g++ harness.

Browser results prove only the tested fixture behavior and geometry. They do
not prove native WebView2 behavior or in-game effects.

Disposable build trees, dependency caches, and browser profiles do not belong
in source backups or user packages. The packaging regression test checks this
boundary. Keep temporary work in a directory that is removed after the job;
retain only the needed patches and reports. Do not auto-delete mod projects,
saves, recovery backups, or required extracted game data as temporary waste.

Run the local RDR2 audit with `tools/verify_rdr2_runtime.py`. It includes executable
C++ checks for climbing transitions, minimap restoration, shoulder switching,
vehicle camera ownership, and independent core/bar rendering. These use controlled
native readbacks and temporary compiler output; they do not open the game.
Missing reference inputs and omitted native-window checks remain explicit failures
or omissions in `out/rdr2-runtime-audit/results.json`.

`tools/prepare_rdr2_gold_cores.py` builds transparent core masks from local stock
art. It verifies that existing resident textures survive exactly and that mask
alpha grows monotonically through all 16 states after a dictionary round trip.
It requires separate input/output paths and never installs its output. Texture
checks do not prove in-game HUD scale, alignment, or draw order.

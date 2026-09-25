"""Run every check that belongs to one plugin, or the shared ones.

    python tools/check_plugin.py ff8          one plugin
    python tools/check_plugin.py --global     everything that belongs to no plugin
    python tools/check_plugin.py ff8 --list   show what would run

Each `.github/workflows/<plugin>-checks.yml` and `global-checks.yml` is this
command and nothing else, so every game gets the same treatment. Checks
live in one folder per plugin, tests/<plugin>/, named after the plugin's
folder in plugins/; tests/shared/ holds everything that belongs to no plugin
and is what --global runs.

Standard steps, in order: compile the Python, syntax-check the JavaScript,
`app.py --game <id> --check`, pytest on the owned test_*.py files, node tests,
then the owned verifier and browser-check scripts through tests/shared/verify_all.py,
which reports a check that needs an installed game as SKIPPED rather than
failed. Extra commands a plugin genuinely needs (a native build) are listed in
tests/plugin_checks.json.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
CONFIG = json.loads((TESTS / "plugin_checks.json").read_text(encoding="utf-8"))
PLUGINS = sorted(p.name for p in (ROOT / "plugins").iterdir()
                 if p.is_dir() and (p / "plugin.py").is_file())
SHARED = "shared"
SCRIPT_SKIP = {"verify_all.py"}


def utf8_console() -> None:
    """Keep the runner's own output alive on a Windows code page.

    A check may report a character such as the floor bracket in a formula
    (U+230A). When the runner's output is piped or saved, Python falls back to
    the locale code page, which cannot hold that character. The stream then
    raises UnicodeEncodeError and the gate dies halfway with a live failure
    list. The children already run as UTF-8; the runner must match them.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def checks_folder(target: str | None) -> Path:
    """tests/<plugin>/ for a plugin, tests/shared/ for the global checks."""
    return TESTS / (target or SHARED)


def owned(target: str | None) -> dict[str, list[Path]]:
    files = {"pytest": [], "node": [], "scripts": [], "powershell": []}
    folder = checks_folder(target)
    for path in sorted(folder.iterdir()) if folder.is_dir() else ():
        if not path.is_file():
            continue
        name = path.name
        if name.startswith("test_") and name.endswith(".py"):
            files["pytest"].append(path)
        elif name.endswith(".test.cjs") or (name.startswith("test_") and name.endswith(".js")):
            files["node"].append(path)
        elif name.endswith(".ps1") and name.startswith("verify_"):
            files["powershell"].append(path)
        elif name.endswith(".py") and name not in SCRIPT_SKIP and (
                name.startswith("verify_") or name.endswith("_check.py")):
            files["scripts"].append(path)
    return files


def javascript(target: str | None) -> list[Path]:
    root = ROOT / "plugins" / target if target else ROOT / "ui"
    skip = {"vendor", "node_modules", "__pycache__"}
    return sorted(p for p in root.rglob("*.js")
                  if not skip & set(p.relative_to(root).parts) and not p.name.endswith(".min.js"))


def commands(target: str | None) -> list[list[str]]:
    py = sys.executable
    steps: list[list[str]] = []
    if target:
        steps.append([py, "-m", "compileall", "-q", f"plugins/{target}"])
        # Plugin ids are the folder name with hyphens (chrono_trigger -> chrono-trigger).
        steps.append([py, "app.py", "--game", target.replace("_", "-"), "--check"])
    else:
        steps.append([py, "-m", "compileall", "-q", "app.py", "core", "tools"])
        steps.append([py, "-m", "core.plugin_metadata"])
        steps.append([py, "tools/generate_credits.py", "--check"])
        steps.append([py, "app.py", "--list"])
    node = shutil.which("node")
    if node:
        steps += [[node, "--check", str(p.relative_to(ROOT))] for p in javascript(target)]
    for extra in CONFIG.get("extra", {}).get(target or "global", []):
        if extra.get("platform") and extra["platform"] != sys.platform:
            continue
        dev = str(Path(__import__("tempfile").gettempdir()) / "lexeditor-dev")
        steps.append([py if part == "{python}" else part.replace("{devcache}", dev) for part in extra["run"]])
    return steps


def run_scripts(scripts: list[Path], jobs: int) -> list[tuple[Path, int, str]]:
    sys.path.insert(0, str(ROOT))
    from tests.shared import verify_all
    output = verify_all.DEV_CACHE / "check-results"
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda tool: verify_all.run(tool, output=output), scripts))
    return [(tool, code, report) for tool, code, _seconds, report in results]


WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW = """\
# Generated by `python tools/check_plugin.py --write-workflows`; do not edit.
name: {title}
on:
  push:
    branches: [master]
    {filter}:
{paths}
  pull_request:
    {filter}:
{paths}
  workflow_dispatch:
jobs:
  checks:
    runs-on: windows-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: python -m pip install -r requirements-test.txt
      - run: python -m playwright install chromium
      - run: python tools/check_plugin.py {argument}
"""


def workflow_files() -> dict[str, str]:
    """The complete, expected contents of .github/workflows/."""
    shared = ["tests/plugin_checks.json", "tools/check_plugin.py", "tests/shared/verify_all.py",
              "requirements-test.txt"]
    files = {}
    for plugin in PLUGINS:
        paths = [f"plugins/{plugin}/**", f"tests/{plugin}/**"] + shared
        paths.append(f".github/workflows/{plugin}-checks.yml")
        files[f"{plugin}-checks.yml"] = WORKFLOW.format(
            title=f"{plugin} checks", filter="paths", argument=plugin,
            paths="\n".join(f"      - '{path}'" for path in paths))
    ignored = ["plugins/**", "worklog/**", "codex/**", "**.md"]
    files["global-checks.yml"] = WORKFLOW.format(
        title="global checks", filter="paths-ignore", argument="--global",
        paths="\n".join(f"      - '{path}'" for path in ignored))
    return files


def main() -> int:
    utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plugin", nargs="?", choices=PLUGINS)
    parser.add_argument("--global", dest="shared", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--write-workflows", action="store_true",
                        help="regenerate .github/workflows: one <plugin>-checks.yml per plugin plus global-checks.yml")
    args = parser.parse_args()
    if args.write_workflows:
        expected = workflow_files()
        for stale in WORKFLOWS.glob("*.yml"):
            if stale.name not in expected:
                stale.unlink()
        for name, text in expected.items():
            (WORKFLOWS / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {len(expected)} workflows")
        return 0
    if bool(args.plugin) == args.shared:
        parser.error("name one plugin, or pass --global")
    target = None if args.shared else args.plugin
    files = owned(target)
    steps = commands(target)
    if args.list:
        for step in steps:
            print("run   ", " ".join(step))
        for kind, paths in files.items():
            for path in paths:
                print(f"{kind:7s}", path.relative_to(ROOT).as_posix())
        return 0

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    failures: list[str] = []
    for step in steps:
        print("::", " ".join(step), flush=True)
        if subprocess.run(step, cwd=ROOT, env=env).returncode:
            failures.append(" ".join(step))
    if files["pytest"]:
        rels = [p.relative_to(ROOT).as_posix() for p in files["pytest"]]
        print(f":: pytest ({len(rels)} files)", flush=True)
        if subprocess.run([sys.executable, "-m", "pytest", "-q", *rels], cwd=ROOT, env=env).returncode:
            failures.append("pytest")
    node = shutil.which("node")
    for test in files["node"]:
        rel = test.relative_to(ROOT).as_posix()
        step = [node, "--test", rel] if rel.endswith(".cjs") else [node, rel]
        print("::", " ".join(step), flush=True)
        if not node or subprocess.run(step, cwd=ROOT, env=env).returncode:
            failures.append(rel)
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    for script in files["powershell"]:
        rel = script.relative_to(ROOT).as_posix()
        if not pwsh:
            print("SKIPPED (no PowerShell):", rel)
            continue
        print("::", rel, flush=True)
        if subprocess.run([pwsh, "-NoProfile", "-File", rel], cwd=ROOT, env=env).returncode:
            failures.append(rel)
    if files["scripts"]:
        print(f":: {len(files['scripts'])} verifier/browser scripts", flush=True)
        for tool, code, report in run_scripts(files["scripts"], args.jobs):
            status = "FAIL" if code else ("SKIP" if report.startswith("SKIPPED") else "ok  ")
            print(f"{status} {tool.name}: {report[:160]}")
            if code:
                failures.append(tool.name)
    print()
    if failures:
        print(f"{len(failures)} failed:", *failures, sep="\n  ")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

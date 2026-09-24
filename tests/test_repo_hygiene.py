"""The checkout holds source, not litter.

Agents once left an 18 GB build tree, a folder of screenshots, per-session
scratch folders, 921 worklog files, 31 hand-written workflows and 324
verifiers mixed into tools/. These checks keep each of those from creeping
back.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_plugin  # noqa: E402

# Working folders that have no business in the checkout: use your session
# scratchpad or %TEMP%/lexeditor-dev instead.
FORBIDDEN = ["_scratch", ".pytest_cache", "artifacts", "$out", "_worktrees", "games"]
# Shipped runtime payloads; every other tracked file stays small.
LARGE_ALLOWED = {
    "plugins/ff8/ffnx_issue_51/package/AF3DN.P",
    "plugins/warband/runtime/wse2-1.1.5.1-lex1.zip",
    "plugins/ff7r2/runtime/shader-injector-2-2-1-maximum-dood.zip",
}
LARGE_BYTES = 10 * 1024 * 1024


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_no_working_folders_in_the_checkout():
    present = [name for name in FORBIDDEN if (ROOT / name).exists()]
    assert not present, f"remove {present}; keep working files in your scratchpad or %TEMP%/lexeditor-dev"


def test_worklog_is_one_file_per_issue():
    stray = [p for p in tracked() if p.startswith("worklog/") and not re.fullmatch(r"worklog/\d+\.md", p)]
    assert not stray, stray


def test_verifiers_live_in_tests_not_tools():
    stray = [p for p in tracked() if p.startswith("tools/") and Path(p).name.startswith("verify_")]
    assert not stray, stray


def test_workflows_are_exactly_the_generated_checks():
    expected = check_plugin.workflow_files()
    actual = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / ".github/workflows").glob("*.y*ml")}
    assert set(actual) == set(expected), (
        f"extra: {sorted(set(actual) - set(expected))}, missing: {sorted(set(expected) - set(actual))}; "
        "run `python tools/check_plugin.py --write-workflows`")
    drifted = [name for name in expected if actual[name].replace("\r\n", "\n") != expected[name]]
    assert not drifted, f"{drifted} edited by hand; run `python tools/check_plugin.py --write-workflows`"


def test_every_plugin_has_checks():
    assert {f"{p}-checks.yml" for p in check_plugin.PLUGINS} <= set(check_plugin.workflow_files())


def test_no_large_files_outside_shipped_runtimes():
    big = [p for p in tracked() if p not in LARGE_ALLOWED and (ROOT / p).is_file()
           and (ROOT / p).stat().st_size > LARGE_BYTES]
    assert not big, big

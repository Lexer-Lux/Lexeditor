"""Every game plugin has its `Plugin` parent and all five subissues on GitHub.

AGENTS.md names the five (Create Editor, UX Refinement, Mod Loader, Create
Theme, ReShade); the developer page shows them per game from the same
`GitHubIntegration.plugin_board` read this uses. The issues are public, so CI
reads them with its own job token (GH_TOKEN in global-checks.yml).
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import discover_plugins  # noqa: E402
from core.desktop_host import LEXEDITOR_REPOSITORY  # noqa: E402
from core.github_integration import GitHubIntegration, PLUGIN_SUBISSUES  # noqa: E402


def test_every_game_has_its_five_plugin_subissues():
    if not shutil.which("gh"):
        # CI always has the GitHub CLI; a checkout without it cannot read the tracker.
        if os.environ.get("CI"):
            pytest.fail("GitHub CLI is missing on CI")
        pytest.skip("GitHub CLI is not installed")
    # Two editions sharing one plugin's code share its label (`issueLabel`).
    games = sorted({plugin.tracker_label for plugin_id, plugin in discover_plugins().items()
                    if plugin_id != "blank"})
    board = GitHubIntegration().plugin_board(LEXEDITOR_REPOSITORY, games, owner_only=False)
    missing = [f"{game}: {title}"
               for game in games
               for key, title in PLUGIN_SUBISSUES
               if board["games"][game]["subissues"][key] is None]
    assert not missing, ("Each game needs a `Plugin` issue with the game's label linking "
                         "these subissues (AGENTS.md, Standard plugin issue structure):\n  "
                         + "\n  ".join(missing))

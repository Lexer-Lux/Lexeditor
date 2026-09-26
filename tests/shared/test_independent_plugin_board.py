"""The issue board finds tasks without a Plugin container, across pages."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_github_integration import REPOSITORY, runner_for
from core.github_integration import GitHubIntegration


def test_board_uses_game_labels_and_prefers_open_tasks():
    def issue(number, title, labels, state="OPEN", blocked=0):
        return dict(number=number, title=title, state=state,
                    labels={"nodes": [{"name": x, "color": "123456"} for x in labels]},
                    issueDependenciesSummary={"blockedBy": blocked})

    def page(*issues):
        return {"data": {"repository": {"issues": {"nodes": issues}}}}

    payload = [page(issue(1, "Plugin", ["ff7"]),
                    issue(2, "Create Editor", ["ff7", "actionable"]),
                    issue(3, "UX Refinement", ["ff7", "waiting"], blocked=1)),
               page(issue(4, "Create Editor", ["ff7"], state="CLOSED"),
                    issue(5, "Create Theme", ["ff7"], state="CLOSED"),
                    issue(6, "Other task", ["global", "untested"]))]
    run = runner_for(json.dumps(payload))
    board = GitHubIntegration(executable="gh", runner=run).plugin_board(
        REPOSITORY, ["ff7", "global"], owner_only=False)
    game = board["games"]["ff7"]
    assert game["subissues"]["editor"]["number"] == 2
    assert game["subissues"]["ux"]["blocked"]
    assert game["subissues"]["theme"]["closed"]
    assert game["subissues"]["reshade"] is None
    assert game["counts"] == dict(actionable=1, waiting=1, untested=0, unfeasible=0, none=0)
    assert board["games"]["global"]["counts"]["untested"] == 1
    assert board["colors"]["waiting"] == "#123456"
    assert len(run.calls) == 1

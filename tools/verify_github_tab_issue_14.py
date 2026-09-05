from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from github_integration import GitHubIntegration
from plugin_api import GitHubRepository


FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
DESKTOP = (ROOT / "desktop_host.py").read_text(encoding="utf-8")
GITHUB = (ROOT / "github_integration.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('id: "plugin-github", class: "lex-developer-button lex-github-tab"' in FRAMEWORK_JS,
        "GitHub must use the shared developer control")
require('class: "lex-developer-actions"' in FRAMEWORK_JS and
        'brandSlot, leftActions, centerActions, rightActions, developerActions, windowControls.root' in FRAMEWORK_JS,
        "the owner-only GitHub control must sit before the window controls")
require("nav.append(github)" not in FRAMEWORK_JS,
        "GitHub must not consume primary game-tab space")
require('const workflows = ["actionable", "waiting", "unfeasible"]' in FRAMEWORK_JS,
        "the GitHub workspace must use the three requested workflow subtabs")
require('panelLayout([issueList, editor, commentsPanel], "lex-github-layout"' in FRAMEWORK_JS,
        "GitHub must use the shared three-panel composer")
require('class: "lex-detail lex-github-comments-panel"' in FRAMEWORK_JS,
        "GitHub must contain separate editor and comments panels")
require('class: `lex-list-row lex-github-issue-row' in FRAMEWORK_JS,
        "dense issue rows must inherit the shared list row")
require('"github_comment_issue"' in FRAMEWORK_JS and
        "requestAnimationFrame(() => { commentsFeed.scrollTop = commentsFeed.scrollHeight; })" in FRAMEWORK_JS,
        "comments must be writable and open at the bottom")
require('class: `lex-github-priority-toggle${priorityActive ? " active" : ""}`' in FRAMEWORK_JS,
        "the selected issue must have a direct high-priority toggle")
require('element("span", {}, "TITLE")' not in FRAMEWORK_JS and
        'element("span", {}, "BODY")' not in FRAMEWORK_JS,
        "the redundant Title and Body captions must stay deleted")
require("grid-template-columns: max-content minmax(0, 1fr) 18px max-content" in FRAMEWORK_CSS and
        "white-space: nowrap" in FRAMEWORK_CSS,
        "issue rows must use one dense line")
require("def github_comment_issue" in DESKTOP and "def comment_issue" in GITHUB,
        "the desktop and GitHub bridges must expose comment posting")
require('"--body-file", str(body_file)' in GITHUB,
        "comments must use a body file instead of command-line body text")


class FakeRunner:
    def __init__(self, login: str = "Lexer-Lux") -> None:
        self.login = login
        self.comment_body = None
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        arguments = command[1:]
        if arguments[:2] == ["auth", "status"]:
            payload = {"hosts": {"github.com": [{
                "active": True, "state": "success", "login": self.login,
            }]}}
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if arguments[:2] == ["issue", "comment"]:
            body_path = Path(arguments[arguments.index("--body-file") + 1])
            self.comment_body = body_path.read_text(encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "posted", "")
        if arguments[:2] == ["issue", "view"]:
            payload = {
                "number": 14,
                "title": "GitHub tab",
                "state": "OPEN",
                "labels": [{"name": "actionable", "color": "0e8a16"}],
                "body": "Body",
                "comments": [{
                    "author": {"login": "Lexer-Lux"},
                    "body": self.comment_body or "",
                    "createdAt": "2026-08-20T00:00:00Z",
                }],
                "author": {"login": "Lexer-Lux"},
                "updatedAt": "2026-08-20T00:00:00Z",
                "url": "https://example.invalid/14",
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        raise AssertionError(f"unexpected fake GitHub command: {arguments}")


repository = GitHubRepository(
    full_name="Lexer-Lux/Lexeditor", authorized_logins=("Lexer-Lux",),
)
runner = FakeRunner()
integration = GitHubIntegration(executable="gh-test", runner=runner)
result = integration.comment_issue(repository, 14, "  New comment body  ")
require(runner.comment_body == "New comment body",
        "comment text must reach the temporary UTF-8 body file")
require(result["comments"][-1]["body"] == "New comment body",
        "posting a comment must return refreshed issue comments")

denied_runner = FakeRunner(login="SomeoneElse")
denied = GitHubIntegration(executable="gh-test", runner=denied_runner)
try:
    denied.comment_issue(repository, 14, "Blocked")
except PermissionError:
    pass
else:
    raise AssertionError("an unauthorized account posted a comment")
require(not any(command[1:3] == ["issue", "comment"] for command in denied_runner.commands),
        "authorization must fail before the comment command")

print("GitHub tab issue 14 source and bridge contract passed")

"""Owner-only GitHub issue links without handling GitHub credentials."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from plugin_api import GitHubRepository


_AUTO = object()
_UNCHECKED = object()
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubIntegration:
    """Use GitHub CLI's keyring session for an embedded owner workspace."""

    def __init__(self, executable: str | Path | None | object = _AUTO,
                 runner: CommandRunner = subprocess.run):
        found = shutil.which("gh") if executable is _AUTO else executable
        self._executable = str(found) if found else None
        self._runner = runner
        self._cached_login: str | None | object = _UNCHECKED
        self._lock = threading.RLock()

    def _run(self, arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        if not self._executable:
            raise FileNotFoundError("GitHub CLI is not installed")
        environment = dict(os.environ)
        environment["GH_PROMPT_DISABLED"] = "1"
        return self._runner(
            [self._executable, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
        )

    def active_login(self, refresh: bool = False) -> str | None:
        """Return the active authenticated github.com login, or no identity."""
        with self._lock:
            if not refresh and self._cached_login is not _UNCHECKED:
                return self._cached_login
            login = None
            if self._executable:
                try:
                    result = self._run([
                        "auth", "status", "--active", "--hostname", "github.com",
                        "--json", "hosts",
                    ], timeout=8)
                    if result.returncode == 0:
                        payload = json.loads(result.stdout)
                        accounts = payload.get("hosts", {}).get("github.com", [])
                        account = next((row for row in accounts
                                        if row.get("active") and row.get("state") == "success"), None)
                        value = str((account or {}).get("login", "")).strip()
                        login = value or None
                except (OSError, subprocess.SubprocessError, ValueError, TypeError):
                    login = None
            self._cached_login = login
            return login

    @staticmethod
    def _authorized(repository: GitHubRepository, login: str | None) -> bool:
        return bool(login) and login.casefold() in {
            allowed.casefold() for allowed in repository.authorized_logins
        }

    def _require_authorized(self, repository: GitHubRepository,
                            refresh: bool = False) -> str:
        login = self.active_login(refresh=refresh)
        if not self._authorized(repository, login):
            raise PermissionError("The authorized GitHub owner account is not active")
        return str(login)

    def _json(self, arguments: list[str], timeout: int = 20) -> object:
        result = self._run(arguments, timeout=timeout)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or "GitHub CLI command failed")
        try:
            return json.loads(result.stdout or "null")
        except (TypeError, ValueError) as error:
            raise RuntimeError("GitHub CLI returned invalid JSON") from error

    @staticmethod
    def _issue_number(number: int | str) -> int:
        value = int(number)
        if value < 1:
            raise ValueError("GitHub issue number must be positive")
        return value

    @staticmethod
    def _labels(rows: object) -> list[dict]:
        if not isinstance(rows, list):
            return []
        labels = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            labels.append({
                "name": name,
                "color": str(row.get("color", "")).strip().lstrip("#") or "808080",
                "description": str(row.get("description", "") or "").strip(),
            })
        return labels

    @classmethod
    def _issue(cls, row: object, *, details: bool = False) -> dict:
        if not isinstance(row, dict):
            raise RuntimeError("GitHub CLI returned an invalid issue")
        author = row.get("author") if isinstance(row.get("author"), dict) else {}
        result = {
            "number": cls._issue_number(row.get("number", 0)),
            "title": str(row.get("title", "")),
            "state": str(row.get("state", "")).upper(),
            "labels": cls._labels(row.get("labels")),
            "updatedAt": str(row.get("updatedAt", "")),
            "author": str(author.get("login", "")),
        }
        if details:
            result["body"] = str(row.get("body", "") or "")
            result["url"] = str(row.get("url", ""))
            comments = []
            for comment in row.get("comments", []) if isinstance(row.get("comments"), list) else []:
                if not isinstance(comment, dict):
                    continue
                comment_author = comment.get("author") if isinstance(comment.get("author"), dict) else {}
                comments.append({
                    "author": str(comment_author.get("login", "")),
                    "body": str(comment.get("body", "") or ""),
                    "createdAt": str(comment.get("createdAt", "")),
                })
            result["comments"] = comments
        return result

    def visible_repository(self, repository: GitHubRepository | None,
                           refresh: bool = False) -> dict | None:
        """Return safe public metadata only for an authorized active account."""
        login = self.active_login(refresh=refresh)
        if repository is None or not self._authorized(repository, login):
            return None
        return {
            "repository": repository.full_name,
            "login": str(login),
        }

    def list_issues(self, repository: GitHubRepository,
                    state: str = "open", limit: int = 500,
                    label: str | None = None) -> dict:
        """List repository issues for the embedded workspace, optionally by game label."""
        self._require_authorized(repository, refresh=True)
        normalized_state = str(state).casefold()
        if normalized_state not in {"open", "closed", "all"}:
            raise ValueError("GitHub issue state must be open, closed, or all")
        normalized_limit = max(1, min(int(limit), 500))
        arguments = [
            "issue", "list", "--repo", repository.full_name,
            "--state", normalized_state, "--limit", str(normalized_limit),
            "--json", "number,title,state,labels,updatedAt,author",
        ]
        clean_label = str(label or "").strip()
        if clean_label:
            arguments.extend(["--label", clean_label])
        payload = self._json(arguments)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub CLI returned an invalid issue list")
        return {
            "repository": repository.full_name,
            "state": normalized_state,
            "issues": [self._issue(row) for row in payload],
        }

    def view_issue(self, repository: GitHubRepository, number: int | str) -> dict:
        """Read one issue and its comments for the embedded detail pane."""
        self._require_authorized(repository, refresh=True)
        issue_number = self._issue_number(number)
        payload = self._json([
            "issue", "view", str(issue_number), "--repo", repository.full_name,
            "--json", "number,title,state,labels,body,comments,author,updatedAt,url",
        ])
        return self._issue(payload, details=True)

    def list_labels(self, repository: GitHubRepository) -> dict:
        """Return labels that the owner can apply in the repository."""
        self._require_authorized(repository, refresh=True)
        payload = self._json([
            "label", "list", "--repo", repository.full_name, "--limit", "200",
            "--json", "name,color,description",
        ])
        labels = sorted(self._labels(payload), key=lambda row: row["name"].casefold())
        return {"repository": repository.full_name, "labels": labels}

    def edit_issue(self, repository: GitHubRepository, number: int | str,
                   title: str, body: str) -> dict:
        """Save an issue title and body without exposing credentials."""
        self._require_authorized(repository, refresh=True)
        issue_number = self._issue_number(number)
        clean_title = str(title).strip()
        if not clean_title:
            raise ValueError("GitHub issue title cannot be empty")
        with tempfile.TemporaryDirectory(prefix="lexeditor-github-") as directory:
            body_file = Path(directory) / "issue-body.md"
            body_file.write_text(str(body), encoding="utf-8", newline="\n")
            result = self._run([
                "issue", "edit", str(issue_number), "--repo", repository.full_name,
                "--title", clean_title, "--body-file", str(body_file),
            ], timeout=30)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or "GitHub could not save the issue")
        return self.view_issue(repository, issue_number)

    def set_issue_labels(self, repository: GitHubRepository, number: int | str,
                         labels: list[str] | tuple[str, ...]) -> dict:
        """Set the complete issue-label selection after exact-name validation."""
        self._require_authorized(repository, refresh=True)
        issue_number = self._issue_number(number)
        available_rows = self.list_labels(repository)["labels"]
        available = {row["name"]: row for row in available_rows}
        desired = {str(label).strip() for label in labels if str(label).strip()}
        unknown = sorted(desired - set(available), key=str.casefold)
        if unknown:
            raise ValueError("Unknown GitHub label: " + ", ".join(unknown))
        current_issue = self.view_issue(repository, issue_number)
        current = {row["name"] for row in current_issue["labels"]}
        add = sorted(desired - current, key=str.casefold)
        remove = sorted(current - desired, key=str.casefold)
        if add or remove:
            arguments = [
                "issue", "edit", str(issue_number), "--repo", repository.full_name,
            ]
            for label in add:
                arguments.extend(["--add-label", label])
            for label in remove:
                arguments.extend(["--remove-label", label])
            result = self._run(arguments, timeout=30)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(detail or "GitHub could not change the issue labels")
        return self.view_issue(repository, issue_number)

    def comment_issue(self, repository: GitHubRepository, number: int | str,
                      body: str) -> dict:
        """Post one issue comment through a temporary UTF-8 body file."""
        self._require_authorized(repository, refresh=True)
        issue_number = self._issue_number(number)
        clean_body = str(body).strip()
        if not clean_body:
            raise ValueError("GitHub comment cannot be empty")
        with tempfile.TemporaryDirectory(prefix="lexeditor-github-") as directory:
            body_file = Path(directory) / "comment.md"
            body_file.write_text(clean_body, encoding="utf-8", newline="\n")
            result = self._run([
                "issue", "comment", str(issue_number), "--repo", repository.full_name,
                "--body-file", str(body_file),
            ], timeout=30)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or "GitHub could not post the comment")
        return self.view_issue(repository, issue_number)

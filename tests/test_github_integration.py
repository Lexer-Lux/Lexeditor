"""Cover the owner-authorization probe without touching a real GitHub session."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from github_integration import GitHubIntegration
from plugin_api import GitHubRepository

REPOSITORY = GitHubRepository(full_name="Lexer-Lux/Lexeditor",
                              authorized_logins=("Lexer-Lux",))
SIGNED_IN = ('{"hosts":{"github.com":[{"state":"success","active":true,'
             '"host":"github.com","login":"Lexer-Lux"}]}}')


def runner_for(*responses):
    """Answer each call in turn; the last response repeats."""
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        response = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(response, BaseException):
            raise response
        return subprocess.CompletedProcess(command, 0, response, "")

    run.calls = calls
    return run


class ActiveLoginTests(unittest.TestCase):
    def test_signed_in_account_is_returned(self):
        integration = GitHubIntegration(executable="gh", runner=runner_for(SIGNED_IN))
        self.assertEqual(integration.active_login(), "Lexer-Lux")

    def test_success_is_cached(self):
        run = runner_for(SIGNED_IN)
        integration = GitHubIntegration(executable="gh", runner=run)
        integration.active_login()
        integration.active_login()
        self.assertEqual(len(run.calls), 1)

    def test_timeout_is_not_cached_and_recovers(self):
        # A slow keyring read once made the account look revoked for the whole
        # session, with no way back except restarting the editor.
        run = runner_for(subprocess.TimeoutExpired("gh", 20), SIGNED_IN)
        integration = GitHubIntegration(executable="gh", runner=run)
        self.assertIsNone(integration.active_login())
        self.assertEqual(integration.active_login(), "Lexer-Lux")

    def test_invalid_payload_is_not_cached(self):
        run = runner_for("not json", SIGNED_IN)
        integration = GitHubIntegration(executable="gh", runner=run)
        self.assertIsNone(integration.active_login())
        self.assertEqual(integration.active_login(), "Lexer-Lux")

    def test_missing_cli_reports_no_login(self):
        integration = GitHubIntegration(executable=None, runner=runner_for(SIGNED_IN))
        self.assertIsNone(integration.active_login())


class AuthorizationMessageTests(unittest.TestCase):
    def message(self, integration):
        with self.assertRaises(PermissionError) as caught:
            integration._require_authorized(REPOSITORY)
        return str(caught.exception)

    def test_missing_cli_names_the_cli(self):
        integration = GitHubIntegration(executable=None, runner=runner_for(SIGNED_IN))
        self.assertIn("not installed", self.message(integration))

    def test_unanswered_probe_does_not_claim_a_revoked_account(self):
        integration = GitHubIntegration(
            executable="gh", runner=runner_for(subprocess.TimeoutExpired("gh", 20)))
        message = self.message(integration)
        self.assertIn("did not report a signed-in account", message)
        self.assertNotIn("not an authorized owner", message)

    def test_other_account_is_named(self):
        other = ('{"hosts":{"github.com":[{"state":"success","active":true,'
                 '"host":"github.com","login":"someone-else"}]}}')
        integration = GitHubIntegration(executable="gh", runner=runner_for(other))
        message = self.message(integration)
        self.assertIn("someone-else", message)
        self.assertIn("Lexer-Lux/Lexeditor", message)

    def test_authorized_account_passes(self):
        integration = GitHubIntegration(executable="gh", runner=runner_for(SIGNED_IN))
        self.assertEqual(integration._require_authorized(REPOSITORY), "Lexer-Lux")

    def test_authorization_is_case_insensitive(self):
        lowered = ('{"hosts":{"github.com":[{"state":"success","active":true,'
                   '"host":"github.com","login":"lexer-lux"}]}}')
        integration = GitHubIntegration(executable="gh", runner=runner_for(lowered))
        self.assertEqual(integration._require_authorized(REPOSITORY), "lexer-lux")

    def test_recovers_after_a_failed_probe(self):
        run = runner_for(subprocess.TimeoutExpired("gh", 20), SIGNED_IN)
        integration = GitHubIntegration(executable="gh", runner=run)
        with self.assertRaises(PermissionError):
            integration._require_authorized(REPOSITORY)
        self.assertEqual(integration._require_authorized(REPOSITORY), "Lexer-Lux")


if __name__ == "__main__":
    unittest.main()

"""Apply the explicitly reviewed September 6 issue descriptions, not inferred statuses.

The workflow downloads the immutable pre-edit snapshot first. Concurrent issue
changes are skipped, original descriptions/comments are archived, and every write
is read back. This tool never rewrites comments, executes issue text, or edits game
code. Remove the temporary workflow after the requested audit.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = "Lexer-Lux/Lexeditor"
ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline"
PLAN_DIR = ROOT / "worklog/issue-status-audit/2026-09-06"
ARCHIVE = ROOT / "worklog/legacy/issue-status-audit-2026-09-06"
WORKFLOW = {"actionable", "waiting", "untested", "unfeasible", "needs testing", "needs a human", "test me"}
ACTIVE = WORKFLOW - {"unfeasible"}
HASHES = {
    "issues.jsonl": "84a7aa39dd260cb377a3f7d5f4c861d5dcc0bbcb642d548d709f59c37eacdc46",
    "comments.jsonl": "5f3cb9e0c18ae29d062e4f0f609f2e6bbc0b55cb63b3a36b1b25bf6398c9b13c",
}
LABEL_DESCRIPTIONS = {
    "actionable": "Agent work remains: research, repair, implementation, build, delivery or test preparation.",
    "waiting": "Blocked on a specific action or decision from Lexer. Never backlog or unfinished agent work.",
    "untested": "Needs Testing: an implemented candidate is available and the human test checklist is ready.",
    "unfeasible": "A verified limitation blocks the available technical path; not merely difficult or unresearched.",
}


def api(path: str, method: str = "GET", payload: dict | None = None):
    """Repository-scoped API calls; never follow external URLs with credentials."""
    if not path.startswith("/") or "://" in path:
        raise ValueError("Only repository-relative API paths are allowed")
    token = os.environ["GH_TOKEN"]
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(
        "https://api.github.com/repos/" + REPO + path,
        data=body,
        method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "Lexeditor-human-issue-audit"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            limited = error.code == 429 or (error.code == 403 and "rate limit" in detail.lower())
            if not limited or attempt == 4:
                raise RuntimeError(f"{method} {path}: HTTP {error.code}: {detail[:800]}") from None
            time.sleep(max(int(error.headers.get("Retry-After", "60")), 60))
    raise RuntimeError("API retries exhausted")


def snapshot(issue: dict) -> dict:
    labels = issue.get("labels", [])
    return {
        "number": issue["number"], "title": issue.get("title", ""),
        "body": issue.get("body") or "", "state": issue["state"],
        "state_reason": issue.get("state_reason"),
        "labels": sorted(x["name"] if isinstance(x, dict) else x for x in labels),
        "comments": issue.get("comments", 0), "updated_at": issue.get("updated_at"),
    }


def parse_plans() -> dict[int, dict]:
    plans: dict[int, dict] = {}
    for path in sorted(PLAN_DIR.glob("plan-*.md")):
        text = path.read_text(encoding="utf-8")
        blocks = re.split(r"(?m)^@@ ", text)[1:]
        for block in blocks:
            header, body = block.split("\n", 1)
            number_text, workflow, title = header.split("|", 2)
            number = int(number_text)
            if number in plans:
                raise ValueError(f"Duplicate plan #{number}")
            if workflow not in {"actionable", "waiting", "untested", "unfeasible", "closed:completed", "closed:not_planned", "closed:duplicate"}:
                raise ValueError(f"Unknown workflow for #{number}: {workflow}")
            body = body.strip()
            if not body or not title.strip():
                raise ValueError(f"Empty title/body for #{number}")
            if workflow in {"waiting", "untested"}:
                if not body.splitlines()[-1].startswith("- [ ] "):
                    raise ValueError(f"#{number} must end in an unchecked human-action checklist")
                if not re.search(r"(?m)^- \[ \] .+", body):
                    raise ValueError(f"#{number} has no human-action checklist")
            plans[number] = {"workflow": workflow, "title": title.strip(), "body": body,
                             "plan_file": path.relative_to(ROOT).as_posix()}
    if not plans:
        raise ValueError("No reviewed plans")
    return plans


def main() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise RuntimeError("This reviewed plan is authorized only for " + REPO)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for filename, expected in HASHES.items():
        raw = (BASELINE / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError("Snapshot integrity check failed: " + filename)
        dest = ARCHIVE / filename
        if dest.exists() and dest.read_bytes() != raw:
            raise RuntimeError("Refusing to replace a different audit archive")
        dest.write_bytes(raw)
    baseline = {x["number"]: x for x in (json.loads(line) for line in (BASELINE / "issues.jsonl").read_text().splitlines())}
    plans = parse_plans()
    unknown = set(plans) - set(baseline)
    if unknown:
        raise ValueError(f"Issues not in the reviewed snapshot: {sorted(unknown)}")
    for name, description in LABEL_DESCRIPTIONS.items():
        path = "/labels/" + urllib.parse.quote(name, safe="")
        existing = api(path)
        if existing.get("description") != description:
            api(path, "PATCH", {"description": description})
            time.sleep(1.1)
    results = []
    targets = set(plans) | {n for n, i in baseline.items() if i["state"] == "closed" and set(i["labels"]) & ACTIVE}
    for number in sorted(targets):
        original = baseline[number]
        current = api(f"/issues/{number}")
        if "pull_request" in current:
            raise RuntimeError(f"Refusing to change pull request #{number}")
        plan = plans.get(number)
        patch: dict = {}
        if plan:
            workflow = plan["workflow"]
            labels = [label for label in original["labels"] if label not in WORKFLOW]
            patch.update(title=plan["title"], body=plan["body"])
            if workflow.startswith("closed:"):
                reason = workflow.split(":", 1)[1]
                patch.update(state="closed", state_reason="not_planned" if reason == "duplicate" else reason)
                if reason == "duplicate" and "duplicate" not in labels:
                    labels.append("duplicate")
                if "unfeasible" in original["labels"] and reason != "duplicate":
                    labels.append("unfeasible")
            else:
                if original["state"] != "open":
                    raise RuntimeError(f"Explicit reopening is required before planning open status for #{number}")
                labels.append(workflow)
            patch["labels"] = labels
        else:
            patch["labels"] = [label for label in original["labels"] if label not in ACTIVE]
        def matches(value: dict) -> bool:
            view = snapshot(value)
            return all(view.get(key) == (sorted(v) if key == "labels" else v) for key, v in patch.items())
        if matches(current):
            results.append({"number": number, "result": "already_matches"})
            continue
        if snapshot(current) != snapshot(original):
            results.append({"number": number, "result": "skipped_concurrent_change",
                            "reviewed_updated_at": original["updated_at"], "current_updated_at": current["updated_at"]})
            print(f"SKIP #{number}: changed since review", flush=True)
            continue
        try:
            api(f"/issues/{number}", "PATCH", patch)
            verified = api(f"/issues/{number}")
            if not matches(verified):
                raise RuntimeError("Readback differs from reviewed patch")
            record = {"number": number, "result": "updated", "before": snapshot(current),
                      "after": snapshot(verified), "plan_file": plan.get("plan_file") if plan else None}
            results.append(record)
            print(f"UPDATED #{number}: {', '.join(snapshot(verified)['labels'])}", flush=True)
            if plan and not plan["workflow"].startswith("closed:"):
                worklog = ROOT / f"worklog/issues/github-{number}.md"
                if not worklog.exists():
                    worklog.parent.mkdir(parents=True, exist_ok=True)
                    worklog.write_text(
                        f"# Issue #{number}: internal status handoff\n\n"
                        "This September 6 audit rewrote the public issue; it did not implement or test game code.\n\n"
                        f"## Reviewed status: {plan['workflow']}\n\n{plan['body']}\n\n"
                        "## Evidence and retained scope\n\n"
                        f"The pre-audit specification is entry {number} in `worklog/legacy/issue-status-audit-2026-09-06/issues.jsonl`.\n"
                        "Its complete comment history is in the adjacent `comments.jsonl`; these are historical evidence, not current facts.\n"
                        "Re-read the live issue and later comments before implementation. Preserve all still-applicable requirements from the archived specification.\n"
                        "Record actual implementation, build, delivery and validation progress here; do not use a human blocker label for remaining agent work.\n",
                        encoding="utf-8",
                    )
            time.sleep(1.1)
        except Exception as error:
            results.append({"number": number, "result": "error", "error": str(error)})
            print(f"ERROR #{number}: {error}", flush=True)
    counts = dict(collections.Counter(r["result"] for r in results))
    report = {"baseline_issue_count": len(baseline), "planned_issue_count": len(plans),
              "target_count": len(targets), "counts": counts, "results": results}
    (ROOT / "audit-results").mkdir(exist_ok=True)
    (ROOT / "audit-results/results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ARCHIVE / f"results-{os.environ['GITHUB_RUN_ID']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUDIT RESULT " + json.dumps({k: v for k, v in report.items() if k != "results"}), flush=True)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
        out.write("## Human-facing issue audit\n\n" + json.dumps(counts) + "\n\n")
        out.write("Original descriptions and comments are preserved. Concurrent changes were not overwritten.\n")
    if counts.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

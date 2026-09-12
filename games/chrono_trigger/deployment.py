"""Server-facing Chrono Trigger deployment orchestration."""

from __future__ import annotations

from pathlib import Path

from .ctext_manager import deploy_project, status as ctext_status
from .data import OverlayStore
from .integrity import audit_project


def deployment_status(store: OverlayStore, game_root: Path) -> dict:
    """Return CTExt state plus a non-mutating project preflight audit."""
    ctext = ctext_status(Path(game_root), store.project_root)
    audit = audit_project(store, "mine")
    return {
        "kind": "chrono-trigger-deployment-status",
        "ctext": ctext,
        "audit": audit,
        "canDeploy": bool(
            store.writable
            and ctext["installed"]
            and ctext["configValid"]
            and audit["ok"]
        ),
        "automatic": False,
    }


def deploy_audited_project(store: OverlayStore, game_root: Path) -> dict:
    """Run preflight and explicitly deploy only when no audit errors exist."""
    if not store.writable:
        raise RuntimeError("Create or select a writable Chrono Trigger project before deployment")
    audit = audit_project(store, "mine")
    if not audit["ok"]:
        codes = sorted({issue["code"] for issue in audit["issues"] if issue["level"] == "error"})
        detail = ", ".join(codes) or "unknown audit error"
        raise RuntimeError(f"Chrono Trigger project audit failed; deployment was not attempted: {detail}")
    deployment = deploy_project(Path(game_root), store.project_root)
    return {
        "kind": "chrono-trigger-deployment-result",
        "deployment": deployment,
        "audit": audit,
        "automatic": False,
    }

"""Windows-only PalServer.exe running-state guard for deployment mutations."""

from __future__ import annotations

import os
import subprocess


class PalServerProcessError(RuntimeError):
    pass


def running() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PalServer.exe", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise PalServerProcessError(f"Could not determine whether PalServer.exe is running: {error}") from error
    if result.returncode != 0:
        raise PalServerProcessError(
            "Could not determine whether PalServer.exe is running; tasklist returned "
            f"exit code {result.returncode}."
        )
    output = result.stdout.casefold()
    return '"palserver.exe"' in output or "palserver.exe" in output and "no tasks" not in output


def require_stopped() -> None:
    if running():
        raise PalServerProcessError(
            "PalServer.exe is running. Stop the dedicated server before changing its package source or PalModSettings.ini; restart it afterward to apply changes."
        )

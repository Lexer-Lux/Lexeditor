"""Compatibility name for the browser helper the verifiers import.

Ninety-nine verifiers open with

    sys.path.insert(0, str(Path(r"C:\\RDR2Mod\\tools\\reverse-engineering")))
    from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json

That path exists on one machine, which is why none of those checks could run on
GitHub or on a fresh checkout. Keeping this module under the same name means
none of those verifiers need editing: when the out-of-repo copy is present it is
found first and behaves exactly as before, and when it is not, Python falls
through to this one.

The name is historical. What it actually provides is a CDP client; the code is
in `tools/cdp.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The client itself lives in tools/, which is not on the path of a verifier
# that only adds the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from cdp import (  # noqa: E402,F401
    OUT,
    ROOT,
    Cdp,
    free_port,
    screenshot,
    wait_eval,
    wait_json,
)

__all__ = ["Cdp", "free_port", "screenshot", "wait_eval", "wait_json", "OUT", "ROOT"]

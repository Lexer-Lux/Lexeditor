"""Verify bounded, atomic FF8 live-condition final-variant composition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import runtime_layout


def price(record0: tuple[int, int, int], record1: tuple[int, int, int]) -> bytes:
    return (record0[0].to_bytes(2, "little") + bytes(record0[1:])
            + record1[0].to_bytes(2, "little") + bytes(record1[1:]))


def make_mod(root: Path, mod_id: str, order: int, files: dict[str, bytes],
             xml: bytes | None = None) -> dict:
    root.mkdir(parents=True)
    for relative, payload in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    if xml is not None:
        (root / "mod.xml").write_bytes(xml)
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": mod_id, "name": mod_id, "enabled": True, "order": order,
    }), encoding="utf-8")
    return {
        "id": mod_id, "name": mod_id, "path": str(root),
        "enabled": True, "order": order, "folderOptions": {},
    }


def asset(runtime: Path, variant: dict) -> bytes:
    return (runtime / "direct" / variant["asset"]).read_bytes()


def main() -> int:
    vanilla = price((10, 2, 0), (20, 3, 0))
    low = price((10, 2, 7), (20, 3, 0))
    conditional = price((10, 2, 0), (222, 8, 0))
    high = price((10, 9, 0), (20, 6, 0))
    xml = b"""<ModInfo><ID>middle</ID><Name>middle</Name>
      <Conditional Folder="memory">
        <RuntimeVar ApplyTo="direct/menu/price.bin" Var="Byte:0x1234" Values="1"/>
        <RuntimeVar ApplyTo="direct/opaque.bin" Var="Byte:0x1234" Values="1"/>
        <RuntimeVar ApplyTo="direct/rejected.bin" Var="Byte:not-an-address" Values="1"/>
      </Conditional></ModInfo>"""

    with tempfile.TemporaryDirectory(prefix="lexeditor-live-variants-") as name:
        root = Path(name)
        baseline = root / "baseline"
        (baseline / "menu").mkdir(parents=True)
        (baseline / "menu" / "price.bin").write_bytes(vanilla)
        rows = [
            make_mod(root / "low", "low", 0, {
                "direct/menu/price.bin": low,
                "direct/opaque.bin": b"LOW OPAQUE",
            }),
            make_mod(root / "middle", "middle", 1, {
                "memory/direct/menu/price.bin": conditional,
                "memory/direct/opaque.bin": b"RAW MIDDLE OPAQUE",
                "memory/direct/rejected.bin": b"RAW REJECTED",
            }, xml),
            make_mod(root / "high", "high", 2, {
                "direct/menu/price.bin": high,
                "direct/opaque.bin": b"HIGH OPAQUE",
            }),
        ]
        runtime = root / "active"
        result = runtime_layout.compose(
            root / "low", runtime, rows, baseline_root=baseline,
            condition_state={"system": {}, "ffnx": {}},
        )
        manifest = json.loads((runtime / runtime_layout.COMPOSITION_FILE).read_text())
        routes = {row["logicalPath"]: row for row in manifest["liveConditionalRoutes"]}
        route = routes["direct/menu/price.bin"]
        assert route["routeVersion"] == 1
        assert route["outcomeEncoding"].startswith("condition-id bitmask")
        assert route["status"] == "ready: final variants precomposed"
        assert len(route["conditions"]) == 1 and len(route["variants"]) == 2
        assert "candidates" not in route

        false_payload = asset(runtime, route["variants"][0])
        true_payload = asset(runtime, route["variants"][1])
        assert asset(runtime, route["fallback"]) == false_payload
        # Low and high independent units survive in every outcome.  The live
        # middle change appears only in the true outcome.  High wins only the
        # sell-multiplier collision with middle.
        assert false_payload == price((10, 9, 7), (20, 6, 0))
        assert true_payload == price((10, 9, 7), (222, 6, 0))
        assert true_payload != conditional
        assert route["variants"][1]["mode"] == "semantic merge"
        conflicts = route["variants"][1]["conflicts"]
        assert any(row["winner"] == "high" and
                   row["unit"].endswith("record:1:sell_multiplier")
                   for row in conflicts)

        opaque = routes["direct/opaque.bin"]
        assert len(opaque["variants"]) == 2
        assert asset(runtime, opaque["variants"][0]) == b"HIGH OPAQUE"
        assert asset(runtime, opaque["variants"][1]) == b"HIGH OPAQUE"
        assert opaque["variants"][0]["asset"] == opaque["variants"][1]["asset"]
        assert all("asset" not in condition for condition in opaque["conditions"])

        rejected = routes["direct/rejected.bin"]
        assert rejected["status"] == "inactive: every live condition was rejected"
        assert rejected["conditions"] == [] and rejected["rejected"]
        assert rejected["variants"][0]["passThrough"] is True
        assert rejected["fallback"]["passThrough"] is True

        # Every route target is inside the atomic output and matches its
        # declared digest.  No raw conditional candidate is copied or named.
        for candidate_route in routes.values():
            assert "candidates" not in candidate_route
            for variant in [*candidate_route["variants"], candidate_route["fallback"]]:
                if "asset" not in variant:
                    continue
                payload = asset(runtime, variant)
                assert hashlib.sha256(payload).hexdigest() == variant["sha256"]
        assert not any(path.read_bytes() == conditional
                       for path in (runtime / "direct" / "lexeditor").rglob("*.*")
                       if path.is_file())
        assert not any(path.read_bytes() in {b"RAW MIDDLE OPAQUE", b"RAW REJECTED"}
                       for path in (runtime / "direct" / "lexeditor").rglob("*.*")
                       if path.is_file())
        assert not list(root.glob(".active.staging-*"))

        # An exponential outcome set is rejected before the old active tree is
        # replaced.  This is the fail-closed and atomic-update contract.
        before = (runtime / runtime_layout.COMPOSITION_FILE).read_bytes()
        old_limit = runtime_layout.MAX_LIVE_CONDITIONS_PER_PATH
        runtime_layout.MAX_LIVE_CONDITIONS_PER_PATH = 0
        try:
            try:
                runtime_layout.compose(
                    root / "low", runtime, rows, baseline_root=baseline,
                    condition_state={"system": {}, "ffnx": {}},
                )
            except ValueError as error:
                assert "condition safety limit" in str(error)
            else:
                raise AssertionError("An over-limit live route was composed")
        finally:
            runtime_layout.MAX_LIVE_CONDITIONS_PER_PATH = old_limit
        assert (runtime / runtime_layout.COMPOSITION_FILE).read_bytes() == before
        assert not list(root.glob(".active.staging-*"))

        assert runtime_layout._runtime_program_error([
            {"op": "or", "arity": 2},
        ]).endswith("underflows the postfix stack")
        assert runtime_layout._runtime_program_error([
            {"op": "unsupported", "reason": "bad input"},
        ]) == "bad input"
        assert runtime_layout._runtime_program_error([
            {"op": "var", "spec": "Byte:not-an-address", "values": "1"},
        ]).startswith("Invalid Byte address")
        assert Path(result["manifest"]).read_bytes() == before
        live_manifest = json.loads(
            (runtime / runtime_layout.LIVE_CONDITIONAL_MANIFEST).read_text()
        )
        assert live_manifest == {
            "schemaVersion": 1,
            "liveConditionalRoutes": manifest["liveConditionalRoutes"],
        }

    print("FF8 bounded live-condition final-variant composition passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

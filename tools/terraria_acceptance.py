"""Build a representative Lexeditor Terraria project with a real Windows tModLoader install.

This is intentionally a local acceptance harness, not a CI substitute. It writes a new
source project under the chosen tModLoader save root and leaves the built project/package
in place so the user can perform the final in-game load check.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "games" / "terraria" / "template"
DEFAULT_SAVE_ROOT = Path.home() / "Documents" / "My Games" / "Terraria" / "tModLoader"
DEFAULT_INSTALL_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\tModLoader")


def default_project_name() -> str:
    return "LexeditorAcceptance_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def _representative_content() -> list[tuple[str, str, dict, str, str]]:
    """Return one conservative representative for every structured-content family."""
    return [
        ("item", "AcceptanceItem", {"damage": 10, "damageClass": "Generic", "useTime": 20, "useAnimation": 20}, "Acceptance Item", "Lexeditor native acceptance item."),
        ("npc", "AcceptanceNPC", {"lifeMax": 20, "damage": 5, "defense": 1}, "Acceptance NPC", ""),
        ("projectile", "AcceptanceProjectile", {"timeLeft": 60}, "Acceptance Projectile", ""),
        ("buff", "AcceptanceBuff", {}, "Acceptance Buff", "Lexeditor acceptance buff."),
        ("tile", "AcceptanceTile", {}, "Acceptance Tile", ""),
        ("wall", "AcceptanceWall", {}, "Acceptance Wall", ""),
        ("globalItem", "AcceptanceGlobalItem", {"targetId": 2}, "", ""),
        ("globalNPC", "AcceptanceGlobalNPC", {"targetId": 1}, "", ""),
        ("globalProjectile", "AcceptanceGlobalProjectile", {"targetId": 1}, "", ""),
        ("prefix", "AcceptancePrefix", {}, "Acceptance Prefix", ""),
        ("rarity", "AcceptanceRarity", {"colorR": 255, "colorG": 0, "colorB": 255}, "", ""),
        ("biome", "AcceptanceBiome", {}, "Acceptance Biome", ""),
        ("config", "AcceptanceConfig", {"fields": "bool:AcceptanceMode=true"}, "", ""),
        ("command", "AcceptanceCommand", {"command": "lexaccept", "replyText": "Lexeditor Terraria acceptance mod loaded."}, "", ""),
        ("sceneEffect", "AcceptanceScene", {}, "", ""),
        ("dust", "AcceptanceDust", {}, "", ""),
        ("globalBuff", "AcceptanceGlobalBuff", {"targetId": 1}, "", ""),
        ("globalTile", "AcceptanceGlobalTile", {"targetId": 0}, "", ""),
        ("globalWall", "AcceptanceGlobalWall", {"targetId": 1}, "", ""),
        ("recipe", "AcceptanceRecipe", {"resultName": "AcceptanceItem", "ingredients": "vanilla:2=1"}, "", ""),
    ]


def populate_acceptance_project(project: Path) -> list[dict]:
    """Create a native project and representative structured content without building it."""
    if project.exists():
        raise ValueError(f"Acceptance project already exists: {project}")
    if not TEMPLATE_ROOT.is_dir():
        raise ValueError(f"Terraria template is missing: {TEMPLATE_ROOT}")

    # Imports are deliberately delayed so the caller can configure Terraria env vars first.
    from games.terraria.plugin import initialize_project
    from games.terraria.structured_content import create_structured_content

    try:
        shutil.copytree(TEMPLATE_ROOT, project)
        initialize_project(project)
        created = []
        for kind, name, values, display_name, description in _representative_content():
            created.append(
                create_structured_content(
                    project,
                    kind,
                    name,
                    values,
                    display_name,
                    description,
                )
            )
        return created
    except Exception:
        shutil.rmtree(project, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and native-build a representative Lexeditor Terraria mod using an installed tModLoader 1.4.4.",
    )
    parser.add_argument(
        "--install-root",
        type=Path,
        default=Path(os.environ.get("LEXEDITOR_TERRARIA_ROOT", DEFAULT_INSTALL_ROOT)),
        help="tModLoader installation root (defaults to LEXEDITOR_TERRARIA_ROOT or the standard Steam path)",
    )
    parser.add_argument(
        "--save-root",
        type=Path,
        default=Path(os.environ.get("LEXEDITOR_TERRARIA_SAVE_ROOT", DEFAULT_SAVE_ROOT)),
        help="tModLoader save root containing ModSources/ and Mods/",
    )
    parser.add_argument("--name", default=None, help="New acceptance mod name; defaults to a timestamped C# identifier")
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Create the representative project but do not invoke tModLoader",
    )
    parser.add_argument("--json", action="store_true", help="Print the final machine-readable result as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    install_root = args.install_root.expanduser().resolve()
    save_root = args.save_root.expanduser().resolve()
    name = args.name or default_project_name()
    project = save_root / "ModSources" / name

    # These must be set before importing games.terraria.server/plugin because those modules
    # intentionally resolve the configured save/install roots at import time.
    os.environ["LEXEDITOR_TERRARIA_ROOT"] = str(install_root)
    os.environ["LEXEDITOR_TERRARIA_SAVE_ROOT"] = str(save_root)
    os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)

    if os.name != "nt" and not args.generate_only:
        print("ERROR: native Terraria acceptance requires Windows; use --generate-only for source generation.", file=sys.stderr)
        return 2

    try:
        project.parent.mkdir(parents=True, exist_ok=True)
        created = populate_acceptance_project(project)
    except Exception as error:
        print(f"ERROR: could not create acceptance project: {error}", file=sys.stderr)
        return 2

    result: dict[str, object] = {
        "project": str(project),
        "managedFamilies": len(created),
        "generated": True,
        "built": False,
        "ok": True,
    }

    if args.generate_only:
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"Generated {len(created)} managed families at {project}")
        return 0

    try:
        from games.terraria import server

        status = server.build_status("nt")
        if not status.get("available"):
            raise ValueError(status.get("reason") or "native tModLoader build is unavailable")
        build = server.build_project(platform_name="nt")
    except Exception as error:
        result.update({"ok": False, "error": str(error)})
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"ERROR: native tModLoader build could not start: {error}", file=sys.stderr)
            print(f"Acceptance project was left at: {project}", file=sys.stderr)
        return 1

    result.update(
        {
            "built": bool(build.get("ok")),
            "ok": bool(build.get("ok")),
            "exitCode": build.get("exitCode"),
            "timedOut": build.get("timedOut"),
            "artifact": build.get("artifact"),
            "artifactExists": build.get("artifactExists"),
            "enabled": build.get("enabled"),
            "enabledStateValid": build.get("enabledStateValid"),
            "diagnostics": build.get("diagnostics", []),
        }
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if build.get("ok"):
            print(f"PASS: native tModLoader built all {len(created)} managed families.")
            print(f"Project:  {project}")
            print(f"Artifact: {build.get('artifact')}")
            print(f"Enabled according to enabled.json: {bool(build.get('enabled'))}")
            print()
            print("Final in-game acceptance:")
            print("  1. Launch this same tModLoader installation and enable the acceptance mod if needed.")
            print("  2. Enter a world and run /lexaccept; it should reply: Lexeditor Terraria acceptance mod loaded.")
            print("  3. With 1 Dirt Block in inventory, craft the magenta checker Acceptance Item by hand.")
            print("  4. Confirm the mod loads without a tModLoader content/asset error.")
        else:
            print("FAIL: native tModLoader did not produce a verified acceptance package.", file=sys.stderr)
            print(f"Exit code: {build.get('exitCode')}", file=sys.stderr)
            if build.get("diagnostics"):
                for diagnostic in build["diagnostics"]:
                    print(
                        f"  {diagnostic.get('severity', 'error')}: {diagnostic.get('code', '')} "
                        f"{diagnostic.get('file', '')}:{diagnostic.get('line', '')} {diagnostic.get('message', '')}",
                        file=sys.stderr,
                    )
            if build.get("stderr"):
                print(build["stderr"], file=sys.stderr)

    return 0 if build.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

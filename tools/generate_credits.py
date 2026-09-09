"""Build offline credits from reviewed attributions and unchanged original notices."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin_metadata import static_plugin_ids, validate_credits_bundle


def read(relative: str) -> str:
    path = (ROOT / relative).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ValueError(f"Invalid credit notice: {relative}")
    return path.read_text("utf-8-sig")


def generate() -> dict:
    spec = json.loads(read("ui/credits-sources.json"))
    if not isinstance(spec, dict) or spec.get("schema") != 1:
        raise ValueError("ui/credits-sources.json must use schema 1")
    recipes = spec.get("plugins")
    if not isinstance(recipes, dict):
        raise ValueError("ui/credits-sources.json must contain a plugins object")

    expected_ids = static_plugin_ids(ROOT)
    present_ids = set(recipes)
    if present_ids != expected_ids:
        missing = sorted(expected_ids - present_ids)
        unexpected = sorted(present_ids - expected_ids)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise ValueError("Credits source plugin IDs do not match discovered plugins: " + "; ".join(details))

    result = {"schema": 1, "shared": copy.deepcopy(spec["shared"]), "plugins": {}}
    for key, recipe in recipes.items():
        if not isinstance(recipe, dict):
            raise ValueError(f"Credits recipe for {key} must be an object")
        if "sameAs" in recipe:
            parent = str(recipe["sameAs"])
            if parent not in result["plugins"]:
                raise ValueError(f"Credits recipe for {key} references unavailable sameAs plugin: {parent}")
            section = copy.deepcopy(result["plugins"][parent])
        elif "source" in recipe:
            section = json.loads(read(str(recipe["source"])))
            license_root = str(recipe.get("licenseRoot", "")).rstrip("/")
            if not license_root:
                raise ValueError(f"Credits recipe for {key} needs licenseRoot when source is used")
            for notice in section.get("licenses", []):
                source_url = notice.pop("url", None)
                if not source_url:
                    raise ValueError(f"Credits source for {key} contains a license without a local notice path")
                notice["sourcePath"] = license_root + "/" + str(source_url).lstrip("/")
        else:
            section = copy.deepcopy(recipe)
        result["plugins"][key] = section

    for section in [result["shared"], *result["plugins"].values()]:
        for notice in section.get("licenses", []):
            notice["text"] = read(notice["sourcePath"])

    # This is deliberately a hard gate. A plugin with no attribution at all is
    # almost always an unfinished research pass. If it genuinely used no other
    # code, documentation, tools, or reverse-engineering work, the author must
    # say so explicitly (for example "Nobody but myself") rather than omit the
    # Credits section and make that ambiguity permanent.
    validate_credits_bundle(result, expected_ids)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated credits without writing files.")
    args = parser.parse_args(argv)
    try:
        expected = json.dumps(generate(), ensure_ascii=False, indent=2) + "\n"
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
    destination = ROOT / "ui" / "credits.json"
    if args.check:
        if not destination.is_file() or destination.read_text("utf-8") != expected:
            parser.exit(1, "Offline credits are stale. Run python tools/generate_credits.py.\n")
        return 0
    destination.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""FF7 preparation seeds only the starter template, never a project (F13).

Opening the game used to materialize a "My Mod" folder the player never
asked for. A project now appears only through the explicit Add a Mod /
Find a Mod actions (or an explicit save to the selected project path).
"""
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.ff7.kernel import Kernel, resolve_kernel  # noqa: E402
from plugins.ff7.plugin import PLUGIN, seed_project_template  # noqa: E402
from project_manager import ProjectManager  # noqa: E402
from tests.verify_ff7_datasets import write_kernel  # noqa: E402


def _game(root: Path) -> Path:
    game = root / "game"
    write_kernel(game / "ff7/workingdir/data/lang-en/kernel/kernel.bin")
    return game


def test_prepare_seeds_template_without_creating_a_project():
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        game = _game(root)
        template = root / "template"
        default = root / "mods" / "ff7" / "My Mod"
        before = {path for path in root.rglob("*")}
        seeded = seed_project_template(game, template)
        source, relative = resolve_kernel(game)
        assert seeded["relativePath"].casefold() == relative.as_posix().casefold()
        assert Kernel(template / relative).sha256 == Kernel(source).sha256
        assert (template / "README.txt").is_file()
        assert not default.exists()
        created = {path for path in root.rglob("*")} - before
        assert created, "seeding must still write the template"
        assert all(str(path).startswith(str(template)) for path in created), created


def test_missing_default_project_offers_create_not_a_phantom():
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        game = _game(root)
        template = root / "template"
        default = root / "mods" / "ff7" / "My Mod"
        seed_project_template(game, template)
        spec = replace(PLUGIN.projects, default_root=default,
                       template_root=template)
        manager = ProjectManager({"ff7": replace(PLUGIN, projects=spec)},
                                 root / "projects.json")
        initial = manager.snapshot("ff7")
        assert initial["current"] == str(default.resolve())
        assert initial["canCreate"]
        current = next(row for row in initial["projects"] if row["current"])
        assert not current["valid"]
        assert not default.exists()
        # The explicit create action still produces a working project.
        (root / "mods" / "ff7").mkdir(parents=True)
        created = manager.create("ff7", str(root / "mods" / "ff7"), "My Mod")
        _source, relative = resolve_kernel(game)
        assert Kernel(default / relative).sha256
        assert created["current"] == str(default.resolve())

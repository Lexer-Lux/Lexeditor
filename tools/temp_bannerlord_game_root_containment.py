from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


paths_file = Path("games/bannerlord/paths.py")
replace_once(
    paths_file,
    '''def clear_write_helper(path: Path) -> None:\n''',
    '''def contained_game_path(\n    game: Path,\n    *parts: str | Path,\n    require_file: bool = False,\n) -> Path:\n    """Resolve a game path without allowing a nested junction/symlink to escape."""\n    root = Path(game).resolve()\n    target = root.joinpath(*parts).resolve()\n    if target != root and root not in target.parents:\n        raise ValueError("Resolved Bannerlord game path escaped the selected game root")\n    if require_file and not target.is_file():\n        raise FileNotFoundError(target)\n    return target\n\n\ndef clear_write_helper(path: Path) -> None:\n''',
    "contained_game_path helper",
)
replace_once(
    paths_file,
    '''    game = Path(game or game_root())\n    executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"\n    if not executable.is_file():\n        problems.append(f"Missing Bannerlord executable: {executable}")\n    if not modules_root(game).is_dir():\n        problems.append(f"Missing Bannerlord Modules directory: {modules_root(game)}")\n\n''',
    '''    game = Path(game or game_root()).resolve()\n    try:\n        executable = contained_game_path(game, "bin", "Win64_Shipping_Client", "Bannerlord.exe")\n        modules = contained_game_path(game, "Modules")\n    except ValueError as error:\n        problems.append(str(error))\n    else:\n        if not executable.is_file():\n            problems.append(f"Missing Bannerlord executable: {executable}")\n        if not modules.is_dir():\n            problems.append(f"Missing Bannerlord Modules directory: {modules}")\n\n''',
    "session game-root preflight",
)

project_data = Path("games/bannerlord/project_data.py")
replace_once(
    project_data,
    '''from .paths import clear_write_helper, contained_project_path\n''',
    '''from .paths import clear_write_helper, contained_game_path, contained_project_path\n''',
    "project_data import",
)
replace_once(
    project_data,
    '''    game_bin = (selected_game / "bin" / "Win64_Shipping_Client").resolve()\n    modules_root = (selected_game / "Modules").resolve()\n''',
    '''    game_bin = contained_game_path(selected_game, "bin", "Win64_Shipping_Client")\n    modules_root = contained_game_path(selected_game, "Modules")\n''',
    "hosted build game subroots",
)

deploy_data = Path("games/bannerlord/deploy_data.py")
replace_once(
    deploy_data,
    '''    executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"\n    if not executable.is_file():\n        raise FileNotFoundError(f"Bannerlord executable not found: {executable}")\n    module_id = _module_id(project)\n    modules_root = paths.modules_root(game).resolve()\n''',
    '''    executable = paths.contained_game_path(game, "bin", "Win64_Shipping_Client", "Bannerlord.exe")\n    if not executable.is_file():\n        raise FileNotFoundError(f"Bannerlord executable not found: {executable}")\n    module_id = _module_id(project)\n    modules_root = paths.contained_game_path(game, "Modules")\n''',
    "deploy game subroots",
)

game_launch = Path("games/bannerlord/game_launch.py")
replace_once(
    game_launch,
    '''from .community_metadata import read_community_dependencies\n''',
    '''from . import paths\nfrom .community_metadata import read_community_dependencies\n''',
    "launch paths import",
)
replace_once(
    game_launch,
    '''    modules_root = game_root.resolve() / "Modules"\n    if not modules_root.is_dir():\n        raise RuntimeError(f"Bannerlord Modules folder not found: {modules_root}")\n''',
    '''    game_root = game_root.resolve()\n    try:\n        modules_root = paths.contained_game_path(game_root, "Modules")\n    except ValueError as error:\n        raise RuntimeError(str(error)) from error\n    if not modules_root.is_dir():\n        raise RuntimeError(f"Bannerlord Modules folder not found: {modules_root}")\n''',
    "launch modules root",
)
replace_once(
    game_launch,
    '''    game_root = game_root.resolve()\n    executable = game_root / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"\n    if not executable.is_file():\n        raise RuntimeError(f"Bannerlord.exe not found: {executable}")\n''',
    '''    game_root = game_root.resolve()\n    try:\n        executable = paths.contained_game_path(\n            game_root, "bin", "Win64_Shipping_Client", "Bannerlord.exe"\n        )\n    except ValueError as error:\n        raise RuntimeError(str(error)) from error\n    if not executable.is_file():\n        raise RuntimeError(f"Bannerlord.exe not found: {executable}")\n''',
    "launch executable root",
)
replace_once(
    game_launch,
    '''            cwd = game_root.resolve() / "bin" / "Win64_Shipping_Client"\n            process = self._process_factory(command, cwd=str(cwd))\n''',
    '''            cwd = Path(command[0]).parent\n            process = self._process_factory(command, cwd=str(cwd))\n''',
    "launch cwd",
)

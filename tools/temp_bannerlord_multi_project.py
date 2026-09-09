from pathlib import Path

# project_data.py
path = Path('games/bannerlord/project_data.py')
text = path.read_text(encoding='utf-8')
old = '''def _project_files(project: Path) -> list[Path]:
    return sorted(path for path in project.glob("*.csproj") if path.is_file())


def primary_project_file(project: Path) -> Path | None:
    root = project.resolve()
    files = _project_files(root)
    if not files:
        return None
    target = files[0].resolve()
    if target != root and root not in target.parents:
        raise ValueError("Project file must stay inside the selected Bannerlord project")
    if target.suffix.casefold() != ".csproj" or not target.is_file():
        raise FileNotFoundError(target)
    return target


def _resolve_project_file(project: Path, requested: str | None = None) -> Path:
    root = project.resolve()
    if requested:
        target = (root / requested).resolve()
    else:
        candidate = primary_project_file(project)
        if candidate is None:
            raise FileNotFoundError(f"No .csproj found in {project}")
        target = candidate.resolve()
'''
new = '''def _project_files(project: Path) -> list[Path]:
    return sorted(path for path in project.glob("*.csproj") if path.is_file())


def project_files(project: Path) -> list[Path]:
    """Return selectable top-level project files without following escapes."""
    root = project.resolve()
    result = []
    for candidate in _project_files(root):
        target = candidate.resolve()
        if target != root and root not in target.parents:
            raise ValueError("Project file must stay inside the selected Bannerlord project")
        if target.suffix.casefold() != ".csproj" or not target.is_file():
            raise FileNotFoundError(target)
        result.append(target)
    return result


def primary_project_file(project: Path) -> Path | None:
    files = project_files(project)
    if not files:
        return None
    if len(files) > 1:
        names = ", ".join(path.name for path in files)
        raise ValueError(f"Several .csproj files exist; select one explicitly: {names}")
    return files[0]


def resolve_project_file(project: Path, requested: str | None = None) -> Path:
    root = project.resolve()
    if requested:
        relative = Path(str(requested).replace("\\\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise ValueError("Project file selection must be a top-level .csproj filename")
        target = (root / relative).resolve()
    else:
        candidate = primary_project_file(project)
        if candidate is None:
            raise FileNotFoundError(f"No .csproj found in {project}")
        target = candidate.resolve()
'''
if text.count(old) != 1:
    raise SystemExit(f'project selection block match count {text.count(old)}')
text = text.replace(old, new, 1)
text = text.replace('project_file = _resolve_project_file(project, requested)', 'project_file = resolve_project_file(project, requested)')
path.write_text(text, encoding='utf-8')

# server.py
path = Path('games/bannerlord/server.py')
text = path.read_text(encoding='utf-8')
old = '''from .project_data import (
    primary_project_file,
    read_project_file,
    read_source,
    run_build,
    save_project_properties,
    save_source,
)
'''
new = '''from .project_data import (
    project_files,
    read_project_file,
    read_source,
    resolve_project_file,
    run_build,
    save_project_properties,
    save_source,
)
'''
if text.count(old) != 1:
    raise SystemExit(f'server import block count {text.count(old)}')
text = text.replace(old, new, 1)
old = '''def project_summary() -> dict:
    project_file = primary_project_file(PROJECT)
    return {
        "root": str(PROJECT),
        "projectFile": read_project_file(project_file) if project_file else None,
    }
'''
new = '''def project_summary(requested: str | None = None) -> dict:
    files = project_files(PROJECT)
    selected = None
    project_error = ""
    if requested:
        selected = resolve_project_file(PROJECT, requested)
    elif len(files) == 1:
        selected = files[0]
    elif len(files) > 1:
        project_error = "Several .csproj files exist; choose the project to edit/build."
    return {
        "root": str(PROJECT),
        "projectFiles": [path.name for path in files],
        "projectFile": read_project_file(selected) if selected else None,
        "projectError": project_error,
    }
'''
if text.count(old) != 1:
    raise SystemExit(f'project summary block count {text.count(old)}')
text = text.replace(old, new, 1)
old = '''        if path == "/api/project":
            try:
                self.send_json(project_summary())
'''
new = '''        if path == "/api/project":
            try:
                requested = (query.get("project") or [""])[0] or None
                self.send_json(project_summary(requested))
'''
if text.count(old) != 1:
    raise SystemExit(f'project GET block count {text.count(old)}')
text = text.replace(old, new, 1)
old = '''        if path == "/api/project/save":
            project_file = primary_project_file(PROJECT)
            if project_file is None:
                self.send_json({"error": f"No .csproj found in {PROJECT}"}, 404)
                return
            try:
                payload = self.read_json()
                self.send_json(
                    save_project_properties(project_file, dict(payload.get("edits") or {}))
                )
'''
new = '''        if path == "/api/project/save":
            try:
                payload = self.read_json()
                project_file = resolve_project_file(PROJECT, payload.get("project"))
                self.send_json(
                    save_project_properties(project_file, dict(payload.get("edits") or {}))
                )
'''
if text.count(old) != 1:
    raise SystemExit(f'project POST block count {text.count(old)}')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')

# editor_boot.js: carry exact selected project on save.
path = Path('games/bannerlord/editor_boot.js')
text = path.read_text(encoding='utf-8')
old = '          const result=await post("/api/project/save",{edits});\n'
new = '          const result=await post("/api/project/save",{project:state.project.projectFile?.name||null,edits});\n'
if text.count(old) != 1:
    raise SystemExit(f'project save UI match count {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

# editor_build.js: graceful selector for ambiguous workspaces.
path = Path('games/bannerlord/editor_build.js')
text = path.read_text(encoding='utf-8')
marker = '''  function renderBuild(){
    const project=state.project?.projectFile;
    if(!project){main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Build"),el("div",{class:"bl-empty"},"No .csproj exists in this project.")));return}
'''
replacement = '''  async function selectBuildProject(name){
    if(!name)return;
    try{
      const project=await api(`/api/project?project=${encodeURIComponent(name)}`);
      state.project=project;state.savedProject=clone(project);renderBuild();refresh();
    }catch(error){showAlert?.(String(error.message||error),"Bannerlord project selection failed")}
  }

  function renderBuild(){
    const project=state.project?.projectFile;
    if(!project){
      const files=state.project?.projectFiles||[];
      if(files.length>1){
        main.replaceChildren(el("section",{class:"bl-card"},
          el("h2",{},"Choose build project"),
          el("div",{class:"bl-list-block"},
            el("div",{class:"bl-note"},state.project?.projectError||"Several .csproj files exist. Lexeditor will not choose one alphabetically."),
            select("",[["","Choose .csproj"],...files.map(name=>[name,name])],value=>selectBuildProject(value))
          )));return
      }
      main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Build"),el("div",{class:"bl-empty"},"No .csproj exists in this project.")));return
    }
'''
if text.count(marker) != 1:
    raise SystemExit(f'renderBuild marker count {text.count(marker)}')
text = text.replace(marker, replacement, 1)
path.write_text(text, encoding='utf-8')

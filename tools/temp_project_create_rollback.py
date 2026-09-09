from pathlib import Path

path = Path('project_manager.py')
text = path.read_text(encoding='utf-8')
old = '''        shutil.copytree(
            spec.template_root, target,
            ignore=lambda _root, names: [name for name in names if name in IGNORED_NAMES],
        )
        if spec.initialize is not None:
            spec.initialize(target)
        return self.select(plugin_id, str(target))
'''
new = '''        try:
            shutil.copytree(
                spec.template_root, target,
                ignore=lambda _root, names: [name for name in names if name in IGNORED_NAMES],
            )
            if spec.initialize is not None:
                spec.initialize(target)
            return self.select(plugin_id, str(target))
        except Exception as error:
            if target.exists():
                try:
                    shutil.rmtree(target)
                except Exception as cleanup_error:
                    raise RuntimeError(
                        f"Project creation failed and the new folder could not be cleaned up: {cleanup_error}"
                    ) from error
            raise
'''
if text.count(old) != 1:
    raise SystemExit(f'project create block match count {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

"""Isolated item project state and stale-write protection."""
import hashlib
from pathlib import Path

from core.plugin_files import atomic_write
from .formats import ItemDocument, SUBTABS, TEXT_SUBTABS, ENEMY_SUBTABS, ATTACK_SUBTABS, EFFECT_TABLE, EFFECT_SUBTABS, STATS_SUBTABS, WORLD_SUBTABS, NPCS_SUBTABS, SHOPS_SUBTABS, MAX_ARCHIVE
from . import texts

RELATIVE = Path('param/GameParam/GameParam.parambnd.dcx')
MARKER = '.lexeditor-ds1-project'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


class ItemStore:
    def __init__(self, game_root, project=None, read_only=True):
        from .tweak_mods import checked
        self.game_root = checked(Path(game_root)).resolve()
        self.project = checked(Path(project)).resolve() if project else None
        self.read_only = read_only or self.project is None
        self.output = self.project / RELATIVE if self.project else None
        # The game's item names live in a second archive the mod also carries.
        self.text_output = self.project / texts.RELATIVE if self.project else None
        # The equipment defense labels live in a third one.
        self.menu_output = self.project / texts.MENU_RELATIVE if self.project else None
        self.document = None

    def writable(self):
        if self.read_only:
            raise PermissionError('Create or select a mod before editing Vanilla.')
        if self.project == self.game_root or self.game_root in self.project.parents:
            raise ValueError('The mod project must be outside the game installation.')
        from .tweak_mods import checked
        checked(self.project / MARKER)
        for output in (self.output, self.text_output, self.menu_output):
            resolved_output = checked(output).resolve()
            if self.game_root in resolved_output.parents or self.project not in resolved_output.parents:
                raise ValueError('The output path leaves the mod project or enters the installed game.')
        if not (self.project / MARKER).is_file():
            raise ValueError('Select a valid Dark Souls mod project.')

    def _vanilla_path(self):
        # Once a deployment owns the installed file, the true pristine original
        # is the preserved backup, not the now-modded installed copy. Deferred
        # import avoids a module-load cycle with deployment, which imports
        # RELATIVE/MARKER from this module.
        from . import deployment
        return deployment.vanilla_source(self.game_root)

    def load(self):
        if not self.read_only: self.writable()
        vanilla = self._vanilla_path()
        source = self.output if self.output and self.output.is_file() else vanilla
        from .tweak_mods import checked
        checked(source)
        if source.stat().st_size > MAX_ARCHIVE:
            raise ValueError('The parameter archive is too large.')
        raw = source.read_bytes()
        document = ItemDocument(raw)
        self.source = source
        self.vanilla = vanilla
        self.source_hash = hashlib.sha256(raw).hexdigest()
        self.vanilla_hash = digest(vanilla)
        self.output_hash = digest(self.output) if self.output else None
        self._load_texts(document)
        self._load_menu_texts(document)
        # A mod's saved archive is not vanilla: read the game's own once, for
        # each field's vanilla value.
        document.vanilla_document = ItemDocument(vanilla.read_bytes()) if source != vanilla else None
        self.document = document
        return document

    def _load_texts(self, document):
        """The mod's names if it has renamed anything, else the game's own. A
        game folder without the text archive simply has no renaming."""
        from . import deployment
        try:
            vanilla = deployment.vanilla_source(self.game_root, texts.RELATIVE)
        except RuntimeError:
            vanilla = None
        source = self.text_output if self.text_output and self.text_output.is_file() else vanilla
        self.text_source = source if source and source.is_file() else None
        self.text_hash = digest(self.text_source) if self.text_source else None
        self.text_output_hash = digest(self.text_output) if self.text_output else None
        document.texts = texts.TextDocument(self.text_source.read_bytes()) if self.text_source else None

    def _load_menu_texts(self, document):
        """The mod's menu labels if it has changed any, else the game's own."""
        from . import deployment
        try:
            vanilla = deployment.vanilla_source(self.game_root, texts.MENU_RELATIVE)
        except RuntimeError:
            vanilla = None
        source = self.menu_output if self.menu_output and self.menu_output.is_file() else vanilla
        self.menu_source = source if source and source.is_file() else None
        self.menu_hash = digest(self.menu_source) if self.menu_source else None
        self.menu_output_hash = digest(self.menu_output) if self.menu_output else None
        document.menu_texts = texts.MenuDocument(self.menu_source.read_bytes()) if self.menu_source else None

    def get(self):
        return self.document if self.document is not None else self.load()

    def state(self):
        document = self.get()
        return {'source': str(self.source), 'output': str(self.output or ''),
                'readOnly': self.read_only, 'dirtyCount': document.dirty_count,
                'effectsAvailable': EFFECT_TABLE in document.params,
                'effectTabs': [{'id': key, 'label': label, 'table': table,
                                'count': len(document.list_rows(key)) if EFFECT_TABLE in document.params else 0}
                               for key, label, table in EFFECT_SUBTABS],
                'enemyTabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                              for key, label, table in ENEMY_SUBTABS],
                'attackTabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                               for key, label, table in ATTACK_SUBTABS],
                'statsTabs': [{'id': key, 'label': label, 'table': table,
                               'count': len(document.list_rows(key)) if table in document.params else 0}
                              for key, label, table in STATS_SUBTABS],
                'worldTabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                              for key, label, table in WORLD_SUBTABS],
                'npcTabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                            for key, label, table in NPCS_SUBTABS],
                'shopTabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                             for key, label, table in SHOPS_SUBTABS],
                'tabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                         for key, label, table in SUBTABS],
                'textTabs': [{'id': key, 'label': label, 'table': table, 'count': len(document.list_rows(key))}
                             for key, label, table in TEXT_SUBTABS]}

    def edit(self, table, row_id, field, value, only=None):
        self.writable()
        return self.get().edit(table, row_id, field, value, only=only)

    def rename(self, table, row_id, name, only=None):
        self.writable()
        return self.get().rename(table, row_id, name, only=only)

    def add_row(self, table, row_id, new_id=None):
        self.writable()
        return self.get().add_row(table, row_id, new_id)

    def remove_row(self, table, row_id):
        self.writable()
        return self.get().remove_row(table, row_id)

    def validate_save(self):
        from .tweak_mods import checked
        self.writable()
        document = self.get()
        for path in (self.source, self._vanilla_path(), self.output):
            if path is not None:
                checked(path)
        # Apply can legitimately replace the live file while this editor stays
        # open. Compare against its verified preserved original after deployment.
        if digest(self.source) != self.source_hash or digest(self._vanilla_path()) != self.vanilla_hash:
            raise ValueError('The source changed outside Lexeditor. Reopen it before saving.')
        if digest(self.output) != self.output_hash:
            raise ValueError('The mod archive changed outside Lexeditor. Reopen it before saving.')
        if document.texts and (digest(self.text_source) != self.text_hash
                               or digest(self.text_output) != self.text_output_hash):
            raise ValueError('The item text changed outside Lexeditor. Reopen it before saving.')
        if document.menu_texts and (digest(self.menu_source) != self.menu_hash
                                    or digest(self.menu_output) != self.menu_output_hash):
            raise ValueError('The menu text changed outside Lexeditor. Reopen it before saving.')
        return document

    def save(self):
        document = self.validate_save()
        payload = document.export()
        ItemDocument(payload)
        # Text is written only once the mod has changed some; until then the
        # mod carries no text archive and the game keeps its own.
        names = document.texts.export() if document.texts and (document.texts.dirty or self.text_output.is_file()) else None
        if names is not None: texts.TextDocument(names)
        menu = document.menu_texts.export() if document.menu_texts and (document.menu_texts.dirty or self.menu_output.is_file()) else None
        if menu is not None: texts.MenuDocument(menu)
        atomic_write(self.output, payload)
        if names is not None: atomic_write(self.text_output, names)
        if menu is not None: atomic_write(self.menu_output, menu)
        self.load()
        return {'saved': True, 'path': str(self.output), 'dirtyCount': 0}

    def discard(self):
        self.load()
        return self.state()

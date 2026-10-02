"""Adapt the sprint tweak to the existing record editor and project lifecycle."""
from __future__ import annotations

from .store import ItemStore
from .sprint_settings import SprintSettings, TABLE, LABEL


class SprintDocument:
    def __init__(self, parameters, settings):
        self.parameters, self.settings = parameters, settings

    def __getattr__(self, name):
        return getattr(self.parameters, name)

    @property
    def dirty_count(self):
        return self.parameters.dirty_count + self.settings.dirty_count

    def list_rows(self, tab):
        if tab == "tweaks":
            return [{"table": TABLE, "id": 0, "name": LABEL}]
        return self.parameters.list_rows(tab)

    def read_row(self, table, row_id):
        return self.settings.row(row_id) if table == TABLE else self.parameters.read_row(table, row_id)

    def edit(self, table, row_id, field, value):
        if table == TABLE:
            return self.settings.edit(row_id, field, value)
        return self.parameters.edit(table, row_id, field, value)


class SprintItemStore(ItemStore):
    def __init__(self, game_root, project=None, read_only=True):
        # Check the original paths before ItemStore resolves them.
        self.sprint = SprintSettings(game_root, project, read_only)
        super().__init__(game_root, project, read_only)

    def get(self):
        return SprintDocument(super().get(), self.sprint)

    def save(self):
        self.writable()
        self.sprint.prepare_save()
        # A tweak-only save must not manufacture a parameter archive.
        result = {"saved": True}
        if super().get().dirty_count or not self.sprint.dirty_count:
            result = super().save()
        self.sprint.save()
        result["dirtyCount"] = self.get().dirty_count
        return result

    def discard(self):
        self.sprint.discard()
        return super().discard()

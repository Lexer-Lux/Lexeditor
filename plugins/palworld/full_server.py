"""Final Palworld loopback service surface."""

from __future__ import annotations

from dataclasses import asdict
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import dedicated_server, loader_state, palserver_process
from .build_server import Handler as BuildHandler
from .palschema import (
    PatchValidationError,
    RawPatchDocument,
    ReadOnlyPatchError,
    StalePatchError,
    field_schema,
    resolve_discovered_patch,
)
from .palschema_fields import schema_scalar_writable
from .palschema_utility import (
    UTILITY_REF_PREFIX,
    apply_existing_utility_policy,
    validate_utility_value,
)
from .server import (
    MAX_PATCH_ADDS,
    MAX_PATCH_EDITS,
    PORT,
    apply_additions,
    info_document,
    palschema_catalog_payload,
    palschema_schema_root,
    project_root,
    safe_patch_payload,
)


def _utility_safe_patch_payload(relative: str, info: dict, schema_root: Path | None) -> dict:
    payload = safe_patch_payload(relative, info, schema_root)
    return apply_existing_utility_policy(payload, schema_root)


def _utility_catalog_payload() -> dict:
    payload = palschema_catalog_payload()
    schema_root = palschema_schema_root()
    if schema_root is None:
        return payload
    info = info_document().data
    for row in payload.get("patches", []):
        if row.get("errors"):
            continue
        try:
            detail = _utility_safe_patch_payload(str(row.get("path", "")), info, schema_root)
            row["schemaBlocked"] = sum(
                record.get("schemaState") not in {"matched", "unavailable", "not-applicable"}
                for record in detail.get("records", [])
            )
        except (OSError, ValueError):
            row["schemaBlocked"] = max(1, int(row.get("schemaBlocked", 0)))
    return payload


def _validate_schema_edits_with_utility(edits: list, schema_root: Path | None) -> None:
    if schema_root is None:
        return
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            continue
        table = edit.get("table")
        field = edit.get("field")
        if not isinstance(table, str) or not isinstance(field, str):
            continue
        spec = field_schema(schema_root, table, field)
        reference = str(spec.get("reference", ""))
        if reference.startswith(UTILITY_REF_PREFIX):
            validate_utility_value(
                schema_root,
                reference,
                edit.get("value"),
                label=f"edits[{index}] {table}.{field}",
            )
            continue
        writable, reason = schema_scalar_writable(spec)
        if not writable:
            raise ValueError(f"edits[{index}] {table}.{field}: {reason}")


class Handler(BuildHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/plugin":
            self.send_json({
                "apiVersion": 1,
                "pluginId": "palworld",
                "name": "Palworld",
                "hosted": True,
                "windowHost": "webview2",
                "capabilities": [
                    "official-package-info",
                    "palschema-raw-patches",
                    "palschema-generated-schemas",
                    "palschema-add-existing-row-fields",
                    "palschema-utility-path-refs",
                    "official-package-build",
                    "official-local-workshop-deploy",
                    "official-loader-state-readonly",
                    "official-dedicated-server-deploy",
                    "official-dedicated-server-activation",
                    "data-map",
                ],
            })
            return
        if path == "/api/loader-state":
            try:
                game_value = os.environ.get("LEXEDITOR_PALWORLD_ROOT")
                game_root = Path(game_value).expanduser().resolve() if game_value else None
                package_name = str(info_document().data.get("PackageName", ""))
                payload = loader_state.status(game_root, package_name)
                payload["readOnly"] = True
                self.send_json(payload)
            except (OSError, ValueError) as error:
                self.send_json({
                    "available": False,
                    "readOnly": True,
                    "error": str(error),
                    "active": False,
                    "listed": False,
                })
            return
        if path == "/api/dedicated-server":
            try:
                payload = dedicated_server.status(project_root())
                payload["serverRunning"] = palserver_process.running()
                payload["ready"] = True
                self.send_json(payload)
            except Exception as error:
                self.send_json({
                    "ready": False,
                    "error": str(error),
                    "serverRoot": "",
                    "serverRunning": None,
                    "platformSupported": os.name == "nt",
                })
            return
        if path == "/api/palschema/patch":
            try:
                values = parse_qs(parsed.query, keep_blank_values=True)
                relative = values.get("path", [""])[0]
                self.send_json(
                    _utility_safe_patch_payload(
                        relative,
                        info_document().data,
                        palschema_schema_root(),
                    )
                )
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/palschema/catalog":
            try:
                self.send_json(_utility_catalog_payload())
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        actions = {
            "/api/dedicated-server/deploy",
            "/api/dedicated-server/remove",
            "/api/dedicated-server/enable",
            "/api/dedicated-server/revert-activation",
        }
        if path not in actions:
            super().do_POST()
            return
        if not self._same_editor_request():
            self.send_json({"error": "Only this editor may change Palworld dedicated-server deployment"}, 403)
            return
        try:
            self._action_payload()
            palserver_process.require_stopped()
            if path == "/api/dedicated-server/deploy":
                result = dedicated_server.deploy(project_root())
            elif path == "/api/dedicated-server/remove":
                result = dedicated_server.remove(project_root())
            elif path == "/api/dedicated-server/enable":
                result = dedicated_server.enable(project_root())
            else:
                result = dedicated_server.revert_activation(project_root())
            result["serverRunning"] = False
            result["ready"] = True
            self.send_json(result)
        except (
            dedicated_server.DedicatedServerOwnershipError,
            dedicated_server.DedicatedServerChangedError,
            dedicated_server.DedicatedServerRefreshError,
            palserver_process.PalServerProcessError,
        ) as error:
            self.send_json({"error": str(error)}, 409)
        except dedicated_server.DedicatedServerUnavailableError as error:
            self.send_json({"error": str(error)}, 400)
        except (OSError, RuntimeError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)

    def save_palschema_patch(self):
        try:
            payload = self.read_json()
            relative = payload.get("path")
            source_sha = payload.get("sourceSha256")
            edits = payload.get("edits", [])
            additions = payload.get("adds", [])
            if not isinstance(source_sha, str) or len(source_sha) != 64:
                raise ValueError("sourceSha256 must be the 64-character hash returned by /api/palschema/patch")
            if not isinstance(edits, list) or len(edits) > MAX_PATCH_EDITS:
                raise ValueError(f"edits must be an array of at most {MAX_PATCH_EDITS} scalar edits")
            if not isinstance(additions, list) or len(additions) > MAX_PATCH_ADDS:
                raise ValueError(f"adds must be an array of at most {MAX_PATCH_ADDS} schema-backed additions")
            info = info_document().data
            schema_root = palschema_schema_root()
            target = resolve_discovered_patch(project_root(), info, relative, schema_root=schema_root)
            document = RawPatchDocument.load(target, schema_root=schema_root)
            _validate_schema_edits_with_utility(edits, schema_root)
            document.apply_edits(edits)
            apply_additions(document, additions, schema_root)
            document.save(expected_sha256=source_sha)
            self.send_json(_utility_safe_patch_payload(relative, info, schema_root))
        except PatchValidationError as error:
            self.send_json({"error": str(error), "issues": [asdict(issue) for issue in error.issues]}, 400)
        except ReadOnlyPatchError as error:
            self.send_json({"error": str(error)}, 400)
        except StalePatchError as error:
            self.send_json({"error": str(error)}, 409)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

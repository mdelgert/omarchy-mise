"""Portable checks for `manifest.json`.

Omarchy's own `omarchy-plugin-validate` stays authoritative; this runs the same
shape of checks anywhere, including CI where Omarchy is not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from . import paths

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
VERSION_PATTERN = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z"
)
REQUIRED_TEXT_FIELDS = ("id", "name", "version", "author", "license", "description")
ENTRY_KEYS = {
    "bar-widget": "barWidget",
    "bar": "bar",
    "overlay": "overlay",
    "panel": "panel",
    "menu": "menu",
    "service": "service",
}


class ManifestError(ValueError):
    """Raised when the manifest would be rejected by Omarchy."""


def manifest_path(root: Path | None = None) -> Path:
    return (root or paths.repo_root()) / "manifest.json"


def read(root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(root)
    try:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read {path}: {error}") from error
    if not isinstance(document, dict):
        raise ManifestError("manifest.json must contain an object")
    return document


def validate(root: Path | None = None) -> dict[str, Any]:
    """Return the manifest, raising ManifestError on the first problem."""
    base = root or paths.repo_root()
    document = read(base)

    if document.get("schemaVersion") != 1:
        raise ManifestError("schemaVersion must be 1")

    for field in REQUIRED_TEXT_FIELDS:
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"{field} must be non-empty text")

    plugin_id = document["id"]
    if not ID_PATTERN.fullmatch(plugin_id) or ".." in plugin_id:
        raise ManifestError("id must be a safe namespaced identifier")
    if plugin_id.startswith("omarchy."):
        raise ManifestError("the omarchy.* namespace is reserved")
    if not VERSION_PATTERN.fullmatch(document["version"]):
        raise ManifestError("version must use semantic versioning")

    kinds = document.get("kinds")
    if not isinstance(kinds, list) or not kinds or len(kinds) != len(set(kinds)):
        raise ManifestError("kinds must be a non-empty list without duplicates")

    entries = document.get("entryPoints")
    if not isinstance(entries, dict):
        raise ManifestError("entryPoints must be an object")

    for kind in kinds:
        entry_key = ENTRY_KEYS.get(kind)
        if entry_key is None:
            raise ManifestError(f"unsupported plugin kind: {kind}")
        relative = entries.get(entry_key)
        if not isinstance(relative, str) or not relative.endswith(".qml"):
            raise ManifestError(f"{kind} requires a QML entry point named {entry_key}")
        target = Path(relative)
        if target.is_absolute() or ".." in target.parts or not (base / target).is_file():
            raise ManifestError(f"unsafe or missing entry point: {relative}")

    return document

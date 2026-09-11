#!/usr/bin/env python3
"""Run portable checks for the Omarchy plugin manifest."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "manifest.json"
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
VERSION_PATTERN = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z"
)
ENTRY_KEYS = {
    "bar-widget": "barWidget",
    "bar": "bar",
    "overlay": "overlay",
    "panel": "panel",
    "menu": "menu",
    "service": "service",
}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as stream:
            manifest = json.load(stream)

        if manifest.get("schemaVersion") != 1:
            fail("schemaVersion must be 1")

        for field in ("id", "name", "version", "author", "license", "description"):
            value = manifest.get(field)
            if not isinstance(value, str) or not value.strip():
                fail(f"{field} must be non-empty text")

        plugin_id = manifest["id"]
        if not ID_PATTERN.fullmatch(plugin_id) or ".." in plugin_id:
            fail("id must be a safe namespaced identifier")
        if plugin_id.startswith("omarchy."):
            fail("the omarchy.* namespace is reserved")
        if not VERSION_PATTERN.fullmatch(manifest["version"]):
            fail("version must use semantic versioning")

        kinds = manifest.get("kinds")
        if not isinstance(kinds, list) or not kinds or len(kinds) != len(set(kinds)):
            fail("kinds must be a non-empty list without duplicates")
        entries = manifest.get("entryPoints")
        if not isinstance(entries, dict):
            fail("entryPoints must be an object")

        for kind in kinds:
            entry_key = ENTRY_KEYS.get(kind)
            if entry_key is None:
                fail(f"unsupported plugin kind: {kind}")
            relative = entries.get(entry_key)
            if not isinstance(relative, str) or not relative.endswith(".qml"):
                fail(f"{kind} requires a QML entry point named {entry_key}")
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
                fail(f"unsafe or missing entry point: {relative}")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"manifest validation failed: {error}", file=sys.stderr)
        return 1

    print(f"manifest validation passed: {manifest['id']} {manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

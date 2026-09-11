from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from omarchy_mise import manifest, paths

VALID = {
    "schemaVersion": 1,
    "id": "io.github.example.plugin",
    "name": "Example",
    "version": "0.1.0",
    "author": "Example Author",
    "license": "MIT",
    "description": "Example plugin.",
    "kinds": ["bar-widget"],
    "entryPoints": {"barWidget": "Main.qml"},
}


class ManifestTests(unittest.TestCase):
    def build(self, document: object, *, entry_point: bool = True) -> Path:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "manifest.json").write_text(json.dumps(document), encoding="utf-8")
        if entry_point:
            (root / "Main.qml").write_text("import QtQuick\nItem {}\n", encoding="utf-8")
        return root

    def assertRejects(self, document: object, fragment: str, *, entry_point: bool = True) -> None:
        root = self.build(document, entry_point=entry_point)
        with self.assertRaises(manifest.ManifestError) as caught:
            manifest.validate(root)
        self.assertIn(fragment, str(caught.exception))

    def test_accepts_a_valid_manifest(self) -> None:
        document = manifest.validate(self.build(copy.deepcopy(VALID)))
        self.assertEqual("io.github.example.plugin", document["id"])

    def test_repository_manifest_is_valid(self) -> None:
        document = manifest.validate(paths.repo_root())
        self.assertEqual("io.github.mdelgert.omarchy-mise", document["id"])

    def test_rejects_the_reserved_namespace(self) -> None:
        document = copy.deepcopy(VALID) | {"id": "omarchy.example"}
        self.assertRejects(document, "namespace is reserved")

    def test_rejects_a_traversing_identifier(self) -> None:
        self.assertRejects(copy.deepcopy(VALID) | {"id": "a..b"}, "safe namespaced identifier")

    def test_rejects_a_non_semver_version(self) -> None:
        self.assertRejects(copy.deepcopy(VALID) | {"version": "1.0"}, "semantic versioning")

    def test_rejects_a_missing_entry_point_file(self) -> None:
        self.assertRejects(copy.deepcopy(VALID), "missing entry point", entry_point=False)

    def test_rejects_an_escaping_entry_point(self) -> None:
        document = copy.deepcopy(VALID)
        document["entryPoints"] = {"barWidget": "../Main.qml"}
        self.assertRejects(document, "unsafe or missing entry point")

    def test_rejects_duplicate_kinds(self) -> None:
        document = copy.deepcopy(VALID) | {"kinds": ["bar-widget", "bar-widget"]}
        self.assertRejects(document, "without duplicates")

    def test_rejects_an_unknown_kind(self) -> None:
        document = copy.deepcopy(VALID)
        document["kinds"] = ["teapot"]
        self.assertRejects(document, "unsupported plugin kind")

    def test_rejects_a_blank_required_field(self) -> None:
        self.assertRejects(copy.deepcopy(VALID) | {"author": "  "}, "author must be non-empty")

    def test_rejects_a_wrong_schema_version(self) -> None:
        self.assertRejects(copy.deepcopy(VALID) | {"schemaVersion": 2}, "schemaVersion must be 1")

    def test_rejects_a_non_object_document(self) -> None:
        self.assertRejects([1, 2, 3], "must contain an object")

    def test_reports_unreadable_json(self) -> None:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "manifest.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(root)


if __name__ == "__main__":
    unittest.main()

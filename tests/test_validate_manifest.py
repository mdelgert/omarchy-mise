from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/python/validate_manifest.py"
SPEC = importlib.util.spec_from_file_location("validate_manifest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

VALID_MANIFEST = {
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


class ManifestValidatorTests(unittest.TestCase):
    def run_validator(self, manifest: dict[str, object], *, entry_point: bool = True) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            if entry_point:
                (root / "Main.qml").write_text("import QtQuick\nItem {}\n", encoding="utf-8")

            output = StringIO()
            with (
                mock.patch.object(VALIDATOR, "ROOT", root),
                mock.patch.object(VALIDATOR, "MANIFEST_PATH", manifest_path),
                redirect_stdout(output),
                redirect_stderr(output),
            ):
                status = VALIDATOR.main()
            return status, output.getvalue()

    def test_accepts_valid_manifest(self) -> None:
        status, output = self.run_validator(copy.deepcopy(VALID_MANIFEST))
        self.assertEqual(0, status)
        self.assertIn("manifest validation passed", output)

    def test_rejects_reserved_identifier(self) -> None:
        manifest = copy.deepcopy(VALID_MANIFEST)
        manifest["id"] = "omarchy.example"
        status, output = self.run_validator(manifest)
        self.assertEqual(1, status)
        self.assertIn("namespace is reserved", output)

    def test_rejects_missing_entry_point(self) -> None:
        status, output = self.run_validator(copy.deepcopy(VALID_MANIFEST), entry_point=False)
        self.assertEqual(1, status)
        self.assertIn("missing entry point", output)


if __name__ == "__main__":
    unittest.main()

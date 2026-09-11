from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from omarchy_mise import catalog, paths

TASKS_DIR = paths.repo_root() / "tasks"

#: Values `run.confirm_risk` is meaningfully compared against.
RISK_LEVELS = {"low", "medium", "high"}


def task_files() -> list[Path]:
    return sorted(p for p in TASKS_DIR.glob("*.toml") if not p.name.endswith(".meta.toml"))


def read(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


class TaskMetadataTests(unittest.TestCase):
    """The plugin scans for mise projects, so it renders this repository's own
    tasks. A task missing from its sidecar shows up blank in the widget, and the
    two files drift easily — so the pairing is checked rather than just documented.
    """

    def test_there_is_at_least_one_task_file(self) -> None:
        self.assertTrue(task_files(), "no task files found; the glob is wrong")

    def test_every_task_file_has_a_sidecar(self) -> None:
        for path in task_files():
            with self.subTest(path.name):
                self.assertTrue(path.with_suffix(".meta.toml").is_file())

    def test_every_task_has_metadata(self) -> None:
        for path in task_files():
            sidecar = path.with_suffix(".meta.toml")
            declared = set(read(path))
            annotated = set(read(sidecar).get("_", {}).get("tasks", {}))
            with self.subTest(path.name):
                self.assertEqual(
                    set(),
                    declared - annotated,
                    f"tasks missing from {sidecar.name}",
                )
                self.assertEqual(
                    set(),
                    annotated - declared,
                    f"{sidecar.name} annotates tasks that no longer exist",
                )

    def test_metadata_uses_known_values(self) -> None:
        for path in task_files():
            sidecar = path.with_suffix(".meta.toml")
            for name, meta in read(sidecar)["_"]["tasks"].items():
                with self.subTest(name):
                    self.assertIn(meta.get("risk"), RISK_LEVELS)
                    self.assertTrue(meta.get("icon"), "icon must be non-empty")
                    self.assertTrue(meta.get("tags"), "tags must be non-empty")

    def test_the_catalog_resolves_metadata_for_every_task(self) -> None:
        # The end-to-end version of the checks above: what the widget would see.
        metadata = catalog.read_metadata(paths.repo_root())
        for path in task_files():
            for name in read(path):
                with self.subTest(name):
                    self.assertIn(name, metadata)


if __name__ == "__main__":
    unittest.main()

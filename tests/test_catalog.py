from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from omarchy_mise import catalog, config


def make_project(root: Path, name: str, body: str = "") -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "mise.toml").write_text(body, encoding="utf-8")
    return project


def trust(root: Path) -> mock._patch_dict:
    """Trust temporary configs for the duration of a test.

    mise refuses to load an untrusted config, which is the behaviour
    TrustTests exercises deliberately; every other test needs it out of the way.
    """
    return mock.patch.dict(os.environ, {"MISE_TRUSTED_CONFIG_PATHS": str(root)})


class ProjectDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_finds_a_project_at_the_top_level(self) -> None:
        project = make_project(self.root, "alpha")
        self.assertEqual([project], catalog.find_projects(self.root, max_depth=2))

    def test_finds_a_nested_project_within_the_depth_limit(self) -> None:
        project = make_project(self.root, "work/beta")
        self.assertEqual([project], catalog.find_projects(self.root, max_depth=2))

    def test_respects_the_depth_limit(self) -> None:
        make_project(self.root, "a/b/c/deep")
        self.assertEqual([], catalog.find_projects(self.root, max_depth=2))

    def test_does_not_descend_into_a_project(self) -> None:
        outer = make_project(self.root, "outer")
        make_project(outer, "inner")
        self.assertEqual([outer], catalog.find_projects(self.root, max_depth=3))

    def test_skips_pruned_and_hidden_directories(self) -> None:
        make_project(self.root, "node_modules/pkg")
        make_project(self.root, ".hidden/pkg")
        self.assertEqual([], catalog.find_projects(self.root, max_depth=3))

    def test_ignores_symlinked_directories_by_default(self) -> None:
        target = make_project(self.root / "elsewhere", "gamma")
        (self.root / "link").symlink_to(target.parent, target_is_directory=True)

        # A symlinked child is skipped, so scanning the parent finds only the
        # real path...
        self.assertEqual(
            [target], catalog.find_projects(self.root, max_depth=3, follow_symlinks=False)
        )
        # ...while following symlinks reaches it through the link as well.
        followed = catalog.find_projects(self.root, max_depth=3, follow_symlinks=True)
        self.assertIn(self.root / "link" / "gamma", followed)

    def test_recognises_a_task_directory_only_project(self) -> None:
        project = self.root / "delta"
        (project / "mise-tasks").mkdir(parents=True)
        self.assertTrue(catalog.is_project(project))


class MetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_reads_metadata_from_the_root_config(self) -> None:
        project = make_project(self.root, "alpha", '[_.tasks."build"]\nicon = "hammer"\n')
        metadata = catalog.read_metadata(project)
        self.assertEqual("hammer", metadata["build"]["icon"])
        self.assertTrue(metadata["build"]["_source"].endswith("mise.toml"))

    def test_sidecar_metadata_wins_over_the_root_config(self) -> None:
        project = make_project(self.root, "alpha", '[_.tasks."build"]\nrisk = "low"\n')
        (project / "tasks").mkdir()
        (project / "tasks" / "x.meta.toml").write_text(
            '[_.tasks."build"]\nrisk = "high"\n', encoding="utf-8"
        )
        self.assertEqual("high", catalog.read_metadata(project)["build"]["risk"])

    def test_missing_metadata_is_empty_not_an_error(self) -> None:
        project = make_project(self.root, "alpha")
        self.assertEqual({}, catalog.read_metadata(project))

    def test_malformed_metadata_is_skipped(self) -> None:
        project = make_project(self.root, "alpha", "[_.tasks.build\n")
        self.assertEqual({}, catalog.read_metadata(project))


class FilterTests(unittest.TestCase):
    def settings(self, **overrides: object) -> dict[str, object]:
        values = dict(config.DEFAULTS["tasks"])
        values.update(overrides)
        return values

    def test_hidden_tasks_are_dropped_by_default(self) -> None:
        self.assertFalse(catalog.keep_task({"name": "x", "hide": True}, self.settings()))
        self.assertTrue(catalog.keep_task({"name": "x", "hide": True}, self.settings(hidden=True)))

    def test_include_is_an_allowlist(self) -> None:
        settings = self.settings(include=["build:*"])
        self.assertTrue(catalog.keep_task({"name": "build:web"}, settings))
        self.assertFalse(catalog.keep_task({"name": "test:web"}, settings))

    def test_exclude_applies_after_include(self) -> None:
        settings = self.settings(include=["build:*"], exclude=["*:secret"])
        self.assertFalse(catalog.keep_task({"name": "build:secret"}, settings))


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def settings(self, **scan: object) -> dict:
        resolved = config.defaults()
        resolved["scan"].update(scan)
        resolved["_warnings"] = []
        resolved["_source"] = None
        return resolved

    def test_warns_when_no_configured_directory_exists(self) -> None:
        payload = catalog.build(self.settings(directories=[str(self.root / "absent")]))
        self.assertEqual(0, payload["projectCount"])
        self.assertTrue(any("no configured scan directory" in w for w in payload["warnings"]))

    def test_records_a_project_error_without_failing_the_catalog(self) -> None:
        make_project(self.root, "broken", "this is not valid toml\n")
        with trust(self.root):
            payload = catalog.build(self.settings(directories=[str(self.root)]))
        self.assertEqual(1, payload["projectCount"])
        self.assertIn("error", payload["projects"][0])
        self.assertTrue(payload["warnings"])

    def test_collects_tasks_and_metadata_from_a_real_project(self) -> None:
        make_project(
            self.root,
            "alpha",
            '[tasks.greet]\nrun = "echo hi"\n\n[_.tasks.greet]\nicon = "hand"\n',
        )
        with trust(self.root):
            payload = catalog.build(self.settings(directories=[str(self.root)]))
        tasks = payload["projects"][0]["tasks"]
        self.assertEqual(["greet"], [task["name"] for task in tasks])
        self.assertEqual("hand", tasks[0]["metadata"]["icon"])

    def test_max_tasks_truncates_and_warns(self) -> None:
        make_project(
            self.root,
            "alpha",
            '[tasks.one]\nrun = "true"\n\n[tasks.two]\nrun = "true"\n',
        )
        settings = self.settings(directories=[str(self.root)])
        settings["ui"]["max_tasks"] = 1
        with trust(self.root):
            payload = catalog.build(settings)
        self.assertEqual(1, payload["taskCount"])
        self.assertTrue(any("truncated" in w for w in payload["warnings"]))


class TrustTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_untrusted_project_is_reported_not_trusted(self) -> None:
        # mise refuses to read a config the user has not trusted. The catalog
        # must surface that as a state the user can act on, never trust it.
        make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hi"\n')
        settings = config.defaults()
        settings["scan"]["directories"] = [str(self.root)]
        settings["_warnings"] = []
        settings["_source"] = None

        refusal = catalog.UntrustedProject("config not trusted; run `mise trust /x`")
        with mock.patch.object(catalog, "read_tasks", side_effect=refusal):
            payload = catalog.build(settings)

        project = payload["projects"][0]
        self.assertFalse(project["trusted"])
        self.assertIn("mise trust", project["error"])
        self.assertEqual([], project["tasks"])
        self.assertTrue(any("not trusted" in item for item in payload["warnings"]))

    def test_trust_refusal_is_detected_from_mise_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["mise"],
            returncode=1,
            stdout="",
            stderr="mise ERROR Config files in /x/mise.toml are not trusted.\n",
        )
        with (
            mock.patch.object(catalog.subprocess, "run", return_value=completed),
            self.assertRaises(catalog.UntrustedProject),
        ):
            catalog.read_tasks(self.root)

    def test_useful_error_strips_mise_boilerplate(self) -> None:
        stderr = (
            "mise ERROR error parsing config file: /x/mise.toml\n"
            "mise ERROR Config files in /x/mise.toml are not trusted.\n"
            "mise ERROR Version: 2026.9.1 linux-x64\n"
            "mise ERROR Run with --verbose for more information\n"
        )
        self.assertEqual(
            "Config files in /x/mise.toml are not trusted.", catalog._useful_error(stderr)
        )


if __name__ == "__main__":
    unittest.main()

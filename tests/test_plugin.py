"""Installing the plugin.

The desktop commands are patched out, so what is under test is the filesystem
work: the symlink and the starter config. That part runs everywhere, which is
why it is worth a test rather than a manual check on one machine.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from omarchy_mise import paths, plugin


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(
            mock.patch.dict(
                os.environ,
                {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config")},
            )
        )
        # `--config` and the test override both win over the XDG location, and
        # this test is about the XDG location.
        os.environ.pop(paths.CONFIG_ENV, None)
        # Talks to a running shell, which a test has no business doing.
        self.enterContext(mock.patch.object(plugin, "rescan"))

    @property
    def config(self) -> Path:
        return self.home / ".config" / "omarchy-mise" / "config.toml"

    def test_install_writes_a_starter_config(self) -> None:
        # Nothing else in the install path creates one, so without this a first
        # install runs on the built-in defaults with no file to edit.
        message = plugin.install(enable=False)
        self.assertTrue(self.config.is_file())
        self.assertIn(str(self.config), message)
        self.assertIn("[scan]", self.config.read_text(encoding="utf-8"))

    def test_a_customised_config_survives_a_reinstall(self) -> None:
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text('[scan]\ndirectories = ["~/mine"]\n', encoding="utf-8")

        message = plugin.install(enable=False)

        self.assertEqual('[scan]\ndirectories = ["~/mine"]\n', self.config.read_text())
        # Nothing was written, so nothing is claimed.
        self.assertNotIn("wrote", message)

    def test_an_unwritable_config_does_not_fail_the_install(self) -> None:
        with mock.patch.object(
            plugin.config_module, "write_default", side_effect=OSError("read-only")
        ):
            message = plugin.install(enable=False)

        self.assertIn("linked:", message)
        self.assertIn("read-only", message)
        self.assertTrue(plugin.install_path().is_symlink())


class DoctorScanDirectoryTests(unittest.TestCase):
    """`scan.directories` has no built-in default, so an unconfigured plugin is
    the state every fresh install starts in. Reporting that as a failing check
    made `doctor` exit 1 on a working install, which is the "broken plugin"
    signal the empty default exists to avoid. A directory that was named and is
    not there is still a failure.
    """

    def _scan_check(self, config: str | None) -> dict[str, object]:
        home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        target = home / "config.toml"
        if config is not None:
            target.write_text(config, encoding="utf-8")
        self.enterContext(mock.patch.dict(os.environ, {paths.CONFIG_ENV: str(target)}))
        report = plugin.doctor()
        return next(item for item in report["checks"] if item["check"] == "scan directories")

    def test_nothing_configured_is_a_warning(self) -> None:
        check = self._scan_check(None)
        self.assertIsNone(check["ok"])
        self.assertIn("none configured", str(check["detail"]))

    def test_a_named_directory_that_is_missing_still_fails(self) -> None:
        check = self._scan_check('[scan]\ndirectories = ["~/definitely-not-here"]\n')
        self.assertIs(False, check["ok"])
        self.assertIn("none of the configured directories exist", str(check["detail"]))


if __name__ == "__main__":
    unittest.main()

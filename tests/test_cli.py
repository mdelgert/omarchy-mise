from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from omarchy_mise import cli, paths


class CliTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = cli.main(list(argv))
        return status, out.getvalue(), err.getvalue()

    def test_validate_reports_the_repository_manifest(self) -> None:
        status, out, _ = self.run_cli("validate")
        self.assertEqual(cli.EXIT_OK, status)
        self.assertIn("manifest ok:", out)

    def test_manifest_prints_a_single_field(self) -> None:
        status, out, _ = self.run_cli("manifest", "id")
        self.assertEqual(cli.EXIT_OK, status)
        self.assertEqual("io.github.mdelgert.omarchy-mise", out.strip())

    def test_manifest_rejects_an_unknown_field(self) -> None:
        status, _, err = self.run_cli("manifest", "nope")
        self.assertEqual(cli.EXIT_FAILURE, status)
        self.assertIn("no such manifest field", err)

    def test_config_emits_json(self) -> None:
        status, out, _ = self.run_cli("--json", "config")
        self.assertEqual(cli.EXIT_OK, status)
        self.assertIn("ui", json.loads(out))

    def test_config_honours_an_explicit_path(self) -> None:
        status, out, _ = self.run_cli(
            "config", "--config", str(paths.repo_root() / "config.example.toml")
        )
        self.assertEqual(cli.EXIT_OK, status)
        self.assertEqual([], json.loads(out)["_warnings"])

    def test_config_init_writes_and_does_not_clobber(self) -> None:
        target = Path(self.enterContext(tempfile.TemporaryDirectory())) / "nested" / "config.toml"
        status, out, _ = self.run_cli("config", "--init", "--config", str(target))
        self.assertEqual(cli.EXIT_OK, status)
        self.assertTrue(target.is_file())
        self.assertIn(str(target), out)

        target.write_text("# edited by the user\n", encoding="utf-8")
        self.run_cli("config", "--init", "--config", str(target))
        self.assertEqual("# edited by the user\n", target.read_text(encoding="utf-8"))

    def test_config_init_force_overwrites(self) -> None:
        target = Path(self.enterContext(tempfile.TemporaryDirectory())) / "config.toml"
        target.write_text("# edited\n", encoding="utf-8")
        self.run_cli("config", "--init", "--force", "--config", str(target))
        self.assertIn("schema_version", target.read_text(encoding="utf-8"))

    def test_bad_config_exits_nonzero_with_a_message(self) -> None:
        target = Path(self.enterContext(tempfile.TemporaryDirectory())) / "config.toml"
        target.write_text("[scan]\nmax_depth = 0\n", encoding="utf-8")
        status, _, err = self.run_cli("config", "--config", str(target))
        self.assertEqual(cli.EXIT_FAILURE, status)
        self.assertIn("scan.max_depth", err)

    def test_paths_lists_the_xdg_locations(self) -> None:
        status, out, _ = self.run_cli("paths")
        self.assertEqual(cli.EXIT_OK, status)
        self.assertEqual({"repo", "config", "cache", "state", "plugins"}, set(json.loads(out)))


if __name__ == "__main__":
    unittest.main()

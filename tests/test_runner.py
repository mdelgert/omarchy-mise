from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from omarchy_mise import cli, config, runner

# These tests run mise for real: a runner that is only ever tested against a
# fake process proves nothing about killing a process tree or bounding a pipe.
# The projects are temporary and hold no [tools], so nothing is installed and
# every task is a shell one-liner.


def make_project(root: Path, name: str, body: str) -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "mise.toml").write_text(body, encoding="utf-8")
    return project


def trust(root: Path) -> mock._patch_dict:
    """Trust temporary configs for the duration of a test, as test_catalog does."""
    return mock.patch.dict(os.environ, {"MISE_TRUSTED_CONFIG_PATHS": str(root)})


def settings(**run_overrides: object) -> dict:
    resolved = config.defaults()
    resolved["run"].update(run_overrides)
    resolved["_warnings"] = []
    resolved["_source"] = None
    return resolved


class RunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(trust(self.root))


class SuccessTests(RunnerTestCase):
    def test_a_successful_task_reports_ok_and_its_output(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        result = runner.run(project, "greet", settings=settings())

        self.assertTrue(result["ok"])
        self.assertEqual("succeeded", result["status"])
        self.assertEqual(0, result["exitCode"])
        self.assertIn("hello", result["stdout"])
        self.assertFalse(result["timedOut"])
        self.assertFalse(result["truncated"])
        self.assertIsNone(result["error"])
        self.assertGreaterEqual(result["durationSeconds"], 0.0)
        self.assertEqual("greet", result["task"])
        self.assertEqual(str(project), result["project"])

    def test_the_command_is_an_argv_array_not_a_shell_string(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        result = runner.run(project, "greet", settings=settings())

        self.assertEqual(
            ["--cd", str(project), "run", "greet"],
            result["argv"][1:],
            "argv must stay a list; the binary is resolved from PATH",
        )
        self.assertTrue(result["argv"][0].endswith("mise"))

    def test_arguments_are_passed_through_verbatim(self) -> None:
        # A single argv element containing spaces and shell metacharacters must
        # arrive as one argument, not as something the shell re-splits or runs.
        project = make_project(
            self.root,
            "alpha",
            '[tasks.echo1]\nrun = "echo \\"$1\\""\n',
        )
        payload = "a b; echo pwned"
        result = runner.run(project, "echo1", [payload], settings=settings())

        self.assertEqual(payload, result["argv"][-1])
        self.assertIn(payload, result["stdout"])
        self.assertNotIn("pwned\n", result["stdout"].replace(payload, ""))

    def test_the_result_is_json_serialisable(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        result = runner.run(project, "greet", settings=settings())
        self.assertEqual(result, json.loads(json.dumps(result)))


class FailureTests(RunnerTestCase):
    def test_a_non_zero_exit_is_a_result_not_an_exception(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.boom]\nrun = "echo nope >&2; exit 3"\n')
        result = runner.run(project, "boom", settings=settings())

        self.assertFalse(result["ok"])
        self.assertEqual("failed", result["status"])
        self.assertEqual(3, result["exitCode"])
        self.assertFalse(result["timedOut"])
        self.assertIn("nope", result["stderr"])
        self.assertIn("exited 3", result["error"])


class TimeoutTests(RunnerTestCase):
    def test_a_slow_task_times_out_and_is_reported_distinctly(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.slow]\nrun = "sleep 30"\n')
        started = time.monotonic()
        result = runner.run(project, "slow", settings=settings(timeout_seconds=1))
        elapsed = time.monotonic() - started

        self.assertTrue(result["timedOut"])
        self.assertEqual("timedOut", result["status"])
        self.assertFalse(result["ok"])
        self.assertNotEqual(0, result["exitCode"])
        self.assertIn("timed out", result["error"])
        self.assertEqual(1.0, result["timeoutSeconds"])
        self.assertLess(elapsed, 20, "the task outlived its deadline")

    def test_the_timeout_argument_overrides_the_configured_one(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.slow]\nrun = "sleep 30"\n')
        result = runner.run(project, "slow", settings=settings(timeout_seconds=300), timeout=1)
        self.assertTrue(result["timedOut"])
        self.assertEqual(1.0, result["timeoutSeconds"])

    def test_a_timeout_kills_the_children_the_task_started(self) -> None:
        # The task backgrounds a grandchild that would create a marker after
        # the deadline. If the whole process group is signalled the marker
        # never appears; if only the direct child is killed, it does.
        marker = self.root / "orphan-marker"
        project = make_project(
            self.root,
            "alpha",
            f'[tasks.spawner]\nrun = "(sleep 3; touch {marker}) & sleep 30"\n',
        )
        result = runner.run(project, "spawner", settings=settings(), timeout=1)

        self.assertTrue(result["timedOut"])
        time.sleep(4)
        self.assertFalse(marker.exists(), "a grandchild outlived the run")

    def test_a_background_child_holding_the_pipes_cannot_hang_the_run(self) -> None:
        # The task exits at once but leaves a child with the pipes still open.
        # Waiting on the readers forever would hang the caller, so the run ends
        # the process group it owns instead.
        project = make_project(self.root, "alpha", '[tasks.daemon]\nrun = "sleep 30 & echo up"\n')
        with mock.patch.object(runner, "DRAIN_JOIN_SECONDS", 0.5):
            started = time.monotonic()
            result = runner.run(project, "daemon", settings=settings())
            elapsed = time.monotonic() - started

        self.assertTrue(result["ok"])
        self.assertIn("up", result["stdout"])
        self.assertLess(elapsed, 15, "the run waited for a process it had already outlived")

    def test_a_nonsensical_timeout_is_an_error_not_a_run(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        with self.assertRaises(runner.RunError):
            runner.run(project, "greet", settings=settings(), timeout=0)


class RiskTests(RunnerTestCase):
    BODY = '[tasks.danger]\nrun = "echo boom"\n\n[_.tasks.danger]\nrisk = "high"\n'

    def test_a_high_risk_task_is_refused_without_confirmation(self) -> None:
        project = make_project(self.root, "alpha", self.BODY)
        result = runner.run(project, "danger", settings=settings())

        self.assertFalse(result["ok"])
        self.assertEqual("refused", result["status"])
        self.assertEqual("confirmation-required", result["reason"])
        self.assertTrue(result["confirmationRequired"])
        self.assertEqual("high", result["risk"])
        self.assertIn("--confirm", result["error"])
        self.assertEqual([], result["argv"], "nothing may be spawned for a refusal")
        self.assertEqual("", result["stdout"])

    def test_a_high_risk_task_runs_once_confirmed(self) -> None:
        project = make_project(self.root, "alpha", self.BODY)
        result = runner.run(project, "danger", settings=settings(), confirm=True)

        self.assertTrue(result["ok"])
        self.assertEqual("high", result["risk"])
        self.assertIn("boom", result["stdout"])

    def test_confirm_risk_is_what_decides_which_risks_need_confirming(self) -> None:
        project = make_project(self.root, "alpha", self.BODY)
        self.assertTrue(runner.run(project, "danger", settings=settings(confirm_risk=[]))["ok"])

        low = make_project(
            self.root, "beta", '[tasks.mild]\nrun = "true"\n\n[_.tasks.mild]\nrisk = "low"\n'
        )
        refused = runner.run(low, "mild", settings=settings(confirm_risk=["low"]))
        self.assertEqual("confirmation-required", refused["reason"])

    def test_a_task_without_risk_metadata_just_runs(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        result = runner.run(project, "greet", settings=settings())
        self.assertTrue(result["ok"])
        self.assertIsNone(result["risk"])


class ValidationTests(RunnerTestCase):
    def test_an_unknown_task_is_refused(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        result = runner.run(project, "nope", settings=settings())

        self.assertFalse(result["ok"])
        self.assertEqual("unknown-task", result["reason"])
        self.assertEqual([], result["argv"])
        self.assertIsNone(result["exitCode"])

    def test_a_task_name_is_never_executed_as_a_command(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        marker = self.root / "injected"
        result = runner.run(project, f"greet; touch {marker}", settings=settings())

        self.assertEqual("unknown-task", result["reason"])
        self.assertFalse(marker.exists())

    def test_a_directory_that_is_not_a_project_is_refused(self) -> None:
        (self.root / "plain").mkdir()
        result = runner.run(self.root / "plain", "greet", settings=settings())
        self.assertEqual("unknown-project", result["reason"])

        missing = runner.run(self.root / "absent", "greet", settings=settings())
        self.assertEqual("unknown-project", missing["reason"])

    def test_an_untrusted_project_is_refused_with_the_trust_command(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        refusal = runner.catalog.UntrustedProject(f"config not trusted; run `mise trust {project}`")
        with mock.patch.object(runner.catalog, "read_tasks", side_effect=refusal):
            result = runner.run(project, "greet", settings=settings())

        self.assertFalse(result["ok"])
        self.assertEqual("untrusted", result["reason"])
        self.assertIn("mise trust", result["error"])
        self.assertEqual([], result["argv"])

    def test_a_project_mise_cannot_read_is_refused_not_raised(self) -> None:
        project = make_project(self.root, "alpha", "this is not valid toml\n")
        result = runner.run(project, "greet", settings=settings())
        self.assertEqual("unreadable", result["reason"])
        self.assertTrue(result["error"])

    def test_an_alias_resolves_to_the_task_it_names(self) -> None:
        project = make_project(
            self.root, "alpha", '[tasks.greet]\nalias = "hi"\nrun = "echo hello"\n'
        )
        result = runner.run(project, "hi", settings=settings())
        self.assertTrue(result["ok"])
        self.assertEqual("greet", result["task"], "the canonical name is what ran")


class OutputBoundTests(RunnerTestCase):
    def test_output_is_capped_and_the_truncation_is_flagged(self) -> None:
        project = make_project(
            self.root,
            "alpha",
            '[tasks.flood]\nrun = "python3 -c \\"print(\'x\' * 200000)\\""\n',
        )
        result = runner.run(project, "flood", settings=settings(), max_output_bytes=4096)

        self.assertTrue(result["ok"])
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["stdout"].encode("utf-8")), 4096)
        self.assertTrue(result["stdout"].endswith("x\n"), "the most recent output is kept")

    def test_output_within_the_cap_is_not_flagged(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        result = runner.run(project, "greet", settings=settings(), max_output_bytes=4096)
        self.assertFalse(result["truncated"])


class TailTests(unittest.TestCase):
    """The buffer itself, at the edges the process tests cannot reach."""

    def test_it_keeps_the_tail_and_records_the_loss(self) -> None:
        tail = runner._Tail(5)
        tail.append(b"abc")
        self.assertFalse(tail.truncated)
        tail.append(b"defgh")
        self.assertTrue(tail.truncated)
        self.assertEqual("defgh", tail.text())

    def test_a_single_oversized_chunk_is_trimmed(self) -> None:
        tail = runner._Tail(3)
        tail.append(b"abcdefg")
        self.assertEqual("efg", tail.text())

    def test_invalid_utf8_does_not_raise(self) -> None:
        tail = runner._Tail(16)
        tail.append(b"\xff\xfe")
        self.assertEqual(2, len(tail.text()))


class CliTests(RunnerTestCase):
    def setUp(self) -> None:
        super().setUp()
        # The CLI resolves its own config; point it at a file that does not
        # exist so the developer's real settings cannot change the outcome.
        self.enterContext(
            mock.patch.dict(os.environ, {"OMARCHY_MISE_CONFIG": str(self.root / "absent.toml")})
        )

    def run_cli(self, *argv: str) -> tuple[int, dict]:
        out = StringIO()
        with redirect_stdout(out):
            status = cli.main(list(argv))
        return status, json.loads(out.getvalue())

    def test_run_prints_json_and_exits_zero_on_success(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.greet]\nrun = "echo hello"\n')
        status, payload = self.run_cli("--json", "run", str(project), "greet")

        self.assertEqual(cli.EXIT_OK, status)
        self.assertTrue(payload["ok"])
        self.assertIn("hello", payload["stdout"])

    def test_run_exits_non_zero_when_the_task_fails(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.boom]\nrun = "exit 2"\n')
        status, payload = self.run_cli("run", str(project), "boom")

        self.assertEqual(cli.EXIT_FAILURE, status)
        self.assertEqual(2, payload["exitCode"])

    def test_run_passes_task_arguments_through(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.echo1]\nrun = "echo \\"$1\\""\n')
        status, payload = self.run_cli("run", str(project), "echo1", "ziggy")
        self.assertEqual(cli.EXIT_OK, status)
        self.assertIn("ziggy", payload["stdout"])

    def test_run_refuses_a_high_risk_task_without_confirm(self) -> None:
        project = make_project(self.root, "alpha", RiskTests.BODY)
        status, payload = self.run_cli("run", str(project), "danger")

        self.assertEqual(cli.EXIT_FAILURE, status)
        self.assertEqual("confirmation-required", payload["reason"])

        status, payload = self.run_cli("run", str(project), "danger", "--confirm")
        self.assertEqual(cli.EXIT_OK, status)
        self.assertTrue(payload["ok"])

    def test_run_honours_the_timeout_flag(self) -> None:
        project = make_project(self.root, "alpha", '[tasks.slow]\nrun = "sleep 30"\n')
        status, payload = self.run_cli("run", str(project), "slow", "--timeout", "1")

        self.assertEqual(cli.EXIT_FAILURE, status)
        self.assertTrue(payload["timedOut"])


if __name__ == "__main__":
    unittest.main()


class ValuesTests(unittest.TestCase):
    """Running with `{name: value}` instead of ready-made argv, which is what
    the argument editor collects."""

    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.root / "mise.toml").write_text(
            "[tasks.greet]\n"
            'usage = \'arg "<name>" help="Who"\'\n'
            "run = 'echo \"hello ${usage_name:?}\"'\n",
            encoding="utf-8",
        )
        self.env = mock.patch.dict(os.environ, {"MISE_TRUSTED_CONFIG_PATHS": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_a_value_becomes_a_positional_argument(self) -> None:
        result = runner.run(self.root, "greet", values={"name": "Omarchy"})
        self.assertEqual("succeeded", result["status"], result)
        self.assertEqual("Omarchy", result["argv"][-1])
        self.assertIn("hello Omarchy", result["stdout"])

    def test_a_blank_required_value_is_refused_before_mise_sees_it(self) -> None:
        result = runner.run(self.root, "greet", values={"name": "   "})
        self.assertEqual("refused", result["status"])
        self.assertEqual(runner.REASON_MISSING_ARGUMENT, result["reason"])
        self.assertIn("name", result["error"])
        # Refusing means refusing: nothing was spawned.
        self.assertEqual([], result["argv"])

    def test_values_and_argv_can_be_combined(self) -> None:
        result = runner.run(self.root, "greet", ["extra"], values={"name": "Omarchy"})
        self.assertEqual(["Omarchy", "extra"], result["argv"][-2:])

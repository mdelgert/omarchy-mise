"""Run one mise task in one project and report what happened.

This is the process boundary the widget runs tasks through. Three rules shape
the whole module:

* The command is always an argv array — `mise --cd <project> run <task> …`.
  A task name, a project path, and a user argument are data, never shell
  source, so nothing here builds a command string and nothing uses a shell.
* Only a task that the catalog says exists, in a project the user has trusted,
  is allowed to run. A caller cannot hand this an arbitrary string to execute.
* An ordinary failure is a result, not an exception. A non-zero exit, a
  timeout, and a refusal are three different things a user needs told apart,
  so each comes back as the same JSON shape with a different `status`.

`RunError` is reserved for the cases where no run could be attempted at all —
a nonsensical timeout, or a process that would not spawn.
"""

from __future__ import annotations

from collections import deque
import contextlib
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Any

from . import catalog, paths
from . import config as config_module

SCHEMA_VERSION = 1

#: Bytes kept per stream. A task that prints megabytes must not be held in
#: memory, and the tail is the part a user reads, so the head is dropped.
MAX_OUTPUT_BYTES = 64 * 1024

#: Read size for the drain threads. Small enough to stay responsive, large
#: enough not to spin on a chatty task.
READ_CHUNK_BYTES = 8192

#: How long a timed-out task gets to exit on SIGTERM before SIGKILL.
TERMINATE_GRACE_SECONDS = 3.0

#: How long to wait for the output readers after the process is gone.
DRAIN_JOIN_SECONDS = 5.0

#: `status` values. Anything other than "succeeded" has `ok` false.
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_TIMED_OUT = "timedOut"
STATUS_REFUSED = "refused"

#: `reason` values on a refusal. Stable strings, because the widget branches on
#: them to decide between an error and a confirmation prompt.
REASON_UNKNOWN_PROJECT = "unknown-project"
REASON_UNKNOWN_TASK = "unknown-task"
REASON_UNTRUSTED = "untrusted"
REASON_UNREADABLE = "unreadable"
REASON_CONFIRMATION_REQUIRED = "confirmation-required"


class RunError(RuntimeError):
    """Raised when a run cannot be attempted at all."""


class _Tail:
    """A byte buffer that keeps only the most recent `limit` bytes.

    Output from a task is unbounded by nature; this makes the memory it can
    cost a constant, and records that it had to drop something so the result
    can say so rather than silently lying about what the task printed.
    """

    def __init__(self, limit: int) -> None:
        self._limit = max(int(limit), 0)
        self._chunks: deque[bytes] = deque()
        self._size = 0
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._chunks.append(chunk)
        self._size += len(chunk)
        while self._size > self._limit:
            self.truncated = True
            overflow = self._size - self._limit
            head = self._chunks.popleft()
            if len(head) > overflow:
                self._chunks.appendleft(head[overflow:])
                self._size = self._limit
                break
            self._size -= len(head)

    def text(self) -> str:
        # Task output is whatever the task chose to print; it is not required
        # to be valid UTF-8, and a decoding error is not a run failure.
        return b"".join(self._chunks).decode("utf-8", "replace")


def _drain(stream: Any, tail: _Tail, lock: threading.Lock) -> None:
    """Copy one pipe into a bounded buffer until it closes."""
    try:
        while True:
            chunk = stream.read(READ_CHUNK_BYTES)
            if not chunk:
                return
            with lock:
                tail.append(chunk)
    except (OSError, ValueError):
        # The pipe was closed underneath us, which is what killing the task
        # does. There is nothing left to read and nothing to report.
        return
    finally:
        with contextlib.suppress(OSError):
            stream.close()


def _terminate(process: subprocess.Popen[bytes], group: int | None) -> None:
    """End the task and everything it started.

    The child is spawned in its own session, so the whole tree shares one
    process group that contains nothing else — signalling that group cleans up
    grandchildren a plain `process.kill()` would orphan. Never `pkill`: this
    only ever signals a group this module created.
    """

    def deliver(sig: int) -> None:
        try:
            if group is not None:
                os.killpg(group, sig)
            else:
                process.send_signal(sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    if process.poll() is None:
        deliver(signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=TERMINATE_GRACE_SECONDS)

    # Sweep the group even when the direct child is already gone: a grandchild
    # that ignored SIGTERM would otherwise survive the widget that started it.
    deliver(signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=TERMINATE_GRACE_SECONDS)


def resolve_timeout(settings: dict[str, Any], override: float | None = None) -> float:
    """Seconds a task may run: `--timeout` if given, else `run.timeout_seconds`."""
    value = settings.get("run", {}).get("timeout_seconds") if override is None else override
    if value is None:
        value = config_module.DEFAULTS["run"]["timeout_seconds"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise RunError(f"timeout must be a positive number of seconds, got {value!r}")
    return float(value)


def _confirm_risk(settings: dict[str, Any]) -> set[str]:
    values = settings.get("run", {}).get("confirm_risk")
    if not isinstance(values, list):
        values = config_module.DEFAULTS["run"]["confirm_risk"]
    return {str(item).strip().lower() for item in values}


def find_task(tasks: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """The catalog entry a caller's task name refers to, by name or alias."""
    for task in tasks:
        if task.get("name") == name:
            return task
    for task in tasks:
        aliases = task.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        if name in aliases:
            return task
    return None


def _result(**fields: Any) -> dict[str, Any]:
    """One JSON shape for every outcome, so the widget parses one thing."""
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "ok": False,
        "status": STATUS_REFUSED,
        "reason": None,
        "error": None,
        "task": "",
        "project": "",
        "argv": [],
        "exitCode": None,
        "durationSeconds": 0.0,
        "timeoutSeconds": None,
        "timedOut": False,
        "truncated": False,
        "risk": None,
        "confirmationRequired": False,
        "stdout": "",
        "stderr": "",
    }
    payload.update(fields)
    return payload


def run(
    project: str | os.PathLike[str],
    task: str,
    args: list[str] | tuple[str, ...] = (),
    *,
    settings: dict[str, Any] | None = None,
    confirm: bool = False,
    timeout: float | None = None,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    """Run `task` in `project` and return the outcome as a JSON-ready dict."""
    resolved = settings if settings is not None else config_module.load()
    limit = resolve_timeout(resolved, timeout)
    # Absolute, but not symlink-resolved: the catalog reports the path it
    # scanned, and the result has to be recognisable as the same project.
    directory = Path(os.path.abspath(paths.expand(project)))
    arguments = [str(item) for item in args]

    def refuse(reason: str, error: str, **extra: Any) -> dict[str, Any]:
        extra.setdefault("task", task)
        return _result(
            reason=reason,
            error=error,
            project=str(directory),
            timeoutSeconds=limit,
            **extra,
        )

    if not directory.is_dir() or not catalog.is_project(directory):
        return refuse(REASON_UNKNOWN_PROJECT, f"not a mise project: {directory}")

    # Reuse the catalog rather than re-deriving what a task is: a run must be
    # of something the widget could have listed, never of a caller's string.
    try:
        tasks = catalog.read_tasks(directory, hidden=True)
    except catalog.UntrustedProject as error:
        # Trusting a config lets it set environment variables and run hooks,
        # so the plugin reports the state with the command the user can run.
        return refuse(REASON_UNTRUSTED, str(error))
    except (catalog.CatalogError, subprocess.TimeoutExpired, OSError) as error:
        return refuse(REASON_UNREADABLE, str(error) or error.__class__.__name__)

    entry = find_task(tasks, task)
    if entry is None:
        return refuse(REASON_UNKNOWN_TASK, f"no task named '{task}' in {directory}")

    name = str(entry.get("name") or task)
    metadata = catalog.read_metadata(directory).get(name, {})
    risk = metadata.get("risk")
    risk = risk if isinstance(risk, str) else None

    if not confirm and risk is not None and risk.strip().lower() in _confirm_risk(resolved):
        # The CLI never prompts: it is called by a bar widget and by scripts.
        # Refusing with a reason lets the caller ask, then re-run with confirm.
        return refuse(
            REASON_CONFIRMATION_REQUIRED,
            f"'{name}' is marked risk '{risk}'; re-run with --confirm to allow it",
            task=name,
            risk=risk,
            confirmationRequired=True,
        )

    # One resolution of the mise binary for the whole package, and an argv
    # array: the task name and every argument are separate elements, so
    # nothing a caller supplies can become part of a command.
    argv = [catalog._mise_binary(), "--cd", str(directory), "run", name, *arguments]
    return _execute(
        argv,
        task=name,
        project=directory,
        timeout=limit,
        risk=risk,
        max_output_bytes=max_output_bytes,
    )


def _execute(
    argv: list[str],
    *,
    task: str,
    project: Path,
    timeout: float,
    risk: str | None,
    max_output_bytes: int,
) -> dict[str, Any]:
    """Spawn the argv array, bound its output, and never outlive it."""
    out, err = _Tail(max_output_bytes), _Tail(max_output_bytes)
    lock = threading.Lock()
    started = time.monotonic()

    try:
        process = subprocess.Popen(
            argv,
            cwd=str(project),
            stdin=subprocess.DEVNULL,  # a task must never block waiting on input
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            # Its own session, so the task and its children form one process
            # group this module owns and can signal as a unit.
            start_new_session=True,
        )
    except OSError as error:
        raise RunError(f"cannot run {argv[0]}: {error}") from error

    try:
        group: int | None = os.getpgid(process.pid)
    except OSError:
        group = None

    readers = [
        threading.Thread(target=_drain, args=(stream, tail, lock), daemon=True)
        for stream, tail in ((process.stdout, out), (process.stderr, err))
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate(process, group)
    finally:
        # The process is gone either way; the pipes close and the readers end.
        for reader in readers:
            reader.join(timeout=DRAIN_JOIN_SECONDS)
        if any(reader.is_alive() for reader in readers):
            # Something the task left behind is still holding our pipes open.
            # The run is over and this module owns that process group, so end
            # it rather than leaking a reader thread for the life of the shell.
            _terminate(process, group)
            for reader in readers:
                reader.join(timeout=DRAIN_JOIN_SECONDS)

    duration = time.monotonic() - started
    exit_code = process.returncode
    if timed_out:
        status = STATUS_TIMED_OUT
    elif exit_code == 0:
        status = STATUS_SUCCEEDED
    else:
        status = STATUS_FAILED

    with lock:
        stdout, stderr = out.text(), err.text()
        truncated = out.truncated or err.truncated

    return _result(
        ok=status == STATUS_SUCCEEDED,
        status=status,
        error=(
            f"timed out after {timeout:g}s"
            if timed_out
            else (None if status == STATUS_SUCCEEDED else f"exited {exit_code}")
        ),
        task=task,
        project=str(project),
        argv=argv,
        exitCode=exit_code,
        durationSeconds=round(duration, 3),
        timeoutSeconds=timeout,
        timedOut=timed_out,
        truncated=truncated,
        risk=risk,
        stdout=stdout,
        stderr=stderr,
    )

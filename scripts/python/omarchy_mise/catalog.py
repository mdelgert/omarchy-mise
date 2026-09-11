"""Discover mise projects and the tasks they expose.

This is the one place that knows how to turn "a directory the user configured"
into "tasks the widget can render". It replaces the earlier pair of bash and
Python metadata scripts.

Task metadata is mise's user-defined `_` table: a project annotates its own
tasks with `[_.tasks."<name>"]`, either in its mise config or in a
`*.meta.toml` sidecar that `task_config.excludes` keeps out of mise itself.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
import shutil
import subprocess
import tomllib
from typing import Any

from . import config as config_module
from . import paths

SCHEMA_VERSION = 1

#: Config files whose presence marks a directory as a mise project.
PROJECT_MARKERS = (
    "mise.toml",
    ".mise.toml",
    "mise.local.toml",
    ".mise.local.toml",
    "mise/config.toml",
    ".mise/config.toml",
    ".config/mise.toml",
    ".config/mise/config.toml",
)

#: Directories mise loads file tasks from; a project may have only these.
TASK_DIR_MARKERS = ("mise-tasks", ".mise/tasks", "mise/tasks", ".config/mise/tasks")

#: Never descend into these while looking for projects.
PRUNED = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".cache",
    ".mypy_cache",
    ".ruff_cache",
    ".terraform",
    "vendor",
}

#: Fields kept from `mise tasks ls --json`. Everything else is noise for a bar
#: widget and would bloat the payload crossing the process boundary.
TASK_FIELDS = ("name", "aliases", "description", "source", "dir", "depends", "usage", "hide")

MISE_TIMEOUT_SECONDS = 20


class CatalogError(RuntimeError):
    """Raised when a project's tasks cannot be read."""


class UntrustedProject(CatalogError):
    """Raised when mise refuses to load a config the user has not trusted.

    Trusting a config lets it set environment variables and run hooks, so this
    is the user's decision to make deliberately with `mise trust`; the plugin
    reports the state and never trusts anything on their behalf.
    """


def is_project(directory: Path) -> bool:
    return any((directory / marker).exists() for marker in PROJECT_MARKERS + TASK_DIR_MARKERS)


def find_projects(root: Path, *, max_depth: int, follow_symlinks: bool = False) -> list[Path]:
    """Breadth-first search for mise projects, not descending into a project."""
    found: list[Path] = []
    frontier = [(root, 0)]

    while frontier:
        directory, depth = frontier.pop(0)
        if is_project(directory):
            found.append(directory)
            # A project's subdirectories belong to it, not to the scan.
            continue
        if depth >= max_depth:
            continue
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name in PRUNED or entry.name.startswith("."):
                continue
            if entry.is_symlink() and not follow_symlinks:
                continue
            if entry.is_dir():
                frontier.append((entry, depth + 1))

    return found


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def read_metadata(project: Path, *, max_depth: int = 3) -> dict[str, dict[str, Any]]:
    """Collect `[_.tasks.*]` metadata declared anywhere in a project.

    Root configs are read first so a `*.meta.toml` sidecar, which exists purely
    to carry metadata, wins on conflict.
    """
    metadata: dict[str, dict[str, Any]] = {}

    def absorb(document: dict[str, Any], source: Path) -> None:
        tasks = document.get("_", {})
        tasks = tasks.get("tasks", {}) if isinstance(tasks, dict) else {}
        if not isinstance(tasks, dict):
            return
        for name, values in tasks.items():
            if isinstance(values, dict):
                entry = dict(values)
                entry["_source"] = str(source)
                metadata[name] = entry

    for marker in PROJECT_MARKERS:
        candidate = project / marker
        if candidate.is_file():
            absorb(_read_toml(candidate), candidate)

    for sidecar in sorted(project.rglob("*.meta.toml")):
        relative = sidecar.relative_to(project).parts
        if len(relative) > max_depth or any(part in PRUNED for part in relative):
            continue
        absorb(_read_toml(sidecar), sidecar)

    return metadata


#: mise repeats its version and a "run with --verbose" hint on every failure.
_NOISE_PREFIXES = ("mise ERROR Version:", "mise ERROR Run with")


def _useful_error(stderr: str) -> str:
    """Pick the line of mise's stderr that actually explains the failure."""
    lines = [
        line.strip().removeprefix("mise ERROR").strip()
        for line in stderr.strip().splitlines()
        if line.strip() and not line.strip().startswith(_NOISE_PREFIXES)
    ]
    return lines[-1] if lines else ""


def _mise_binary() -> str:
    found = shutil.which("mise")
    if not found:
        raise CatalogError("mise is not on PATH")
    return found


def read_tasks(project: Path, *, hidden: bool = False) -> list[dict[str, Any]]:
    """Run `mise tasks ls --json` inside a project and trim the result."""
    command = [_mise_binary(), "--cd", str(project), "tasks", "ls", "--json"]
    if hidden:
        command.append("--hidden")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=MISE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        detail = _useful_error(completed.stderr) or f"mise exited {completed.returncode}"
        if "not trusted" in completed.stderr:
            raise UntrustedProject(f"config not trusted; run `mise trust {project}`")
        raise CatalogError(detail)

    try:
        raw = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as error:
        raise CatalogError(f"mise returned invalid JSON: {error}") from error
    if not isinstance(raw, list):
        raise CatalogError("mise returned an unexpected task payload")

    return [{field: task.get(field) for field in TASK_FIELDS} for task in raw]


def _matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def keep_task(task: dict[str, Any], settings: dict[str, Any]) -> bool:
    name = task.get("name") or ""
    if task.get("hide") and not settings["hidden"]:
        return False
    if settings["include"] and not _matches(name, settings["include"]):
        return False
    return not (settings["exclude"] and _matches(name, settings["exclude"]))


def build(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Produce the full catalog payload consumed by the widget."""
    settings = config if config is not None else config_module.load()
    warnings = list(settings.get("_warnings", []))
    scan = settings["scan"]
    limit = settings["ui"]["max_tasks"]

    roots = config_module.scan_roots(settings)
    if not roots:
        warnings.append(
            f"no configured scan directory exists; set scan.directories in {paths.config_file()}"
        )

    projects: list[dict[str, Any]] = []
    total = 0
    truncated = False

    for root in roots:
        for project in find_projects(
            root, max_depth=scan["max_depth"], follow_symlinks=scan["follow_symlinks"]
        ):
            entry: dict[str, Any] = {
                "path": str(project),
                "name": project.name,
                "root": str(root),
                "trusted": True,
                "tasks": [],
            }
            try:
                tasks = read_tasks(project, hidden=settings["tasks"]["hidden"])
            except UntrustedProject as error:
                entry["trusted"] = False
                entry["error"] = str(error)
                warnings.append(f"{project}: not trusted")
                projects.append(entry)
                continue
            except (CatalogError, subprocess.TimeoutExpired, OSError) as error:
                entry["error"] = str(error) or error.__class__.__name__
                warnings.append(f"{project}: {entry['error']}")
                projects.append(entry)
                continue

            metadata = read_metadata(project)
            for task in tasks:
                if not keep_task(task, settings["tasks"]):
                    continue
                if total >= limit:
                    truncated = True
                    break
                task["metadata"] = metadata.get(task.get("name") or "", {})
                entry["tasks"].append(task)
                total += 1
            projects.append(entry)
            if truncated:
                break
        if truncated:
            break

    if truncated:
        warnings.append(f"task list truncated at ui.max_tasks = {limit}")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "config": settings.get("_source"),
        "taskCount": total,
        "projectCount": len(projects),
        "projects": projects,
        "warnings": warnings,
    }

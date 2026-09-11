"""Load and validate `~/.config/omarchy-mise/config.toml`.

The file is optional: a missing config resolves to the defaults below, so the
plugin works on a fresh machine. Unknown keys are reported as warnings rather
than errors so a config written for a newer plugin still loads; wrong types are
hard errors, because silently ignoring them hides the user's intent.
"""

from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any

from . import paths

SCHEMA_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "ui": {
        # Bar label. Kept short; the widget elides anything longer.
        "label": "Mise",
        # Upper bound on tasks held in memory, so a huge tree cannot stall the bar.
        "max_tasks": 200,
    },
    "scan": {
        # Directories searched for mise projects. Missing entries are skipped.
        # Deliberately empty, and no path is hard-coded here: a default that
        # guesses at someone's layout scans directories they never asked for,
        # and a wrong guess is indistinguishable from a broken plugin. The
        # starter config in `config.example.toml` is where a real entry lives,
        # and the plugin writes that file on its first run, so an install still
        # arrives with something to list. An empty list is not an error -- the
        # catalog reports it as a warning naming the file to edit.
        "directories": [],
        # How many levels below each entry to descend before giving up.
        "max_depth": 2,
        "follow_symlinks": False,
    },
    "tasks": {
        # Glob allowlist/denylist matched against the task name. Empty include
        # means "every task".
        "include": [],
        "exclude": [],
        # Include tasks mise marks hidden.
        "hidden": False,
    },
    "run": {
        "timeout_seconds": 300,
        # Task metadata risk levels that must be confirmed before running.
        "confirm_risk": ["high"],
    },
}

#: section -> key -> (python type, coercion/validation hint)
_SPEC: dict[str, dict[str, type | tuple[type, ...]]] = {
    "ui": {"label": str, "max_tasks": int},
    "scan": {"directories": list, "max_depth": int, "follow_symlinks": bool},
    "tasks": {"include": list, "exclude": list, "hidden": bool},
    "run": {"timeout_seconds": int, "confirm_risk": list},
}

_POSITIVE_INTS = {("ui", "max_tasks"), ("scan", "max_depth"), ("run", "timeout_seconds")}
_STRING_LISTS = {
    ("scan", "directories"),
    ("tasks", "include"),
    ("tasks", "exclude"),
    ("run", "confirm_risk"),
}


class ConfigError(ValueError):
    """Raised when config.toml exists but cannot be honoured."""


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


def defaults() -> dict[str, Any]:
    return _deep_copy(DEFAULTS)


def _check(section: str, key: str, value: Any) -> Any:
    expected = _SPEC[section][key]
    # bool is a subclass of int; an int field must not silently accept `true`.
    if expected is int and isinstance(value, bool):
        raise ConfigError(f"{section}.{key} must be an integer, got a boolean")
    if not isinstance(value, expected):
        name = getattr(expected, "__name__", str(expected))
        raise ConfigError(f"{section}.{key} must be of type {name}, got {type(value).__name__}")
    if (section, key) in _POSITIVE_INTS and value < 1:
        raise ConfigError(f"{section}.{key} must be 1 or greater, got {value}")
    if (section, key) in _STRING_LISTS:
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ConfigError(f"{section}.{key} must contain only non-empty strings")
        return [item.strip() for item in value]
    if section == "ui" and key == "label":
        return value.strip()[:80] or DEFAULTS["ui"]["label"]
    return value


def load(path: Path | None = None) -> dict[str, Any]:
    """Return the resolved configuration, annotated with where it came from."""
    config_path = path if path is not None else paths.config_file()
    resolved = defaults()
    warnings: list[str] = []

    if not config_path.is_file():
        resolved["_source"] = None
        resolved["_warnings"] = warnings
        return resolved

    try:
        with config_path.open("rb") as stream:
            document = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read {config_path}: {error}") from error

    declared = document.pop("schema_version", SCHEMA_VERSION)
    if not isinstance(declared, int) or isinstance(declared, bool):
        raise ConfigError("schema_version must be an integer")
    if declared > SCHEMA_VERSION:
        warnings.append(
            f"config declares schema_version {declared}; this plugin understands {SCHEMA_VERSION}"
        )
    resolved["schema_version"] = declared

    for section, values in document.items():
        if section not in _SPEC:
            warnings.append(f"ignoring unknown section [{section}]")
            continue
        if not isinstance(values, dict):
            raise ConfigError(f"[{section}] must be a table")
        for key, value in values.items():
            if key not in _SPEC[section]:
                warnings.append(f"ignoring unknown key {section}.{key}")
                continue
            resolved[section][key] = _check(section, key, value)

    resolved["_source"] = str(config_path)
    resolved["_warnings"] = warnings
    return resolved


def scan_roots(config: dict[str, Any]) -> list[Path]:
    """Configured scan directories that actually exist, de-duplicated."""
    seen: dict[Path, None] = {}
    for entry in config["scan"]["directories"]:
        candidate = paths.expand(entry)
        if candidate.is_dir():
            seen.setdefault(candidate.resolve(), None)
    return list(seen)


def write_default(path: Path | None = None, *, force: bool = False) -> Path:
    """Create a commented starter config. Never clobbers an existing file."""
    target = path if path is not None else paths.config_file()
    if target.exists() and not force:
        return target
    template = paths.repo_root() / "config.example.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    return target

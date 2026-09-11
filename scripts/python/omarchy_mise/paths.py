"""Filesystem locations the plugin reads and writes.

Nothing here ever writes into the installed plugin checkout: user state belongs
in XDG directories so an upgrade or a reinstall cannot destroy it.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "omarchy-mise"

#: Overrides the resolved config file. Used by tests and by `--config`.
CONFIG_ENV = "OMARCHY_MISE_CONFIG"


def xdg_dir(env: str, default: str) -> Path:
    """Return an XDG base directory, ignoring a relative (invalid) override."""
    value = os.environ.get(env, "").strip()
    if value and Path(value).is_absolute():
        return Path(value)
    return Path.home() / default


def config_home() -> Path:
    return xdg_dir("XDG_CONFIG_HOME", ".config") / APP_NAME


def cache_home() -> Path:
    return xdg_dir("XDG_CACHE_HOME", ".cache") / APP_NAME


def state_home() -> Path:
    return xdg_dir("XDG_STATE_HOME", ".local/state") / APP_NAME


def config_file() -> Path:
    override = os.environ.get(CONFIG_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return config_home() / "config.toml"


def repo_root() -> Path:
    """The plugin checkout this module was loaded from."""
    return Path(__file__).resolve().parents[3]


def plugins_dir() -> Path:
    """Where Omarchy keeps user-installed plugins."""
    return Path.home() / ".config" / "omarchy" / "plugins"


def expand(path: str | os.PathLike[str]) -> Path:
    """Expand `~` and environment variables in a user-supplied path."""
    return Path(os.path.expandvars(os.fspath(path))).expanduser()

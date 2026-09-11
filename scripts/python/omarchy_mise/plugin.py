"""Install, remove, and diagnose this plugin on an Omarchy desktop.

Development installs are symlinks: Omarchy's catalog follows them, so an edit
in the working tree is live after a reload, and `omarchy plugin remove` unlinks
rather than deleting the repository.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from . import catalog, manifest, paths
from . import config as config_module

COMMAND_TIMEOUT_SECONDS = 30


class PluginError(RuntimeError):
    """Raised when a desktop operation cannot be completed."""


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not shutil.which(command[0]):
        raise PluginError(f"{command[0]} is not installed; this needs an Omarchy desktop")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or f"exit {completed.returncode}"
        raise PluginError(f"{' '.join(command)}: {detail}")
    return completed


def plugin_id(root: Path | None = None) -> str:
    return str(manifest.read(root)["id"])


def install_path(root: Path | None = None) -> Path:
    return paths.plugins_dir() / plugin_id(root)


def default_section(root: Path | None = None) -> str:
    widget = manifest.read(root).get("barWidget")
    section = widget.get("defaultSection") if isinstance(widget, dict) else None
    return section if section in {"left", "center", "right"} else "center"


def rescan() -> None:
    """Ask a running shell to re-read the plugin catalog. Best effort."""
    if shutil.which("omarchy-shell"):
        _run(["omarchy-shell", "-q", "shell", "rescanPlugins"], check=False)


def install(root: Path | None = None, *, section: str | None = None, enable: bool = True) -> str:
    """Symlink the working tree into the Omarchy plugin directory."""
    source = (root or paths.repo_root()).resolve()
    manifest.validate(source)
    target = install_path(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_symlink():
        if target.readlink() == source:
            message = f"already linked: {target} -> {source}"
        else:
            target.unlink()
            target.symlink_to(source, target_is_directory=True)
            message = f"relinked: {target} -> {source}"
    elif target.exists():
        raise PluginError(
            f"{target} exists and is not a symlink; remove that install first with "
            f"`omarchy plugin remove {plugin_id(source)}`"
        )
    else:
        target.symlink_to(source, target_is_directory=True)
        message = f"linked: {target} -> {source}"

    rescan()
    if enable:
        _run(
            [
                "omarchy-plugin-enable",
                plugin_id(source),
                "--section",
                section or default_section(source),
            ]
        )
        message += " (enabled)"
    return message


def uninstall(root: Path | None = None) -> str:
    """Disable and remove this plugin's install, leaving the repository intact."""
    source = root or paths.repo_root()
    identifier = plugin_id(source)
    target = install_path(source)

    if not target.exists() and not target.is_symlink():
        return f"not installed: {target}"

    if shutil.which("omarchy-shell"):
        _run(["omarchy-shell", "-q", "shell", "setPluginEnabled", identifier, "false"], check=False)

    if target.is_symlink():
        target.unlink()
        message = f"unlinked: {target}"
    else:
        _run(["omarchy-plugin-remove", identifier, "--yes"])
        message = f"removed: {target}"

    rescan()
    return message


def _installed_state(identifier: str) -> dict[str, Any]:
    if not shutil.which("omarchy-plugin-list"):
        return {}
    completed = _run(["omarchy-plugin-list", "--json"], check=False)
    if completed.returncode != 0:
        return {}

    try:
        entries = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == identifier:
            return entry
    return {}


def doctor(root: Path | None = None) -> dict[str, Any]:
    """Collect everything worth knowing when the widget misbehaves."""
    source = root or paths.repo_root()
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool | None, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    for tool, required in (
        ("mise", True),
        ("python3", True),
        ("omarchy", False),
        ("qmllint", False),
    ):
        found = shutil.which(tool)
        if tool == "qmllint" and not found and Path("/usr/lib/qt6/bin/qmllint").is_file():
            found = "/usr/lib/qt6/bin/qmllint"
        record(
            f"{tool} available",
            bool(found) if required else (bool(found) or None),
            found or "not found",
        )

    try:
        document = manifest.validate(source)
        record("manifest valid", True, f"{document['id']} {document['version']}")
        identifier = str(document["id"])
    except manifest.ManifestError as error:
        record("manifest valid", False, str(error))
        identifier = ""

    try:
        settings = config_module.load()
        source_file = settings.get("_source") or f"{paths.config_file()} (absent, using defaults)"
        record("config loads", True, source_file)
        for warning in settings.get("_warnings", []):
            record("config warning", None, warning)
        roots = config_module.scan_roots(settings)
        record(
            "scan directories",
            bool(roots),
            ", ".join(str(item) for item in roots) or "none of the configured directories exist",
        )
    except config_module.ConfigError as error:
        record("config loads", False, str(error))
        roots = []

    if roots:
        try:
            built = catalog.build()
            record(
                "catalog builds",
                True,
                f"{built['taskCount']} tasks in {built['projectCount']} projects",
            )
            for warning in built["warnings"]:
                record("catalog warning", None, warning)
        except catalog.CatalogError as error:
            record("catalog builds", False, str(error))

    target = install_path(source) if identifier else None
    if target is not None:
        if target.is_symlink():
            record("plugin installed", True, f"{target} -> {target.readlink()} (development link)")
        elif target.exists():
            record("plugin installed", True, f"{target} (copy)")
        else:
            record("plugin installed", None, "not installed; run `mise run omarchy:install`")

        state = _installed_state(identifier)
        if state:
            record(
                "plugin enabled",
                bool(state.get("enabled")),
                f"enabled={state.get('enabled')} active={state.get('active')}",
            )

    if shutil.which("omarchy-shell"):
        alive = _run(["omarchy-shell", "shell", "ping"], check=False).returncode == 0
        record("omarchy-shell responding", alive, "ping ok" if alive else "shell not running")

    failed = [item for item in checks if item["ok"] is False]
    return {"ok": not failed, "checks": checks, "failures": len(failed)}

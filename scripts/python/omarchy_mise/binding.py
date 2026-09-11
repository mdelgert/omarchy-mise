"""Add and remove the optional Hyprland keybinding for the task browser.

The plugin never installs a binding on its own: a binding the user did not ask
for is one that silently shadows something they already use. This module exists
so that *asking* is one command instead of a hand-edit, and so that asking is
safe -- it refuses a combination something else already owns, writes a single
delimited block it can later remove exactly, and backs the file up first.

Everything is written into `~/.config/hypr/bindings.lua`, which Omarchy reserves
for user overrides. The delimiters follow the convention already used by other
tools that manage a region of that file:

    -- >>> omarchy-mise: task browser binding
    o.bind("SUPER + CTRL + M", "Mise tasks", "omarchy-shell shell toggle <id>")
    -- <<< omarchy-mise: task browser binding

Nothing outside those two lines is ever touched, so the rest of the file -- and
any other tool's block in it -- survives byte for byte.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

from . import manifest, paths

COMMAND_TIMEOUT_SECONDS = 15

#: Marker name for the managed region. Matches the `-- >>> name` / `-- <<< name`
#: convention other tools use in this file.
MARKER = "omarchy-mise: task browser binding"
BEGIN = f"-- >>> {MARKER}"
END = f"-- <<< {MARKER}"

#: Verified unbound in a stock Omarchy install -- `SUPER + SHIFT + M` is
#: "Music" and `SUPER + SHIFT + ALT + M` is "Music TUI", but plain `SUPER + M`
#: is free. Note that Omarchy binds its own shell *panels* as
#: SUPER + CTRL + <letter> (clipboard V, audio A, bluetooth B, network W,
#: power P), so `SUPER + CTRL + M` is the more conventional slot if you would
#: rather match that family. Either way `add()` checks before it writes.
DEFAULT_KEY = "SUPER + M"

#: Shown in `omarchy menu keybindings`.
DESCRIPTION = "Mise tasks"

#: Modifier names Hyprland accepts, upper-cased.
MODIFIERS = {"SUPER", "SHIFT", "CTRL", "CONTROL", "ALT", "MOD", "META"}

#: A key combination is written into a Lua string literal, so it is restricted
#: to what a combination can legitimately contain. This is the only untrusted
#: input this module puts in the file.
_KEY_TOKEN = re.compile(r"^[A-Za-z0-9_]+$")


class BindingError(RuntimeError):
    """Raised when the binding cannot be added or removed."""


def bindings_file() -> Path:
    """`~/.config/hypr/bindings.lua`, the file Omarchy reserves for overrides."""
    return paths.hypr_bindings_file()


def normalise(combo: str) -> str:
    """Canonical `MOD + MOD + KEY` spelling, or raise.

    Accepts the spellings a user might type -- `super+ctrl+m`, `SUPER CTRL M`,
    `Super + Ctrl + M` -- because the whole point is not having to remember the
    exact one. Rejects anything that is not modifiers plus a single key, which
    is also what keeps the value safe to write into a Lua literal.
    """
    tokens = [token for token in re.split(r"[+\s]+", str(combo).strip()) if token]
    if not tokens:
        raise BindingError("a key combination is required, e.g. 'SUPER + CTRL + M'")
    for token in tokens:
        if not _KEY_TOKEN.match(token):
            raise BindingError(
                f"invalid key combination {combo!r}: {token!r} is not a modifier or a key"
            )
    upper = [token.upper() for token in tokens]
    key = upper[-1]
    modifiers = upper[:-1]
    if key in MODIFIERS:
        raise BindingError(f"invalid key combination {combo!r}: it names no key, only modifiers")
    unknown = [item for item in modifiers if item not in MODIFIERS]
    if unknown:
        raise BindingError(
            f"invalid key combination {combo!r}: {', '.join(unknown)} is not a modifier"
        )
    # Duplicates collapse, and declaration order is not meaningful to Hyprland,
    # but a stable order makes the written line diff-stable.
    order = ("SUPER", "CTRL", "CONTROL", "META", "MOD", "ALT", "SHIFT")
    ordered = [item for item in order if item in modifiers]
    return " + ".join([*ordered, key])


def _comparable(combo: str) -> tuple[frozenset[str], str]:
    tokens = [token.upper() for token in re.split(r"[+\s]+", combo.strip()) if token]
    canonical = {"CONTROL": "CTRL", "META": "SUPER", "MOD": "SUPER"}
    tokens = [canonical.get(token, token) for token in tokens]
    return frozenset(tokens[:-1]), tokens[-1]


def existing_bindings() -> list[tuple[str, str]] | None:
    """Every binding Omarchy currently reports, or None if it cannot be asked.

    `omarchy menu keybindings --print` is the only source that sees Omarchy's
    defaults, the preinstalled app bindings, and the user's overrides together.
    Off an Omarchy desktop it does not exist, and a conflict check that cannot
    run is reported as such rather than guessed at.
    """
    if not shutil.which("omarchy"):
        return None
    try:
        completed = subprocess.run(
            ["omarchy", "menu", "keybindings", "--print"],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None

    found: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        # "SUPER CTRL + V   → Clipboard manager"
        left, separator, right = line.partition("→")
        if not separator or not left.strip():
            continue
        found.append((left.strip(), right.strip()))
    return found


def conflict(combo: str) -> str | None:
    """What already owns `combo`, or None when nothing does or nothing can say."""
    listing = existing_bindings()
    if listing is None:
        return None
    wanted = _comparable(combo)
    for spelling, description in listing:
        try:
            if _comparable(spelling) == wanted:
                return description or spelling
        except IndexError:
            continue
    return None


def _block(combo: str, *, unbind: bool) -> str:
    action = f"omarchy-shell shell toggle {manifest.read()['id']}"
    lines = [
        BEGIN,
        "-- Managed by `omarchy-mise bind`. Remove it with `omarchy-mise unbind`",
        "-- rather than by hand, so the whole block goes with it.",
    ]
    if unbind:
        lines.append(f'hl.unbind("{combo}")')
    lines.append(f'o.bind("{combo}", "{DESCRIPTION}", "{action}")')
    lines.append(END)
    return "\n".join(lines)


def _split(text: str) -> tuple[str, str | None, str]:
    """Return the text before the managed block, the block, and the text after."""
    start = text.find(BEGIN)
    if start == -1:
        return text, None, ""
    end = text.find(END, start)
    if end == -1:
        # A truncated block is still ours to replace; take it to end of file
        # rather than leaving a dangling opener behind.
        return text[:start], text[start:], ""
    end += len(END)
    return text[:start], text[start:end], text[end:]


def _read() -> str:
    target = bindings_file()
    if not target.is_file():
        raise BindingError(
            f"{target} does not exist; this needs an Omarchy desktop "
            "(`omarchy refresh config hypr/bindings.lua` restores it)"
        )
    try:
        return target.read_text(encoding="utf-8")
    except OSError as error:
        raise BindingError(f"cannot read {target}: {error}") from error


def _write(text: str) -> Path:
    """Write `text`, leaving a timestamped backup of what was there before."""
    target = bindings_file()
    backup = target.with_suffix(f".lua.bak.{int(time.time())}")
    try:
        shutil.copy2(target, backup)
        # Replace through a temporary file in the same directory so an
        # interrupted write cannot leave a half-written bindings file behind.
        scratch = target.with_suffix(f".lua.omarchy-mise.{os.getpid()}")
        scratch.write_text(text, encoding="utf-8")
        os.replace(scratch, target)
    except OSError as error:
        raise BindingError(f"cannot write {target}: {error}") from error
    return backup


def _validate() -> str | None:
    """Ask Hyprland to reload and report any config error it finds."""
    if not shutil.which("hyprctl"):
        return None
    try:
        subprocess.run(
            ["hyprctl", "reload"],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
        completed = subprocess.run(
            ["hyprctl", "configerrors"],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    detail = (completed.stdout or "").strip()
    if not detail or detail.lower().startswith("no errors"):
        return None
    return detail


def status() -> dict[str, Any]:
    """Whether the managed binding is present, and with which combination."""
    target = bindings_file()
    if not target.is_file():
        return {"ok": True, "bound": False, "key": None, "path": str(target), "exists": False}
    _, block, _ = _split(target.read_text(encoding="utf-8"))
    combo = None
    if block:
        match = re.search(r'o\.bind\("([^"]+)"', block)
        combo = match.group(1) if match else None
    return {
        "ok": True,
        "bound": block is not None,
        "key": combo,
        "path": str(target),
        "exists": True,
    }


def add(key: str | None = None, *, force: bool = False) -> dict[str, Any]:
    """Bind `key` to toggling the task browser.

    Refuses a combination something else already owns, because shadowing an
    existing binding is the failure this plugin's no-keybinding rule exists to
    avoid. `force` accepts the collision and emits `hl.unbind` ahead of the
    bind, which is what Omarchy requires to override one of its defaults.
    """
    combo = normalise(key or DEFAULT_KEY)
    text = _read()
    before, existing, after = _split(text)

    # `omarchy menu keybindings` lists our own block too, so a binding that is
    # already ours is not a collision to report back.
    owner = conflict(combo)
    if owner == DESCRIPTION:
        owner = None

    if owner is not None and not force:
        return {
            "ok": False,
            "action": "bind",
            "key": combo,
            "path": str(bindings_file()),
            "changed": False,
            "conflict": owner,
            "detail": (
                f"{combo} is already bound to '{owner}'. Choose another combination, "
                f"or pass --force to override it (an hl.unbind is written first)."
            ),
        }

    block = _block(combo, unbind=owner is not None)
    if existing is not None and existing.strip() == block.strip():
        return {
            "ok": True,
            "action": "bind",
            "key": combo,
            "path": str(bindings_file()),
            "changed": False,
            "conflict": owner,
            "detail": f"already bound: {combo}",
        }

    if existing is not None:
        updated = before + block + after
    else:
        if before == "" or before.endswith("\n\n"):
            separator = ""
        elif before.endswith("\n"):
            separator = "\n"
        else:
            separator = "\n\n"
        updated = before + separator + block + "\n"

    backup = _write(updated)
    errors = _validate()
    return {
        "ok": errors is None,
        "action": "bind",
        "key": combo,
        "path": str(bindings_file()),
        "backup": str(backup),
        "changed": True,
        "conflict": owner,
        "replaced": existing is not None,
        "detail": errors or f"bound {combo} to '{DESCRIPTION}'",
    }


def remove() -> dict[str, Any]:
    """Remove the managed block, leaving everything else in the file intact."""
    text = _read()
    before, existing, after = _split(text)
    if existing is None:
        return {
            "ok": True,
            "action": "unbind",
            "key": None,
            "path": str(bindings_file()),
            "changed": False,
            "detail": "no omarchy-mise binding to remove",
        }

    combo = None
    match = re.search(r'o\.bind\("([^"]+)"', existing)
    if match:
        combo = match.group(1)

    # Collapse the blank line the block was separated by, so removing it twice
    # over does not leave a growing gap behind.
    updated = before.rstrip("\n") + ("\n" if before.strip() else "") + after.lstrip("\n")
    if before.strip() and after.strip():
        updated = before.rstrip("\n") + "\n\n" + after.lstrip("\n")

    backup = _write(updated)
    errors = _validate()
    return {
        "ok": errors is None,
        "action": "unbind",
        "key": combo,
        "path": str(bindings_file()),
        "backup": str(backup),
        "changed": True,
        "detail": errors or f"removed the binding for {combo or DESCRIPTION}",
    }

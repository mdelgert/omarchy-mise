---
name: omarchy-mise-dev
description: Build, debug, and test the Omarchy Mise plugin on a desktop. Use when changing Main.qml, the Python support library under scripts/python/omarchy_mise/, manifest.json, or the mise tasks; when the widget does not appear, does not update, or misbehaves; or when a check fails and you need to know which layer broke.
---

# Developing Omarchy Mise

The build/debug/test loop for this plugin. Read [AGENTS.md](../../../AGENTS.md) first —
it holds the boundaries this skill assumes.

## The gate

Run after every coherent change; it must exit zero before you call anything done.

```sh
mise run omarchy:check          # portable: lint + tests + manifest + catalog
mise run omarchy:check-desktop  # adds omarchy-plugin-validate and qmllint
```

`omarchy:check` runs anywhere, including CI. `omarchy:check-desktop` needs Omarchy
installed. Static checks are not visual validation: a QML change is not verified until
you have seen it in a running bar.

## Which layer broke

Work outwards from the smallest failing piece rather than restarting the shell first.

| Symptom | Check |
| --- | --- |
| Anything unexpected | `mise run omarchy:doctor` — tools, config, catalog, install, shell |
| Wrong or missing tasks in the catalog | `mise run omarchy:catalog` |
| A project shows `"trusted": false` | mise refuses untrusted configs; the user runs `mise trust <path>`, never you |
| Config not taking effect | `mise run omarchy:config` shows what was actually resolved, including `_warnings` |
| Widget absent from the bar | `omarchy plugin list --json`, then `mise run omarchy:install` |
| Widget present but stale | `mise run omarchy:reload` for a rescan; `mise run omarchy:restart` after a QML edit |
| QML error at runtime | `mise run omarchy:logs` (`journalctl --user -t omarchy-shell`) |

## Editing QML

1. Install once with `mise run omarchy:install`. It symlinks the working tree into
   `~/.config/omarchy/plugins/`, so edits are live — there is nothing to copy.
2. After a QML edit run `mise run omarchy:restart`. A rescan alone does not reload
   QML that the shell has already instantiated.
3. Watch `mise run omarchy:logs` while it comes back up.
4. Check the bar horizontally and vertically, on every monitor, and after a reload.

`qmllint` runs inside `omarchy:check-desktop` against a `qs` symlink of the installed
shell; without that layout every import and inherited property reports as unresolved.
Remaining `missing-property` lines on `bar` and `Style.font` are expected — the host
declares both as untyped `QObject`, so those members cannot be resolved from here.

## Editing the support library

Everything non-trivial lives in `scripts/python/omarchy_mise/` and is reached through
the `bin/omarchy-mise` shim, which both the mise tasks and (eventually) the QML widget
call. Stdlib only — no third-party runtime dependency.

- `config.py` — `~/.config/omarchy-mise/config.toml`: defaults, validation, warnings
- `catalog.py` — find mise projects, read their tasks and `[_.tasks.*]` metadata
- `manifest.py` — portable `manifest.json` checks
- `plugin.py` — install, uninstall, and `doctor`
- `cli.py` — the subcommands; keep JSON output stable, the widget parses it

Add a test in `tests/` for every behaviour change; `mise run omarchy:test` runs them.

## Before finishing

- `mise run omarchy:check` exits zero (plus `omarchy:check-desktop` on a desktop).
- QML changes were seen running, not just linted.
- `git diff --check` is clean and every changed line belongs to the request.
- `mise run omarchy:uninstall` if you installed the plugin only to test it.

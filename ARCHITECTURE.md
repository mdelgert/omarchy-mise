# Architecture

## Shape

Three layers, each with one job:

```
Main.qml                    presentation, owned by the Omarchy shell
   |  process boundary: bin/omarchy-mise <command> --json
scripts/python/omarchy_mise support library: config, discovery, install, diagnostics
   |  subprocess: mise --cd <project> tasks ls --json
mise                        the authority on what tasks exist
```

The boundary matters: QML never parses TOML, never walks the filesystem, and never
builds a shell command. It asks the CLI a question and renders the JSON answer. The
same CLI backs the `omarchy:*` mise tasks, so what a developer sees in a terminal is
exactly what the widget sees.

## Current scaffold

`manifest.json` declares a third-party `bar-widget` whose entry point is `Main.qml`.
The widget renders only a configurable, theme-aware label: it establishes plugin
discovery, package metadata, bar placement, host settings, and horizontal/vertical
sizing without starting processes, writing state, or contacting the network.

The host owns bar instances, placement, settings persistence, and destruction.
`Main.qml` validates its optional `label` setting and owns presentation-only state.
`allowMultiple: false` prevents duplicate layout entries; the host may still create one
instance per monitor.

## Support library

`scripts/python/omarchy_mise/`, standard library only, reached through
`bin/omarchy-mise`:

| Module | Responsibility |
| --- | --- |
| `paths.py` | XDG locations; nothing is written inside the installed checkout |
| `config.py` | Load and validate `config.toml`; unknown keys warn, wrong types fail |
| `catalog.py` | Find mise projects, read their tasks and `[_.tasks.*]` metadata |
| `manifest.py` | Portable `manifest.json` validation, mirroring Omarchy's validator |
| `plugin.py` | Install, uninstall, and `doctor` |
| `cli.py` | Subcommands and JSON output |

Discovery is breadth-first to `scan.max_depth`, skipping hidden and vendored
directories, and never descending into a directory that is itself a project. Tasks
come from `mise --cd <project> tasks ls --json` — mise is the authority, so the plugin
never reimplements task resolution. Metadata comes from the project's `[_.tasks.*]`
tables and `*.meta.toml` sidecars, read directly.

Failure is per-project: a project that is broken, untrusted, or slow carries an
`error` and the rest of the catalog still loads. An untrusted project is reported as
`trusted: false` with the `mise trust` command the user can run — the plugin never
trusts a config on their behalf, because trusting one allows environment changes and
hooks.

## Planned task browser

- `Main.qml` — entry-point composition and small view-local interactions.
- `services/TaskCatalog.qml` — one owner for refreshes, execution requests,
  cancellation, and errors.
- `components/` — task list, parameter editor, status, and reusable presentation.
- `Model.js` — pure validation, filtering, and conversion of the catalog JSON.

Finite operations need deadlines, output limits, cancellation on replacement or
destruction, and distinct empty, error, and cancelled states. Task execution must
require an explicit user action and visibly report the selected project and task.
Arguments stay an argv array; task names are never interpolated into a shell command.

The plugin does not own a global keybinding. The panel is reached through the host's
`shell toggle`, `summon`, and `hide` actions, so existing Omarchy and user mappings
keep working and the host decides which monitor's copy answers.

A binding is therefore opt-in and never automatic: no install, enable, or load path
creates one. `omarchy-mise bind` exists so that opting in is one command rather than a
hand-edit, and it is built so that opting in cannot break something else — it asks
`omarchy menu keybindings` what already holds the combination and refuses rather than
shadowing it, writes a single delimited block in `~/.config/hypr/bindings.lua` after
backing the file up, and removes exactly that block on `unbind`. A conflict check that
cannot run (off an Omarchy desktop) is reported, not assumed clear. The key
combination is the only untrusted value written into that file, so it is validated
down to modifiers plus one key before it reaches a Lua literal.

## State and lifecycle

Configuration lives at `~/.config/omarchy-mise/config.toml`; cache and runtime state
have their own XDG locations if they are ever needed. Nothing writes into the
installed checkout, so an upgrade or reinstall cannot lose user data. Long-lived state
belongs to one host-loaded service rather than one process per monitor; UI instances
subscribe to that owner and release connections, timers, and in-flight work when
hidden or destroyed.

## Validation

`omarchy:check` is portable and runs in CI: `mise tasks validate`, ruff, shellcheck,
taplo, unit tests, manifest validation, and a catalog smoke test. `omarchy:check-desktop`
adds Omarchy's authoritative validator and `qmllint` against the installed shell
imports. Releases additionally require a local install and visual interaction checks.

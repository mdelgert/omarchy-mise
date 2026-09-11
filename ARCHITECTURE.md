# Architecture

## Current starter

`manifest.json` declares a third-party `bar-widget` whose entry point is `Main.qml`. The starter intentionally renders only a configurable, theme-aware label. It establishes plugin discovery, package metadata, bar placement, host settings, and horizontal/vertical sizing without starting processes, writing state, contacting the network, or claiming the task browser is implemented.

The host owns bar instances, placement, settings persistence, and destruction. `Main.qml` validates its optional `label` setting and owns presentation-only state. `allowMultiple: false` prevents duplicate layout entries; the host may still create one instance per monitor.

## Planned task-browser boundaries

- `Main.qml`: entry-point composition and small view-local interactions.
- `services/TaskCatalog.qml`: one owner for catalog refreshes, execution requests, cancellation, and errors.
- `components/`: task list, parameter editor, status, and reusable presentation.
- `Model.js`: pure validation, filtering, and conversion of mise JSON.
- `scripts/`: bounded adapters only where mise or the host cannot provide structured data directly.
- `tasks/*.toml` and `tasks/*.meta.toml`: development examples and exact metadata fixtures.

The task catalog must use structured `mise` output and keep task arguments as an argv array. It must not build shell commands from task names or user input. Finite operations need deadlines, output limits, cancellation on replacement/destruction, and distinct empty/error/cancelled states. Task execution must require an explicit user action and visibly report the selected project and task.

The plugin will not own global keybindings. A future panel or overlay will expose host summon/toggle actions and document optional user-selected bindings. Keyboard navigation remains inside the focused surface, preserving existing Omarchy and user mappings.

## State and lifecycle

Configuration, cache, runtime files, and durable data belong in separate plugin-specific XDG locations if introduced. Nothing writes into the installed checkout. Long-lived state should use one host-loaded service rather than one process per monitor. UI instances subscribe to that owner and release connections, captures, timers, and in-flight work when hidden or destroyed.

## Validation

`scripts/python/validate_manifest.py` provides portable CI checks. Omarchy's validator remains authoritative and is run by `omarchy:check-desktop`; `qmllint` verifies QML against the installed shell imports. Releases additionally require a local install and visual interaction checks on Omarchy.

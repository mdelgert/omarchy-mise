# Roadmap to v1

What "version one" means: a bar widget that lists the mise tasks in your configured
directories, runs one on an explicit click, and shows what happened. Nothing more.

The data layer for all of it is already built and tested — `bin/omarchy-mise catalog`
returns exactly what the browser needs. What remains is QML and the process
boundary between it and that CLI.

Each item below is sized to be picked up on its own. Do them in order; each states its
scope, the files it touches, and how to know it is finished. Every item inherits the
rules in [AGENTS.md](../AGENTS.md) and finishes with `mise run omarchy:check-desktop`
passing plus a visual check on a running bar.

---

## R1 — Read the configured label

**Scope.** Make the widget show `ui.label` from `config.toml` instead of only the
host's inline `settings` entry. Precedence: host setting, then config file, then
`"Mise"`.

**Files.** `Main.qml`; a new `services/Config.qml`.

**Notes.** This introduces the first subprocess, so it sets the pattern for R2: own the
process, give it a deadline, bound its output, and cancel it on destruction. One
host-loaded owner, not one process per monitor. Read the config through
`bin/omarchy-mise config --json` rather than parsing TOML in QML.

**Done when.** Editing `ui.label` and reloading the shell changes the bar text; no
process is left running after the widget is destroyed; `Text.PlainText` still renders
the value.

---

## R2 — Task catalog service

**Scope.** One `services/TaskCatalog.qml` that owns catalog refreshes: runs
`bin/omarchy-mise catalog --json`, parses it, and exposes tasks, a loading state, and
an error state. No UI.

**Files.** `services/TaskCatalog.qml`, `Model.js` (pure parsing and validation),
`manifest.json` if a service entry point is needed.

**Notes.** Refresh on demand and on a bounded interval, never on a tight loop. A
replaced refresh cancels the one in flight. Distinguish empty, error, and cancelled —
they look the same to a user otherwise and each needs different wording. Carry the
per-project `trusted` flag through; a `trusted: false` project is a state to render,
not an error to swallow.

**Done when.** Unit tests cover `Model.js` parsing (including a malformed payload and
an untrusted project), and the service survives repeated creation and destruction with
no leaked process.

---

## R3 — Task list surface

**Scope.** A panel or overlay listing projects and their tasks, with filtering by name.
Read-only: no execution yet.

**Files.** `components/TaskList.qml`, `components/TaskRow.qml`, `Main.qml`.

**Notes.** Use Omarchy theme tokens throughout; no hard-coded colours. Keyboard
navigation stays inside the focused surface. Render task names and descriptions with
`Text.PlainText` — they come from files the plugin does not control. Show the `icon`
and `risk` metadata. Render empty, error, and untrusted states explicitly.

**Done when.** The list opens, filters, and closes; it looks right in both themes and
on a vertical bar; focus returns cleanly to the compositor on close.

---

## R4 — Run a task

**Scope.** Run the selected task from the list and report the outcome.

**Files.** `services/TaskRunner.qml`, `components/TaskStatus.qml`, and a `run`
subcommand in `scripts/python/omarchy_mise/`.

**Notes.** This is the part that must not be rushed. Execution requires an explicit
user action, never a hover or a focus change. Pass arguments as an argv array — never
build a shell string from a task name or user input. Honour `run.timeout_seconds` and
`run.confirm_risk`: a task whose metadata `risk` is in that list needs confirmation
first. Bound captured output. Show the project and task actually selected before
running. Cancellation must work and must be visible.

**Done when.** A task runs, a failing task reports its status and exit code, a
long-running task can be cancelled, a `high` risk task asks first, and no orphan
process survives the shell restarting.

---

## R5 — Task arguments

**Scope.** Prompt for the arguments a task declares in its `usage` string.

**Files.** `components/ParameterEditor.qml`, `Model.js`.

**Notes.** The catalog already carries each task's raw `usage`; parsing it into
required, optional, default, flag, and choice arguments belongs in `Model.js` where it
can be tested. The fixtures in `tasks/examples.toml` cover the required and defaulted
cases. Required arguments block the run; defaults pre-fill.

**Done when.** `example:param` prompts and refuses to run empty, `example:param-default`
pre-fills `world` and accepts an override, and `Model.js` has tests for each shape.

---

## R6 — Shell action and documented binding

**Scope.** Expose summon/toggle as Omarchy shell actions.

**Files.** `Main.qml`, `README.md`.

**Notes.** The plugin must not own a global keybinding — it would collide with Omarchy
defaults or the user's own mappings. Expose the action and document the binding a user
can add themselves.

**Done when.** `omarchy-shell <target> toggle` opens and closes the surface, and the
README documents an optional binding without installing one.

---

## R7 — Release 1.0.0

**Scope.** Ship it.

**Notes.** Follow the release steps in [DEVELOPMENT.md](DEVELOPMENT.md): desktop
checks, manual verification across bars, monitors, scale factors, reload and removal,
then the version bump, changelog, and tag.

---

## Deliberately out of scope for v1

Kept out so v1 stays a task runner:

- Watching the filesystem for task changes — refresh on demand is enough.
- Task output streamed into a terminal view; a status and an exit code suffice.
- Editing tasks or configuration from the widget. The config file is the interface.
- Caching the catalog on disk. Rebuild it; it is fast, and a stale cache is worse.
- Any network access, by the plugin or its support library.

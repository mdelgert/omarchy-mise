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

## How to pick up the next item

Everything that could run in parallel already has. Lanes B and C are merged, and
what remains — 4b, 5b, R6, R7 — is one sequential chain: 5b needs 4b, and all of it
edits `services/` and `components/`. **Do not fan these out to parallel agents.**
Two concrete reasons, beyond the dependency order:

- **Only one working tree can hold the plugin install.** The plugin id is unique, so
  `omarchy:install` from a second worktree relinks the first one out. Two agents
  doing QML would fight over the desktop.
- **QML fails at runtime in ways the linter cannot see.** Every item in this chain so
  far shipped a bug that `omarchy:check-desktop` passed happily: a delegate reading
  `ListView.view` from a nested child (null at runtime), a filter field that never
  received focus because `KeyboardPanel` overwrites `focusTarget` on a `callLater`,
  and three panels cancelling each other through the bar's single `activePopout`. An
  agent that only lints will hand you something plausible and broken.

So: one branch per item, one at a time, verified on a real bar before merging.

```sh
git switch dev && git pull
git switch -c lane/4b-run-task        # one branch per roadmap item
mise install                          # once per checkout
mise run omarchy:install              # symlink + enable; edits are then live
```

Then the loop, for every change:

```sh
mise run omarchy:check                # portable gate
mise run omarchy:check-desktop        # validator + qmllint on every QML file
mise run omarchy:restart              # QML changes need a restart, not a rescan
mise run omarchy:logs                 # watch for runtime errors
```

**Then actually use it.** Open the panel, click the thing, type in the field, try it
on a second monitor. A screenshot is evidence; a passing lint is not. `wtype` sends
real keystrokes and `grim -g "<x>,<y> <w>x<h>"` captures a region, which is how the
current surface was verified.

Finish by merging to `dev` with the gates green, then `mise run omarchy:uninstall`
if you are done on this machine.

## Parallelism, for the record

Earlier work split into three lanes by file ownership — QML, `usage.py`, `runner.py`
— run as concurrent agents in separate git worktrees. That worked because two of the
three lanes were pure Python with tests and needed no desktop. Keep the pattern in
mind for future work of that shape; it does not apply to what is left here.

## R1 — Read the configured label ✅ done

**Scope.** Make the widget show `ui.label` from `config.toml` instead of only the
host's inline `settings` entry. Precedence: host setting, then config file, then
the built-in default.

**Files.** `Main.qml`; a new `services/Config.qml`.

**Notes.** This introduces the first subprocess, so it sets the pattern for R2: own the
process, give it a deadline, bound its output, and cancel it on destruction. One
host-loaded owner, not one process per monitor. Read the config through
`bin/omarchy-mise config --json` rather than parsing TOML in QML.

**Done when.** Editing `ui.label` and reloading the shell changes the bar text; no
process is left running after the widget is destroyed; `Text.PlainText` still renders
the value.

---

## R2 — Task catalog service ✅ done

**Scope.** One `services/TaskCatalog.qml` that owns catalog refreshes: runs
`bin/omarchy-mise catalog --json`, parses it, and exposes tasks, a loading state, and
an error state. No UI.

**Files.** `services/TaskCatalog.qml`, `Model.js` (shaping already-valid JSON for the
view), `manifest.json` if a service entry point is needed.

**Depends on.** R1, for the process-ownership pattern.

**Notes.** Refresh on demand and on a bounded interval, never on a tight loop. A
replaced refresh cancels the one in flight. Distinguish empty, error, and cancelled —
they look the same to a user otherwise and each needs different wording. Carry the
per-project `trusted` flag through; a `trusted: false` project is a state to render,
not an error to swallow.

Validation belongs in the CLI, not in `Model.js`. This repository has no JavaScript
test runner and is not getting one — `omarchy-mise catalog` already guarantees the
payload's shape, so QML should trust it and fail visibly if it ever cannot parse it.

**Done when.** The service survives repeated creation and destruction with no leaked
process, renders a malformed payload as an error state rather than crashing, and
carries `trusted: false` through to the view.

---

## R3 — Task list surface ✅ done

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

## R4 — Run a task ✅ done

**Scope.** Run the selected task from the list and report the outcome.

**Files.** `scripts/python/omarchy_mise/runner.py` plus a `run` subcommand and tests
(4a); `services/TaskRunner.qml` and `components/TaskStatus.qml` (4b).

**Depends on.** 4a depends on nothing. 4b depends on 4a and R3.

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

## R5 — Task arguments ✅ done

**Scope.** Prompt for the arguments a task declares in its `usage` string.

**Files.** `scripts/python/omarchy_mise/usage.py` and its tests (5a);
`components/ParameterEditor.qml` (5b).

**Depends on.** 5a depends on nothing. 5b depends on 5a and R4.

**Notes.** Split this in two. The catalog already carries each task's raw `usage`
string; parsing it into required, optional, default, flag, and choice arguments is
pure string work, so it belongs in Python next to the tests that can prove it — not
in `Model.js`, which nothing in this repository can test. Emit the result as a
structured `arguments` list on each task, additively, so the existing JSON stays
valid. The fixtures in `tasks/examples.toml` cover the required and defaulted cases.
Required arguments block the run; defaults pre-fill.

**Done when.** `omarchy-mise catalog` reports structured arguments for
`example:param` and `example:param-default` with tests for each `usage` shape, then
the editor prompts, refuses to run an empty required argument, pre-fills `world`, and
accepts an override.

---

## R6 — Shell action and documented binding ✅ done

**Scope.** Expose summon/toggle as Omarchy shell actions.

**Files.** `Main.qml`, `README.md`.

**Already done by R3.** The widget implements the host's summon shape contract
(`open()`, `close()`, `opened`, plus the `closeForPopoutSwitch` /
`popoutSwitchClosing` forwarders), so `omarchy-shell shell toggle
io.github.mdelgert.omarchy-mise` already opens the panel on the focused monitor.
What is left here is documenting it as an optional user-chosen binding.

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

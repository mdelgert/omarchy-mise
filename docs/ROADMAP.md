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

## Working in parallel

The items below form a dependency chain, so handing R1–R7 to seven agents produces
seven conflicting edits to `Main.qml`. Split by *file ownership* instead. Three lanes
never touch the same file:

| Lane | Owns | Items | Needs a desktop |
| --- | --- | --- | --- |
| **A — QML** | `Main.qml`, `services/`, `components/` | ~~R1 → R2 → R3~~ → 4b → 5b → R6 | Yes |
| **B — argument parser** | `scripts/python/omarchy_mise/usage.py` | ~~5a~~ | No |
| **C — task runner** | `scripts/python/omarchy_mise/runner.py` | ~~4a~~ | No |

**Where things stand.** R1, R2, R3, 4a and 5a are merged. What remains is the QML
half of running a task (4b), the argument editor (5b), the documented binding (R6),
and the release (R7) — all of it lane A, all of it sequential, and all of it needing
a desktop. The data layer beneath it is complete: `omarchy-mise catalog` reports
every task with structured `arguments`, and `omarchy-mise run` executes one safely.

Lane A is strictly sequential: each item establishes something the next one uses, and
R1 exists to set the process-ownership pattern the rest copy. Lanes B and C are pure
Python with tests and can start immediately, in parallel with each other and with
lane A.

Both Python lanes touch `cli.py` to register a subcommand and `catalog.py` or its
payload, so keep those edits additive and expect a small merge there. Nothing else
overlaps.

Two constraints on running lanes concurrently:

- **Only one working tree can be installed at a time.** The plugin id is unique, so
  `omarchy:install` from a second worktree relinks the first one out. Give the
  install to whichever lane is doing QML; the Python lanes never need it.
- **Visual verification is not parallelisable and is not an agent's job.** An agent
  can get `omarchy:check-desktop` to pass; only a person can confirm the widget looks
  right on a real bar. Merge a QML lane only after you have seen it running.

Give each lane its own git worktree so the trees cannot collide:

```sh
claude --worktree lane-b            # new worktree + branch + session
# or, by hand:
git worktree add ../omarchy-mise-lane-b -b lane/usage-parser
cd ../omarchy-mise-lane-b && mise install && claude
```

Run one in the background and check on it later:

```sh
claude --bg --worktree lane-c "Implement roadmap item 4a in docs/ROADMAP.md."
claude agents        # list background sessions
claude logs <id>     # read its output
claude attach <id>   # take it over interactively
```

Each lane finishes the same way any change does: `mise run omarchy:check` green, a
test for every behaviour, a `CHANGELOG.md` entry, then merge to `dev`.

---

## R1 — Read the configured label ✅ done

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

## R4 — Run a task — 4a ✅ done, 4b remaining

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

## R5 — Task arguments — 5a ✅ done, 5b remaining

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

## R6 — Shell action and documented binding

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

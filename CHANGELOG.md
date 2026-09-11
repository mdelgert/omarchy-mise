# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Running a task from the panel: `services/TaskRunner.qml` starts `omarchy-mise run`,
  parses the one JSON object it prints, and exposes the outcome; `components/TaskStatus.qml`
  shows a one-line summary plus the last few lines of output. Every decision that
  matters — whether the task exists, whether the project is trusted, the risk
  confirmation, the timeout, the output cap — stays in the CLI. A task whose risk is
  in `run.confirm_risk` is refused first and only retried with `--confirm` after a
  `ConfirmDialog` is answered, so nothing is spawned before a human agrees.
- `components/ParameterEditor.qml`, an inline form for the arguments a task declares.
  It collects `{name: value}` and nothing else; `omarchy-mise run --arg NAME=VALUE`
  (new, repeatable) orders the values into argv against the task's own usage spec, so
  the widget never has to know whether an argument is positional or which spelling a
  flag declared. A required argument left blank, a name the task does not declare,
  and a `usage` spec that cannot be parsed are all refused before mise is spawned.
- A documented keybinding for the panel in `README.md`, routed through
  `omarchy-shell shell toggle` so the host picks which monitor's copy to act on.
- `~/.config/omarchy-mise/config.toml` is now created automatically: by
  `mise run omarchy:install`, and by `services/TaskCatalog.qml` the first time the
  service loads, which is the earliest moment a plugin added with `omarchy plugin add`
  can write anything (Omarchy deliberately runs no plugin code at install time).
  Neither path overwrites an existing file, so an edited config survives a reinstall.

### Changed

- The bar label defaults to an icon instead of the word "Mise": U+F487, a rocket and
  one of the glyphs Omarchy's own menu draws. Omarchy pins
  fontconfig's `monospace` alias to a Nerd Font and draws its own bar and menu icons
  from that range, so it renders everywhere without this plugin shipping a font. Any
  string still works, and `config.example.toml` links the Nerd Fonts cheat sheet and
  lists the icons Omarchy itself uses. `DEFAULT_LABEL` in `services/Plugin.js` is the
  QML-side fallback; a test fails if it drifts from the Python default.
- `scan.directories` no longer has a built-in default. Guessing at a layout meant
  scanning directories the user never named, so the list now starts empty in Python
  and the starter `config.example.toml` is the only place a path is suggested — it
  ships the plugin's own install, which is a mise project itself, so a fresh install
  still has something to list. An empty list stays a warning naming the file to edit,
  not an error.
- `omarchy-mise doctor` no longer fails when `scan.directories` is unconfigured. With
  no built-in default that is the state every fresh install starts in, so the check
  now reports it as a warning naming the config file and exits 0; a directory that
  was named and is not there still fails.

- Task argument parsing: `scripts/python/omarchy_mise/usage.py` turns a task's `usage`
  string into a structured list, and every task in `omarchy-mise catalog` now carries
  it under a new `arguments` key alongside the raw `usage` string. Each entry reports
  `name`, `kind`, `required`, `default`, `help`, `variadic`, `choices`, and a flag's
  `long`, `short`, `valueName`, and `negate`. A `usage` string that cannot be parsed
  becomes an `error` on that one task, like an unreadable project, rather than
  failing the catalog.
- Task execution: `omarchy-mise run <project> <task> [args...]` runs one mise task and
  reports the outcome as JSON — `ok`, `status`, `exitCode`, `durationSeconds`,
  `timedOut`, `truncated`, and the bounded `stdout`/`stderr`. The command is always an
  argv array, so a task name, a project path, and a user argument are data and never
  shell source. Only a task the catalog says exists, in a project the user has trusted,
  can run; `run.timeout_seconds` (overridable with `--timeout`) ends a task and the
  whole process group it created; a task whose metadata `risk` is in `run.confirm_risk`
  is refused until `--confirm` is passed, because the CLI has no way to prompt.
- `services/TaskCatalog.qml`, the single owner of the task catalog, declared as the
  plugin's `service` entry point so the host loads one for the whole shell rather
  than one per monitor. It distinguishes idle, loading, ready, empty, error, and
  cancelled; a newer refresh cancels the one in flight; a cancelled refresh keeps the
  previous catalog rather than blanking it. Bar widgets subscribe through
  `bar.shell.serviceFor()` and never start a catalog process of their own.
- The bar label now comes from `ui.label` in the configuration file, read through
  `services/Config.qml`. Precedence is the host's inline `shell.json` setting, then
  the config file, then the built-in default; an unreadable or invalid config falls
  back to the default and logs the reason from the CLI.
- `~/.config/omarchy-mise/config.toml` as the plugin's configuration: the directories
  to scan for mise projects, scan depth, task include/exclude globs, the bar label,
  and run limits. Documented in `docs/CONFIGURATION.md`, templated in
  `config.example.toml`, created by `omarchy:config-init`.
- Project and task discovery: `omarchy:catalog` reports the mise projects found under
  the configured directories with their tasks and `[_.tasks.*]` metadata. Projects
  that are broken or untrusted are reported individually instead of failing the
  catalog.
- `bin/omarchy-mise`, one entry point for the mise tasks and the future widget, with
  `config`, `catalog`, `validate`, `manifest`, `install`, `uninstall`, `doctor`, and
  `paths` subcommands.
- `omarchy:install` and `omarchy:uninstall`, which symlink this checkout into Omarchy
  and remove it again, plus `omarchy:reload`, `omarchy:restart`, `omarchy:logs`, and
  `omarchy:doctor` for the debug loop.
- `omarchy:lint` and `omarchy:fmt` covering Python, shell, and TOML, with ruff,
  shellcheck, and taplo pinned in `mise.toml`.
- `docs/DEVELOPMENT.md` (build, debug, test, release), `docs/CONFIGURATION.md`,
  `docs/ROADMAP.md` (the sequenced v1 backlog), and `CONTRIBUTING.md`.
- Project agent configuration: `CLAUDE.md`, permission settings, and the
  `omarchy-mise-dev` and `omarchy-mise-tasks` skills under `.claude/`.
- `tasks/omarchy.meta.toml`, giving the developer tasks the same `icon`/`risk`/`tags`
  metadata as the fixtures. The plugin scans for mise projects, so it renders this
  repository's own tasks; `omarchy:restart` is marked `high` risk because it tears
  down the bar the widget runs in.
- A test that every task has a metadata entry and every entry names a real task, so
  the two files cannot drift.
- A *Working in parallel* section in the roadmap: the lane split by file ownership,
  the two constraints on running lanes concurrently, and the worktree commands.
- CI now runs on a concurrency group and tests against Python 3.11 and 3.13.

### Changed

- Consolidated the duplicate bash and Python metadata scripts into one Python support
  library at `scripts/python/omarchy_mise/`, which now also merges task metadata with
  live `mise tasks` output rather than only reading the metadata.
- Split the task files: developer tasks stay under `omarchy:` in `tasks/omarchy.toml`,
  and the fixtures the plugin browses moved to `tasks/examples.toml` under the
  `example:` prefix (`omarchy:hello` is now `example:hello`, and so on).
- `omarchy:check` now runs lint and tests as well as manifest validation.
- `omarchy:check-desktop` lints every QML file rather than only the entry point, so a
  service or component nothing imports yet cannot hide an error. It also demotes
  `signal-handler-parameters`: Quickshell does not export `QProcess::ExitStatus` to
  QML, and `Process.exited` is the only way to read an exit code.
- Roadmap R2 and R5 no longer put testable logic in `Model.js`; this repository has
  no JavaScript test runner, so `usage`-string parsing moves to Python and QML trusts
  the CLI's payload. R4 and R5 are split into their Python and QML halves so the two
  can be owned separately.
- `omarchy:check-desktop` gives `qmllint` a `qs`-rooted import path. Quickshell
  exposes the shell config root as the `qs` namespace, so the previous import path
  left every import, the `BarWidget` base type, and every inherited property
  unresolved — fourteen spurious warnings.
- Moved the project skill from `skills/authoring/` to `.claude/skills/`, where Claude
  Code discovers it.

### Removed

- `scripts/bash/all-metadata.sh` and `scripts/bash/task-meta.sh`, duplicated by the
  Python implementation.
- `scripts/python/task_meta.py`, which nothing referenced.

[Unreleased]: https://github.com/mdelgert/omarchy-mise/compare/v0.1.0...HEAD

## [0.1.0] - Unreleased

Initial scaffold: an installable, theme-aware Omarchy bar widget with portable
manifest validation and desktop checks.

[0.1.0]: https://github.com/mdelgert/omarchy-mise/releases/tag/v0.1.0

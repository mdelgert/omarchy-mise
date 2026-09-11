# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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

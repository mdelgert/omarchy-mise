# Configuration

The plugin reads one optional TOML file:

```
~/.config/omarchy-mise/config.toml
```

`$XDG_CONFIG_HOME` is honoured if set, and `$OMARCHY_MISE_CONFIG` overrides the path
entirely. Nothing is ever written inside the installed plugin, so a reinstall or an
upgrade cannot lose your settings.

```sh
bin/omarchy-mise config --init    # copy the documented template into place
bin/omarchy-mise config           # show what actually resolved
```

`bin/omarchy-mise` lives inside the plugin, so an installed copy is reached at
`~/.config/omarchy/plugins/io.github.mdelgert.omarchy-mise/bin/omarchy-mise`. From a
development checkout, `mise run omarchy:config-init` and `mise run omarchy:config` do
the same thing.

The file is optional: with no config the defaults below apply. Unknown sections and
keys load with a warning rather than an error, so a file written for a newer version
still works; a wrong type is a hard error naming the key.

## Settings

### `schema_version`

Integer, default `1`. A value higher than the plugin understands loads with a warning.

### `[ui]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `label` | string | `"Mise"` | Bar text. Trimmed to 80 characters and elided to fit. A blank value falls back to the default. |
| `max_tasks` | integer ≥ 1 | `200` | Hard ceiling on tasks loaded, so a large tree cannot stall the bar. Hitting it adds a `truncated` warning. |

### `[scan]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `directories` | list of strings | `["~/Source", "~/Projects", "~/src", "~/code"]` | Directories searched for mise projects. `~` and `$VARS` expand; entries that do not exist are skipped silently. |
| `max_depth` | integer ≥ 1 | `2` | Levels below each entry to descend. A directory that is itself a project is never descended into. |
| `follow_symlinks` | boolean | `false` | Follow symlinked directories while scanning. Off by default to avoid loops. |

A directory counts as a mise project when it contains any of `mise.toml`,
`.mise.toml`, `mise.local.toml`, `.mise.local.toml`, `mise/config.toml`,
`.mise/config.toml`, `.config/mise.toml`, `.config/mise/config.toml`, or a task
directory (`mise-tasks`, `.mise/tasks`, `mise/tasks`, `.config/mise/tasks`).

Scanning skips hidden directories and the usual noise: `.git`, `node_modules`,
`target`, `dist`, `build`, `.venv`, `vendor`, and similar.

### `[tasks]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `include` | list of glob patterns | `[]` | Allowlist matched against the task name. Empty means every task. |
| `exclude` | list of glob patterns | `[]` | Denylist, applied after `include`. |
| `hidden` | boolean | `false` | Include tasks mise marks hidden. |

Patterns are shell globs against the full task name, so `build:*` and `*:deploy` both
work.

### `[run]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `timeout_seconds` | integer ≥ 1 | `300` | Give up on a task that runs longer. |
| `confirm_risk` | list of strings | `["high"]` | Task metadata `risk` values that require confirmation before running. |

`[run]` is read by the task runner, which is [roadmap](ROADMAP.md) work; the settings
are validated today so configs written now stay valid.

## Trusted projects

mise refuses to read a config the user has not trusted, and a `[_.tasks.*]` metadata
table is enough to require it. Such a project appears in the catalog with
`"trusted": false` and an error telling you the command to run:

```sh
mise trust /path/to/project
```

The plugin never trusts a config for you. Trusting one lets it set environment
variables and run hooks, which is the user's decision to make deliberately.

Metadata in a `*.meta.toml` sidecar is read directly and needs no trust — only the
task list itself comes from mise.

## Task metadata

mise carries a user-defined `_` table through without interpreting it, which is where
a project describes how its tasks should be presented:

```toml
[_.tasks."build:web"]
icon = "hammer"
risk = "low"
tags = ["build", "frontend"]
```

Any keys are allowed; the plugin passes them through as the task's `metadata`. The two
recognised ones so far are `icon` and `risk` (compared against `run.confirm_risk`).

Put the table in the project's mise config, or in a sidecar next to the tasks it
describes. This repository uses a sidecar — see `tasks/examples.meta.toml` — and keeps
it out of mise's task loading with:

```toml
[task_config]
includes = ["tasks"]
excludes = ["tasks/**/*.meta.toml"]
```

Root configs are read first, so a sidecar wins on conflict.

## Inspecting

```sh
mise run omarchy:config      # resolved settings and any warnings
mise run omarchy:catalog     # what the widget would render
mise run omarchy:doctor      # config, catalog, install, and shell in one report
```

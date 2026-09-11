# Configuration

The plugin reads one optional TOML file:

```
~/.config/omarchy-mise/config.toml
```

`$XDG_CONFIG_HOME` is honoured if set, and `$OMARCHY_MISE_CONFIG` overrides the path
entirely. Nothing is ever written inside the installed plugin, so a reinstall or an
upgrade cannot lose your settings.

The plugin writes this file itself, so neither command below is a required step —
`--init` is there to recreate a file you deleted, and to see the template without
waiting for a shell restart:

```sh
bin/omarchy-mise config --init    # copy the documented template into place
bin/omarchy-mise config           # show what actually resolved
```

`bin/omarchy-mise` lives inside the plugin, so an installed copy is reached at
`~/.config/omarchy/plugins/io.github.mdelgert.omarchy-mise/bin/omarchy-mise`. From a
development checkout, `mise run omarchy:config-init` and `mise run omarchy:config` do
the same thing.

The plugin creates the file from `config.example.toml` the first time its service
loads, and `mise run omarchy:install` writes it too. Neither ever overwrites an
existing file, so an edited config survives every reinstall and upgrade. Omarchy runs
no plugin code during `omarchy plugin add` — a plugin is unsandboxed, so that is
deliberate — which is why the first load, rather than the install, is the earliest
moment the file can appear.

The file is still optional: with no config the defaults below apply. Unknown sections
and keys load with a warning rather than an error, so a file written for a newer
version still works; a wrong type is a hard error naming the key.

## Settings

### `schema_version`

Integer, default `1`. A value higher than the plugin understands loads with a warning.

### `[ui]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `label` | string | `""` (U+F487) | Shown in the bar. Any string: a glyph, a word, a letter, an emoji. Trimmed to 80 characters and elided to fit; a blank value falls back to the default. The default is a Nerd Font icon rather than a word — Omarchy pins fontconfig's `monospace` alias to a Nerd Font and draws its own bar and menu icons from that range, so it renders on every Omarchy install. Pick another from the [Nerd Fonts cheat sheet](https://www.nerdfonts.com/cheat-sheet) and paste the glyph, or use a `\uXXXX` / `\UXXXXXXXX` escape. `config.example.toml` lists the icons Omarchy itself uses. |
| `max_tasks` | integer ≥ 1 | `200` | Hard ceiling on tasks loaded, so a large tree cannot stall the bar. Hitting it adds a `truncated` warning. |

### `[scan]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `directories` | list of strings | `[]` | Directories searched for mise projects. `~` and `$VARS` expand; entries that do not exist are skipped silently. There is no built-in default — nothing is scanned unless this says so, so the plugin never reads directories you did not name. The starter config ships the plugin's own install here, so a fresh install has something to show; replace it with the directories your projects live in (for example `["~/Source", "~/Projects"]`). An empty list is not an error: the catalog returns no projects and a warning naming this file. |
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

Both are enforced by `omarchy-mise run`. A task whose metadata `risk` appears in
`confirm_risk` is refused unless the caller passes `--confirm`, and a task that
outruns `timeout_seconds` is terminated along with anything it spawned. The bar's
own `omarchy:restart` is marked `high`, so it makes a safe thing to try this on:

```sh
bin/omarchy-mise run . omarchy:restart      # refused, and nothing is spawned
```

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

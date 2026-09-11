# Authoring example tasks

The tasks in `tasks/examples.toml` are fixtures: the plugin discovers and renders them,
and they exercise mise's argument handling. Keep them realistic, deterministic, fast,
and safe to run repeatedly.

Developer tooling belongs in `tasks/omarchy.toml` under the `omarchy:` prefix instead.
Everything below applies to both files — the plugin scans for mise projects, so it
finds this repository and renders the developer tasks alongside the fixtures.

## Structure

Each task file has a sidecar next to it, and the pair is kept in sync:

| Runnable definitions | Display metadata | Prefix |
| --- | --- | --- |
| `tasks/examples.toml` | `tasks/examples.meta.toml` | `example:` |
| `tasks/omarchy.toml` | `tasks/omarchy.meta.toml` | `omarchy:` |

- Metadata goes under `[_.tasks."<name>"]`: `icon`, `risk`, and `tags`.
- `risk` is `low`, `medium`, or `high`, compared against the user's
  `run.confirm_risk` (default `["high"]`). Reserve `high` for a task that disrupts
  the session — `omarchy:restart` tears down the bar the widget runs in.
- Task definitions stay declarative. Non-trivial logic belongs in
  `scripts/python/omarchy_mise/` and is reached through `bin/omarchy-mise`.
- Use repository-relative paths, or `$MISE_PROJECT_ROOT` when a task needs an
  absolute one.

The sidecar exists because `task_config.excludes` keeps `*.meta.toml` out of mise's
task loading, which lets metadata sit next to the tasks it describes without mise
reading `_` as a task name. See [CONFIGURATION.md](CONFIGURATION.md) for how the same
keys work in a project's own mise config, and why that form requires the project to be
trusted.

## Arguments

Declare arguments with a `usage` string. A required positional argument has no
default:

```toml
usage = 'arg "<name>" help="Name to greet"'
run = 'echo "hello ${usage_name:?}"'
```

An optional positional argument declares one:

```toml
usage = 'arg "[name]" help="Name to greet" default="world"'
run = 'echo "hello ${usage_name?}"'
```

Quote every expansion. Choose argument names that stay valid in the `usage_...`
environment variables mise generates.

## Verification

```sh
mise run omarchy:check
```

Then exercise every branch directly — a missing required argument must fail, a default
must apply, an explicit value must override it:

```sh
mise run example:param Omarchy
mise run example:param            # must fail
mise run example:param-default
mise run example:param-default Omarchy
```

Confirm the plugin sees the task:

```sh
mise run omarchy:catalog --names | grep example:
```

On an Omarchy desktop, finish with:

```sh
mise run omarchy:check-desktop
```

`mise tasks validate` proves configuration shape, not runtime argument behaviour —
only running the task does that.

## Rules

- Never build a shell command by interpolating a task name or user input.
- Never add a global keybinding from a task, and never make one a side effect of
  another task. `omarchy:bind` is the one exception and already exists; it is
  explicit, conflict-checked, and reversible.
- Never change installed Omarchy files while developing fixtures.
- Change a task file and its `*.meta.toml` sidecar together; they drift easily. A
  task with no metadata renders blank in the plugin.

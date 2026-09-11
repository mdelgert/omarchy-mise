# Authoring mise task fixtures

The task files in this repository exercise behavior that Omarchy Mise will eventually discover and render. Keep fixtures realistic, deterministic, fast, and safe to run repeatedly.

## Structure

- Define runnable tasks in `tasks/omarchy.toml`.
- Keep the `omarchy:` namespace so fixtures remain grouped in `mise tasks`.
- Mirror custom metadata in `tasks/omarchy.meta.toml` for metadata-tool tests.
- Use repository-relative paths through `$MISE_PROJECT_ROOT` when a task calls a script.
- Put non-trivial logic in `scripts/`; task definitions should remain declarative.

## Arguments

Declare task arguments with a `usage` string. A required positional argument has no default:

```toml
usage = 'arg "<name>" help="Name to greet"'
run = 'echo "hello ${usage_name:?}"'
```

An optional positional argument declares a default:

```toml
usage = 'arg "[name]" help="Name to greet" default="world"'
run = 'echo "hello ${usage_name?}"'
```

Quote every expansion. Choose argument names that remain valid in mise's generated `usage_...` environment variables.

## Verification

Run the portable checks after each fixture change:

```sh
mise run omarchy:check
```

Then exercise every changed behavior directly, including missing required arguments, default values, and explicit overrides. On Omarchy, also run:

```sh
mise run omarchy:check-desktop
```

Before release, install the local checkout and manually verify horizontal and vertical bars, multiple monitors, scale factors, keyboard focus, shell reload, and clean removal.

---
name: omarchy-mise-tasks
description: Add or change a mise task and its display metadata in this repository. Use when adding a task to tasks/examples.toml or tasks/omarchy.toml, adding required/optional/flag/choice arguments to one, or editing the [_.tasks.*] icon/risk/tags metadata in the matching .meta.toml sidecar. Not for adding arbitrary user commands or global keybindings.
---

# Authoring example tasks

The tasks in `tasks/examples.toml` are fixtures: the plugin discovers and renders them,
and they exercise mise's argument handling. Keep them realistic, deterministic, fast,
and safe to run repeatedly. Developer tooling belongs in `tasks/omarchy.toml` instead.

Either way the task needs a metadata entry: each task file has a `*.meta.toml`
sidecar beside it (`examples.toml` / `examples.meta.toml`, `omarchy.toml` /
`omarchy.meta.toml`), and the plugin renders this repository's own tasks, so a task
missing from its sidecar shows up blank.

Full reference: [docs/AUTHORING.md](../../../docs/AUTHORING.md).

## Procedure

1. Check the name is free: `mise tasks ls --name-only`. Example tasks use the
   `example:` prefix; developer tasks use `omarchy:`.
2. Add the runnable definition to `tasks/examples.toml`, keeping it declarative —
   anything non-trivial belongs in `scripts/python/omarchy_mise/`.
3. Add matching display metadata to that file's sidecar under `[_.tasks."<name>"]`:
   `icon`, `risk` (`low`, `medium`, or `high`), and `tags`. `high` means the user is
   asked to confirm before it runs, so reserve it for a task that disrupts the
   session. The two files drift easily; change them together.
4. Quote every generated expansion. A required argument uses `${usage_name:?}`, a
   defaulted one `${usage_name?}`.
5. Run `mise run omarchy:check`.
6. Run the task for every argument branch: omitted required argument fails, supplied
   value succeeds, default applies, explicit override wins.
7. Confirm the catalog sees it: `mise run omarchy:catalog --names | grep <name>`.

## Pitfalls

- `mise tasks validate` proves configuration shape, not runtime argument behaviour.
- A `[_.tasks.*]` table in a project's own mise config makes mise require that config
  to be trusted. The sidecar keeps metadata readable without trust; see
  [docs/CONFIGURATION.md](../../../docs/CONFIGURATION.md).
- Never build a shell command by interpolating a task name or user input.
- Never add a global keybinding or change installed Omarchy files.

## Verification

- `mise run omarchy:check` exits zero.
- The task appears in `mise tasks ls` and in `mise run omarchy:catalog`.
- Every argument branch has direct execution evidence.
- `git diff --check` passes and unrelated work is untouched.

---
name: authoring-omarchy-mise-tasks
description: Author and verify Omarchy Mise task fixtures.
version: 0.1.0
author: Matthew Elgert, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [omarchy, mise, tasks]
    related_skills: []
---

# Omarchy Mise Task Authoring

Use this workflow to add or change mise task fixtures in this repository. It does not cover implementing the QML task browser.

## When to Use

- Adding a runnable example under the `omarchy:` namespace.
- Adding required, optional, variadic, flag, or choice arguments.
- Changing task metadata consumed by development scripts.

Do not use it to add arbitrary user commands or global keybindings.

## Prerequisites

- Work from the repository root on Linux.
- Load the `developer-toolchain-management` and `omarchy` skills first.
- Inspect `docs/AUTHORING.md`, `tasks/omarchy.toml`, and `tasks/omarchy.meta.toml` with `read_file` before editing.

## Procedure

1. Search for the intended task name with `search_files`; continue only when it does not collide with an existing task.
2. Add the executable definition to `tasks/omarchy.toml` and matching descriptive metadata to `tasks/omarchy.meta.toml` using `patch`.
3. Keep scripts declarative and quote every generated `usage_...` expansion. Required arguments use `${usage_name:?}`; defaulted arguments use `${usage_name?}`.
4. Run `terminal(command="mise run omarchy:check")`; completion requires a zero exit status.
5. Invoke the task for every argument branch. For a required argument, verify omission fails and a supplied value succeeds. For a default, verify both omission and override output.
6. Inspect `git diff --check` and `git diff`; completion requires every changed line to belong to the requested fixture.

## Pitfalls

- `mise tasks validate` proves configuration shape, not runtime argument behavior.
- Metadata can drift because executable and descriptive fixtures are separate files.
- Do not use shell interpolation for untrusted task names or convert argument arrays into command strings.
- Do not change installed Omarchy files while developing fixtures.

## Verification

- `mise run omarchy:check` passes.
- The task appears under the `omarchy:` namespace in `mise tasks`.
- Required/default/error paths have direct execution evidence.
- `git diff --check` passes and unrelated user work remains untouched.

#!/usr/bin/env bash
set -euo pipefail

jq -n \
  --arg implementation "bash" \
  --arg task_name "${MISE_TASK_NAME:-}" \
  --arg task_dir "${MISE_TASK_DIR:-}" \
  --arg project_root "${MISE_PROJECT_ROOT:-}" \
  --arg original_cwd "${MISE_ORIGINAL_CWD:-}" \
  --arg pwd "$PWD" \
  --arg user "${USER:-}" \
  --arg shell "${SHELL:-}" \
  '{
    implementation: $implementation,
    task_name: $task_name,
    task_dir: $task_dir,
    project_root: $project_root,
    original_cwd: $original_cwd,
    pwd: $pwd,
    user: $user,
    shell: $shell
  }'

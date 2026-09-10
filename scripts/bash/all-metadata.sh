#!/usr/bin/env bash
set -euo pipefail

command -v jq >/dev/null || {
  echo "jq is required" >&2
  exit 1
}

root="${MISE_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

tasks_json="$(mise tasks --json)"

# Metadata lives in two places:
#   1. the root mise.toml [_.tasks.*] table, readable via `mise config get`
#   2. tasks/**/*.meta.toml sidecars, which task_config.excludes keeps out of
#      mise entirely, so they must be read straight off disk
metadata_toml="$(
  mise config get _.tasks 2>/dev/null || true
  while IFS= read -r meta_file; do
    printf '\n'
    cat "$meta_file"
  done < <(find "$root/tasks" -name '*.meta.toml' -type f | sort)
)"

metadata_json='{}'
current_task=''

while IFS= read -r line; do
  # Ignore blank lines and comments
  [[ -z "${line//[[:space:]]/}" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue

  # Table headers arrive in two shapes:
  #   [hello]                     from `mise config get _.tasks`
  #   [_.tasks."dev:git:status"]  from a *.meta.toml sidecar
  # Any name containing a colon is emitted quoted, so the quotes must be
  # stripped or the name never matches the task name in `mise tasks --json`.
  if [[ "$line" =~ ^\[(.+)\]$ ]]; then
    current_task="${BASH_REMATCH[1]}"
    current_task="${current_task#_.tasks.}"
    current_task="${current_task#\"}"
    current_task="${current_task%\"}"

    metadata_json="$(
      jq \
        --arg task "$current_task" \
        '. + {($task): {}}' \
        <<<"$metadata_json"
    )"

    continue
  fi

  [[ -z "$current_task" ]] && continue

  # key = value
  if [[ "$line" =~ ^[[:space:]]*([^=[:space:]]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"

    # Let jq parse TOML-compatible primitive values:
    # strings, numbers, booleans, arrays.
    parsed="$(
      jq -cn \
        --arg value "$value" '
          $value
          | if test("^\".*\"$") then
              fromjson
            elif . == "true" then
              true
            elif . == "false" then
              false
            elif test("^-?[0-9]+(\\.[0-9]+)?$") then
              tonumber
            elif test("^\\[.*\\]$") then
              fromjson
            else
              .
            end
        '
    )"

    metadata_json="$(
      jq \
        --arg task "$current_task" \
        --arg key "$key" \
        --argjson value "$parsed" \
        '.[$task][$key] = $value' \
        <<<"$metadata_json"
    )"
  fi
done <<<"$metadata_toml"

jq \
  --argjson metadata "$metadata_json" '
    map(
      . as $task
      | . + {
          metadata: ($metadata[$task.name] // {})
        }
    )
  ' <<<"$tasks_json"

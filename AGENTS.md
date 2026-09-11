# Contributor instructions

These rules apply to every change in this repository, human or agent.

Preserve user work. Inspect the affected QML, Python, tests, and the git diff before
editing, and make the smallest coherent change. Never modify the installed Omarchy
tree or a user's desktop configuration while developing this repository.

## Plugin boundaries

- `manifest.json` is the public package contract. Keep its version consistent with
  the changelog.
- Keep `Main.qml` focused on composition and view-local behaviour. Reusable UI goes in
  `components/`, shared state in `services/`, pure parsing in JavaScript modules, and
  system integration in the Python support library — never in QML.
- Inspect the installed Omarchy APIs before using a property, signal, or injected
  object. `/usr/share/omarchy/shell/Ui/BarWidget.qml` is the base type. Do not guess
  host contracts.
- Use Omarchy theme tokens. Support horizontal and vertical bars, multiple monitors,
  mixed scale factors, reloads, and repeated creation and destruction.
- Render external strings with `Text.PlainText`. Bound external input and output.
  Pass arguments as argv arrays, never as shell strings, and never expose arbitrary
  command execution through settings.
- Own and cancel every process, timer, connection, and temporary file. Never block the
  QML thread, and never use `pkill` or `killall` for cleanup.
- Store mutable state under plugin-specific XDG paths, never in the installed
  checkout. Preserve unrelated user configuration on upgrade or removal.
- Do not add global keybindings. Expose shell actions and document optional bindings
  so the plugin cannot conflict with existing mappings.
- Never trust a mise config on the user's behalf. An untrusted project is a state to
  report, with the `mise trust` command they can run.

## Code boundaries

- One implementation per behaviour. The support library in
  `scripts/python/omarchy_mise/` is the single home for non-trivial logic; mise tasks
  and QML both reach it through `bin/omarchy-mise`. Do not add a second implementation
  in another language.
- Standard library only at runtime. `ruff`, `shellcheck`, and `taplo` are development
  tools, pinned in `mise.toml`.
- Keep the CLI's JSON output stable — the widget parses it. Extend it additively.
- Every behaviour change gets a test in `tests/`.
- Every task file has a `*.meta.toml` sidecar beside it, and every task in it has an
  entry. The plugin scans for mise projects, so it renders this repository's own
  tasks; a task with no metadata shows up blank. Add both halves in one change.
- Configuration belongs in `~/.config/omarchy-mise/config.toml`, documented in
  [docs/CONFIGURATION.md](docs/CONFIGURATION.md). Adding a setting means adding it to
  the schema, `config.example.toml`, the docs, and the tests.

## Verification

Run `mise run omarchy:check` after every coherent change; it must exit zero. Before a
release, or before calling any desktop change done, run
`mise run omarchy:check-desktop`, install from a local clone, and manually verify
placement, keyboard focus, reload, multi-monitor behaviour, and removal.

Static checks are not visual validation. A QML change is not verified until it has
been seen running. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) has the full loop.

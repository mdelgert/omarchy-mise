# Contributor instructions

Preserve user work and inspect the affected QML, scripts, tests, and Git diff before editing. Make the smallest coherent change; do not modify the installed Omarchy tree or a user's desktop configuration while developing this repository.

## Plugin boundaries

- Treat `manifest.json` as the public package contract and keep its version consistent with release notes.
- Keep `Main.qml` focused on composition and view-local behavior. Put reusable UI in `components/`, shared state in `services/`, pure parsing in JavaScript modules, and system integration in narrow scripts only when host APIs cannot provide it.
- Inspect the installed Omarchy APIs before using a property, signal, or injected object. Do not guess host contracts.
- Use Omarchy theme tokens and support horizontal and vertical bars, multiple monitors, mixed scale factors, reloads, and repeated creation/destruction.
- Render external strings with `Text.PlainText`. Bound external inputs and output. Prefer argument arrays over shell strings; never expose arbitrary command execution through settings.
- Own and cancel every process, timer, connection, and temporary file. Never block the QML thread or use `pkill`/`killall` for cleanup.
- Store mutable state under plugin-specific XDG paths, never in the installed checkout. Preserve unrelated user configuration and data on upgrade or removal.
- Do not add global keybindings. Expose shell actions and document optional user-chosen bindings so the plugin cannot conflict with existing mappings.

## Verification

Run `mise run omarchy:check` after every coherent change. Before release on Omarchy, run `mise run omarchy:check-desktop`, install from a local clone, and manually verify placement, keyboard focus, reload, multi-monitor behavior, and removal. Static checks are not visual validation.

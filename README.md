# Omarchy Mise

An [Omarchy](https://omarchy.org/) shell plugin for browsing and running
[mise](https://mise.jdx.dev/) tasks from the bar.

> **Status: browsing works, running does not — yet.** Clicking the bar widget opens a
> panel listing every task in your configured directories, grouped by project and
> filtered as you type. It is read-only for now: the runner underneath it is built and
> tested (`omarchy-mise run`), but it is not wired to the panel. What remains is the
> QML to run a task and prompt for its arguments — see
> [docs/ROADMAP.md](docs/ROADMAP.md).

## Install

Requires an Omarchy release with shell-plugin support.

```sh
omarchy plugin add https://github.com/mdelgert/omarchy-mise.git --enable
```

The plugin writes `~/.config/omarchy-mise/config.toml` the first time it loads, and
never overwrites it afterwards. That file is the only place scan directories come
from — there is no built-in default, so nothing outside it is ever read. It starts
pointing at the plugin's own install so the panel is not empty; edit it to name the
directories holding your mise projects. To create it up front instead:

```sh
~/.config/omarchy/plugins/io.github.mdelgert.omarchy-mise/bin/omarchy-mise config --init
```

From a development checkout the same command is `bin/omarchy-mise config --init`, or
`mise run omarchy:config-init`; `mise run omarchy:install` also writes it.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for every setting.

### Opening it with a key

The plugin installs no keybinding of its own — one you did not ask for is one that
silently shadows something you already use. Asking for it is one command:

```sh
omarchy-mise bind                      # SUPER + M, or pass your own combination
omarchy-mise bind "SUPER + CTRL + M"   # matches Omarchy's own panel bindings
omarchy-mise bind --status             # is it installed, and on which key
omarchy-mise unbind                    # remove it again
```

From a development checkout: `mise run omarchy:bind`, `omarchy:bind-status`,
`omarchy:unbind`.

It refuses a combination something else already holds and names the owner, so it
cannot shadow an Omarchy default or one of yours — `--force` accepts the collision
and writes the `hl.unbind` Omarchy requires ahead of the bind. The change is a single
delimited block in `~/.config/hypr/bindings.lua`, the file is backed up first, and
`unbind` removes exactly that block and nothing else.

To do it by hand instead, add this to `~/.config/hypr/bindings.lua` — but check
`omarchy menu keybindings --print` first, because many obvious combinations are
taken (`SUPER + SHIFT + M`, for one, is Omarchy's "Music"):

```lua
o.bind("SUPER + M", "Mise tasks", "omarchy-shell shell toggle io.github.mdelgert.omarchy-mise")
```

Go through `shell toggle`, not the plugin's own IPC target: the host resolves which
copy to act on, preferring one that is already open and otherwise the focused
monitor's. A bar widget exists per screen, so addressing the plugin directly reaches
whichever instance happened to register first.

`shell summon` and `shell hide` work the same way. The plugin also answers
`omarchy-shell io.github.mdelgert.omarchy-mise refresh`, which rebuilds the task
catalog — useful after adding a task to a project. One catalog is shared by every
screen, so that is a single rebuild however many monitors you have.

Remove it with `omarchy plugin remove io.github.mdelgert.omarchy-mise`.

## Develop

```sh
git clone https://github.com/mdelgert/omarchy-mise.git
cd omarchy-mise
mise install                    # ruff, shellcheck, taplo
mise run omarchy:check          # the gate — lint, tests, manifest, catalog
mise run omarchy:install        # symlink this checkout into Omarchy and enable it
```

`omarchy:install` links rather than copies, so edits are live. Restart the shell to
pick up QML changes, and remove the link when you are done:

```sh
mise run omarchy:restart
mise run omarchy:uninstall
```

[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) covers the full debug and test process.

## Tasks

Developer tasks use the `omarchy:` prefix; `example:` tasks are fixtures the plugin
discovers. `mise tasks` lists them all.

| Task | Purpose |
| --- | --- |
| `omarchy:check` | Portable gate: lint, tests, manifest, catalog smoke test |
| `omarchy:check-desktop` | Adds `omarchy-plugin-validate` and `qmllint` |
| `omarchy:test` | Unit tests |
| `omarchy:lint` / `omarchy:fmt` | Check / apply formatting for Python, shell, TOML |
| `omarchy:install` / `omarchy:uninstall` | Link or unlink this checkout as a plugin |
| `omarchy:reload` / `omarchy:restart` | Rescan plugins / restart the shell |
| `omarchy:logs` | Follow the Omarchy shell log |
| `omarchy:doctor` | Diagnose tools, config, catalog, install, and shell |
| `omarchy:catalog` | Print the projects and tasks the plugin would show |
| `omarchy:config` / `omarchy:config-init` | Show / create the configuration |
| `omarchy:bind` / `omarchy:unbind` | Add / remove the optional keybinding |
| `omarchy:bind-status` | Report whether the keybinding is installed |

## Layout

```
manifest.json          public plugin contract
Main.qml               bar-widget entry point
config.example.toml    documented configuration template
bin/omarchy-mise       one entry point for tasks and the widget
scripts/python/        the support library (stdlib only)
tasks/                 developer tasks and example fixtures
tests/                 unit tests
docs/                  contributor documentation
.claude/skills/        project skills for coding agents
```

## Contributing

Read [AGENTS.md](AGENTS.md) for the boundaries that apply to every change and
[CONTRIBUTING.md](CONTRIBUTING.md) for the workflow. `mise run omarchy:check` must
pass before a change is complete.

## License

[MIT](LICENSE)

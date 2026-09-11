# Omarchy Mise

An [Omarchy](https://omarchy.org/) shell plugin for browsing and running
[mise](https://mise.jdx.dev/) tasks from the bar.

> **Status: scaffold.** The plugin installs, themes itself, and renders a configurable
> bar label. The task browser is not built yet — but everything behind it is: the
> configuration format, project discovery, task and metadata collection, and the CLI
> the widget will call are all implemented and tested. Run `mise run omarchy:catalog`
> to see the data the browser will render. [docs/ROADMAP.md](docs/ROADMAP.md) lists
> what remains.

## Install

Requires an Omarchy release with shell-plugin support.

```sh
omarchy plugin add https://github.com/mdelgert/omarchy-mise.git --enable
```

Then create the configuration and point it at the directories holding your mise
projects:

```sh
~/.config/omarchy/plugins/io.github.mdelgert.omarchy-mise/bin/omarchy-mise config --init
```

That writes `~/.config/omarchy-mise/config.toml`. From a development checkout the
same command is `bin/omarchy-mise config --init`, or `mise run omarchy:config-init`.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for every setting. The plugin
installs no global keybinding; interactive surfaces will be exposed as shell actions
you can bind yourself.

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

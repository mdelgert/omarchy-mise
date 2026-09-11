# Omarchy Mise

An [Omarchy](https://omarchy.org/) shell plugin for browsing and running [mise](https://mise.jdx.dev/) tasks.

This repository currently provides an installable, theme-aware bar-widget scaffold. The task browser and runner are intentionally not implemented yet; the boundaries for that work are documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## Install

Requires an Omarchy release with shell-plugin support:

```sh
omarchy plugin add https://github.com/mdelgert/omarchy-mise.git --enable
```

The plugin does not install a global keybinding. Future interactive surfaces will be exposed as shell actions so users can bind them explicitly without overriding Omarchy or personal mappings.

## Development

```sh
mise install
mise tasks
mise run omarchy:check
```

Run the task argument fixtures:

```sh
mise run omarchy:param Omarchy
mise run omarchy:param-default
mise run omarchy:param-default Omarchy
```

On an Omarchy development machine, also run the authoritative manifest validator and QML linter:

```sh
mise run omarchy:check-desktop
```

Install the working tree for manual testing without modifying the system checkout:

```sh
omarchy plugin add "file://$(pwd)" --enable
```

Use `omarchy plugin remove io.github.mdelgert.omarchy-mise --yes` when testing is complete. Review [docs/AUTHORING.md](docs/AUTHORING.md) before adding task fixtures and [AGENTS.md](AGENTS.md) before changing plugin code.

## Project layout

- `manifest.json` — public plugin contract
- `Main.qml` — current bar-widget entry point
- `tasks/` — mise development and fixture tasks
- `scripts/` — bounded development utilities
- `docs/` — contributor documentation
- `skills/` — project-local agent workflows

## License

[MIT](LICENSE)

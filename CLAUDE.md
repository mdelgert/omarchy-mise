# Omarchy Mise

An Omarchy shell plugin that browses and runs mise tasks. Read **[AGENTS.md](AGENTS.md)**
before changing anything — it holds the plugin boundaries and the rules that apply to
every change in this repository.

## The loop

```sh
mise install              # once, to get ruff/shellcheck/taplo
mise run omarchy:check    # the gate: lint, tests, manifest, catalog (portable)
```

On an Omarchy desktop, also run `mise run omarchy:check-desktop` before calling
anything done, and `mise run omarchy:doctor` when something behaves oddly.

## Where things are

| Need | Read |
| --- | --- |
| Rules for changing plugin code | [AGENTS.md](AGENTS.md) |
| Build, debug, and test the plugin on a desktop | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| What is built and what the boundaries are | [ARCHITECTURE.md](ARCHITECTURE.md) |
| The next unit of work to pick up | [docs/ROADMAP.md](docs/ROADMAP.md) |
| `config.toml` schema and task metadata | [docs/CONFIGURATION.md](docs/CONFIGURATION.md) |
| Adding example tasks | [docs/AUTHORING.md](docs/AUTHORING.md) |

Two project skills cover the common workflows: `omarchy-mise-dev` for the
build/debug/test loop and `omarchy-mise-tasks` for adding example tasks.

# Development

How to build, debug, and test this plugin. Read [AGENTS.md](../AGENTS.md) first for the
boundaries every change has to respect.

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Linux | The plugin targets Omarchy; the support library and tests are portable |
| Python 3.11+ | Only the standard library is used (`tomllib` needs 3.11) |
| mise | Provides the tasks, and is what the plugin reads task data from |
| Omarchy with shell-plugin support | Needed for install, `qmllint`, and any visual check |

```sh
mise install    # ruff, shellcheck, taplo, pinned in mise.toml
```

`mise run omarchy:doctor` tells you what is missing.

## The loop

```sh
mise run omarchy:check          # run after every coherent change
mise run omarchy:check-desktop  # before calling a desktop change done
```

`omarchy:check` is portable and is what CI runs: `mise tasks validate`, ruff,
shellcheck, taplo, the unit tests, manifest validation, and a catalog smoke test.
`omarchy:check-desktop` adds Omarchy's own validator and `qmllint`.

## Installing for development

```sh
mise run omarchy:install
```

This symlinks the working tree into `~/.config/omarchy/plugins/<plugin id>` and enables
it. Omarchy's plugin catalog follows symlinks, so your edits are live and
`omarchy plugin remove` unlinks rather than deleting the repository. The task is
idempotent: running it again relinks and re-enables.

```sh
mise run omarchy:uninstall      # disable and unlink; the repository is untouched
```

To rehearse what a user experiences — a real clone rather than a link — use the
ordinary command and then remove it:

```sh
omarchy plugin add "file://$(pwd)" --enable
omarchy plugin remove io.github.mdelgert.omarchy-mise --yes
```

## Seeing a change

| Change | What to run |
| --- | --- |
| `manifest.json`, a new plugin file | `mise run omarchy:reload` (rescan) |
| `Main.qml` or any QML | `mise run omarchy:restart` — a rescan does not reload instantiated QML |
| Python support library | Nothing; the next `bin/omarchy-mise` call picks it up |
| `~/.config/omarchy-mise/config.toml` | Nothing; it is read on each call |

Restarting the shell is safe but visible — the bar disappears and comes back. It is
refused while the session is locked.

## Debugging

Start with the diagnostic, which covers the whole chain in one pass:

```sh
mise run omarchy:doctor
```

It reports each tool, whether the manifest and config load, which scan directories
exist, whether the catalog builds, whether the plugin is installed and enabled, and
whether the shell is responding. A failing line names the layer to look at.

### Runtime logs

Omarchy launches the shell under `systemd-cat`, so QML errors land in the journal:

```sh
mise run omarchy:logs                  # follow, last 200 lines
mise run omarchy:logs --lines 1000
journalctl --user -t omarchy-shell --since "10 min ago"
```

A QML error appears as a `WARN scene:` line naming the file and line number. Warnings
from other plugins are interleaved — match on this plugin's path.

### Inspecting the data layer

```sh
mise run omarchy:config                # resolved settings, including _warnings
mise run omarchy:catalog               # projects, tasks, metadata, warnings
bin/omarchy-mise catalog --names       # one project<TAB>task per line
```

`catalog` never fails because one project is broken: the project carries an `error`
and the rest still load. Two states are worth recognising:

- `"trusted": false` — mise refuses to read a config the user has not trusted.
  Trusting a config lets it set environment variables and run hooks, so it is the
  user's decision: they run `mise trust <path>`. The plugin never trusts anything on
  their behalf.
- `warnings` containing `task list truncated` — `ui.max_tasks` was reached.

### QML linting

`omarchy:check-desktop` builds a temporary directory containing a `qs` symlink to the
installed shell before calling `qmllint`. Quickshell exposes the shell config root as
the `qs` namespace, so `import qs.Ui` resolves to `<import path>/qs/Ui`; pointing
`qmllint` straight at the shell directory makes every import, the `BarWidget` base
type, and every inherited property report as unresolved.

Four `missing-property` lines on `bar` and `Style.font` remain by design — the host
declares both as untyped `QObject`, so their members cannot be resolved from outside.
They are demoted to `Info` so that a genuinely new warning stands out.

## Testing

```sh
mise run omarchy:test
python3 -m unittest tests.test_catalog -v          # one module
python3 -m unittest tests.test_catalog.TrustTests  # one class
```

Tests are stdlib `unittest`, run without installing anything (`tests/__init__.py` puts
the library on `sys.path`). Tests that shell out to mise create a real project in a
temporary directory and set `MISE_TRUSTED_CONFIG_PATHS` so the config is readable;
everything else is deterministic and offline.

Static checks are not visual validation. Before a release, install the plugin and
verify by hand: horizontal and vertical bars, multiple monitors, mixed scale factors,
keyboard focus, a shell reload, and clean removal.

## Releasing

1. `mise run omarchy:check-desktop` passes.
2. Manual desktop verification as above.
3. Bump `version` in `manifest.json` and move the `CHANGELOG.md` entries from
   Unreleased into the new version.
4. Tag `vX.Y.Z` and push. Users pick it up with `omarchy plugin update`.

"""Command line entry point: `bin/omarchy-mise <command>`.

Machine-readable subcommands print JSON, because the QML widget is the other
caller. `--json` makes that output compact for piping; the default is indented
so a developer reading it in a terminal can follow it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from . import __version__, catalog, manifest, paths, plugin
from . import config as config_module

EXIT_OK = 0
EXIT_FAILURE = 1


def _emit(payload: Any, compact: bool) -> None:
    if compact:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _config_path(args: argparse.Namespace) -> Path | None:
    return Path(args.config).expanduser() if args.config else None


def cmd_config(args: argparse.Namespace) -> int:
    if args.init:
        target = config_module.write_default(_config_path(args), force=args.force)
        print(f"config: {target}")
        return EXIT_OK
    _emit(config_module.load(_config_path(args)), args.json)
    return EXIT_OK


def cmd_catalog(args: argparse.Namespace) -> int:
    settings = config_module.load(_config_path(args))
    payload = catalog.build(settings)
    if args.names:
        for project in payload["projects"]:
            for task in project["tasks"]:
                print(f"{project['path']}\t{task['name']}")
        return EXIT_OK
    _emit(payload, args.json)
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    document = manifest.validate()
    print(f"manifest ok: {document['id']} {document['version']}")
    return EXIT_OK


def cmd_manifest(args: argparse.Namespace) -> int:
    document = manifest.read()
    if args.field:
        if args.field not in document:
            raise manifest.ManifestError(f"no such manifest field: {args.field}")
        value = document[args.field]
        print(value if isinstance(value, str) else json.dumps(value))
        return EXIT_OK
    _emit(document, args.json)
    return EXIT_OK


def cmd_install(args: argparse.Namespace) -> int:
    print(plugin.install(section=args.section, enable=not args.no_enable))
    return EXIT_OK


def cmd_uninstall(args: argparse.Namespace) -> int:
    print(plugin.uninstall())
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    report = plugin.doctor()
    if args.json:
        _emit(report, compact=True)
    else:
        marks = {True: "ok  ", False: "FAIL", None: "--  "}
        for item in report["checks"]:
            print(f"{marks[item['ok']]} {item['check']}: {item['detail']}")
        print(f"\n{report['failures']} failing check(s)")
    return EXIT_OK if report["ok"] else EXIT_FAILURE


def cmd_paths(args: argparse.Namespace) -> int:
    _emit(
        {
            "repo": str(paths.repo_root()),
            "config": str(paths.config_file()),
            "cache": str(paths.cache_home()),
            "state": str(paths.state_home()),
            "plugins": str(paths.plugins_dir()),
        },
        args.json,
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    # The shared options are accepted on either side of the subcommand, because
    # `omarchy-mise config --json` is what everyone types first. SUPPRESS keeps
    # an unused subcommand flag from overwriting the value given up front.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="emit compact JSON"
    )
    common.add_argument(
        "--config",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="override the config file location",
    )

    parser = argparse.ArgumentParser(
        prog="omarchy-mise",
        description="Support commands for the Omarchy Mise plugin.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--json", action="store_true", help="emit compact JSON")
    parser.add_argument("--config", metavar="PATH", help="override the config file location")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser(
        "config", help="show or create the configuration", parents=[common]
    )
    config_parser.add_argument("--init", action="store_true", help="write a starter config.toml")
    config_parser.add_argument("--force", action="store_true", help="overwrite an existing config")
    config_parser.set_defaults(handler=cmd_config)

    catalog_parser = subparsers.add_parser(
        "catalog", help="discover mise projects and tasks", parents=[common]
    )
    catalog_parser.add_argument(
        "--names", action="store_true", help="print 'project<TAB>task' lines instead of JSON"
    )
    catalog_parser.set_defaults(handler=cmd_catalog)

    subparsers.add_parser("validate", help="validate manifest.json", parents=[common]).set_defaults(
        handler=cmd_validate
    )

    manifest_parser = subparsers.add_parser(
        "manifest", help="print manifest.json or one field", parents=[common]
    )
    manifest_parser.add_argument("field", nargs="?", help="field to print, e.g. id")
    manifest_parser.set_defaults(handler=cmd_manifest)

    install_parser = subparsers.add_parser(
        "install", help="link this checkout into Omarchy and enable it", parents=[common]
    )
    install_parser.add_argument("--section", choices=("left", "center", "right"))
    install_parser.add_argument("--no-enable", action="store_true", help="link without enabling")
    install_parser.set_defaults(handler=cmd_install)

    subparsers.add_parser(
        "uninstall", help="disable and unlink this plugin", parents=[common]
    ).set_defaults(handler=cmd_uninstall)

    subparsers.add_parser(
        "doctor", help="diagnose the local plugin setup", parents=[common]
    ).set_defaults(handler=cmd_doctor)

    subparsers.add_parser(
        "paths", help="print the paths this plugin uses", parents=[common]
    ).set_defaults(handler=cmd_paths)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (
        config_module.ConfigError,
        manifest.ManifestError,
        catalog.CatalogError,
        plugin.PluginError,
    ) as error:
        print(f"omarchy-mise {args.command}: {error}", file=sys.stderr)
        return EXIT_FAILURE
    except KeyboardInterrupt:
        return 130

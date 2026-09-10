#!/usr/bin/env python3
"""Read arbitrary [_.tasks.*] metadata from the root config and *.meta.toml sidecars."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tomllib

ROOT = Path(os.environ.get("MISE_PROJECT_ROOT") or Path(__file__).resolve().parents[2])

def read_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)

def collect() -> dict:
    catalog: dict[str, dict] = {}

    # Root mise.toml demonstrates the exact [_.tasks.hello] form.
    root_cfg = read_toml(ROOT / "mise.toml")
    for name, meta in root_cfg.get("_", {}).get("tasks", {}).items():
        catalog[name] = dict(meta)

    # Sidecars allow metadata to stay next to included task TOMLs without
    # making mise interpret "_" as an included task name.
    for path in sorted((ROOT / "tasks").rglob("*.meta.toml")):
        doc = read_toml(path)
        for name, meta in doc.get("_", {}).get("tasks", {}).items():
            item = dict(meta)
            item["_metadata_file"] = str(path.relative_to(ROOT))
            catalog[name] = item

    return catalog

if __name__ == "__main__":
    print(json.dumps(collect(), indent=2, sort_keys=True))

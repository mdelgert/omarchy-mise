"""Support library for the Omarchy Mise plugin.

Every non-trivial operation the plugin or its mise tasks need lives here so
there is exactly one implementation of each behaviour. The QML widget and the
`omarchy:*` mise tasks both reach it through the `bin/omarchy-mise` shim.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"

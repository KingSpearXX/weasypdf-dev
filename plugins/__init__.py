"""Plugin auto-discovery for data map extensions."""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Callable, MutableMapping

Registry = dict[str, Callable[..., object]]
REGISTRY: Registry = {}
_LOADED = False


def load_plugins(force_reload: bool = False) -> Registry:
    """
    Import every module inside this package and collect their plugins.

    Modules can either expose a ``register(registry)`` function or define
    ``PLUGIN`` (callable) plus optional ``PLUGIN_NAME``.
    """

    global REGISTRY, _LOADED
    if _LOADED and not force_reload:
        return REGISTRY

    registry: Registry = {}
    package_name = __name__
    package_path = __path__  # type: ignore[name-defined]

    for module_info in pkgutil.iter_modules(package_path):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package_name}.{module_info.name}")
        _register_module_plugins(module, registry)

    REGISTRY = registry
    _LOADED = True
    return REGISTRY


def _register_module_plugins(
    module: ModuleType, registry: MutableMapping[str, Callable[..., object]]
) -> None:
    if callable(getattr(module, "register", None)):
        module.register(registry)
        return

    plugin = getattr(module, "PLUGIN", None)
    if not callable(plugin):
        return

    name = getattr(module, "PLUGIN_NAME", module.__name__.rsplit(".", 1)[-1])
    registry[str(name)] = plugin


# Prime the registry on import for convenience.
load_plugins()

__all__ = ["REGISTRY", "load_plugins"]

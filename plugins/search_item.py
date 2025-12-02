"""Plugin utilities for searching lists of mappings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, MutableMapping


def find_item(
    items: Iterable[Mapping[str, Any]] | None,
    *,
    key: str,
    value: Any,
) -> Mapping[str, Any] | None:
    if not items or not key:
        return None

    for item in items:
        if not isinstance(item, Mapping):
            continue
        candidate = item.get(key)
        if candidate == value:
            return deepcopy(item)
        if _loose_equals(candidate, value):
            return deepcopy(item)
    return None

def _loose_equals(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)

def register(registry: MutableMapping[str, Any]) -> None:
    """Expose plugin(s) to the shared registry."""

    registry["find_item"] = find_item
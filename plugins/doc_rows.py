"""Utilities for generating SAP-style document row sequences."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Callable, Iterable, Mapping, MutableMapping, MutableSequence


def get_doc_rows(
    *,
    document_lines: Iterable[Mapping[str, object]] | None = None,
    special_lines: Iterable[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """
    Merge main document lines and special lines in SAP's row order.

    Args:
        document_lines: Main `DocumentLines` collection already fetched upstream.
        special_lines: Optional `DocumentSpecialLines` collection.

    Returns:
        A list combining main and special lines in the expected sequence.
    """

    main_rows = _normalize_lines(document_lines, default_line_type="dlt_Regular")
    special_rows = _normalize_lines(special_lines)

    sorted_main = sorted(main_rows, key=_safe_line_num)
    grouped_specials = _group_special_lines(special_rows)

    final_rows: MutableSequence[dict[str, object]] = []
    for main_line in sorted_main:
        final_rows.append(deepcopy(main_line))
        line_num = _safe_line_num(main_line)
        for special_line in grouped_specials.get(line_num, []):
            final_rows.append(deepcopy(special_line))

    return list(final_rows)


def register(registry: MutableMapping[str, Callable[..., object]]) -> None:
    """Register this module's plugin(s) into the shared registry."""

    registry["doc_rows"] = get_doc_rows


def _group_special_lines(
    special_lines: Iterable[Mapping[str, object]]
) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)

    for line in special_lines:
        after_line = _to_int(line.get("AfterLineNumber"), default=-1)
        grouped[after_line].append(dict(line))

    for lines in grouped.values():
        lines.sort(key=_safe_order_number)

    return grouped


def _safe_line_num(line: Mapping[str, object]) -> int:
    return _to_int(line.get("LineNum"), default=0)


def _safe_order_number(line: Mapping[str, object]) -> int:
    return _to_int(line.get("OrderNumber"), default=0)


def _normalize_lines(
    lines: Iterable[Mapping[str, object]] | None, *, default_line_type: str | None = None
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if not lines:
        return normalized

    for line in lines:
        entry = dict(line)
        if default_line_type and not entry.get("LineType"):
            entry["LineType"] = default_line_type
        normalized.append(entry)

    return normalized


def _to_int(value: object, *, default: int) -> int:
    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int,)):
        return int(value)

    if isinstance(value, float):
        return int(value)

    try:
        text = str(value).strip()
        if not text:
            return default
        if "." in text:
            return int(float(text))
        return int(text, 10)
    except (TypeError, ValueError):
        return default

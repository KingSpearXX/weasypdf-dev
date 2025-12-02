from __future__ import annotations

import json
import time
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Sequence
from urllib import error as url_error
from urllib import parse, request

from plugins import REGISTRY as PLUGIN_REGISTRY
from plugins import load_plugins

PLACEHOLDER_PATTERN = re.compile(r"{([^{}]+)}")


@dataclass
class FetchRequest:
    """Normalized fetch configuration provided to the HTTP client layer."""

    method: str
    url: str
    headers: dict[str, Any]
    params: dict[str, Any] | None
    body: Any
    timeout: float | None


class DataMapResolver:
    def __init__(
        self,
        *,
        default_timeout: float = 15.0,
        http_fetcher: Callable[[FetchRequest], bytes] | None = None,
        plugin_registry: Mapping[str, Callable[..., Any]] | None = None,
    ):
        self.default_timeout = default_timeout
        self._http_fetcher = http_fetcher
        self._plugins = dict(plugin_registry or load_plugins() or PLUGIN_REGISTRY)

    def resolve(
        self,
        data_map: Mapping[str, Any],
        seed_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:

        state: dict[str, Any] = dict(seed_context or {})
        resolved: dict[str, Any] = {}
        for key, value in data_map.items():
            resolved_value = self._resolve_node(value, state)
            resolved[key] = resolved_value
            state[key] = resolved_value
        return resolved

    def _resolve_node(self, node: Any, state: MutableMapping[str, Any]) -> Any:
        if isinstance(node, str):
            return self._interpolate(node, state)

        if isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            return [self._resolve_node(item, state) for item in node]

        if isinstance(node, Mapping):
            if "fetch" in node:
                result = self._handle_fetch(node["fetch"], state)
                return self._apply_transform(node.get("transform"), result)

            if "sequence" in node:
                result = self._handle_sequence(node["sequence"], state)
                return self._apply_transform(node.get("transform"), result)

            if "value" in node and set(node.keys()) <= {"value", "transform"}:
                value = self._resolve_node(node["value"], state)
                return self._apply_transform(node.get("transform"), value)

            if set(node.keys()) == {"ref"}:
                reference = self._resolve_reference(str(node["ref"]), state)
                return deepcopy(reference)

            # Nested mapping: resolve each item individually
            nested: dict[str, Any] = {}
            for key, value in node.items():
                nested[key] = self._resolve_node(value, state)
            return nested

        return deepcopy(node)

    def _handle_sequence(
        self, steps: Sequence[Mapping[str, Any]], state: MutableMapping[str, Any]
    ) -> list[Any]:
        results: list[Any] = []
        for step in steps:
            action = step.get("action", "value")
            result: Any
            if action == "fetch":
                result = self._handle_fetch(step.get("config", {}), state)
            elif action == "assign":
                result = self._resolve_node(step.get("value"), state)
            elif action == "plugin":
                result = self._handle_plugin(step, state)
            elif action == "delay":
                seconds = float(step.get("seconds", 0))
                time.sleep(max(seconds, 0))
                result = None
            else:
                result = self._resolve_node(step, state)

            result = self._apply_transform(step.get("transform"), result)

            if identifier := step.get("id"):
                state[identifier] = result

            results.append(result)

        return results

    def _handle_plugin(
        self,
        step: Mapping[str, Any],
        state: MutableMapping[str, Any],
    ) -> Any:
        name = step.get("name")
        if not name:
            raise ValueError("plugin action requires a 'name' field")

        plugin = self._plugins.get(str(name))
        if plugin is None:
            raise ValueError(f"Unknown plugin '{name}'")

        raw_args = step.get("args", [])
        raw_kwargs = step.get("kwargs", {})
        if raw_args and (
            not isinstance(raw_args, Sequence) or isinstance(raw_args, (str, bytes))
        ):
            raise TypeError("plugin args must be a list")
        if raw_kwargs and not isinstance(raw_kwargs, Mapping):
            raise TypeError("plugin kwargs must be an object")

        args = [
            self._resolve_plugin_param(value, state) for value in (raw_args or [])
        ]
        kwargs = {
            key: self._resolve_plugin_param(value, state)
            for key, value in (raw_kwargs or {}).items()
        }

        return plugin(*args, **kwargs)

    def _resolve_plugin_param(self, value: Any, state: Mapping[str, Any]) -> Any:
        if isinstance(value, str):
            return self._interpolate(value, state)
        if isinstance(value, Mapping):
            if "ref" in value and set(value.keys()) == {"ref"}:
                reference = self._resolve_reference(str(value["ref"]), state)
                return deepcopy(reference)
            return {
                key: self._resolve_plugin_param(inner, state)
                for key, inner in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [
                self._resolve_plugin_param(item, state) for item in value
            ]
        return deepcopy(value)

    def _handle_fetch(
        self,
        config: Mapping[str, Any],
        state: MutableMapping[str, Any],
    ) -> Any:
        if "url" not in config:
            raise ValueError("fetch config requires a 'url' field")

        method = config.get("method", "GET").upper()
        url = self._interpolate(config["url"], state)
        headers = self._interpolate_structure(config.get("headers", {}), state)
        params = self._interpolate_structure(config.get("params"), state)
        body = self._interpolate_structure(config.get("body"), state)
        timeout = config.get("timeout", self.default_timeout)
        default_value = deepcopy(config.get("default"))

        fetch_request = FetchRequest(
            method=method,
            url=url,
            headers=dict(headers) if headers else {},
            params=dict(params) if isinstance(params, Mapping) else params,
            body=body,
            timeout=timeout,
        )

        try:
            raw_response = (
                self._http_fetcher(fetch_request)
                if self._http_fetcher
                else self._default_http_fetch(fetch_request)
            )
        except Exception as exc:  # noqa: BLE001
            if "default" in config:
                return default_value
            raise RuntimeError(f"fetch failed for {url}") from exc

        try:
            processed = self._apply_fetch_transform(config.get("transform"), raw_response)
        except Exception as exc:  # noqa: BLE001
            if "default" in config:
                return default_value
            raise
        if target := config.get("target"):
            self._assign_path(state, target, processed)
        if fetch_id := config.get("id"):
            state[fetch_id] = processed
        return processed

    def _default_http_fetch(self, request_config: FetchRequest) -> bytes:
        url = request_config.url
        params = request_config.params
        if params:
            query = parse.urlencode(params, doseq=True)
            separator = "&" if ("?" in url) else "?"
            url = f"{url}{separator}{query}"

        data_bytes = self._prepare_body(request_config.body, request_config.headers)

        req = request.Request(url, data=data_bytes, method=request_config.method)
        for header_key, header_value in request_config.headers.items():
            req.add_header(header_key, str(header_value))

        try:
            with request.urlopen(req, timeout=request_config.timeout) as response:
                return response.read()
        except url_error.URLError as exc:
            raise RuntimeError(f"Error fetching {url}") from exc

    def _prepare_body(self, body: Any, headers: MutableMapping[str, Any]) -> bytes | None:
        if body is None:
            return None
        if isinstance(body, (dict, list)):
            headers.setdefault("Content-Type", "application/json")
            return json.dumps(body).encode("utf-8")
        if isinstance(body, str):
            return body.encode("utf-8")
        if isinstance(body, bytes):
            return body
        return str(body).encode("utf-8")

    def _apply_fetch_transform(self, transform: str | None, raw_response: bytes) -> Any:
        transform_name = (transform or "json").lower()
        if transform_name == "json":
            try:
                return json.loads(raw_response.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("Failed to decode JSON response") from exc
        if transform_name == "text":
            return raw_response.decode("utf-8")
        if transform_name == "bytes":
            return raw_response
        raise ValueError(f"Unknown fetch transform '{transform_name}'")

    def _apply_transform(self, transform: str | None, value: Any) -> Any:
        if transform is None:
            return value
        normalized = transform.lower()
        if normalized == "uppercase":
            return str(value).upper()
        if normalized == "lowercase":
            return str(value).lower()
        if normalized == "json":
            if isinstance(value, (bytes, bytearray)):
                return json.loads(value.decode("utf-8"))
            if isinstance(value, str):
                return json.loads(value)
            return value
        raise ValueError(f"Unsupported transform '{transform}'")

    def _interpolate_structure(self, value: Any, state: Mapping[str, Any]) -> Any:
        if isinstance(value, str):
            return self._interpolate(value, state)
        if isinstance(value, Mapping):
            return {k: self._interpolate_structure(v, state) for k, v in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [self._interpolate_structure(item, state) for item in value]
        return value

    def _interpolate(self, template: str, state: Mapping[str, Any]) -> str:
        def replace(match: re.Match[str]) -> str:
            path = match.group(1).strip()
            value = self._resolve_reference(path, state)
            return "" if value is None else str(value)

        return PLACEHOLDER_PATTERN.sub(replace, template)

    def _resolve_reference(self, path: str, state: Mapping[str, Any]) -> Any:
        cursor: Any = state
        for part in path.split("."):
            if isinstance(cursor, Mapping):
                cursor = cursor.get(part)
            elif isinstance(cursor, Sequence) and not isinstance(cursor, (str, bytes)):
                cursor = cursor[int(part)]
            else:
                cursor = None
            if cursor is None:
                break
        return cursor

    def _assign_path(self, state: MutableMapping[str, Any], dotted_path: str, value: Any) -> None:
        cursor = state
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            next_value = cursor.get(part)
            if not isinstance(next_value, MutableMapping):
                next_value = {}
            cursor[part] = next_value
            cursor = next_value
        cursor[parts[-1]] = value


def resolve_data_map_file(
    map_path: str | Path,
    *,
    seed_context: Mapping[str, Any] | None = None,
    resolver: DataMapResolver | None = None,
) -> dict[str, Any]:

    resolver = resolver or DataMapResolver()
    path_obj = Path(map_path)
    data = json.loads(path_obj.read_text())
    return resolver.resolve(data, seed_context)

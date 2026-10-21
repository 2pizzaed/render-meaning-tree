from __future__ import annotations

from typing import Any, cast

from src.json_search import JSONPath
from src.model.situation import Construct
from src.types import Node

_INLINE_CALL_NODE_TYPES = frozenset({"function_call", "method_call"})


def lookup_next_inline_compound_call_node(
    construct: Construct, previous_path: JSONPath | None
) -> tuple[Node, JSONPath] | None:
    call_nodes = _iter_inline_call_nodes(construct.ast_node)
    if previous_path is None:
        if not call_nodes:
            return None
        path, node = call_nodes[0]
        return node, path

    for index, (path, _) in enumerate(call_nodes):
        if path == previous_path:
            next_index = index + 1
            if next_index >= len(call_nodes):
                return None
            next_path, next_node = call_nodes[next_index]
            return next_node, next_path
    return None


def _iter_inline_call_nodes(
    value: Any, path: JSONPath = ()
) -> list[tuple[JSONPath, Node]]:
    result: list[tuple[JSONPath, Node]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(_iter_inline_call_nodes(child, (*path, key)))
        if value.get("type") in _INLINE_CALL_NODE_TYPES and isinstance(
            value.get("id"), int
        ):
            result.append((path, cast(Node, value)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(_iter_inline_call_nodes(child, (*path, index)))
    return result

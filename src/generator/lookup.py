from __future__ import annotations

from typing import Any, cast

from src.ast_managers import CodeManager
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


def lookup_function_call_definition(
    code: CodeManager, construct: Construct
) -> Node | None:
    return lookup_function_call_definition_by_ast_id(code, construct.ast_id)


def lookup_function_call_definition_by_ast_id(
    code: CodeManager,
    ast_id: int,
) -> Node | None:
    node = code.ast.get_path(ast_id)
    if node is None or not node.instanceof("function_call"):
        return None

    node_content = node.get(code.ast)
    if not node_content:
        return None

    name = _call_target_name(node_content)
    if name is None:
        return None

    found = code.user_defined_function_names.get(name)
    if found is None:
        return None

    function_node = _function_definition_node_for(code, found)
    return function_node if function_node is not None else code.get_node_by_id(found)


def _function_definition_node_for(code: CodeManager, ast_id: int) -> Node | None:
    current = code.get_node_by_id(ast_id)
    while current is not None:
        node_type = current.get("type")
        if node_type in {"function_definition", "method_definition"}:
            return current
        current_id = cast(int | None, current.get("id"))
        if current_id is None:
            return None
        parent = code.ast.get_parent_of(current_id)
        current = cast(Node | None, parent) if isinstance(parent, dict) else None
    return None


def _call_target_name(node_content: Node) -> str | None:
    function = node_content.get("function", {})
    if not isinstance(function, dict):
        return None

    name = function.get("name")
    if isinstance(name, str) and name:
        return name

    repr_name = function.get("repr_name")
    if isinstance(repr_name, str) and repr_name:
        return repr_name

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

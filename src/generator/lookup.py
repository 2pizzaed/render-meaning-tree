from __future__ import annotations

from typing import Any

from src.generator.evaluation_order import steps_of
from src.json_search import JSONPath, search_with_paths_dfs
from src.model.situation import Construct
from src.types import Node


def lookup_next_inline_compound_call_node(
    construct: Construct, previous_path: JSONPath | None
) -> tuple[Node, JSONPath] | None:
    call_nodes = _inline_steps(construct)
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


def _inline_steps(construct: Construct) -> list[tuple[JSONPath, Node]]:
    steps = steps_of(construct.ast_node, construct.owner.code.language)
    step_ids = {step["id"] for step in steps}

    def is_step(value: Any) -> bool:
        return isinstance(value, dict) and value.get("id") in step_ids

    paths = {
        node["id"]: path
        for path, node in search_with_paths_dfs(construct.ast_node, is_step)
    }
    return [(paths[step["id"]], step) for step in steps]

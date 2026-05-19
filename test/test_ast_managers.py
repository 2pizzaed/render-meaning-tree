from __future__ import annotations

from src.ast_managers import ASTNodeManager, CodeManager, NodePathElement
from src.coderenderer.entities import Token


def _path(
    node_id: int,
    node_type: str,
    parent: NodePathElement | None = None,
) -> NodePathElement:
    return NodePathElement(
        parent=parent,
        id=node_id,
        type=node_type,
        field_name=None,
        field_type="plain",
        container_field_id=None,
    )


def _manager(
    paths: list[NodePathElement],
    tokens: list[Token],
) -> CodeManager:
    ast = object.__new__(ASTNodeManager)
    ast._cache = {
        path.id: (path, {"id": path.id, "type": path.type})
        for path in paths
    }
    manager = object.__new__(CodeManager)
    manager._ast = ast
    manager._source_map = {}
    manager._tokens = tokens
    manager._code = ""
    manager._declarations = {"functions": [], "classes": [], "globals": []}
    manager._last_stream = None
    return manager


def _token(index: int, value: str, ast_node: NodePathElement | None) -> Token:
    return Token(index, value, "unknown", "unknown", index, ast_node)


def test_line_number_to_ast_node_returns_least_nested_node_starting_on_line() -> None:
    root = _path(1, "program_entry_point")
    statement = _path(2, "assignment_statement", root)
    expression = _path(3, "binary_expression", statement)
    next_statement = _path(4, "return_statement", root)
    manager = _manager(
        [root, statement, expression, next_statement],
        [
            _token(0, "x", expression),
            _token(1, "\n", None),
            _token(2, "return", next_statement),
        ],
    )

    assert manager.line_number_to_ast_node(1) is statement
    assert manager.line_number_to_ast_node(2) is next_statement


def test_line_number_to_ast_node_returns_none_for_ambiguous_least_depth() -> None:
    root = _path(1, "program_entry_point")
    left_statement = _path(2, "assignment_statement", root)
    right_statement = _path(3, "assignment_statement", root)
    manager = _manager(
        [root, left_statement, right_statement],
        [
            _token(0, "x", left_statement),
            _token(1, ";", None),
            _token(2, "y", right_statement),
        ],
    )

    assert manager.line_number_to_ast_node(1) is None


def test_line_number_to_ast_node_returns_none_for_invalid_or_empty_line() -> None:
    root = _path(1, "program_entry_point")
    statement = _path(2, "assignment_statement", root)
    manager = _manager(
        [root, statement],
        [_token(0, "x", statement)],
    )

    assert manager.line_number_to_ast_node(0) is None
    assert manager.line_number_to_ast_node(2) is None


def test_ast_node_manager_finds_paths_and_nodes_by_exact_type() -> None:
    root = _path(1, "program_entry_point")
    first_statement = _path(2, "assignment_statement", root)
    expression = _path(3, "binary_expression", first_statement)
    second_statement = _path(4, "assignment_statement", root)
    manager = _manager(
        [root, first_statement, expression, second_statement],
        [],
    )

    assert manager.ast.find_paths_by_type("assignment_statement") == [
        first_statement,
        second_statement,
    ]
    assert manager.ast.find_paths_by_type("missing") == []
